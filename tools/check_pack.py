#!/usr/bin/env python3
"""
Check a pack before pushing it:  python3 tools/check_pack.py packs/pack-05.json
Exits 1 and lists every problem. Same rules as build.py's validate(), plus the master prompt's shape rules.
"""
import json, re, sys
from pathlib import Path

SPEAKERS = {"george", "gabi", "mãe", "ana", "rafa", "bia", "seu zé", "narrador", "barista", "atendente", "vendedor",
            "garçom", "motorista", "passageiro", "farmacêutico", "estranho", "torcedor"}
EUROPEAN = [r"\btu\b", r"\bestás\b", r"\btelemóvel\b", r"\bautocarro\b", r"\bcomboio\b", r"\bpequeno-almoço\b", r"\bfixe\b", r"\bestou a \w+r\b"]


def check(path):
    errs, warns = [], []
    try:
        p = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception as e:
        return [f"not valid JSON: {e}"], []
    if not isinstance(p.get("pack"), int):
        errs.append('"pack" must be a number')
    m = re.search(r"pack-(\d+)\.json$", str(path))
    if m and isinstance(p.get("pack"), int) and int(m.group(1)) != p["pack"]:
        errs.append(f'file name says pack {int(m.group(1))} but "pack" is {p["pack"]}')
    eps = p.get("episodes", [])
    if not 3 <= len(eps) <= 5:
        errs.append(f"{len(eps)} episodes (expected 3 to 5)")
    nums = [e.get("ep") for e in eps]
    if nums != sorted(nums) or len(set(nums)) != len(nums):
        errs.append(f"episode numbers out of order or repeated: {nums}")
    for e in eps:
        tag = f"ep {e.get('ep')}"
        if not isinstance(e.get("ep"), int):
            errs.append(f"{tag}: 'ep' must be a number")
        for f in ("title", "intro", "lines", "chunks", "speak", "task"):
            if not e.get(f):
                errs.append(f"{tag}: missing {f!r}")
        lines = e.get("lines", [])
        if not 10 <= len(lines) <= 16:
            errs.append(f"{tag}: {len(lines)} lines (need 11 to 14)")
        elif not 11 <= len(lines) <= 14:
            warns.append(f"{tag}: {len(lines)} lines (aim for 11 to 14)")
        g = sum(1 for l in lines if str(l.get("speaker", "")).lower() == "george")
        if lines and not 0.25 <= g / len(lines) <= 0.55:
            warns.append(f"{tag}: George has {g} of {len(lines)} lines (aim for about 40%)")
        for j, l in enumerate(lines, 1):
            for f in ("speaker", "pt", "heard", "en"):
                if not l.get(f):
                    errs.append(f"{tag} line {j}: missing {f!r}")
            if str(l.get("speaker", "")).lower() not in SPEAKERS:
                errs.append(f"{tag} line {j}: unknown speaker {l.get('speaker')!r}")
            if "kkk" in str(l.get("pt", "")).lower():
                errs.append(f"{tag} line {j}: written laughter is read aloud; remove it")
            for pat in EUROPEAN:
                if re.search(pat, str(l.get("pt", "")).lower()):
                    warns.append(f"{tag} line {j}: looks European ({pat}): {l.get('pt')!r}")
        if len(e.get("chunks", [])) != 5:
            errs.append(f"{tag}: {len(e.get('chunks', []))} chunks (need 5)")
        for j, c in enumerate(e.get("chunks", []), 1):
            if not c.get("pt") or not c.get("en"):
                errs.append(f"{tag} chunk {j}: needs 'pt' and 'en'")
            if len(str(c.get("note", "")).split()) > 12:
                warns.append(f"{tag} chunk {j}: note is over 12 words")
        if len(e.get("speak", [])) != 4:
            errs.append(f"{tag}: {len(e.get('speak', []))} speak questions (need 4)")
        for j, q in enumerate(e.get("speak", []), 1):
            if not q.get("speaker") or not q.get("q") or not (q.get("model") or q.get("hint")):
                errs.append(f"{tag} speak {j}: needs 'speaker', 'q' and 'model' or 'hint'")
    d = p.get("drills", [])
    if not 25 <= len(d) <= 30:
        errs.append(f"{len(d)} drills (need 25 to 30)")
    for j, x in enumerate(d, 1):
        if not x.get("en") or not x.get("pt"):
            errs.append(f"drill {j}: needs 'en' and 'pt'")
    t = p.get("talk", [])
    if len(t) != 3:
        errs.append(f"{len(t)} talk topics (need 3)")
    for j, x in enumerate(t, 1):
        if not x.get("en") or not x.get("pt"):
            errs.append(f"talk topic {j}: needs 'en' and 'pt'")
    return errs, warns


if __name__ == "__main__":
    bad = False
    for path in sys.argv[1:]:
        errs, warns = check(path)
        for w in warns:
            print(f"⚠️  {path}: {w}")
        for e in errs:
            print(f"❌ {path}: {e}")
        if errs:
            bad = True
        else:
            print(f"✅ {path}: OK")
    sys.exit(1 if bad else 0)
