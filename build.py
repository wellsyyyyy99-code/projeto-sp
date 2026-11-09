#!/usr/bin/env python3
"""
Projeto SP — 44-episode São Paulo sprint builder.

Reads packs/pack-XX.json (each pack = a few story episodes) and produces in docs/:
  audio/        one MP3 per episode + one drill MP3 per pack
  decks/        one Anki deck per pack (.apkg, audio included)
  transcripts/  one page per pack (normal + as-heard spelling + hidden English)
  feed.xml      private podcast feed
  index.html    home page

Speed ladder: episodes get faster automatically as the episode number rises.
Only new packs are built (FORCE=1 rebuilds all). DRY_RUN=1 = beeps instead of voices.
"""
import asyncio, hashlib, json, os, re, shutil, sys, time, unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pydub import AudioSegment
import genanki
from feedgen.feed import FeedGenerator

ROOT = Path(__file__).parent
PACKS, DOCS = ROOT / "packs", ROOT / "docs"
AUDIO, DECKS, TRANS = DOCS / "audio", DOCS / "decks", DOCS / "transcripts"
CACHE, MEDIA = ROOT / ".tts_cache", ROOT / ".anki_media"
DRY = os.getenv("DRY_RUN") == "1"
FORCE = os.getenv("FORCE") == "1" or "--force" in sys.argv
DAY1 = datetime(2026, 11, 1, 6, tzinfo=timezone.utc)  # Episode 1 date

VOICES = {
    "george":   ("pt-BR-AntonioNeural",   "+0Hz"),
    "gabi":     ("pt-BR-FranciscaNeural", "+0Hz"),
    "mãe":      ("pt-BR-ThalitaNeural",   "-4Hz"),
    "mae":      ("pt-BR-ThalitaNeural",   "-4Hz"),
    "bia":      ("pt-BR-FranciscaNeural", "+12Hz"),
    "seu zé":   ("pt-BR-AntonioNeural",   "-16Hz"),
    "seu ze":   ("pt-BR-AntonioNeural",   "-16Hz"),
    "narrador": ("pt-BR-ThalitaNeural",   "+10Hz"),
    "ana":      ("pt-BR-FranciscaNeural", "-10Hz"),
    "rafa":     ("pt-BR-AntonioNeural",   "-8Hz"),
    "garçom":   ("pt-BR-AntonioNeural",   "-14Hz"),
    "garcom":   ("pt-BR-AntonioNeural",   "-14Hz"),
    "torcedor": ("pt-BR-AntonioNeural",   "+8Hz"),
    "barista":  ("pt-BR-ThalitaNeural",   "+18Hz"),
    "atendente": ("pt-BR-ThalitaNeural",  "+4Hz"),
    "vendedor": ("pt-BR-AntonioNeural",   "-4Hz"),
    "motorista": ("pt-BR-AntonioNeural",  "-20Hz"),
    "passageiro": ("pt-BR-AntonioNeural", "+14Hz"),
    "farmacêutico": ("pt-BR-FranciscaNeural", "-16Hz"),
    "estranho": ("pt-BR-AntonioNeural",   "+4Hz"),
}
EXTRA = [("pt-BR-AntonioNeural", "-8Hz"), ("pt-BR-FranciscaNeural", "-10Hz"), ("pt-BR-ThalitaNeural", "+16Hz")]
EN_VOICE = ("en-GB-RyanNeural", "+0Hz")
_extra = {}


def voice_for(speaker):
    k = speaker.strip().lower()
    if k in VOICES:
        return VOICES[k]
    _extra.setdefault(k, EXTRA[len(_extra) % len(EXTRA)])
    return _extra[k]


def speed(ep):
    """Speed ladder: slow at the start, faster than normal by the end."""
    for top, pct in ((8, -25), (15, -15), (22, -8), (30, 0), (37, 6), (44, 12)):
        if ep <= top:
            return pct
    return 12


def rate(pct):
    return f"{pct:+d}%"


# ---- TTS with cache -------------------------------------------------------------------
async def _edge(text, voice, r, pitch, out):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=r, pitch=pitch).save(str(out))


def tts_path(text, voice, pitch="+0Hz", r="+0%"):
    key = hashlib.sha1(f"{text}|{voice}|{r}|{pitch}".encode()).hexdigest()[:16]
    path = CACHE / f"psp_{key}.mp3"
    if path.exists() and path.stat().st_size > 0:
        return path
    CACHE.mkdir(exist_ok=True)
    if DRY:
        from pydub.generators import Sine
        Sine(330 if voice.startswith("en") else 520).to_audio_segment(
            duration=400 + 55 * len(text)).apply_gain(-18).export(path, format="mp3")
        return path
    v, last = voice, None
    for attempt in range(4):
        try:
            asyncio.run(_edge(text, v, r, pitch, path))
            if path.exists() and path.stat().st_size > 0:
                return path
        except Exception as e:
            last = e
        if attempt == 1 and v.startswith("pt-BR") and v not in ("pt-BR-FranciscaNeural", "pt-BR-AntonioNeural"):
            v = "pt-BR-FranciscaNeural"
        time.sleep(2 + attempt * 2)
    raise RuntimeError(f"TTS failed for {text!r} ({voice}): {last}")


def tts(*a, **k):
    return AudioSegment.from_file(tts_path(*a, **k))


def sil(ms):
    return AudioSegment.silent(duration=int(ms))


def en(text):
    return tts(text, *EN_VOICE)


def say(line, pct):
    v, p = voice_for(line["speaker"])
    return tts(line["pt"], v, p, rate(pct))


# ---- Validation -----------------------------------------------------------------------
def validate(pack, name):
    errs = []
    if not isinstance(pack.get("pack"), int):
        errs.append('"pack" must be a number')
    for i, e in enumerate(pack.get("episodes", [])):
        if not isinstance(e.get("ep"), int):
            errs.append(f"episode {i+1}: 'ep' must be a number")
        for f in ("title", "lines"):
            if f not in e:
                errs.append(f"episode {i+1}: missing {f!r}")
        for j, l in enumerate(e.get("lines", [])):
            for f in ("speaker", "pt", "en"):
                if not l.get(f):
                    errs.append(f"episode {i+1} line {j+1}: missing {f!r}")
        for j, c in enumerate(e.get("chunks", [])):
            if not c.get("pt") or not c.get("en"):
                errs.append(f"episode {i+1} chunk {j+1}: needs 'pt' and 'en'")
        for j, q in enumerate(e.get("speak", [])):
            if not q.get("speaker") or not q.get("q") or not (q.get("model") or q.get("hint")):
                errs.append(f"episode {i+1} speak {j+1}: needs 'speaker', 'q' and 'model' or 'hint'")
    for j, t in enumerate(pack.get("talk", [])):
        if not t.get("en") or not t.get("pt"):
            errs.append(f"talk topic {j+1}: needs 'en' and 'pt'")
    for j, d in enumerate(pack.get("drills", [])):
        if not d.get("en") or not d.get("pt"):
            errs.append(f"drill {j+1}: needs 'en' and 'pt'")
    if errs:
        sys.exit(f"\n❌ {name} has problems:\n  - " + "\n  - ".join(errs))


def slug(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:40]


def ep_file(e):
    return f"ep{e['ep']:02d}-{slug(e['title'])}.mp3"


def drill_file(p):
    return f"pack{p['pack']:02d}-drills.mp3"


# ---- Episodes -------------------------------------------------------------------------
def episode_audio(e):
    pct = speed(e["ep"])
    lines = e["lines"]
    full = sum((say(l, pct) + sil(420) for l in lines), sil(0))
    out = en(f"Episode {e['ep']}. {e['title']}.") + sil(700)
    if e.get("intro"):
        out += en(e["intro"]) + sil(1000)
    out += en("Listen.") + sil(400) + full + sil(1300)
    out += en("Again, with the transcript.") + sil(400) + full + sil(1500)
    out += en("Shadow each line. Slow, then story speed.") + sil(900)
    for l in lines:
        sl, n = say(l, pct - 20), say(l, pct)
        out += sl + sil(len(sl) * 1.1 + 500) + n + sil(len(n) * 1.1 + 600)
    if any(l["speaker"].lower() == "george" for l in lines):
        out += sil(800) + en("Now you are George. Say his lines in the gaps.") + sil(900)
        for l in lines:
            n = say(l, pct)
            if l["speaker"].lower() == "george":
                out += sil(len(n) * 1.4 + 1500) + n + sil(700)
            else:
                out += n + sil(420)
    qs = e.get("speak", [])
    if qs:
        out += sil(900) + en("Your turn. Answer each question out loud. Then hear an example.") + sil(900)
        for q in qs:
            v, p = voice_for(q["speaker"])
            out += tts(q["q"], v, p, rate(pct))
            if q.get("model"):
                out += sil(7000) + say({"speaker": "george", "pt": q["model"]}, pct) + sil(1400)
            else:  # personal question: no example, just a longer gap for your own answer
                out += sil(10000)
    out += sil(800) + en("Final listen. No transcript.") + sil(500) + full
    return out


def drill_audio(pack):
    g = VOICES["george"]
    out = en(f"Pack {pack['pack']} drills. Say the Portuguese before you hear it.") + sil(1000)
    for d in pack["drills"]:
        out += en(d["en"]) + sil(3200 + 25 * len(d["pt"])) + tts(d["pt"], *g) + sil(1000) + tts(d["pt"], *g) + sil(1600)
    return out


def gym_file(p):
    return f"pack{p['pack']:02d}-speaking-gym.mp3"


def beep(ms=350, hz=880):
    from pydub.generators import Sine
    return Sine(hz).to_audio_segment(duration=ms).apply_gain(-8)


def speaking_gym_audio(pack):
    first = min(e["ep"] for e in pack["episodes"])
    rounds = (60, 45, 30) if first <= 15 else (120, 90, 60) if first <= 30 else (180, 120, 90)
    words = {60: "one minute", 45: "forty-five seconds", 30: "thirty seconds", 120: "two minutes",
             90: "ninety seconds", 180: "three minutes"}
    m, mp = voice_for("mãe")
    out = en("Speaking gym. For each topic, talk out loud in Portuguese until the beep. "
             "Then say it all again, faster. Don't stop, don't translate. Simple is fine.") + sil(1200)
    for t in pack["talk"]:
        out += en(f"Topic: {t['en']}.") + sil(500) + tts(t["pt"], m, mp) + sil(800)
        for i, secs in enumerate(rounds):
            out += en(f"Round {i+1}. {words[secs]}. Go.") + beep() + sil(secs * 1000) + beep(600, 660) + sil(1500)
    out += en("Great work. Write down anything you couldn't say in your mistake log.")
    return out


def export(seg, path, title):
    seg.set_channels(1).export(path, format="mp3", bitrate="64k", tags={"title": title, "album": "Projeto SP"})


# ---- Anki -----------------------------------------------------------------------------
CSS = """.card{font-family:Arial,sans-serif;font-size:22px;text-align:center;color:#222;background:#fff}
.pt{font-size:28px;font-weight:bold;margin:10px}.heard{color:#7a4bb3;font-style:italic;margin:6px}
.en{font-size:22px;margin:8px}.note{font-size:16px;color:#666;margin-top:12px}.hint{font-size:15px;color:#999;margin-top:14px}
.nightMode .card,.night_mode .card{background:#1e1e1e;color:#eee}.nightMode .heard{color:#c9a7f0}"""
MODEL = genanki.Model(
    1849200511, "Projeto SP Listen + Say",
    fields=[{"name": n} for n in ("PT", "Heard", "EN", "Note", "Audio", "AudioSlow", "SayEN")],
    templates=[
        {"name": "1 Listen", "qfmt": '{{Audio}}<div class="hint">🎧 What does this mean?</div>',
         "afmt": '{{FrontSide}}<hr id="answer"><div class="pt">{{PT}}</div><div class="heard">{{Heard}}</div>'
                 '<div class="en">{{EN}}</div><div class="note">{{Note}}</div>{{AudioSlow}}'},
        {"name": "2 Say it", "qfmt": '{{#SayEN}}<div class="en">{{SayEN}}</div><div class="hint">🗣️ Say it out loud first</div>{{/SayEN}}',
         "afmt": '{{FrontSide}}<hr id="answer"><div class="pt">{{PT}}</div><div class="heard">{{Heard}}</div>'
                 '{{Audio}}<div class="note">{{Note}}</div>'},
    ], css=CSS)


SPEAK = genanki.Model(
    1849200512, "Projeto SP Answer Aloud",
    fields=[{"name": n} for n in ("Q", "QEN", "Model", "ModelEN", "Hint", "AudioQ", "AudioModel")],
    templates=[{"name": "Answer aloud",
        "qfmt": '{{AudioQ}}<div class="pt">{{Q}}</div><div class="hint">🗣️ Answer OUT LOUD, then flip</div>',
        "afmt": '{{FrontSide}}<hr id="answer"><div class="en">{{QEN}}</div>'
                '{{#Model}}<div class="pt">{{Model}}</div>{{AudioModel}}<div class="note">{{ModelEN}}</div>{{/Model}}'
                '<div class="note">{{Hint}}</div>'}], css=CSS)


class SpeakNote(genanki.Note):
    @property
    def guid(self):
        return genanki.guid_for("pspspeak", self.fields[0])


class StableNote(genanki.Note):
    @property
    def guid(self):
        return genanki.guid_for("psp", self.fields[0], self.fields[6] != "")


def deck_files(pack):
    """Pack 00 = one bonus deck. Story packs = one deck per episode, imported the day you do it."""
    if pack["pack"] == 0:
        return [("pack-00.apkg", pack["episodes"], 2044100000, "Projeto SP::Pack 00")]
    return [(f"ep-{e['ep']:02d}.apkg", [e], 2044200000 + e["ep"], f"Projeto SP::Ep {e['ep']:02d} · {e['title']}")
            for e in pack["episodes"]]


def build_deck(pack, out_path, episodes, did, name):
    p = pack["pack"]
    deck = genanki.Deck(did, name)
    MEDIA.mkdir(exist_ok=True)
    media, seen = [], set()

    def add(pt, heard, en_, note, speaker, production, pct):
        if pt in seen and not production:
            return
        seen.add(pt)
        v, ph = voice_for(speaker)
        a, s = tts_path(pt, v, ph, rate(max(pct, 0))), tts_path(pt, v, ph, rate(-25))
        for f in (a, s):
            dst = MEDIA / f.name
            if not dst.exists():
                shutil.copy(f, dst)
            media.append(str(dst))
        deck.add_note(StableNote(model=MODEL, tags=[f"pack{p:02d}"], fields=[
            pt, heard or "", en_, note or "", f"[sound:{a.name}]", f"[sound:{s.name}]", en_ if production else ""]))

    for e in episodes:
        pct = speed(e["ep"])
        for c in e.get("chunks", []):
            add(c["pt"], c.get("heard"), c["en"], c.get("note"), "george", True, pct)
        for l in e["lines"]:
            if l["speaker"].lower() == "narrador" and e["ep"] > 0:
                continue  # story narration is for listening, not cards
            add(l["pt"], l.get("heard"), l["en"], f"Ep {e['ep']} — {l['speaker']}", l["speaker"], False, pct)
        for q in e.get("speak", []):
            if q["q"] in seen:
                continue
            seen.add(q["q"])
            v, ph = voice_for(q["speaker"])
            aq = tts_path(q["q"], v, ph, rate(max(pct, -10)))
            files = [aq]
            am = ""
            if q.get("model"):
                g, gp = voice_for("george")
                m = tts_path(q["model"], g, gp, rate(max(pct, -10)))
                files.append(m)
                am = f"[sound:{m.name}]"
            for f in files:
                dst = MEDIA / f.name
                if not dst.exists():
                    shutil.copy(f, dst)
                media.append(str(dst))
            deck.add_note(SpeakNote(model=SPEAK, tags=[f"pack{p:02d}", "speak"], fields=[
                q["q"], q.get("q_en", ""), q.get("model", ""), q.get("model_en", ""), q.get("hint", ""),
                f"[sound:{aq.name}]", am]))
    pkg = genanki.Package(deck)
    pkg.media_files = sorted(set(media))
    pkg.write_to_file(out_path)
    return len(deck.notes)


# ---- Transcripts ----------------------------------------------------------------------
TCSS = """:root{--bg:#fff;--fg:#1b1b1b;--muted:#666;--heard:#7a4bb3;--card:#f5f5f7;--line:#e2e2e2}
@media (prefers-color-scheme:dark){:root{--bg:#121212;--fg:#eee;--muted:#aaa;--heard:#c9a7f0;--card:#1e1e1e;--line:#333}}
body{font-family:Arial,sans-serif;background:var(--bg);color:var(--fg);max-width:720px;margin:0 auto;padding:1em;line-height:1.45}
h2{margin-top:1.6em;border-bottom:2px solid var(--line);padding-bottom:.2em}.ln{background:var(--card);border-radius:10px;padding:.6em .8em;margin:.5em 0}
.sp{font-size:.8em;color:var(--muted);text-transform:uppercase;letter-spacing:.05em}.pt{font-size:1.15em;font-weight:bold}
.heard{color:var(--heard);font-style:italic}.en{color:var(--muted)}a{color:var(--heard)}summary{cursor:pointer;color:var(--muted)}
.nar{font-style:italic;color:var(--muted);margin:.8em 0}textarea{background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:.5em;font-family:inherit}button{margin:.4em 0;padding:.4em 1em;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--fg)}"""


def esc(t):
    return (t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def write_transcript(pack):
    TRANS.mkdir(exist_ok=True)
    b = ['<p><a href="../index.html">← Home</a></p>',
         f'<h1>Pack {pack["pack"]:02d}</h1><p class="en">Purple = how it actually sounds. Tap "English" to check.</p>']
    for e in pack["episodes"]:
        b.append(f'<h2 id="ep{e["ep"]}">Ep {e["ep"]}: {esc(e["title"])}</h2>'
                 + (f'<p><b>🎯 Goal:</b> {esc(e["intro"])}</p>' if e.get("intro") else "")
                 + f'<p><a href="../audio/{ep_file(e)}">▶ Play episode</a> · speed {speed(e["ep"]):+d}%'
                 + (f' · <a href="../decks/ep-{e["ep"]:02d}.apkg">🃏 Anki deck (import after the episode)</a>' if e["ep"] > 0 else "")
                 + '</p>')
        for l in e["lines"]:
            if l["speaker"].lower() == "narrador":
                b.append(f'<div class="nar">{esc(l["pt"])}<details><summary>English</summary>{esc(l["en"])}</details></div>')
            else:
                b.append(f'<div class="ln"><div class="sp">{esc(l["speaker"])}</div><div class="pt">{esc(l["pt"])}</div>'
                         f'<div class="heard">{esc(l.get("heard"))}</div>'
                         f'<details><summary>English</summary><div class="en">{esc(l["en"])}</div></details></div>')
        if e.get("speak"):
            b.append("<h3>🗣️ Your turn — answer out loud</h3>")
            for q in e["speak"]:
                ans = (f'<b>{esc(q["model"])}</b><div class="en">{esc(q.get("model_en"))}</div>' if q.get("model") else "")
                hint = f'<div class="en">💡 {esc(q["hint"])}</div>' if q.get("hint") else ""
                b.append(f'<div class="ln"><div class="sp">{esc(q["speaker"])} asks</div><div class="pt">{esc(q["q"])}</div>'
                         f'<details><summary>English + example answer</summary><div class="en">{esc(q.get("q_en"))}</div>{ans}{hint}</details></div>')
        if e.get("task"):
            b.append(f'<p><b>🎯 Speaking mission:</b> {esc(e["task"])}</p>')
        chars = sorted({l["speaker"] for l in e["lines"]} - {"George", "Narrador"}) or ["Gabi's mum"]
        qlist = " / ".join(q["q"] for q in e.get("speak", []))
        ai = (f"Role-play in Brazilian Portuguese (São Paulo). You play {' and '.join(chars)} from episode {e['ep']} "
              f"of my story, '{e['title']}'. I'm George. Keep it at my level (episode {e['ep']} of 44), 1–2 sentences per turn, "
              f"ask me questions so I do most of the talking, never switch to English. "
              + (f"Start with these questions, then improvise: {qlist}. " if qlist else "")
              + "If I make a mistake, repeat it back correctly in your next line without stopping. "
              "When I say 'fim', give me in English: my 3 biggest errors with corrections, 3 phrases I should have used, and a score out of 10.")
        b.append(f'<details><summary>🎙️ AI voice practice prompt (tap to open, then copy)</summary>'
                 f'<textarea id="ai{e["ep"]}{len(b)}" rows="7" style="width:100%">{esc(ai)}</textarea>'
                 f'<button onclick="navigator.clipboard.writeText(this.previousElementSibling.value);this.textContent=\'Copied ✓\'">Copy</button></details>')
        if e.get("chunks"):
            b.append("<h3>Key phrases</h3><ul>" + "".join(
                f'<li><b>{esc(c["pt"])}</b> <span class="heard">({esc(c.get("heard"))})</span> = {esc(c["en"])}</li>'
                for c in e["chunks"]) + "</ul>")
    if pack.get("talk"):
        b.append('<h2>🗣️ Speaking gym topics</h2><p class="en">Play the Speaking gym episode, or set a timer: talk non-stop, then again faster.</p><ul>'
                 + "".join(f'<li><b>{esc(t["pt"])}</b> <span class="en">({esc(t["en"])})</span></li>' for t in pack["talk"]) + "</ul>")
    if pack.get("drills"):
        b.append('<h2>Drills</h2><details><summary>Show answers</summary><ol>' + "".join(
            f'<li>{esc(d["en"])} → <b>{esc(d["pt"])}</b></li>' for d in pack["drills"]) + "</ol></details>")
    (TRANS / f"pack-{pack['pack']:02d}.html").write_text(
        '<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>Pack {pack["pack"]:02d}</title><style>{TCSS}</style>' + "".join(b), encoding="utf-8")


# ---- Extras (Claude-made bonus audio: packs/extras-*.json) ---------------------------
# {"id": "2026-11-09", "date": "2026-11-09", "title": "...", "intro": "English intro",
#  "items": [{"speaker": "Rafa", "pt": "...", "en": "..."},            -> listen + shadow
#            {"speaker": "Mãe", "pt": "question", "answer": "..."}]}   -> answer drill
def extra_file(x):
    return f"extra-{slug(x['id'])}.mp3"


def extra_audio(x):
    pct = int(x.get("speed", -10))
    out = en(x["title"] + ".") + sil(600)
    if x.get("intro"):
        out += en(x["intro"]) + sil(900)
    for it in x["items"]:
        v, p = voice_for(it.get("speaker", "narrador"))
        line = tts(it["pt"], v, p, rate(pct))
        if it.get("answer"):
            g = say({"speaker": "george", "pt": it["answer"]}, pct)
            out += line + sil(6000) + g + sil(len(g) * 1.2 + 800) + g + sil(1500)
        else:
            out += line + sil(len(line) * 1.2 + 700) + line + sil(1200)
    return out


def build_extras():
    extras = []
    for p in sorted(PACKS.glob("extras-*.json")):
        try:
            x = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"\n❌ {p.name} isn't valid JSON: {e}")
        if not x.get("id") or not x.get("title") or not x.get("items"):
            sys.exit(f"\n❌ {p.name} needs 'id', 'title' and 'items'")
        f = AUDIO / extra_file(x)
        if FORCE or not f.exists():
            export(extra_audio(x), f, x["title"])
            print(f"   🎧 {f.name}")
        extras.append(x)
    return extras


# ---- Feed + index ---------------------------------------------------------------------
def base_url():
    if os.getenv("PAGES_URL"):
        return os.getenv("PAGES_URL").rstrip("/") + "/"
    repo = os.getenv("GITHUB_REPOSITORY")
    if repo:
        owner, name = repo.split("/")
        return f"https://{owner.lower()}.github.io/{name}/"
    return "http://localhost:8000/"


def write_feed_and_index(packs, extras=()):
    url, now = base_url(), datetime.now(timezone.utc)
    fg = FeedGenerator()
    fg.load_extension("podcast")
    fg.title("Projeto SP — São Paulo Sprint")
    fg.link(href=url, rel="alternate")
    fg.description("George's private 44-episode Portuguese story")
    fg.language("pt-BR")
    fg.podcast.itunes_category("Education", "Language Learning")
    fg.podcast.itunes_block(True)
    fg.podcast.itunes_explicit("no")
    eps_html, packs_html = [], []
    for pack in packs:
        write_transcript(pack)
        t = f"transcripts/pack-{pack['pack']:02d}.html"
        items = [(e, ep_file(e), f"Ep {e['ep']:02d} · {e['title']}") for e in pack["episodes"]]
        if pack.get("drills"):
            last = max(e["ep"] for e in pack["episodes"])
            items.append(({"ep": last}, drill_file(pack), f"Pack {pack['pack']:02d} · Drills (ep {pack['episodes'][0]['ep']}–{last})"))
        if pack.get("talk"):
            last = max(e["ep"] for e in pack["episodes"])
            items.append(({"ep": last}, gym_file(pack), f"Pack {pack['pack']:02d} · Speaking gym 🗣️"))
        for k, (e, fname, title) in enumerate(items):
            f = AUDIO / fname
            if not f.exists():
                continue
            when = min(DAY1 + timedelta(days=max(e["ep"], 1) - 1), now - timedelta(hours=1)) + timedelta(minutes=k)
            fe = fg.add_entry()
            fe.id(url + "audio/" + fname)
            fe.title(title)
            fe.description(f"Transcript: {url}{t}")
            fe.enclosure(url + "audio/" + fname, str(f.stat().st_size), "audio/mpeg")
            fe.pubDate(when)
            eps_html.append(f'<li><a href="audio/{fname}">{esc(title)}</a></li>')
        packs_html.append(f'<tr><td>Pack {pack["pack"]:02d}</td><td>Ep {pack["episodes"][0]["ep"]}–{pack["episodes"][-1]["ep"]}</td>'
                          f'<td><a href="{t}">📖 Transcript</a></td><td>' + " ".join(
                              f'<a href="decks/{f}">🃏 {"Deck" if pack["pack"] == 0 else "Ep " + f[3:5]}</a>'
                              for f, *_ in deck_files(pack) if (DECKS / f).exists()) + "</td></tr>")
    extras_html = []
    for k, x in enumerate(extras):
        f = AUDIO / extra_file(x)
        if not f.exists():
            continue
        try:
            when = datetime.fromisoformat(x.get("date", "")).replace(hour=7, tzinfo=timezone.utc)
        except ValueError:
            when = now - timedelta(hours=1)
        when = min(when, now - timedelta(hours=1)) + timedelta(minutes=k)
        fe = fg.add_entry()
        fe.id(url + "audio/" + f.name)
        fe.title("⭐ " + x["title"])
        fe.description(x.get("intro", "Bonus audio"))
        fe.enclosure(url + "audio/" + f.name, str(f.stat().st_size), "audio/mpeg")
        fe.pubDate(when)
        extras_html.append(f'<li><a href="audio/{f.name}">⭐ {esc(x["title"])}</a></li>')
    fg.rss_file(str(DOCS / "feed.xml"), pretty=True)
    (DOCS / "index.html").write_text(f"""<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Projeto SP</title><style>{TCSS}
table{{border-collapse:collapse;width:100%}}td{{padding:.4em;border-bottom:1px solid var(--line)}}code{{background:var(--card);padding:2px 6px;border-radius:4px;word-break:break-all}}</style>
<h1>Projeto SP 🇧🇷</h1><p>Podcast feed:<br><code>{url}feed.xml</code></p>
<h2>Packs</h2><table>{''.join(reversed(packs_html))}</table>
<h2>⭐ Extras</h2><ul>{''.join(reversed(extras_html)) or '<li>None yet</li>'}</ul>
<h2>Episodes</h2><ul>{''.join(reversed(eps_html))}</ul>""", encoding="utf-8")
    (DOCS / ".nojekyll").write_text("")


# ---- Main -----------------------------------------------------------------------------
def main():
    for d in (AUDIO, DECKS):
        d.mkdir(parents=True, exist_ok=True)
    packs = []
    for p in sorted(PACKS.glob("*.json")):
        if p.name.startswith("extras-"):
            continue
        try:
            pack = json.loads(p.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            sys.exit(f"\n❌ {p.name} isn't valid JSON: {e}\nTip: copy Claude's whole reply, from the first {{ to the last }}.")
        validate(pack, p.name)
        packs.append(pack)
    packs.sort(key=lambda x: x["pack"])
    for pack in packs:
        files = [ep_file(e) for e in pack["episodes"]] + ([drill_file(pack)] if pack.get("drills") else []) \
            + ([gym_file(pack)] if pack.get("talk") else [])
        decks = deck_files(pack)
        if not FORCE and all((DECKS / d[0]).exists() for d in decks) and all((AUDIO / f).exists() for f in files):
            print(f"✓ Pack {pack['pack']:02d} already built — skipping")
            continue
        print(f"▶ Building pack {pack['pack']:02d}")
        for e in pack["episodes"]:
            export(episode_audio(e), AUDIO / ep_file(e), f"Ep {e['ep']:02d} · {e['title']}")
            print(f"   🎧 {ep_file(e)} (speed {speed(e['ep']):+d}%)")
        if pack.get("drills"):
            export(drill_audio(pack), AUDIO / drill_file(pack), f"Pack {pack['pack']:02d} · Drills")
            print(f"   🎧 {drill_file(pack)}")
        if pack.get("talk"):
            export(speaking_gym_audio(pack), AUDIO / gym_file(pack), f"Pack {pack['pack']:02d} · Speaking gym")
            print(f"   🎧 {gym_file(pack)}")
        for fname, eps_, did, name in decks:
            print(f"   🃏 {fname} ({build_deck(pack, DECKS / fname, eps_, did, name)} notes)")
    extras = build_extras()
    write_feed_and_index(packs, extras)
    print(f"\n✅ Done. Home: {base_url()}")


if __name__ == "__main__":
    main()
