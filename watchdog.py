"""
Kris relay watchdog - keeps relay.py + ngrok alive so Hark can always reach the AdsPower browsers.
Runs hidden (pythonw), checks every 60 s, restarts whatever died, keeps the PC awake.
Log: watchdog_log.txt (same folder).  Stop it: Task Manager -> end pythonw.exe running watchdog.py.
"""
import ctypes, json, os, shutil, socket, subprocess, sys, time, urllib.request, urllib.error
from datetime import datetime

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
LOG = os.path.join(HERE, "watchdog_log.txt")
RELAY_PORT = 9333
NGROK_URL = "https://hefty-courier-garment.ngrok-free.dev"
CHECK_EVERY = 60
NO_WINDOW = 0x08000000  # CREATE_NO_WINDOW

def log(msg):
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    try:
        # keep the log small
        if os.path.exists(LOG) and os.path.getsize(LOG) > 2_000_000:
            os.replace(LOG, LOG + ".old")
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def single_instance():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", 9339))
        s.listen(1)
        return s
    except OSError:
        sys.exit(0)  # another watchdog is already running

def keep_awake():
    # ES_CONTINUOUS | ES_SYSTEM_REQUIRED : stop Windows from sleeping while the watchdog runs
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)
    except Exception:
        pass

def token():
    try:
        return open(os.path.join(HERE, "token.txt")).read().strip()
    except Exception:
        return ""

def http_get(url, headers=None, timeout=8, proxy=None):
    h = urllib.request.ProxyHandler({"http": proxy, "https": proxy} if proxy else {})
    opener = urllib.request.build_opener(h)
    req = urllib.request.Request(url, headers=headers or {})
    with opener.open(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "ignore")

# ---------- relay ----------
def relay_ok():
    try:
        st, body = http_get(f"http://127.0.0.1:{RELAY_PORT}/health", {"X-Relay-Token": token()}, 5)
        return st == 200 and json.loads(body).get("ok") is True
    except urllib.error.HTTPError as e:
        return e.code == 401  # server is up, token mismatch is not a crash
    except Exception:
        return False

def kill_matching(pred):
    for p in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            if pred(p):
                p.kill()
        except Exception:
            pass

def python_exe():
    exe = sys.executable
    if exe.lower().endswith("pythonw.exe"):
        cand = exe[:-len("pythonw.exe")] + "python.exe"
        if os.path.exists(cand):
            return cand
    return exe

def start_relay():
    kill_matching(lambda p: any(os.path.basename(a).lower() == "relay.py" for a in (p.info["cmdline"] or [])))
    time.sleep(2)
    out = open(os.path.join(HERE, "relay_log.txt"), "a", encoding="utf-8")
    subprocess.Popen([python_exe(), "-u", "relay.py"], cwd=HERE, stdout=out, stderr=out,
                     creationflags=NO_WINDOW)
    log("relay restarted")

# ---------- ngrok ----------
def ngrok_agent_ok():
    try:
        st, body = http_get("http://127.0.0.1:4040/api/tunnels", timeout=5)
        tunnels = json.loads(body).get("tunnels", [])
        return any(t.get("public_url", "").rstrip("/") == NGROK_URL for t in tunnels)
    except Exception:
        return False

def public_says_offline():
    """True only when ngrok's edge explicitly answers that the endpoint is offline (404/502/ERR_NGROK).
    Network errors from this PC (e.g. no VPN) never count, to avoid needless restarts."""
    for proxy in (None, "http://127.0.0.1:7897", "http://127.0.0.1:7899"):
        try:
            st, _ = http_get(NGROK_URL + "/health", {"X-Relay-Token": token(),
                             "ngrok-skip-browser-warning": "1"}, 10, proxy)
            return False
        except urllib.error.HTTPError as e:
            if e.code == 401:
                return False
            body = ""
            try:
                body = e.read().decode("utf-8", "ignore")
            except Exception:
                pass
            if e.code in (404, 502, 503, 504) or "ERR_NGROK" in body:
                return True
            return False
        except Exception:
            continue
    return False

def start_ngrok():
    kill_matching(lambda p: (p.info["name"] or "").lower().startswith("ngrok"))
    time.sleep(3)
    exe = shutil.which("ngrok") or os.path.join(HERE, "ngrok.exe")
    out = open(os.path.join(HERE, "ngrok_log.txt"), "a", encoding="utf-8")
    subprocess.Popen([exe, "http", str(RELAY_PORT), f"--url={NGROK_URL}", "--log=stdout"],
                     cwd=HERE, stdout=out, stderr=out, creationflags=NO_WINDOW)
    log("ngrok restarted")

# ---------- main loop ----------
def main():
    lock = single_instance()
    log("watchdog started")
    relay_fail = ngrok_fail = 1; public_fail = 0  # act at once on first check
    last_status = None
    while True:
        keep_awake()
        try:
            if relay_ok():
                relay_fail = 0
            else:
                relay_fail += 1
                if relay_fail >= 2:
                    start_relay(); relay_fail = 0; time.sleep(8)

            if ngrok_agent_ok():
                ngrok_fail = 0
                public_fail = public_fail + 1 if public_says_offline() else 0
                if public_fail >= 3:
                    log("public url offline 3x while agent up -> restart ngrok")
                    start_ngrok(); public_fail = 0
            else:
                ngrok_fail += 1
                if ngrok_fail >= 2:
                    start_ngrok(); ngrok_fail = 0

            status = "ok" if (relay_ok() and ngrok_agent_ok()) else "degraded"
            if status != last_status:
                log(f"status: {status}")
                last_status = status
        except Exception as e:
            log(f"error: {e!r}")
        time.sleep(CHECK_EVERY)

if __name__ == "__main__":
    main()
