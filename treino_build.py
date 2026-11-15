#!/usr/bin/env python3
"""
Treino data + audio clips for the Treino speaking app.

Reads packs/*.json and curriculum/situations.json and writes into docs/treino/:
  data/cards.json   every drill card (speaking core, episode chunks, drills, "your turn" answers)
  data/eps.json     every episode's lines and questions (fast-listening round)
  data/sits.json    the 15 must-win situations
  a/<id>.mp3        one short clip per Portuguese line (id = FNV-1a of the text); the build's cache
  b/<group>-<n>.mp3 the same clips joined into bundles of about 400 KB (an artifact holds at most
                    512 files, so the app loads bundles, not single clips)
  b/index.json      {"bundles": [names], "clips": {id: [bundle number, byte offset, byte length]}}

`python treino_build.py` writes the data files only (no voices needed).
build.py calls build(tts_path, voice_for) to add the clips.
"""
import json, shutil
from pathlib import Path

ROOT = Path(__file__).parent
PACKS = ROOT / "packs"
OUT = ROOT / "docs" / "treino"
SITS = ROOT / "curriculum" / "situations.json"


def _slug(t):
    """Same as build.py's slug(): the episode's audio file name."""
    import re, unicodedata
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:40]


def fnv(s):
    """FNV-1a 32-bit of the trimmed text. The app computes the same id in JS."""
    h = 0x811C9DC5
    for b in s.strip().encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return f"{h:08x}"


def _load(p):
    return json.loads(p.read_text(encoding="utf-8"))


BONUS = []
DEFAULT_EXAM = [
    "Se apresenta pra mim: quem é você, onde cê mora e com o que cê trabalha?",
    "Me conta como foi a sua semana. O que cê fez?",
    "Como você e a Gabi se conheceram?",
    "Quais são os seus planos pra viagem pro Brasil?",
    "O que cê acha mais difícil no português, e por quê?",
]


def collect():
    """Returns (cards, eps, clips). clips = {id: (text, speaker)}."""
    cards, seen, eps, clips = [], set(), [], {}
    grp = ["core"]          # bundle group of whatever is being collected right now

    def clip(text, speaker):
        if text and text.strip():
            clips.setdefault(fnv(text), (text.strip(), speaker, grp[0]))

    def card(c):
        cid = "c" + fnv(c["pt"])
        if cid in seen:
            return
        seen.add(cid)
        c["id"] = cid
        cards.append({k: v for k, v in c.items() if v not in (None, "", [])})
        if c.get("mode") != "open":       # an open card's pt is a hint, partly English
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
        grp[0] = f"p{int(pack.get('pack', 0)):02d}"
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
            fn = f"ep{ep:02d}-{_slug(e.get('title', ''))}.mp3"
            eps.append({"ep": ep, "title": e.get("title", ""), "pack": pack.get("pack"), "intro": e.get("intro", ""),
                        "task": e.get("task", ""), "audio": fn if (ROOT / "docs" / "audio" / fn).exists() else "",
                        "chunks": [{"pt": c.get("pt"), "en": c.get("en"), "heard": c.get("heard"), "note": c.get("note")}
                                   for c in e.get("chunks", [])],
                        "lines": lines,
                        "speak": [{"s": q.get("speaker"), "q": q.get("q"), "qen": q.get("q_en"),
                                   "model": q.get("model"), "hint": q.get("hint")} for q in e.get("speak", [])]})
        if first >= 1:
            for d in pack.get("drills", []):
                card({"k": "drill", "ep": first, "en": d["en"], "pt": d["pt"]})

    daily = PACKS / "treino-daily.json"
    if daily.exists():
        grp[0] = "d"
        try:
            dd = _load(daily)
        except json.JSONDecodeError:
            dd = {}
        for day in dd.get("days", []):
            r = day.get("rafa") or {}
            for l in r.get("lines", []):
                clip(l.get("pt"), "rafa")
            clip((r.get("q") or {}).get("pt"), "rafa")
            clip((day.get("diario") or {}).get("pt"), "narrador")
            for t in day.get("exam", []):
                clip(t.get("pt"), t.get("who") or "mãe")

    grp[0] = "x"
    for q in DEFAULT_EXAM:
        clip(q, "mãe")
    bonus = []
    for bp in sorted(PACKS.glob("extras-*.json")):
        try:
            x = _load(bp)
        except json.JSONDecodeError:
            continue
        aud = sorted((ROOT / "docs" / "audio").glob(f"extra-{_slug(str(x.get('id', '')))}*.mp3"))
        items = []
        for it in x.get("items", []):
            clip(it.get("pt"), it.get("speaker", "rafa"))
            clip(it.get("answer"), "george")
            items.append({k: it[k] for k in ("speaker", "pt", "en", "answer", "answer_en") if it.get(k)})
        bonus.append({"id": x.get("id"), "date": x.get("date", ""), "title": x.get("title", ""), "intro": x.get("intro", ""),
                      "audio": aud[0].name if aud else "", "items": items})
    BONUS[:] = bonus
    if SITS.exists():
        for st in _load(SITS).get("situations", []):
            clip(st.get("open", {}).get("pt"), st.get("char", "rafa"))
            for m in st.get("must", []):
                clip(m.get("pt"), "george")

    # cards brought over from Anki (episode lines to listen to, Pack 00 sound rules, answer-aloud)
    ak = PACKS / "anki-cards.json"
    if ak.exists():
        grp[0] = "x"
        for c in _load(ak).get("cards", []):
            clip(c.get("pt"), (c.get("who") or "narrador") if c.get("mode") == "listen" else "george")
            card({"k": "anki", "mode": c.get("mode"), "en": c.get("en", ""), "pt": c["pt"], "heard": c.get("heard"),
                  "who": c.get("who"), "q": c.get("q"), "qen": c.get("qen"), "note": c.get("note")})

    # cards the Coach adds (mistakes and pattern drills live in the app's database;
    # this file only exists so their audio gets built)
    extra = PACKS / "treino-cards.json"
    if extra.exists():
        for c in _load(extra).get("cards", []):
            clip(c.get("pt"), "george")
            clip(c.get("q"), c.get("qs") or "rafa")

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
    (d / "bonus.json").write_text(dump(BONUS), encoding="utf-8")
    meta = ROOT / "curriculum" / "episodes.json"
    if meta.exists():
        (d / "meta.json").write_text(dump(_load(meta)), encoding="utf-8")
    return cards, eps, clips


def build(tts_path, voice_for):
    """Called by build.py: data files + any missing clips."""
    cards, eps, clips = write_data()
    a = OUT / "a"
    a.mkdir(parents=True, exist_ok=True)
    todo = [(cid, t, sp) for cid, (t, sp, _g) in sorted(clips.items())
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
    n = bundle(clips)
    print(f"🥊 Treino: {len(cards)} cards, {len(eps)} episodes, {made} new clips, {n} bundles")


BUNDLE_BYTES = 400_000


def bundle(clips):
    """Join the clips of each group, in the order they were collected, into ~400 KB bundles."""
    a, b = OUT / "a", OUT / "b"
    b.mkdir(parents=True, exist_ok=True)
    groups = {}
    for cid, (_t, _sp, g) in clips.items():
        f = a / f"{cid}.mp3"
        if f.exists() and f.stat().st_size > 0:
            groups.setdefault(g, []).append(cid)
    names, index, keep = [], {}, set()
    for g, ids in groups.items():
        k, buf = 0, bytearray()

        def flush():
            nonlocal k, buf
            if buf:
                (b / f"{g}-{k}.mp3").write_bytes(bytes(buf))
                keep.add(f"{g}-{k}.mp3")
                k, buf = k + 1, bytearray()

        for cid in ids:
            data = (a / f"{cid}.mp3").read_bytes()
            if buf and len(buf) + len(data) > BUNDLE_BYTES:
                flush()
            if not buf:
                names.append(f"{g}-{k}")
            index[cid] = [len(names) - 1, len(buf), len(data)]
            buf += data
        flush()
    for old in b.glob("*.mp3"):
        if old.name not in keep:
            old.unlink()
    (b / "index.json").write_text(json.dumps({"bundles": names, "clips": index}, separators=(",", ":")), encoding="utf-8")
    old_index = a / "index.json"
    if old_index.exists():
        old_index.unlink()
    return len(names)

if __name__ == "__main__":
    c, e, k = write_data()
    print(f"{len(c)} cards, {len(e)} episodes, {len(k)} clip texts, {bundle(k)} bundles")
