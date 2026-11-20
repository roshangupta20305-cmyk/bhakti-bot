# Idea -> script (shots.json) -> metadata, using Gemini free API.
import os, json, re, random
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
TEXT_MODEL = os.environ.get("TEXT_MODEL", "gemini-2.5-flash")
HERE = os.path.dirname(os.path.abspath(__file__))
HISTORY = os.path.join(HERE, "history.json")
EXAMPLE = open(os.path.join(HERE, "example_shots.json"), encoding="utf-8").read()
ENDING = "जो लाइक करे और कमेंट में जय श्री राम लिखे, उस पर प्रभु की कृपा सदा बनी रहे।"
VOICES = ["Orus", "Gacrux", "Algieba", "Puck", "Kore", "Charon", "Aoede", "Fenrir", "Leda", "Sulafat", "Achird", "Iapetus"]

def _json(text):
    m = re.search(r"\{.*\}|\[.*\]", text, re.S)
    return json.loads(m.group(0))

def _ask(prompt):
    r = client.models.generate_content(model=TEXT_MODEL, contents=prompt,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.9))
    return _json(r.text)

def history():
    return json.load(open(HISTORY, encoding="utf-8")) if os.path.exists(HISTORY) else []

def remember(topic):
    h = history(); h.append(topic); os.makedirs(os.path.dirname(HISTORY), exist_ok=True)
    json.dump(h, open(HISTORY, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

def ideas(n=5, niche="Hindi bhakti stories from Ramayan, Mahabharat, Krishna leela, Shiv katha, Hanuman ji"):
    done = ", ".join(history()[-60:]) or "none"
    return _ask(f"""Give {n} fresh YouTube Shorts story ideas in the niche: {niche}.
Each must be one short, emotional prasang that works in 50 seconds with 2-4 characters and a clear moral.
Already made (do NOT repeat): {done}.
Return JSON list: [{{"topic_hi": "...", "topic_en": "...", "why_viral": "..."}}]""")

def script(topic):
    s = _ask(f"""You write 3D Pixar-style animated Hindi bhakti YouTube Shorts. Topic: {topic}
Return JSON with EXACTLY the same schema as this example (same keys, same style string idea):
{EXAMPLE}
Rules:
- 10-12 beats, exactly 16 shots total, total spoken text about 45 seconds.
- Lines in simple Devanagari Hindi. A talking line (beat whose single shot has talking=true) max 12 words.
- Narrator beats can have 1-2 shots with talking=false. Character beats have exactly 1 shot, talking=true, close-up front-facing portrait, face large and centered.
- Every character in "characters" needs "name" (Hindi), "voice" (choose from {VOICES}, all different), "ref" (full body, plain white background, detailed face, skin, hair, costume). Narrator has name "सूत्रधार", voice "Orus", no ref.
- Image prompts: no text, no signboards; say exactly who is in the frame.
- Motion prompts: talking shots must contain "mouth opens and closes, talking, static locked-off camera, no zoom, no push in".
- "hook": 2 short Hindi lines (max 4 words each) that create curiosity.
- The LAST beat is narrator saying exactly: {ENDING}
- shot ids s01..s16 in order.""")
    n = sum(len(b["shots"]) for b in s["beats"])
    assert 12 <= n <= 18, f"bad shot count {n}"
    if s["beats"][-1]["line"].strip() != ENDING:
        s["beats"].append({"speaker": "narrator", "line": ENDING, "shots": [dict(s["beats"][-1]["shots"][-1], id="s99", talking=False)]})
    return s

def metadata(s):
    m = _ask(f"""Write YouTube Shorts / Instagram Reels metadata in Hindi+Hinglish for this bhakti short:
Title: {s['title']}. Story lines: {[b['line'] for b in s['beats']]}
Return JSON: {{"title": "<=90 chars, Hindi, ends with #shorts", "description": "3-5 lines, includes the line '{ENDING}', then 3 hashtags",
"tags": ["15 search tags, mix Hindi and Hinglish"], "hashtags": ["8 hashtags with #"]}}""")
    return m

def write_job(job_dir, topic):
    s = script(topic); m = metadata(s)
    os.makedirs(job_dir, exist_ok=True)
    json.dump(s, open(f"{job_dir}/shots.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(m, open(f"{job_dir}/meta.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    open(f"{job_dir}/metadata.txt", "w", encoding="utf-8").write(
        f"TITLE\n{m['title']}\n\nDESCRIPTION\n{m['description']}\n\nTAGS\n{', '.join(m['tags'])}\n\nHASHTAGS\n{' '.join(m['hashtags'])}\n")
    remember(topic)
    return s, m

def qc_sheet(jpg_path):
    """Step 6 automated: Gemini looks at a 6-frame contact sheet and says if the clip is usable."""
    img = open(jpg_path, "rb").read()
    r = client.models.generate_content(model=TEXT_MODEL, contents=[
        types.Part.from_bytes(data=img, mime_type="image/jpeg"),
        "These are 6 frames from one 3D cartoon video clip, left to right. Is it usable? Reject for: extra or duplicate "
        "person, deformed hands, melted or blurry face, face changing identity, sudden zoom, text. "
        'Return JSON {"ok": true/false, "reason": "...", "camera_moves_at_end": true/false}'],
        config=types.GenerateContentConfig(response_mime_type="application/json"))
    return _json(r.text)
