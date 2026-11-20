# STEP 3 + 5 on Kaggle (Accelerator: GPU T4 x2, Internet ON).
# Run cells in order. Put shots.json, keyframes/, audio/ in /kaggle/working (or copy from your dataset).
#   python 02_kaggle_gpu.py images            -> FREE character refs + keyframes (SDXL + IP-Adapter, both GPUs)
#   python 02_kaggle_gpu.py encode            -> T5 prompt embeds once (GPU0), then frees the 9GB encoder
#   python 02_kaggle_gpu.py ltx               -> spawns 2 workers, one per T4, half the shots each
#   python 02_kaggle_gpu.py latentsync        -> lip-sync talking shots (both GPUs) + mouth/jaw blend
#   python 02_kaggle_gpu.py redo s07 1234     -> re-render one shot with a new seed
# Setup cell:
#   !pip install -q -U diffusers transformers accelerate sentencepiece imageio imageio-ffmpeg mediapipe opencv-python-headless
import os, sys, json, subprocess, torch
S = json.load(open("shots.json", encoding="utf-8"))
SHOTS = [sh for b in S["beats"] for sh in b["shots"]]
NEG = "zoom in, push in, dolly, camera shake, extra person, duplicate person, deformed hands, extra fingers, distorted face, blurry face, text, watermark"
TXT_REPO = "Lightricks/LTX-Video-0.9.5"
CKPT = "https://huggingface.co/Lightricks/LTX-Video/blob/main/ltxv-2b-0.9.8-distilled.safetensors"
os.makedirs("clips", exist_ok=True); os.makedirs("embeds", exist_ok=True)
os.makedirs("refs", exist_ok=True); os.makedirs("keyframes", exist_ok=True)
SDXL = "stabilityai/stable-diffusion-xl-base-1.0"
IMG_NEG = "text, watermark, logo, extra fingers, deformed hands, extra limbs, extra person, duplicate person, distorted face, blurry, lowres, photo, realistic"

# ---- FREE images on Kaggle GPU: SDXL + IP-Adapter (same character face/costume from its reference) ----
def sdxl_pipe():
    from diffusers import StableDiffusionXLPipeline, AutoencoderKL
    from transformers import CLIPVisionModelWithProjection
    enc = CLIPVisionModelWithProjection.from_pretrained("h94/IP-Adapter", subfolder="models/image_encoder", torch_dtype=torch.float16)
    vae = AutoencoderKL.from_pretrained("madebyollin/sdxl-vae-fp16-fix", torch_dtype=torch.float16)
    pipe = StableDiffusionXLPipeline.from_pretrained(SDXL, vae=vae, image_encoder=enc, torch_dtype=torch.float16,
                                                     variant="fp16", use_safetensors=True).to("cuda")
    pipe.load_ip_adapter("h94/IP-Adapter", subfolder="sdxl_models", weight_name="ip-adapter-plus_sdxl_vit-h.safetensors")
    return pipe

def ref_crop(k):
    from PIL import Image
    im = Image.open(f"refs/{k}.png").convert("RGB"); w, h = im.size
    return im.crop((int(w * .2), 0, int(w * .8), int(h * .5)))   # head + upper body

def fit_576x1024(im):
    from PIL import Image
    W, H = 576, 1024; s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    l, t = (im.width - W) // 2, (im.height - H) // 2
    return im.crop((l, t, l + W, t + H))

def gen_refs():
    from PIL import Image
    pipe = sdxl_pipe(); pipe.set_ip_adapter_scale(0.0); blank = Image.new("RGB", (224, 224), "white")
    for i, (k, c) in enumerate(S["characters"].items()):
        if "ref" not in c or os.path.exists(f"refs/{k}.png"): continue
        im = pipe(prompt=f"{S['style']}. {c['ref']}. Single character only, full body, centered.", negative_prompt=IMG_NEG,
                  ip_adapter_image=blank, width=1024, height=1024, num_inference_steps=30, guidance_scale=6.5,
                  generator=torch.Generator("cuda").manual_seed(1000 + i)).images[0]
        im.save(f"refs/{k}.png"); print("ref", k, flush=True)

def img_worker(ids):
    from PIL import Image
    pipe = sdxl_pipe(); blank = Image.new("RGB", (224, 224), "white")
    for sid in ids:
        sh = next(x for x in SHOTS if x["id"] == sid)
        if os.path.exists(f"keyframes/{sid}.png"): continue
        chars = [c for c in sh["chars"] if os.path.exists(f"refs/{c}.png")]
        if sh["talking"]:
            extra = " Exactly one person, front-facing close-up, face large and centered, mouth closed, neutral."
        else:
            extra = f" Exactly {len(sh['chars'])} person(s) in frame. No other people."
        prompt = f"{S['style']}. Vertical frame. {sh['image']}.{extra} Five fingers on each hand. No text."
        if chars:
            pipe.set_ip_adapter_scale(0.6 if len(chars) == 1 else 0.35); ref = ref_crop(chars[0])
        else:
            pipe.set_ip_adapter_scale(0.0); ref = blank
        seed = int(sid.strip("s") or 0) * 7 + 11 if sid.strip("s").isdigit() else 11
        im = pipe(prompt=prompt, negative_prompt=IMG_NEG, ip_adapter_image=ref, width=768, height=1344,
                  num_inference_steps=30, guidance_scale=6.5, generator=torch.Generator("cuda").manual_seed(seed)).images[0]
        fit_576x1024(im).save(f"keyframes/{sid}.png"); print("keyframe", sid, flush=True)

def images():
    subprocess.run([sys.executable, __file__, "_refs"], env={**os.environ, "CUDA_VISIBLE_DEVICES": "0"}, check=True)
    ids = [sh["id"] for sh in SHOTS]
    ps = [subprocess.Popen([sys.executable, __file__, "_img", ",".join(h)], env={**os.environ, "CUDA_VISIBLE_DEVICES": str(g)})
          for g, h in enumerate([ids[0::2], ids[1::2]]) if h]
    for p in ps: p.wait()
    miss = [i for i in ids if not os.path.exists(f"keyframes/{i}.png")]
    if miss: raise SystemExit("keyframes missing: " + ",".join(miss))

def prompt_for(sh):
    return f"{S['style']}. {sh['image']}. {sh['motion']}. Smooth natural motion, consistent faces."

def encode():
    from transformers import T5EncoderModel, T5TokenizerFast
    tok = T5TokenizerFast.from_pretrained(TXT_REPO, subfolder="tokenizer")
    enc = T5EncoderModel.from_pretrained(TXT_REPO, subfolder="text_encoder", torch_dtype=torch.float16).to("cuda:0")
    def e(t):
        x = tok(t, padding="max_length", max_length=128, truncation=True, return_tensors="pt").to("cuda:0")
        with torch.no_grad(): h = enc(x.input_ids, attention_mask=x.attention_mask)[0]
        return h.cpu(), x.attention_mask.cpu()
    neg = e(NEG)
    for sh in SHOTS:
        p = e(prompt_for(sh))
        torch.save({"pe": p[0], "pm": p[1], "ne": neg[0], "nm": neg[1]}, f"embeds/{sh['id']}.pt")
    print("embeds done")

def worker(ids, seed_base=42):
    from diffusers import LTXConditionPipeline, LTXVideoTransformer3DModel
    from diffusers.pipelines.ltx.pipeline_ltx_condition import LTXVideoCondition
    from diffusers.utils import export_to_video, load_image
    tr = LTXVideoTransformer3DModel.from_single_file(CKPT, torch_dtype=torch.float16)
    pipe = LTXConditionPipeline.from_pretrained(TXT_REPO, transformer=tr, text_encoder=None, tokenizer=None,
                                                torch_dtype=torch.float16).to("cuda")
    pipe.vae.enable_tiling()
    for sid in ids:
        seed = seed_base if ":" not in sid else int(sid.split(":")[1]); sid = sid.split(":")[0]
        em = torch.load(f"embeds/{sid}.pt")
        cond = LTXVideoCondition(image=load_image(f"keyframes/{sid}.png"), frame_index=0)
        frames = pipe(conditions=[cond], width=576, height=1024, num_frames=121, num_inference_steps=8,
                      guidance_scale=1.0,   # NOTE: at guidance 1 the negative prompt has no effect
                      prompt_embeds=em["pe"].cuda(), prompt_attention_mask=em["pm"].cuda(),
                      negative_prompt_embeds=em["ne"].cuda(), negative_prompt_attention_mask=em["nm"].cuda(),
                      decode_timestep=0.05, decode_noise_scale=0.025,
                      generator=torch.Generator("cuda").manual_seed(seed), output_type="pil").frames[0]
        export_to_video(frames, f"clips/{sid}.mp4", fps=24)
        print("clip", sid, "seed", seed, flush=True)

def launch(ids_all):
    halves = [ids_all[0::2], ids_all[1::2]]
    ps = [subprocess.Popen([sys.executable, __file__, "_w", ",".join(h)],
                           env={**os.environ, "CUDA_VISIBLE_DEVICES": str(g)}) for g, h in enumerate(halves) if h]
    for p in ps: p.wait()

def setup_latentsync():
    if os.path.exists("LatentSync"): return
    os.system("git clone -q https://github.com/bytedance/LatentSync")
    # keep Kaggle's torch; install only what's missing
    os.system("pip install -q omegaconf einops decord python_speech_features librosa insightface onnxruntime-gpu face-alignment kornia DeepCache 'huggingface_hub[cli]'")
    os.system("huggingface-cli download ByteDance/LatentSync-1.5 whisper/tiny.pt latentsync_unet.pt --local-dir LatentSync/checkpoints")

def ls_one(sid, beat_idx, gpu):
    os.makedirs("ls", exist_ok=True)
    timing = json.load(open("audio/timing.json"))
    a = timing[beat_idx]["file"]; dur = min(5.0, timing[beat_idx]["dur"] + 0.3)
    os.system(f"ffmpeg -y -loglevel error -i clips/{sid}.mp4 -t {dur} -r 25 -c:v libx264 -pix_fmt yuv420p ls/{sid}_25.mp4")
    os.system(f"ffmpeg -y -loglevel error -i {a} -af apad -t {dur} -ar 16000 -ac 1 ls/{sid}.wav")
    cmd = (f"cd LatentSync && CUDA_VISIBLE_DEVICES={gpu} python -m scripts.inference --unet_config_path configs/unet/stage2.yaml "
           f"--inference_ckpt_path checkpoints/latentsync_unet.pt --inference_steps 20 --guidance_scale 1.5 "
           f"--video_path ../ls/{sid}_25.mp4 --audio_path ../ls/{sid}.wav --video_out_path ../ls/{sid}_ls.mp4")
    return subprocess.Popen(cmd, shell=True)

def blend(sid):
    """Keep LTX frame sharp, paste only mouth+jaw from LatentSync with a feathered mask."""
    import cv2, numpy as np, mediapipe as mp
    LIPS_JAW = [61,146,91,181,84,17,314,405,321,375,291,409,270,269,267,0,37,39,40,185,
                2,164,98,327,205,425,214,434,135,364,138,367,172,397,136,365,150,379,149,378,176,400,148,377,152]
    A = cv2.VideoCapture(f"ls/{sid}_25.mp4"); B = cv2.VideoCapture(f"ls/{sid}_ls.mp4")
    fm = mp.solutions.face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1)
    out = None; last = None; n_det = 0
    while True:
        ok1, fa = A.read(); ok2, fb = B.read()
        if not (ok1 and ok2): break
        h, w = fa.shape[:2]
        if fb.shape[:2] != (h, w): fb = cv2.resize(fb, (w, h))
        r = fm.process(cv2.cvtColor(fa, cv2.COLOR_BGR2RGB))
        if r.multi_face_landmarks:
            lm = r.multi_face_landmarks[0].landmark
            pts = np.array([[lm[i].x * w, lm[i].y * h] for i in LIPS_JAW], np.int32)
            m = np.zeros((h, w), np.uint8); cv2.fillConvexPoly(m, cv2.convexHull(pts), 255)
            k = max(9, (w // 40) | 1); m = cv2.dilate(m, np.ones((k, k), np.uint8))
            last = cv2.GaussianBlur(m, (0, 0), w / 60).astype(np.float32)[..., None] / 255.0; n_det += 1
        alpha = last if last is not None else np.ones((h, w, 1), np.float32)
        fr = (fb * alpha + fa * (1 - alpha)).astype(np.uint8)
        if out is None: out = cv2.VideoWriter(f"ls/{sid}_blend_noaudio.mp4", cv2.VideoWriter_fourcc(*"mp4v"), 25, (w, h))
        out.write(fr)
    out.release()
    os.system(f"ffmpeg -y -loglevel error -i ls/{sid}_blend_noaudio.mp4 -c:v libx264 -crf 16 -pix_fmt yuv420p clips/{sid}_sync.mp4")
    print(sid, "blend done, face found in", n_det, "frames (0 = full LatentSync frame used)")

if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "images": images()
    elif cmd == "_refs": gen_refs()
    elif cmd == "_img": img_worker(sys.argv[2].split(","))
    elif cmd == "encode": encode()
    elif cmd == "_w": worker(sys.argv[2].split(","))
    elif cmd == "ltx": launch([sh["id"] for sh in SHOTS])
    elif cmd == "redo": launch([f"{sys.argv[2]}:{sys.argv[3]}"])
    elif cmd == "latentsync":
        setup_latentsync()
        jobs = [(sh["id"], i) for i, b in enumerate(S["beats"]) for sh in b["shots"] if sh["talking"]]
        only = sys.argv[2:]  # optional: latentsync s03 s10
        if only: jobs = [j for j in jobs if j[0] in only]
        for k in range(0, len(jobs), 2):
            ps = [ls_one(sid, bi, g) for g, (sid, bi) in enumerate(jobs[k:k + 2])]
            for p in ps: p.wait()
        for sid, _ in jobs: blend(sid)
