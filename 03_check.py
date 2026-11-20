# STEP 6: 6 frames per clip -> one contact sheet per clip in check/. Look at every sheet.
# Bad clip? python 02_kaggle_gpu.py redo s07 777   (new seed, small run)
# Camera drifts at the end? set "use": 2.5 for that shot in shots.json (04_edit uses only that many seconds).
import os, glob, subprocess
os.makedirs("check", exist_ok=True)
for c in sorted(glob.glob("clips/*.mp4")):
    sid = os.path.basename(c)[:-4]
    d = float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",c]))
    fps = 6 / d
    subprocess.run(["ffmpeg","-y","-loglevel","error","-i",c,"-vf",f"fps={fps:.4f},scale=288:-2,tile=6x1",
                    "-frames:v","1",f"check/{sid}.jpg"])
    print("check/", sid, ".jpg")
print("Look for: extra/duplicate people, broken hands, melted faces, blur, sudden zoom, face change vs refs/")
