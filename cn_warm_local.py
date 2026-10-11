# -*- coding: utf-8 -*-
"""国内平台本地养号：抖音 / 小红书 / 闲鱼（不占 Hark 额度）
放在 tiktok-relay 文件夹里，和 relay.py、token.txt 同目录。
前提：AdsPower 的 China-Direct 环境已打开（已登录抖音、小红书、闲鱼），start.bat 已运行（relay 在 127.0.0.1:9333）。
每次约 15–20 分钟：
  抖音   搜一个办公/AI 词，看 4–6 条视频，部分点赞
  小红书 搜一个词，慢慢下滑浏览，部分笔记点赞
  闲鱼   搜一个词，浏览 1–2 分钟，不做任何互动
每天（本机日期）上限：抖音赞 8、小红书赞 8；不关注、不评论、不私信、不发布。
出现验证码/登录/风控提示：该平台立即停止并写日志。
每次自己新开标签，用完关闭，不动其他标签（比如闲鱼发布二维码页）。
日志：同目录 cn_local_log.txt
"""
import os, sys, time, random, json, re, datetime, urllib.parse
try:
    import requests
except ImportError:
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "requests"], check=False)
    import requests

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = os.environ.get("RELAY", "http://127.0.0.1:9333")
PROFILE = "cn"
H = {"ngrok-skip-browser-warning": "1"}
for d in (HERE, os.path.dirname(HERE), os.path.join(os.path.dirname(HERE), "tiktok-relay")):
    if os.path.exists(os.path.join(d, "token.txt")):
        H["X-Relay-Token"] = open(os.path.join(d, "token.txt")).read().strip(); break
LOG = os.path.join(HERE, "cn_local_log.txt")
STATE = os.path.join(HERE, "cn_local_state.json")
CAP = {"dy": 8, "xhs": 8}
KW = {
    "dy": ["Excel技巧", "AI办公", "WPS技巧", "豆包", "财务对账", "表格函数", "AI做PPT", "办公软件技巧"],
    "xhs": ["Excel技巧", "AI办公", "财务工作", "WPS表格", "豆包使用技巧", "打工人效率", "行政工作", "AI工具推荐"],
    "xy": ["Excel代做", "PDF转Word", "发票整理", "AI办公", "表格代做"],
}
TOPIC = re.compile(r"(excel|wps|表格|函数|公式|办公|财务|会计|对账|发票|报表|ppt|word|pdf|ai|豆包|deepseek|kimi|效率|行政|文员|职场|打工)", re.I)

def log(msg):
    line = "%s  %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def call(method, params=None, sid=None, timeout=60):
    for n in range(3):
        try:
            r = requests.post(BASE + "/cmd", json={"profile": PROFILE, "method": method, "params": params or {},
                                                   "sessionId": sid, "timeout": timeout}, headers=H, timeout=timeout + 15)
            d = r.json()
            if "error" in d:
                raise RuntimeError(d["error"])
            return d.get("result", d)
        except Exception:
            if n == 2:
                raise
            time.sleep(3)

def ev(sid, expr):
    try:
        return call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True}, sid)["result"].get("value")
    except Exception:
        return None

def nap(a, b):
    time.sleep(random.uniform(a, b))

def nav(sid, url, wait=(6, 9)):
    call("Page.navigate", {"url": url}, sid); nap(*wait)

def front(sid):
    try:
        call("Page.bringToFront", {}, sid); time.sleep(.6)
    except Exception:
        pass

def click(sid, x, y):
    front(sid)
    call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "buttons": 0}, sid); nap(.25, .5)
    call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "buttons": 1, "clickCount": 1}, sid); nap(.07, .14)
    call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "buttons": 0, "clickCount": 1}, sid)

def scroll(sid, px=None):
    ev(sid, "window.scrollBy({top:%d,behavior:'smooth'})" % (px or random.randint(350, 800)))

def open_tab(url):
    tid = call("Target.createTarget", {"url": url})["targetId"]
    sid = call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
    front(sid); nap(6, 9)
    return tid, sid

def close_tab(tid):
    try:
        call("Target.closeTarget", {"targetId": tid})
    except Exception:
        pass

BLOCK_JS = r"""(()=>{const t=(document.body?document.body.innerText:'').slice(0,4000);
if(document.querySelector('#captcha_container,.captcha_verify_container,[id*=captcha],[class*=captcha],.red-captcha,.baxia-dialog,#nc_1_wrapper'))return 'captcha';
if(/请完成(安全)?验证|滑动.{0,6}验证|拖动.{0,6}滑块|访问频繁|操作频繁|账号(存在)?异常|违规|封禁/.test(t))return 'risk';
if(/扫码登录|登录后(查看|即可)|手机号登录|请先登录/.test(t)&&t.length<1500)return 'login';
return ''})()"""

def blocked(sid):
    return ev(sid, BLOCK_JS) or ""

def load_state():
    today = datetime.date.today().isoformat()
    try:
        s = json.load(open(STATE, encoding="utf-8"))
    except Exception:
        s = {}
    last = s.get("last_kw", {})
    if s.get("date") != today:
        s = {"date": today, "dy": 0, "xhs": 0, "last_kw": last}
    return s

def save_state(s):
    json.dump(s, open(STATE, "w", encoding="utf-8"), ensure_ascii=False)

def pick_kw(st, plat):
    used = st.setdefault("last_kw", {}).get(plat, [])
    pool = [k for k in KW[plat] if k not in used] or KW[plat]
    kw = random.choice(pool)
    st["last_kw"][plat] = (used + [kw])[-3:]; save_state(st)
    return kw

# ---------------- 抖音 ----------------
DY_LINKS = r"""(()=>[...new Set([...document.querySelectorAll('a[href*="/video/"]')].map(a=>a.href.split('?')[0]))].slice(0,15))()"""
DY_INFO = r"""(()=>{const e=document.querySelector('[data-e2e=video-player-digg]');const v=document.querySelector('video');
const d=document.querySelector('[data-e2e=video-desc],h1');const r=e?e.getBoundingClientRect():null;
return {state:e?e.getAttribute('data-e2e-state'):'',desc:d?d.innerText.slice(0,120):document.title,dur:v?v.duration:0,
x:r?r.x+r.width/2:0,y:r?r.y+r.height/2:0}})()"""

def douyin(st):
    kw = pick_kw(st, "dy")
    tid, sid = open_tab("https://www.douyin.com/search/" + urllib.parse.quote(kw) + "?type=video")
    try:
        b = blocked(sid)
        if b:
            return "STOP 抖音搜索页出现%s，已停止抖音" % b
        nap(2, 4); scroll(sid); nap(3, 5)
        links = ev(sid, DY_LINKS) or []
        if not links:
            scroll(sid, 900); nap(4, 6); links = ev(sid, DY_LINKS) or []
        if not links:
            return "抖音「%s」没读到视频链接（页面可能改版）" % kw
        random.shuffle(links)
        n, liked = 0, 0
        for url in links[:random.randint(4, 6)]:
            nav(sid, url, (6, 9))
            b = blocked(sid)
            if b:
                return "STOP 抖音视频页出现%s，已停止（已看%d条 赞%d）" % (b, n, liked)
            i = ev(sid, DY_INFO) or {}
            stay = min(max(random.uniform(10, 25), (i.get("dur") or 0) * random.uniform(.6, 1.0)), 60)
            nap(stay * .7, stay * .7 + .1)
            if (st["dy"] < CAP["dy"] and "no-digged" in (i.get("state") or "") and TOPIC.search(i.get("desc", "") + kw)
                    and random.random() < 0.5):
                if i.get("x"):
                    click(sid, i["x"], i["y"])
                else:
                    ev(sid, "document.querySelector('[data-e2e=video-player-digg]').click()")
                nap(2, 3)
                j = ev(sid, DY_INFO) or {}
                if (j.get("state") or "").startswith("digged") or j.get("state") == "digged":
                    st["dy"] += 1; liked += 1; save_state(st)
            nap(stay * .3, stay * .3 + .1)
            n += 1
        return "抖音「%s」看%d条 赞%d（今日%d）" % (kw, n, liked, st["dy"])
    finally:
        close_tab(tid)

# ---------------- 小红书 ----------------
XHS_ITEMS = r"""(()=>{const out=[];document.querySelectorAll('section.note-item').forEach((s,i)=>{const w=s.querySelector('.like-wrapper');if(!w)return;
const r=w.getBoundingClientRect();if(r.top<80||r.bottom>innerHeight-20)return;
const t=(s.querySelector('.title,a.title span,.footer .title')||{}).innerText||'';const c=(w.innerText||'').trim();
out.push({i,title:t.slice(0,60),cnt:c,active:/active|liked/.test(w.className)||!!w.querySelector('.like-active,[class*=active]'),x:r.x+r.width/2,y:r.y+r.height/2})});return out})()"""

def xhs(st):
    kw = pick_kw(st, "xhs")
    tid, sid = open_tab("https://www.xiaohongshu.com/search_result?keyword=" + urllib.parse.quote(kw) + "&source=web_search_result_notes&type=51")
    try:
        b = blocked(sid)
        if b:
            return "STOP 小红书出现%s，已停止小红书" % b
        t0, liked, seen = time.time(), 0, set()
        dur = random.uniform(180, 300)
        while time.time() - t0 < dur:
            items = [x for x in (ev(sid, XHS_ITEMS) or []) if x["title"] not in seen]
            for it in items:
                seen.add(it["title"])
            cand = [x for x in items if not x["active"] and TOPIC.search(x["title"] + kw)]
            if cand and st["xhs"] < CAP["xhs"] and random.random() < 0.35:
                it = random.choice(cand)
                nap(3, 8)
                click(sid, it["x"], it["y"]); nap(2, 3)
                after = [x for x in (ev(sid, XHS_ITEMS) or []) if x["title"] == it["title"]]
                if after and (after[0]["active"] or after[0]["cnt"] != it["cnt"]):
                    st["xhs"] += 1; liked += 1; save_state(st)
            nap(6, 18)
            scroll(sid)
            if blocked(sid):
                return "STOP 小红书浏览中出现验证/风控，已停止（赞%d）" % liked
        return "小红书「%s」浏览%d篇 赞%d（今日%d）" % (kw, len(seen), liked, st["xhs"])
    finally:
        close_tab(tid)

# ---------------- 闲鱼（只浏览） ----------------
def xianyu(st):
    kw = pick_kw(st, "xy")
    tid, sid = open_tab("https://www.goofish.com/search?q=" + urllib.parse.quote(kw))
    try:
        b = blocked(sid)
        if b:
            return "STOP 闲鱼出现%s，已停止闲鱼" % b
        t0 = time.time()
        while time.time() - t0 < random.uniform(60, 120):
            nap(5, 14); scroll(sid)
        return "闲鱼「%s」浏览约%d秒" % (kw, time.time() - t0)
    finally:
        close_tab(tid)

def main():
    if "--now" not in sys.argv:
        time.sleep(random.uniform(0, 900))
    try:
        h = requests.get(BASE + "/health", params={"profile": PROFILE}, headers=H, timeout=20).json()
    except Exception as e:
        log("FAIL relay 连不上（先运行 start.bat）: %s" % e); return
    if h.get("ok") is False and "profile" not in h:
        log("FAIL relay 拒绝访问：没找到 token.txt"); return
    if not h.get("profile_open"):
        log("FAIL AdsPower China-Direct 环境没打开"); return
    st = load_state()
    plats = [douyin, xhs, xianyu]
    random.shuffle(plats)
    res = []
    for f in plats:
        try:
            res.append(f(st))
        except Exception as e:
            res.append("%s 出错: %s" % (f.__name__, str(e)[:120]))
        nap(20, 60)
    log("OK " + " | ".join(res))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("FAIL %s" % e)
