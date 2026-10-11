# -*- coding: utf-8 -*-
"""TikTok 本地养号（不占 Hark 额度）
放在 tiktok-relay 文件夹里，和 relay.py、token.txt 同目录。
前提：AdsPower 的 TikTok 环境已打开，start.bat 已运行（relay 在 127.0.0.1:9333）。
每次约 15 分钟：For You 看 ~5 分钟 + 搜索看 ~8 条；只给 AI 视频内容点赞；
每天（本机日期）上限 10 个赞、3 个关注。
v3：点击前 Page.bringToFront + 鼠标事件带 buttons=1；拦截 digg/follow 接口回包；
    关注后刷新主页复查，若服务器没保存（账号互动被静默限制）则当天停止点赞/关注。不发帖、不评论、不私信。
日志：同目录 tiktok_local_log.txt
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
H = {"ngrok-skip-browser-warning": "1"}
TOKEN_FILE = None
for d in (HERE, os.path.dirname(HERE), os.path.join(os.path.dirname(HERE), "tiktok-relay")):
    if os.path.exists(os.path.join(d, "token.txt")):
        TOKEN_FILE = os.path.join(d, "token.txt"); break
if TOKEN_FILE:
    H["X-Relay-Token"] = open(TOKEN_FILE).read().strip()
LOG = os.path.join(HERE, "tiktok_local_log.txt")
STATE = os.path.join(HERE, "tiktok_local_state.json")
MAX_LIKES_DAY, MAX_FOLLOWS_DAY = 10, 3
KEYWORDS = ["AI short film", "Kling AI", "Veo 3", "AI filmmaking", "AI video", "Seedance", "Runway AI"]
AIRE = re.compile(r"(#ai(video|film|movie|animation|generated|filmmaking|shortfilm|cinema)?\b|kling|veo ?3|\bsora\b|runway|hailuo|seedance|midjourney|higgsfield|minimax|pika|luma|ai[- ]generated|ai short film|ai film|ai video|generative ai|\bgen ?ai\b)", re.I)

def log(msg):
    line = "%s  %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), msg)
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def call(method, params=None, sid=None, timeout=60):
    for n in range(3):
        try:
            r = requests.post(BASE + "/cmd", json={"profile": "tiktok", "method": method, "params": params or {},
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
    return call("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True}, sid)["result"].get("value")

def nav(sid, url, wait=(6, 9)):
    call("Page.navigate", {"url": url}, sid)
    time.sleep(random.uniform(*wait))

def front(sid):
    # 后台标签 visibilityState=hidden 时点击不生效，先切到前台
    try:
        call("Page.bringToFront", {}, sid); time.sleep(.6)
    except Exception:
        pass

def click(sid, x, y):
    front(sid)
    call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "buttons": 0}, sid)
    time.sleep(random.uniform(.25, .5))
    call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "buttons": 1, "clickCount": 1}, sid)
    time.sleep(random.uniform(.07, .14))
    call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "buttons": 0, "clickCount": 1}, sid)

# 拦截 TikTok 的点赞/关注接口回包（status_code / follow_status），用于日志与判断
HOOK_JS = r"""(()=>{if(window.__hk)return 1;window.__hk=[];const push=(u,s,b)=>{if(/commit\/(item\/digg|follow)/.test(u))window.__hk.push({u:u.slice(0,200),s,b:(b||'').slice(0,300)})};
const oo=XMLHttpRequest.prototype.open,os=XMLHttpRequest.prototype.send;XMLHttpRequest.prototype.open=function(m,u){this.__u=u;return oo.apply(this,arguments)};
XMLHttpRequest.prototype.send=function(){this.addEventListener('loadend',()=>{try{push(String(this.__u),this.status,typeof this.responseText==='string'?this.responseText:'')}catch(e){}});return os.apply(this,arguments)};
const of=window.fetch;window.fetch=async function(...a){const r=await of.apply(this,a);try{const u=(a[0]&&a[0].url)||String(a[0]);if(/commit\/(item\/digg|follow)/.test(u))r.clone().text().then(t=>push(u,r.status,t))}catch(e){}return r};return 1})()"""

def hook(sid):
    try:
        ev(sid, HOOK_JS)
    except Exception:
        pass

def hook_last(sid):
    try:
        a = ev(sid, "(window.__hk||[]).slice(-1)[0]||null")
        return a
    except Exception:
        return None

def key(sid, k="ArrowDown", code=40):
    for t in ("rawKeyDown", "keyUp"):
        call("Input.dispatchKeyEvent", {"type": t, "key": k, "code": k, "windowsVirtualKeyCode": code, "nativeVirtualKeyCode": code}, sid)
        time.sleep(random.uniform(.05, .15))

def load_state():
    today = datetime.date.today().isoformat()
    try:
        s = json.load(open(STATE))
    except Exception:
        s = {}
    if s.get("date") != today:
        s = {"date": today, "likes": 0, "follows": 0, "muted": False, "last_kw": s.get("last_kw", [])}
    return s

def save_state(s):
    json.dump(s, open(STATE, "w"))

BLOCK_JS = r"""(()=>{const t=document.body.innerText.slice(0,3000);
return /captcha|verify to continue|Drag the slider|Log in to TikTok|account (was|has been) (banned|suspended)|violat/i.test(t)
 || !!document.querySelector('#captcha-verify-container, .captcha_verify_container, [class*=captcha]')})()"""

def blocked(sid):
    try:
        return ev(sid, BLOCK_JS)
    except Exception:
        return False

FY_INFO = r"""(()=>{const as=[...document.querySelectorAll('article[data-e2e=recommend-list-item-container]')];
let best=null,bd=1e9;for(const a of as){const r=a.getBoundingClientRect();const d=Math.abs(r.top);if(d<bd){bd=d;best=a}}
if(!best)return null;const q=s=>best.querySelector(s);
const link=q('a[href^="/@"]');
const lk=q('[data-e2e=like-icon]');const btn=lk;const r=lk?lk.getBoundingClientRect():null;const v=q('video');
return {author:link?link.getAttribute('href'):'',desc:(q('[data-e2e=video-desc]')||{}).innerText||'',
pressed:btn?btn.getAttribute('aria-pressed'):null,lx:r?r.x+r.width/2:0,ly:r?r.y+r.height/2:0,
dur:v?v.duration:0,ad:/Sponsored|Ad\b/.test(best.innerText.slice(0,300))}})()"""

def like_current(sid, info, st, liked):
    if st.get("muted") or st["likes"] >= MAX_LIKES_DAY or not info.get("lx") or info.get("pressed") == "true":
        return
    if st.get("muted"):
        return
    hook(sid)
    click(sid, info["lx"], info["ly"])
    time.sleep(2)
    j = ev(sid, FY_INFO) or {}
    if j.get("pressed") == "true":
        st["likes"] += 1; liked.append(info.get("author", "")); save_state(st)

def for_you(sid, st, liked, seconds):
    nav(sid, "https://www.tiktok.com/foryou")
    if blocked(sid):
        return "blocked"
    time.sleep(4)
    t0, n, last = time.time(), 0, None
    while time.time() - t0 < seconds:
        i = ev(sid, FY_INFO)
        if not i:
            key(sid); time.sleep(2); continue
        if last == (i["author"], i["desc"][:40]):
            ev(sid, "window.scrollBy(0, innerHeight)")
            time.sleep(2)
        last = (i["author"], i["desc"][:40]); n += 1
        isai = bool(AIRE.search(i["desc"])) and not i["ad"]
        stay = random.uniform(6, 35)
        if isai and i["dur"] and i["dur"] < 90:
            stay = max(stay, i["dur"] + random.uniform(1, 3))
        if isai and random.random() < 0.7:
            time.sleep(stay * 0.7); like_current(sid, i, st, liked); time.sleep(stay * 0.3)
        else:
            time.sleep(stay)
        key(sid); time.sleep(random.uniform(.8, 2.5))
    return n

SEARCH_LINKS = r"""(()=>[...new Set([...document.querySelectorAll('a[href*="/video/"]')].map(a=>a.href))].slice(0,12))()"""
VID_INFO = r"""(()=>{const u=document.querySelector('[data-e2e=browse-username],[data-e2e=video-author-uniqueid]');
const d=document.querySelector('[data-e2e=browse-video-desc],[data-e2e=video-desc]');const v=document.querySelector('video');
const lk=document.querySelector('[data-e2e=browse-like-icon],[data-e2e=like-icon]');const btn=lk&&(lk.hasAttribute('aria-pressed')?lk:lk.closest('[aria-pressed]'));const r=lk?lk.getBoundingClientRect():null;
return {user:(location.pathname.split('/')[1]||'').replace('@','')||(u?u.innerText.trim():''),desc:d?d.innerText.slice(0,200):'',dur:v?v.duration:0,
pressed:btn?btn.getAttribute('aria-pressed'):null,lx:r?r.x+r.width/2:0,ly:r?r.y+r.height/2:0}})()"""
PROFILE_INFO = r"""(()=>{const f=document.querySelector('[data-e2e=followers-count]');const b=document.querySelector('[data-e2e=user-bio]');
const t=document.querySelector('[data-e2e=user-title],[data-e2e=user-subtitle]');const btn=document.querySelector('[data-e2e=follow-button]');
const r=btn?btn.getBoundingClientRect():null;
return {followers:f?f.innerText:'',bio:(b?b.innerText:'')+' '+(t?t.innerText:''),btn:btn?btn.innerText:'',x:r?r.x+r.width/2:0,y:r?r.y+r.height/2:0}})()"""

def num(s):
    s = (s or "").strip().upper().replace(",", "")
    m = re.match(r"([\d.]+)([KM]?)", s)
    if not m:
        return 0
    return float(m.group(1)) * {"": 1, "K": 1e3, "M": 1e6}[m.group(2)]

def search(sid, st, liked, followed, kw, nvid):
    nav(sid, "https://www.tiktok.com/search/video?q=" + urllib.parse.quote(kw), (7, 10))
    if blocked(sid):
        return "blocked"
    links = ev(sid, SEARCH_LINKS) or []
    if not links:
        ev(sid, "window.scrollBy(0, innerHeight)"); time.sleep(4); links = ev(sid, SEARCH_LINKS) or []
    random.shuffle(links)
    watched, cand = 0, []
    for url in links[:nvid]:
        nav(sid, url, (4, 6))
        info = ev(sid, VID_INFO) or {}
        stay = min(max(random.uniform(8, 20), (info.get("dur") or 0) + random.uniform(0, 2)), 55)
        isai = bool(AIRE.search(info.get("desc", "") + " " + kw))
        time.sleep(stay * 0.7)
        if isai and not st.get("muted") and st["likes"] < MAX_LIKES_DAY and info.get("lx") and info.get("pressed") != "true" and random.random() < 0.5:
            hook(sid)
            click(sid, info["lx"], info["ly"]); time.sleep(2)
            j = ev(sid, VID_INFO) or {}
            if j.get("pressed") == "true":
                st["likes"] += 1; liked.append(info.get("user", "")); save_state(st)
        time.sleep(stay * 0.3)
        watched += 1
        if info.get("user"):
            cand.append(info["user"])
    # 关注：最多 1 个/次，作者 ≥1000 粉且简介/名字和 AI 视频相关
    if st["follows"] < MAX_FOLLOWS_DAY and not st.get("muted"):
        for u in list(dict.fromkeys(cand))[:3]:
            nav(sid, "https://www.tiktok.com/@" + u.lstrip("@"), (7, 9))  # 主页需 ≥6 秒才渲染完
            p = ev(sid, PROFILE_INFO) or {}
            if num(p.get("followers")) >= 1000 and AIRE.search(p.get("bio", "") + " " + u) and p.get("btn", "").strip().lower() in ("follow", "关注"):
                hook(sid)
                click(sid, p["x"], p["y"]); time.sleep(3)
                p2 = ev(sid, PROFILE_INFO) or {}
                resp = hook_last(sid) or {}
                if p2.get("btn", "").strip().lower() in ("following", "friends", "已关注", "互相关注", "朋友"):
                    # 刷新主页复查服务器是否真的保存了关注
                    time.sleep(random.uniform(4, 7))
                    nav(sid, "https://www.tiktok.com/@" + u.lstrip("@"), (8, 10))
                    p3 = ev(sid, PROFILE_INFO) or {}
                    if p3.get("btn", "").strip().lower() in ("follow", "关注"):
                        st["muted"] = True; save_state(st)
                        log("WARN 关注 @%s 页面显示成功、接口回包 %s，但刷新后没保存 → 账号互动被 TikTok 静默限制，今天停止点赞/关注" % (u, (resp.get("b") or "")[:120]))
                    else:
                        st["follows"] += 1; followed.append(u); save_state(st)
                break
    return watched

def main():
    if "--now" not in sys.argv:
        time.sleep(random.uniform(0, 1200))  # 随机延迟 0–20 分钟，避免每天同一秒开始
    try:
        h = requests.get(BASE + "/health", params={"profile": "tiktok"}, headers=H, timeout=20).json()
    except Exception as e:
        log("FAIL relay 连不上（先运行 start.bat）: %s" % e); return
    if h.get("ok") is False and "profile" not in h:
        log("FAIL relay 拒绝访问：没找到 token.txt（把本脚本放在 relay.py 和 token.txt 所在的文件夹或其子文件夹）"); return
    if not h.get("profile_open"):
        log("FAIL AdsPower TikTok 环境没打开"); return
    tabs = [t for t in call("Target.getTargets")["targetInfos"] if t["type"] == "page"]
    tt = [t for t in tabs if "tiktok.com" in t["url"]]
    tid = tt[0]["targetId"] if tt else call("Target.createTarget", {"url": "https://www.tiktok.com/foryou"})["targetId"]
    sid = call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
    front(sid)
    st = load_state(); liked, followed = [], []
    fy = for_you(sid, st, liked, random.uniform(240, 330))
    if fy == "blocked":
        log("STOP 出现验证码/登录/违规提示，已停止，请人工查看"); return
    pool = [k for k in KEYWORDS if k not in st.get("last_kw", [])] or KEYWORDS
    kw = random.choice(pool)
    st["last_kw"] = (st.get("last_kw", []) + [kw])[-3:]; save_state(st)
    sw = search(sid, st, liked, followed, kw, random.randint(6, 9))
    if sw == "blocked":
        log("STOP 搜索页出现验证码/登录/违规提示，已停止"); return
    nav(sid, "https://www.tiktok.com/foryou", (3, 5))
    log("OK FY看%s条 | 搜索「%s」看%s条 | 本次赞%d %s | 本次关注%d %s | 今日累计赞%d 关注%d%s"
        % (fy, kw, sw, len(liked), ",".join(liked), len(followed), ",".join(followed), st["likes"], st["follows"],
           " | 互动被静默限制(已暂停)" if st.get("muted") else ""))

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log("FAIL %s" % e)
