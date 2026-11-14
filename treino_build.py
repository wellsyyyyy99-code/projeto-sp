#!/usr/bin/env python3
"""
Treino data + audio clips for the Treino speaking app.

Reads packs/*.json and curriculum/situations.json and writes into docs/treino/:
  data/cards.json   every drill card (speaking core, episode chunks, drills, "your turn" answers)
  data/eps.json     every episode's lines and questions (fast-listening round)
  data/sits.json    the 15 must-win situations
  a/<id>.mp3        one short clip per Portuguese line (id = FNV-1a of the text)
  a/index.json      list of clip ids that exist

`python treino_build.py` writes the data files only (no voices needed).
build.py calls build(tts_path, voice_for) to add the clips.
"""
import json, shutil
from pathlib import Path

ROOT = Path(__file__).parent
PACKS = ROOT / "packs"
OUT = ROOT / "docs" / "treino"
SITS = ROOT / "curriculum" / "situations.json"


def fnv(s):
    """FNV-1a 32-bit of the trimmed text. The app computes the same id in JS."""
    h = 0x811C9DC5
    for b in s.strip().encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def _load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def collect():
    """Returns (cards, eps, clips). clips = {id: (text, speaker)}."""
    cards, seen, eps, clips = [], set(), [], {}

    def clip(text, speaker):
        if text and text.strip():
            clips.setdefault(fnv(text), (text.strip(), speaker))

    def card(c):
        cid = "c" + fnv(c["pt"])
        if cid in seen:
            return
        seen.add(cid)
        c["id"] = cid
        cards.append({k: v for k, v in c.items() if v not in (None, "", [])})
        clip(c["pt"], "george")
        if c.get("q"):
            clip(c["q"], c.get("qs") or "rafa")

    for p in sorted(PACKS.glob("speaking-*.json")):
        for c in _load(p).get("cards", []):
            card({"k": "core", "topic": c.get("topic"), "en": c["en"], "pt": c["pt"], "heard": c.get("heard"),
                  "q": c.get("q"), "qs": c.get("q_speaker"), "frame": c.get("frame")})

    packs = []
    for p in sorted(PACKS.glob("pack-*.json")):
        try:
            packs.append(_load(p))
        except json.JSONDecodeError:
            continue
    packs.sort(key=lambda x: x.get("pack", 0))
    for pack in packs:
        first = min([e["ep"] for e in pack.get("episodes", []) if isinstance(e.get("ep"), int)] or [0])
        for e in pack.get("episodes", []):
            ep = e.get("ep", 0)
            if ep < 1:      # pack 0 = sound rules, not story
                continue
            for c in e.get("chunks", []):
                card({"k": "chunk", "ep": ep, "en": c["en"], "pt": c["pt"], "heard": c.get("heard"), "note": c.get("note")})
            for q in e.get("speak", []):
                clip(q.get("q"), q.get("speaker", "rafa"))
                if q.get("model"):
                    card({"k": "speak", "ep": ep, "en": q.get("model_en") or q.get("q_en", ""), "pt": q["model"],
                          "q": q["q"], "qs": q.get("speaker"), "qen": q.get("q_en")})
            lines = []
            for l in e.get("lines", []):
                clip(l["pt"], l["speaker"])
                lines.append({"s": l["speaker"], "pt": l["pt"], "en": l["en"], "heard": l.get("heard")})
            eps.append({"ep": ep, "title": e.get("title", ""), "lines": lines,
                        "speak": [{"s": q.get("speaker"), "q": q.get("q"), "qen": q.get("q_en"),
                                   "model": q.get("model"), "hint": q.get("hint")} for q in e.get("speak", [])]})
        if first >= 1:
            for d in pack.get("drills", []):
                card({"k": "drill", "ep": first, "en": d["en"], "pt": d["pt"]})

    # cards the Coach adds (mistakes and pattern drills live in the app's database;
    # this file only exists so their audio gets built)
    extra = PACKS / "treino-cards.json"
    if extra.exists():
        for c in _load(extra).get("cards", []):
            clip(c.get("pt"), "george")
            clip(c.get("q"), c.get("qs") or "rafa")

    if SITS.exists():
        for s in _load(SITS).get("situations", []):
            clip(s.get("open", {}).get("pt"), s.get("char", "rafa"))
            for m in s.get("must", []):
                clip(m.get("pt"), "george")

    eps.sort(key=lambda x: x["ep"])
    return cards, eps, clips


def write_data():
    cards, eps, clips = collect()
    d = OUT / "data"
    d.mkdir(parents=True, exist_ok=True)
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":"))
    (d / "cards.json").write_text(dump(cards), encoding="utf-8")
    (d / "eps.json").write_text(dump(eps), encoding="utf-8")
    if SITS.exists():
        (d / "sits.json").write_text(dump(_load(SITS)), encoding="utf-8")
    return cards, eps, clips


def build(tts_path, voice_for):
    """Called by build.py: data files + any missing clips."""
    cards, eps, clips = write_data()
    a = OUT / "a"
    a.mkdir(parents=True, exist_ok=True)
    todo = [(cid, t, sp) for cid, (t, sp) in sorted(clips.items())
            if not ((a / f"{cid}.mp3").exists() and (a / f"{cid}.mp3").stat().st_size > 0)]

    def one(job):
        cid, text, speaker = job
        v, pitch = voice_for(speaker)
        try:
            shutil.copyfile(tts_path(text, v, pitch, "+0%"), a / f"{cid}.mp3")
            return 1
        except Exception as e:      # one bad line must not break the podcast build
            print(f"   ⚠️ clip skipped ({text[:40]!r}): {e}")
            return 0

    for job in todo[:1]:            # first one alone, so voice_for's cache is warm
        one(job)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=5) as ex:
        made = sum(ex.map(one, todo[1:])) + (1 if todo else 0)
    have = sorted(p.stem for p in a.glob("*.mp3") if p.stat().st_size > 0)
    (a / "index.json").write_text(json.dumps(have), encoding="utf-8")
    print(f"🥊 Treino: {len(cards)} cards, {len(eps)} episodes, {made} new clips ({len(have)} total)")


if __name__ == "__main__":
    c, e, k = write_data()
    print(f"{len(c)} cards, {len(e)} episodes, {len(k)} clip texts")
