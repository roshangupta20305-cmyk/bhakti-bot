# STEP 2 + 4: character refs, keyframes (Nano Banana), Gemini TTS, faster-whisper timing.
# CPU only. Run in Kaggle (no GPU needed) or locally.  pip install google-genai pillow faster-whisper
# Set GEMINI_API_KEY (Kaggle: Add-ons > Secrets).
import os, json, time, wave, io
from PIL import Image
from google import genai
from google.genai import types

S = json.load(open("shots.json", encoding="utf-8"))
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"], http_options=types.HttpOptions(api_version="v1beta"))
IMG_MODEL = "gemini-2.5-flash-image"
TTS_MODEL = os.environ.get("TTS_MODEL", "gemini-2.5-flash-preview-tts")
os.makedirs("refs", exist_ok=True); os.makedirs("keyframes", exist_ok=True); os.makedirs("audio", exist_ok=True)

def gen_image(parts, out, tries=4):
    for t in range(tries):
        try:
            r = client.models.generate_content(model=IMG_MODEL, contents=parts,
                config=types.GenerateContentConfig(response_modalities=["IMAGE"]))
            for p in r.candidates[0].content.parts:
                if p.inline_data:
                    Image.open(io.BytesIO(p.inline_data.data)).convert("RGB").save(out); return out
        except Exception as e:
            print("retry", out, e); time.sleep(20)
    raise RuntimeError("image failed " + out)

def fit_576x1024(path):
    im = Image.open(path); W, H = 576, 1024
    s = max(W / im.width, H / im.height)
    im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    l, t = (im.width - W) // 2, (im.height - H) // 2
    im.crop((l, t, l + W, t + H)).save(path)

IMG_BACKEND = os.environ.get("IMG_BACKEND", "kaggle")   # "kaggle" = FREE (SDXL on Kaggle GPU); "gemini" = paid Nano Banana
# 1) Character reference sheets (one per character, full body, clean bg)
for k, c in (S["characters"].items() if IMG_BACKEND == "gemini" else []):
    if "ref" not in c: continue
    out = f"refs/{k}.png"
    if not os.path.exists(out):
        gen_image([f"{S['style']}. {c['ref']}. Single character only."], out); time.sleep(8)

# 2) Keyframes, always passing the reference images so faces stay the same
for b in (S["beats"] if IMG_BACKEND == "gemini" else []):
    for sh in b["shots"]:
        out = f"keyframes/{sh['id']}.png"
        if os.path.exists(out): continue
        refs = [Image.open(f"refs/{c}.png") for c in sh["chars"]]
        names = ", ".join(sh["chars"])
        extra = (" Exactly ONE person in frame, front-facing, face fills at least half the frame width, mouth clearly visible, closed neutral mouth."
                 if sh["talking"] else f" Exactly {len(sh['chars'])} person(s) in frame: {names}. No other people.")
        prompt = (f"{S['style']}. Vertical 9:16 frame. {sh['image']}.{extra} Keep each character's face, skin tone, hair "
                  f"and costume IDENTICAL to the reference image(s). Correct hands with five fingers. No text anywhere.")
        gen_image([prompt] + refs, out); fit_576x1024(out); time.sleep(8)
        print("keyframe", out)

# 3) TTS, one file per beat. Free tier = 3 req/min -> sleep 21s
def save_pcm(pcm, path, rate=24000):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)

for i, b in enumerate(S["beats"]):
    out = f"audio/b{i:02d}.wav"
    if os.path.exists(out): continue
    voice = S["characters"][b["speaker"]]["voice"]
    style = ("Read in clear, warm, devotional Hindi storytelling voice, medium pace, not deep or heavy"
             if b["speaker"] == "narrator" else "Speak this Hindi line naturally and clearly, warm emotion, medium pace")
    ok = False
    for t in range(3):
        try:
            r = client.models.generate_content(model=TTS_MODEL, contents=f"{style}: {b['line']}",
                config=types.GenerateContentConfig(response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))))
            save_pcm(r.candidates[0].content.parts[0].inline_data.data, out); ok = True; break
        except Exception as e:
            print("tts retry", i, e); time.sleep(30)
    if not ok:   # FREE fallback: Microsoft Edge neural Hindi voices
        import asyncio, edge_tts
        FEMALE = {"Gacrux","Kore","Aoede","Leda","Zephyr","Callirrhoe","Autonoe","Despina","Erinome","Laomedeia","Pulcherrima","Sulafat","Vindemiatrix","Achernar"}
        ev = "hi-IN-SwaraNeural" if voice in FEMALE else "hi-IN-MadhurNeural"
        asyncio.run(edge_tts.Communicate(b["line"], ev, rate="-5%").save(f"audio/b{i:02d}.mp3"))
        os.system(f"ffmpeg -y -loglevel error -i audio/b{i:02d}.mp3 -ar 24000 -ac 1 {out}")
        print("tts fallback edge", ev)
    print("tts", out); time.sleep(21)

# 4) faster-whisper: trim silence, store exact speech start/end per line
from faster_whisper import WhisperModel
wm = WhisperModel("small", device="cpu", compute_type="int8")
timing = []
for i, b in enumerate(S["beats"]):
    segs, _ = wm.transcribe(f"audio/b{i:02d}.wav", language="hi", word_timestamps=True)
    words = [w for s in segs for w in (s.words or [])]
    st = max(0.0, words[0].start - 0.08) if words else 0.0
    en = (words[-1].end + 0.15) if words else None
    out = f"audio/b{i:02d}_trim.wav"
    cmd = f'ffmpeg -y -loglevel error -i audio/b{i:02d}.wav -ss {st:.3f} ' + (f'-to {en:.3f} ' if en else '') + f'-ar 48000 -ac 1 {out}'
    os.system(cmd)
    dur = float(os.popen(f'ffprobe -v error -show_entries format=duration -of csv=p=0 {out}').read())
    timing.append({"beat": i, "file": out, "dur": round(dur, 3)})
    print(i, b["speaker"], round(dur, 2), "s")
    if any(sh["talking"] for sh in b["shots"]) and dur > 4.8:
        print("  !! talking line > 4.8s: shorten text or regenerate faster")
json.dump(timing, open("audio/timing.json", "w"), indent=1)
print("Done. Upload refs/, keyframes/, audio/ + shots.json to the Kaggle GPU notebook as a dataset.")
