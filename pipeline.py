# A to Z: idea -> script -> keyframes+voice -> Kaggle GPU (video + lip-sync) -> auto QC + redo -> edit -> final MP4
import os, sys, json, shutil, subprocess, datetime, random
import brain, gpu_kaggle
HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = os.path.join(HERE, "jobs")

def sh(cmd, cwd):
    r = subprocess.run([sys.executable, *cmd], cwd=cwd, capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr[-1500:])
    return r.stdout

def make_video(topic=None, log=print):
    if not topic:
        topic = brain.ideas(3)[0]["topic_hi"]
    job = os.path.join(JOBS, datetime.datetime.now().strftime("%Y%m%d_%H%M"))
    os.makedirs(job, exist_ok=True)
    log(f"Topic: {topic}\nScript likh raha hoon...")
    s, meta = brain.write_job(job, topic)
    log("Script ready:\n" + "\n".join(f"{s['characters'][b['speaker']]['name']}: {b['line']}" for b in s["beats"]))

    for f in ["01_keyframes_tts.py", "03_check.py", "04_edit.py"]: shutil.copy(f"{HERE}/{f}", job)
    if not (os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY")):
        raise RuntimeError("Script ban gayi, par video ke liye Kaggle token chahiye (free GPU). GitHub repo Settings > Secrets mein KAGGLE_USERNAME aur KAGGLE_KEY daalo.")
    log("Awaaz bana raha hoon, phir photos + video free Kaggle GPU par (~1 ghanta)...")
    sh(["01_keyframes_tts.py"], job)

    gpu_kaggle.run(job, "full", log)

    # Step 6: automatic check, one redo round for bad clips
    talking = {sh_["id"] for b in s["beats"] for sh_ in b["shots"] if sh_["talking"]}
    bad = []
    for sid in [x["id"] for b in s["beats"] for x in b["shots"]]:
        jpg = f"{job}/check/{sid}.jpg"
        if not os.path.exists(jpg): bad.append(sid); continue
        q = brain.qc_sheet(jpg)
        if not q.get("ok"): bad.append(sid); log(f"QC fail {sid}: {q.get('reason')}")
        elif q.get("camera_moves_at_end"):
            for b in s["beats"]:
                for x in b["shots"]:
                    if x["id"] == sid: x["use"] = 2.5
    json.dump(s, open(f"{job}/shots.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if bad:
        mode = "redo " + " ".join(f"{b}:{random.randint(100, 99999)}" + (":t" if b in talking else "") for b in bad)
        log(f"{len(bad)} clip dobara bana raha hoon: {', '.join(bad)}")
        gpu_kaggle.run(job, mode, log)

    log("Final edit (captions, music, -14 LUFS)...")
    for m in ["music.mp3", "bell.mp3"]:
        src = os.path.join(HERE, m)
        if os.path.exists(src): shutil.copy(src, job)
    sh(["04_edit.py"], job)
    return {"job": job, "video": f"{job}/final/short.mp4", "cover": f"{job}/final/cover.png", "meta": meta, "topic": topic}

if __name__ == "__main__":
    print(make_video(" ".join(sys.argv[1:]) or None))
