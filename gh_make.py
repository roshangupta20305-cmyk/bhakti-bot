# GitHub Actions job: make one video A-Z, save it as a GitHub Release, send it to you on Telegram for approval.
import os, sys, json, subprocess, shutil
import tg, pipeline

topic = " ".join(sys.argv[1:]).strip() or None
try:
    res = pipeline.make_video(topic, log=tg.send)
except Exception as e:
    tg.send(f"❌ Video nahi ban paaya: {e}"[:3900]); raise

jid = os.path.basename(res["job"])
rel = f"job-{jid}"
shutil.copy(res["video"], "short.mp4"); shutil.copy(res["cover"], "cover.png")
json.dump(res["meta"], open("meta.json", "w", encoding="utf-8"), ensure_ascii=False)
subprocess.run(["gh", "release", "create", rel, "short.mp4", "cover.png", "meta.json",
                "--title", res["meta"]["title"][:100], "--notes", res["topic"]], check=True)

# remember used topics across runs
subprocess.run('git config user.name bot && git config user.email bot@users.noreply.github.com && '
               'git add history.json && git commit -m "history" && git push', shell=True)

m = res["meta"]
tg.send_video("short.mp4", f"{m['title']}\n\n{m['description'][:600]}",
              buttons=[[{"text": "✅ Post karo", "callback_data": f"post:{rel}"},
                        {"text": "❌ Mat karo", "callback_data": f"drop:{rel}"}]])
