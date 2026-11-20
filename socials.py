# Auto-post to YouTube Shorts, Instagram Reels, Facebook Page Reels. All official free APIs.
import os, time, json, requests
GV = "v21.0"

# ---------------- YouTube ----------------
def youtube(video, meta, privacy=os.environ.get("YT_PRIVACY", "public")):
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload
    if os.environ.get("YT_REFRESH_TOKEN"):   # phone setup via OAuth Playground
        creds = Credentials(None, refresh_token=os.environ["YT_REFRESH_TOKEN"], token_uri="https://oauth2.googleapis.com/token",
                            client_id=os.environ["YT_CLIENT_ID"], client_secret=os.environ["YT_CLIENT_SECRET"],
                            scopes=["https://www.googleapis.com/auth/youtube.upload"])
    else:
        creds = Credentials.from_authorized_user_file(os.environ.get("YT_TOKEN", "data/yt_token.json"),
                                                      ["https://www.googleapis.com/auth/youtube.upload"])
    yt = build("youtube", "v3", credentials=creds)
    body = {"snippet": {"title": meta["title"][:100], "description": meta["description"] + "\n" + " ".join(meta["hashtags"]),
                        "tags": meta["tags"][:15], "categoryId": "24", "defaultLanguage": "hi"},
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False}}
    req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(video, chunksize=-1, resumable=True))
    res = None
    while res is None: _, res = req.next_chunk()
    return f"https://youtube.com/shorts/{res['id']}"

def youtube_login():
    """Run ONCE on your PC: python -c "from publish.socials import youtube_login; youtube_login()" """
    from google_auth_oauthlib.flow import InstalledAppFlow
    flow = InstalledAppFlow.from_client_secrets_file("data/client_secret.json", ["https://www.googleapis.com/auth/youtube.upload"])
    creds = flow.run_local_server(port=0)
    open("data/yt_token.json", "w").write(creds.to_json()); print("YouTube login saved")

# ---------------- Instagram Reels (Business/Creator account linked to a FB Page) ----------------
def instagram(video, meta):
    uid, tok = os.environ["IG_USER_ID"], os.environ["META_PAGE_TOKEN"]
    cap = f"{meta['title'].replace('#shorts', '').strip()}\n\n{meta['description']}\n\n{' '.join(meta['hashtags'])}"[:2200]
    c = requests.post(f"https://graph.facebook.com/{GV}/{uid}/media",
                      data={"media_type": "REELS", "upload_type": "resumable", "caption": cap, "share_to_feed": "true",
                            "access_token": tok}).json()
    cid = c["id"]; size = os.path.getsize(video)
    r = requests.post(f"https://rupload.facebook.com/ig-api-upload/{GV}/{cid}",
                      headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(size)}, data=open(video, "rb"))
    r.raise_for_status()
    for _ in range(60):
        st = requests.get(f"https://graph.facebook.com/{GV}/{cid}", params={"fields": "status_code,status", "access_token": tok}).json()
        if st.get("status_code") == "FINISHED": break
        if st.get("status_code") == "ERROR": raise RuntimeError(f"IG processing error: {st}")
        time.sleep(10)
    p = requests.post(f"https://graph.facebook.com/{GV}/{uid}/media_publish", data={"creation_id": cid, "access_token": tok}).json()
    if "id" not in p: raise RuntimeError(f"IG publish failed: {p}")
    link = requests.get(f"https://graph.facebook.com/{GV}/{p['id']}", params={"fields": "permalink", "access_token": tok}).json()
    return link.get("permalink", p["id"])

# ---------------- Facebook Page Reels ----------------
def facebook(video, meta):
    pid, tok = os.environ["FB_PAGE_ID"], os.environ["META_PAGE_TOKEN"]
    s = requests.post(f"https://graph.facebook.com/{GV}/{pid}/video_reels", data={"upload_phase": "start", "access_token": tok}).json()
    vid = s["video_id"]
    r = requests.post(f"https://rupload.facebook.com/video-upload/{GV}/{vid}",
                      headers={"Authorization": f"OAuth {tok}", "offset": "0", "file_size": str(os.path.getsize(video))},
                      data=open(video, "rb"))
    r.raise_for_status()
    desc = f"{meta['title'].replace('#shorts', '').strip()}\n\n{meta['description']}\n{' '.join(meta['hashtags'])}"
    f = requests.post(f"https://graph.facebook.com/{GV}/{pid}/video_reels",
                      data={"upload_phase": "finish", "video_id": vid, "video_state": "PUBLISHED", "description": desc,
                            "access_token": tok}).json()
    if not f.get("success"): raise RuntimeError(f"FB publish failed: {f}")
    return f"https://www.facebook.com/reel/{vid}"

PLATFORMS = {"youtube": youtube, "instagram": instagram, "facebook": facebook}

def post_all(video, meta, which=None, log=print):
    which = which or [p.strip() for p in os.environ.get("POST_TO", "youtube,instagram,facebook").split(",") if p.strip()]
    out = {}
    for p in which:
        try: out[p] = PLATFORMS[p](video, meta)
        except Exception as e: out[p] = f"ERROR: {e}"
        log(f"{p}: {out[p]}")
    return out
