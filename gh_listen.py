# GitHub Actions job every ~15 min: reads your Telegram commands/buttons and acts.
#   /ideas          -> 5 ideas with buttons
#   /make <topic>   -> starts the "make" workflow (khali topic = bot khud chunega)
#   /status         -> running jobs
#   Post button     -> uploads to YouTube + Instagram + Facebook
import os, json, subprocess, requests
import tg

REPO = os.environ["GITHUB_REPOSITORY"]
GH = {"Authorization": f"Bearer {os.environ['GH_TOKEN']}", "Accept": "application/vnd.github+json"}

def start_make(topic=""):
    r = requests.post(f"https://api.github.com/repos/{REPO}/actions/workflows/make.yml/dispatches", headers=GH,
                      json={"ref": "main", "inputs": {"topic": topic}})
    tg.send(f"▶️ Shuru: {topic or 'main khud topic chunta hoon'}. Lagbhag 1.5-2 ghante." if r.status_code == 204 else f"Start nahi hua: {r.text}")

def running():
    r = requests.get(f"https://api.github.com/repos/{REPO}/actions/workflows/make.yml/runs", headers=GH,
                     params={"status": "in_progress"}).json()
    return r.get("total_count", 0)

def post(rel):
    from socials import post_all
    os.makedirs("dl", exist_ok=True)
    subprocess.run(["gh", "release", "download", rel, "-D", "dl", "--clobber"], check=True)
    meta = json.load(open("dl/meta.json", encoding="utf-8"))
    tg.send("📤 Post kar raha hoon...")
    out = post_all("dl/short.mp4", meta)
    tg.send("\n".join(f"{k}: {v}" for k, v in out.items()))
    subprocess.run(["gh", "release", "edit", rel, "--title", "POSTED " + meta["title"][:90]])

print("owner id set:", bool(tg.OWNER))
for u in tg.updates():
    print("update from:", ((u.get("message") or {}).get("from") or {}).get("id") == tg.OWNER)
    if "callback_query" in u:
        cb = u["callback_query"]
        if cb["from"]["id"] != tg.OWNER: continue
        tg.answer_cb(cb["id"])
        kind, val = cb["data"].split(":", 1)
        if kind == "post": post(val)
        elif kind == "drop": tg.send("Theek hai, post nahi kiya.")
        elif kind == "idea": start_make(val)
        continue
    msg = u.get("message") or {}
    if (msg.get("from") or {}).get("id") != tg.OWNER: continue
    text = (msg.get("text") or "").strip()
    if text.startswith("/ideas"):
        import brain
        ide = brain.ideas(5)
        tg.send("\n\n".join(f"{i+1}. {x['topic_hi']} — {x['why_viral']}" for i, x in enumerate(ide)),
                buttons=[[{"text": str(i + 1), "callback_data": ("idea:" + x["topic_en"].encode("ascii", "ignore").decode())[:60]}] for i, x in enumerate(ide)])
    elif text.startswith("/make"):
        start_make(text[5:].strip())
    elif text.startswith("/status"):
        n = running(); tg.send(f"{n} video abhi ban raha hai." if n else "Abhi kuch nahi chal raha.")
    else:
        tg.send("Commands: /ideas, /make <topic>, /status. Har video pehle aapko aayega, Post dabane par hi upload hoga. Jawab 15-20 min mein aata hai.")
