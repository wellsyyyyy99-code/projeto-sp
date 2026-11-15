#!/usr/bin/env python3
"""
Which Treino app files differ from what was last published to the artifact?

  python3 tools/publish_list.py          prints {"batches": [[{"as", "path"}, ...], ...], "remove": ["as", ...]}
  python3 tools/publish_list.py --mark   records the current files as published (run after every batch went through)

Publish each batch with its own publish_files call (mode "patch"); put "remove" on the first call if it is not empty.
A batch stays under 200 files and 50 MB, inside the tool's limits.

Full episode audio is heavy (about 7 MB each), so the app only holds a window of it: from 3 days before today's
episode to 3 days after. Older episodes stay playable line by line, and complete in the podcast feed.
The record lives in treino/published.json.
"""
import datetime as dt, hashlib, json, sys
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
REC = ROOT / "treino" / "published.json"
START = dt.date(2026, 11, 1)
MAX_FILES, MAX_BYTES = 200, 50_000_000


def day_number():
    return (dt.datetime.now(ZoneInfo("Europe/London")).date() - START).days + 1


def current():
    files = {"index.html": ROOT / "treino" / "index.html"}
    for sub in ("data", "b"):
        d = ROOT / "docs" / "treino" / sub
        if d.exists():
            for p in sorted(d.iterdir()):
                if p.is_file() and p.suffix in (".json", ".mp3"):
                    files[f"{sub}/{p.name}"] = p
    eps = ROOT / "docs" / "treino" / "data" / "eps.json"
    if eps.exists():
        n = day_number()
        for e in json.loads(eps.read_text(encoding="utf-8")):
            f = ROOT / "docs" / "audio" / (e.get("audio") or "-")
            if e.get("audio") and n - 3 <= e["ep"] <= n + 3 and f.exists():
                files[f"ep/{e['audio']}"] = f
    bonus = ROOT / "docs" / "treino" / "data" / "bonus.json"
    if bonus.exists():
        for b in json.loads(bonus.read_text(encoding="utf-8"))[-2:]:
            f = ROOT / "docs" / "audio" / (b.get("audio") or "-")
            if b.get("audio") and f.exists():
                files[f"bonus/{b['audio']}"] = f
    return files


def sha(p):
    return hashlib.sha1(p.read_bytes()).hexdigest()


def main():
    files = current()
    now = {k: sha(p) for k, p in files.items()}
    if "--mark" in sys.argv:
        REC.write_text(json.dumps(now, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        print(f"recorded {len(now)} files")
        return
    old = json.loads(REC.read_text(encoding="utf-8")) if REC.exists() else {}
    todo = [k for k in now if old.get(k) != now[k]]
    batches, cur, size = [], [], 0
    for k in todo:
        b = files[k].stat().st_size
        if cur and (len(cur) >= MAX_FILES or size + b > MAX_BYTES):
            batches.append(cur)
            cur, size = [], 0
        cur.append({"as": k, "path": str(files[k])})
        size += b
    if cur:
        batches.append(cur)
    print(json.dumps({"batches": batches, "remove": [k for k in old if k not in now]}))


if __name__ == "__main__":
    main()
