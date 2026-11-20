# Tiny Telegram helper (plain HTTPS, works from GitHub Actions)
import os, json, requests
API = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}"
OWNER = int(os.environ["TELEGRAM_OWNER_ID"])

def send(text, buttons=None):
    d = {"chat_id": OWNER, "text": text[:4000]}
    if buttons: d["reply_markup"] = json.dumps({"inline_keyboard": buttons})
    try:
        r = requests.post(f"{API}/sendMessage", data=d, timeout=30); print("send:", r.status_code, r.text[:200])
    except Exception as e: print("tg send failed", e)

def send_video(path, caption, buttons=None):
    d = {"chat_id": OWNER, "caption": caption[:1000], "supports_streaming": "true"}
    if buttons: d["reply_markup"] = json.dumps({"inline_keyboard": buttons})
    r = requests.post(f"{API}/sendVideo", data=d, files={"video": open(path, "rb")}, timeout=300)
    print(r.text[:300])

def updates():
    """Read all pending updates, then confirm them so they are not read again."""
    j = requests.get(f"{API}/getUpdates", params={"timeout": 0}, timeout=30).json()
    print("getUpdates ok:", j.get("ok"), j.get("description", ""), "count:", len(j.get("result", [])))
    u = j.get("result", [])
    if u: requests.get(f"{API}/getUpdates", params={"offset": u[-1]["update_id"] + 1, "timeout": 0}, timeout=30)
    return u

def answer_cb(cb_id):
    requests.post(f"{API}/answerCallbackQuery", data={"callback_query_id": cb_id}, timeout=30)
