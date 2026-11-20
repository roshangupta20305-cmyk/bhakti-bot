# STEP 7: final edit on CPU. Needs: shots.json, clips/ (+ *_sync.mp4), audio/timing.json, keyframes/
# Optional: music.mp3 (copyright-free flute+tanpura, e.g. YouTube Audio Library / Pixabay), bell.mp3
# Output: final/short.mp4 (1080x1920, 30fps, H.264, yuv420p, -14 LUFS), final/cover.png, final/metadata.txt
import os, json, subprocess, urllib.request
S = json.load(open("shots.json", encoding="utf-8")); T = json.load(open("audio/timing.json"))
os.makedirs("final", exist_ok=True); os.makedirs("tmp", exist_ok=True); os.makedirs("fonts", exist_ok=True)
FONT = "fonts/NotoSansDevanagari-Bold.ttf"
if not os.path.exists(FONT):
    urllib.request.urlretrieve("https://github.com/notofonts/notofonts.github.io/raw/main/fonts/NotoSansDevanagari/hinted/ttf/NotoSansDevanagari-Bold.ttf", FONT)
FD, COVER, PAD, MAXCUT = 0.3, 0.6, 0.35, 3.2   # crossfade, cover length, gap after each line, max secs for non-talking shot
run = lambda a: subprocess.run(a, check=True)
def dur(p): return float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",p]))

# ---- timeline: each beat lasts its line + pad, split over its shots
shots, caps, t = [], [], COVER
for i, b in enumerate(S["beats"]):
    bd = T[i]["dur"] + PAD
    n = len(b["shots"]); bd = max(bd, 2.2 * n)
    caps.append((t, t + T[i]["dur"] + 0.15, S["characters"][b["speaker"]]["name"], b["line"], T[i]["file"]))
    for sh in b["shots"]:
        d = bd / n
        src = f"clips/{sh['id']}_sync.mp4" if sh["talking"] and os.path.exists(f"clips/{sh['id']}_sync.mp4") else f"clips/{sh['id']}.mp4"
        lim = sh.get("use", 4.9 if sh["talking"] else MAXCUT)
        shots.append({"id": sh["id"], "src": src, "d": d, "lim": lim}); t += d
TOTAL = t + 0.4
print(f"total {TOTAL:.1f}s")
if TOTAL > 60: print("!! over 60s: shorten lines")

GRADE = "eq=contrast=1.06:saturation=1.12:gamma=0.98,colorbalance=rm=0.03:gm=0.01:bm=-0.03"
UP = "scale=1152:2048:flags=lanczos,scale=1080:1920:flags=lanczos,unsharp=5:5:0.6:5:5:0.0"

# ---- cover still (keyframe of s01 + hook) via ASS so Devanagari shapes correctly
def ass_header():
    return ("[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\n\n[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
            "Style: Hook,Noto Sans Devanagari,118,&H0000E1FF,&H000000FF,&H00000000,&H64000000,1,0,0,0,100,100,0,0,1,9,4,8,60,60,260,1\n"
            "Style: Name,Noto Sans Devanagari,58,&H0000D7FF,&H000000FF,&H00000000,&H78000000,1,0,0,0,100,100,0,0,1,5,2,2,70,70,520,1\n"
            "Style: Line,Noto Sans Devanagari,72,&H00FFFFFF,&H000000FF,&H00000000,&H78000000,1,0,0,0,100,100,0,0,1,6,2,2,70,70,360,1\n\n"
            "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
def ts(x): h=int(x//3600); m=int(x%3600//60); s=x%60; return f"{h}:{m:02d}:{s:05.2f}"
hook = "\\N".join(S["hook"])
open("tmp/cover.ass","w",encoding="utf-8").write(ass_header()+f"Dialogue: 0,{ts(0)},{ts(5)},Hook,,0,0,0,,{hook}\n")
cover_src = "keyframes/s15.png" if os.path.exists("keyframes/s15.png") else "keyframes/s01.png"
run(["ffmpeg","-y","-loglevel","error","-i",cover_src,"-vf",f"{UP},{GRADE},subtitles=tmp/cover.ass:fontsdir=fonts","-frames:v","1","final/cover.png"])

# ---- prepare each clip: trim, 30fps, upscale, sharpen, grade (+FD tail for crossfade)
parts = []
run(["ffmpeg","-y","-loglevel","error","-loop","1","-i","final/cover.png","-t",f"{COVER+FD+0.1}","-r","30","-c:v","libx264","-crf","14","-pix_fmt","yuv420p","tmp/p00.mp4"])
parts.append(("tmp/p00.mp4", COVER))
for k, s in enumerate(shots, 1):
    need = s["d"] + FD; avail = min(dur(s["src"]), s["lim"])
    o = f"tmp/p{k:02d}.mp4"
    slow = "" if avail >= need else f",setpts=PTS*{need/avail:.4f}"    # stretch gently if clip too short (non-talking only)
    if s["src"].endswith("_sync.mp4") and avail < need: slow = f",tpad=stop_mode=clone:stop_duration={need-avail:.3f}"
    run(["ffmpeg","-y","-loglevel","error","-t",f"{avail:.3f}","-i",s["src"],"-an","-vf",
         f"fps=30{slow},tpad=stop_mode=clone:stop_duration=3,{UP},{GRADE},trim=duration={need:.3f},setpts=PTS-STARTPTS,setsar=1","-r","30","-c:v","libx264","-crf","14","-pix_fmt","yuv420p",o])
    parts.append((o, s["d"]))

# ---- crossfade chain
inp, fc, prev, off = [], [], "0:v", 0.0
for p, _ in parts: inp += ["-i", p]
for k in range(1, len(parts)):
    off += parts[k-1][1]; lab = f"x{k}"
    fc.append(f"[{prev}][{k}:v]xfade=transition=fade:duration={FD}:offset={off:.3f}[{lab}]"); prev = lab

# ---- captions
ev = ass_header()
for st, en, name, line, _ in caps:
    ev += f"Dialogue: 0,{ts(st)},{ts(en)},Name,,0,0,0,,{name}\n"
    ev += f"Dialogue: 0,{ts(st)},{ts(en)},Line,,0,0,0,,{line}\n"
open("tmp/caps.ass","w",encoding="utf-8").write(ev)
fc.append(f"[{prev}]subtitles=tmp/caps.ass:fontsdir=fonts,format=yuv420p[v]")
run(["ffmpeg","-y","-loglevel","error"]+inp+["-filter_complex",";".join(fc),"-map","[v]","-t",f"{TOTAL:.3f}","-r","30","-an","-c:v","libx264","-crf","16","tmp/video.mp4"])

# ---- audio: voices placed on timeline, music ducked under voice, bell at start, -14 LUFS
ai, af, mix = [], [], []
for j, (st, _, _, _, f) in enumerate(caps):
    ai += ["-i", f]; af.append(f"[{j}:a]aresample=48000,adelay={int(st*1000)}|{int(st*1000)},apad[v{j}]"); mix.append(f"[v{j}]")
n = len(caps)
af.append(f"{''.join(mix)}amix=inputs={n}:normalize=0:duration=longest,atrim=0:{TOTAL:.3f}[voice]")
last = "[voice]"
if os.path.exists("music.mp3"):
    ai += ["-stream_loop","-1","-i","music.mp3"]
    af.append(f"[{n}:a]aresample=48000,atrim=0:{TOTAL:.3f},volume=0.35,afade=t=out:st={TOTAL-1.5:.2f}:d=1.5[m]")
    af.append("[voice]asplit[vo][sc];[m][sc]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=300[md];[vo][md]amix=inputs=2:normalize=0[vm]")
    last = "[vm]"; n += 1
if os.path.exists("bell.mp3"):
    ai += ["-i","bell.mp3"]; af.append(f"[{n}:a]aresample=48000,volume=0.6[b];{last}[b]amix=inputs=2:normalize=0:duration=first[vb]"); last = "[vb]"
af.append(f"{last}loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[a]")
run(["ffmpeg","-y","-loglevel","error"]+ai+["-filter_complex",";".join(af),"-map","[a]","-t",f"{TOTAL:.3f}","-c:a","pcm_s16le","tmp/audio.wav"])
run(["ffmpeg","-y","-loglevel","error","-i","tmp/video.mp4","-i","tmp/audio.wav","-map","0:v","-map","1:a","-c:v","copy",
     "-c:a","aac","-b:a","192k","-movflags","+faststart","-shortest","final/short.mp4"])
os.system("cp metadata.txt final/ 2>/dev/null")
print("final/short.mp4  final/cover.png  final/metadata.txt")
