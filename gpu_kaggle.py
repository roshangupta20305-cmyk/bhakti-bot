# Runs the GPU part (LTX-Video + LatentSync) on Kaggle's free T4 x2, fully by API.
# Needs ~/.kaggle/kaggle.json (Kaggle > Settings > Create New Token) and phone-verified Kaggle account.
import os, json, time, shutil, subprocess, zipfile
HERE = os.path.dirname(os.path.abspath(__file__))
USER = os.environ.get("KAGGLE_USERNAME", "")
if os.environ.get("KAGGLE_KEY", "").startswith("KGAT_"):   # new-style Kaggle API token
    os.environ["KAGGLE_API_TOKEN"] = os.environ["KAGGLE_KEY"]

RUNNER = r'''
import os, shutil, glob, subprocess, sys
src = glob.glob("/kaggle/input/*/")[0]
os.chdir("/kaggle/working")
for f in os.listdir(src):
    p = os.path.join(src, f)
    (shutil.copytree if os.path.isdir(p) else shutil.copy)(p, f)
for z in glob.glob("*.zip"): subprocess.run(["unzip", "-oq", z]); os.remove(z)
subprocess.run("pip install -q -U diffusers transformers accelerate peft sentencepiece imageio imageio-ffmpeg mediapipe opencv-python-headless", shell=True)
print(subprocess.run("nvidia-smi; python -c 'import torch,diffusers,transformers;print(torch.__version__,diffusers.__version__,transformers.__version__)'", shell=True, capture_output=True, text=True).stdout, flush=True)
MODE = open("mode.txt").read().split()
if MODE[0] == "full":
    subprocess.run([sys.executable, "02_kaggle_gpu.py", "images"], check=True)
    subprocess.run([sys.executable, "02_kaggle_gpu.py", "encode"], check=True)
    subprocess.run([sys.executable, "02_kaggle_gpu.py", "ltx"], check=True)
    subprocess.run([sys.executable, "02_kaggle_gpu.py", "latentsync"], check=True)
else:  # redo s07:777 s10:778 ...
    subprocess.run([sys.executable, "02_kaggle_gpu.py", "encode"], check=True)
    talk = []
    for item in MODE[1:]:          # "s07:777" or "s10:778:t" (t = talking shot, needs lip-sync again)
        sid, seed, *t = item.split(":")
        subprocess.run([sys.executable, "02_kaggle_gpu.py", "redo", sid, seed], check=True)
        if t: talk.append(sid)
    if talk: subprocess.run([sys.executable, "02_kaggle_gpu.py", "latentsync", *talk], check=True)
subprocess.run([sys.executable, "03_check.py"])
subprocess.run("zip -qr out.zip clips check keyframes refs", shell=True)
for d in ["LatentSync", "ls", "embeds", "keyframes", "audio", "refs"]: shutil.rmtree(d, ignore_errors=True)
'''

def _k(*a):
    r = subprocess.run(["kaggle", *a], capture_output=True, text=True)
    if r.returncode: raise RuntimeError(r.stderr or r.stdout)
    return r.stdout

def _fail_log(ref, job_dir):
    d = os.path.join(job_dir, "_faillog"); shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
    try: subprocess.run(["kaggle", "kernels", "output", ref, "-p", d], capture_output=True, text=True, timeout=600)
    except Exception as e: return "log download failed: " + str(e)
    txt = ""
    for f in os.listdir(d):
        if f.endswith(".log") or f.endswith(".txt"):
            raw = open(os.path.join(d, f), errors="ignore").read()
            try:
                lines = [json.loads(x).get("data", "") for x in json.loads(raw)] if raw.lstrip().startswith("[") else [raw]
            except Exception:
                lines = [raw]
            txt += "".join(lines)
    return txt[-8000:] or "no log file found"

def run(job_dir, mode="full", log=print):
    if not (USER and os.environ.get("KAGGLE_KEY")):
        raise RuntimeError("Kaggle token abhi nahi laga. GitHub repo Settings > Secrets mein KAGGLE_USERNAME aur KAGGLE_KEY daalo.")
    tag = "full" if mode == "full" else f"redo{int(time.time()) % 100000}"
    slug = ("hb-" + os.path.basename(job_dir.rstrip("/")).lower().replace("_", "-"))[:40] + "-" + tag
    ds = os.path.join(job_dir, "_ds"); shutil.rmtree(ds, ignore_errors=True); os.makedirs(ds)
    with zipfile.ZipFile(f"{ds}/inputs.zip", "w") as z:
        for d in ["keyframes", "refs", "audio"]:
            if not os.path.isdir(f"{job_dir}/{d}"): continue
            for f in os.listdir(f"{job_dir}/{d}"): z.write(f"{job_dir}/{d}/{f}", f"{d}/{f}")
        if os.path.isdir(f"{job_dir}/clips"):
            for f in os.listdir(f"{job_dir}/clips"): z.write(f"{job_dir}/clips/{f}", f"clips/{f}")
    for f in ["02_kaggle_gpu.py", "03_check.py"]: shutil.copy(f"{HERE}/{f}", ds)
    shutil.copy(f"{job_dir}/shots.json", ds)
    open(f"{ds}/mode.txt", "w").write(mode)
    json.dump({"title": slug, "id": f"{USER}/{slug}", "licenses": [{"name": "CC0-1.0"}]}, open(f"{ds}/dataset-metadata.json", "w"))
    log("Kaggle: uploading inputs")
    _k("datasets", "create", "-p", ds, "-q", "-r", "skip")
    time.sleep(60)  # dataset processing
    kd = os.path.join(job_dir, "_kernel"); shutil.rmtree(kd, ignore_errors=True); os.makedirs(kd)
    open(f"{kd}/runner.py", "w").write(RUNNER)
    json.dump({"id": f"{USER}/{slug}-gpu", "title": f"{slug}-gpu", "code_file": "runner.py", "language": "python",
               "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_internet": True,
               "machine_shape": "NvidiaTeslaT4",   # T4 x2
               "dataset_sources": [f"{USER}/{slug}"], "competition_sources": [], "kernel_sources": []},
              open(f"{kd}/kernel-metadata.json", "w"))
    _k("kernels", "push", "-p", kd)
    log("Kaggle: GPU run started (~1 hour)")
    while True:
        time.sleep(120)
        st = _k("kernels", "status", f"{USER}/{slug}-gpu").lower()
        if "complete" in st: break
        if "error" in st or "cancel" in st:
            tail = _fail_log(f"{USER}/{slug}-gpu", job_dir)
            print("===== KAGGLE LOG TAIL =====\n" + tail + "\n===== END =====", flush=True)
            try: log("Kaggle GPU error:\n" + tail[-3000:])
            except Exception: pass
            raise RuntimeError("Kaggle run failed: " + st)
    out = os.path.join(job_dir, "_out"); shutil.rmtree(out, ignore_errors=True)
    _k("kernels", "output", f"{USER}/{slug}-gpu", "-p", out)
    with zipfile.ZipFile(f"{out}/out.zip") as z: z.extractall(job_dir)
    log("Kaggle: clips downloaded")
