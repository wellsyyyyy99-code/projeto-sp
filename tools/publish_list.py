#!/usr/bin/env python3
"""
Which Treino app files differ from what was last published to the artifact?

  python3 tools/publish_list.py          prints {"files": [{"as", "path"}, ...], "remove": ["as", ...]}
  python3 tools/publish_list.py --mark   records the current files as published (run after a successful publish)

Pass "files" (and "remove", if not empty) straight to publish_files with mode "patch".
The record lives in treino/published.json.
"""
import hashlib, json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REC = ROOT / "treino" / "published.json"


def current():
    files = {"index.html": ROOT / "treino" / "index.html"}
    for sub in ("data", "b"):
        d = ROOT / "docs" / "treino" / sub
        if d.exists():
            for p in sorted(d.iterdir()):
                if p.is_file() and p.suffix in (".json", ".mp3"):
                    files[f"{sub}/{p.name}"] = p
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
    out = {"files": [{"as": k, "path": str(files[k])} for k in now if old.get(k) != now[k]],
           "remove": [k for k in old if k not in now]}
    print(json.dumps(out))


if __name__ == "__main__":
    main()
