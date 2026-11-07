#!/usr/bin/env python3
"""sync_claude.py - keep the project-local .claude/ copies in step with skills/ and templates/.

    python3 scripts/sync_claude.py            # copy what changed, remove what is gone
    python3 scripts/sync_claude.py --check    # change nothing; exit 1 if anything is out of sync
    python3 scripts/sync_claude.py --voice    # also overwrite .claude/youtube/voice.md

skills/yt-* is the source of truth. Each folder is mirrored into .claude/skills/: new and changed
files are copied, files that no longer exist in the source are deleted, and a .claude/skills/yt-*
folder whose source was removed is deleted too. Folders in .claude/skills/ that do not start with
yt- are yours and are never touched.

voice.md is different. The template is meant to be filled in, so .claude/youtube/voice.md is only
created when it is missing. If it differs from templates/voice.md it is left alone and reported;
pass --voice to overwrite it with the template.

Plain Python 3, no dependencies.
"""
import argparse, filecmp, shutil, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SKILLS_SRC = ROOT / "skills"
SKILLS_DST = ROOT / ".claude" / "skills"
VOICE_SRC = ROOT / "templates" / "voice.md"
VOICE_DST = ROOT / ".claude" / "youtube" / "voice.md"
IGNORE = {"__pycache__", ".DS_Store"}


def ignored(path):
    return path.suffix == ".pyc" or any(part in IGNORE for part in path.parts)


def files_under(folder):
    """Relative paths of every file under folder, skipping caches."""
    if not folder.is_dir():
        return set()
    return {p.relative_to(folder) for p in folder.rglob("*")
            if p.is_file() and not ignored(p.relative_to(folder))}


def plan():
    """Every action needed to bring .claude/ in line, as (verb, target, source-or-None)."""
    actions = []
    sources = {d.name: d for d in sorted(SKILLS_SRC.glob("yt-*")) if d.is_dir()}

    for name, src in sources.items():
        dst = SKILLS_DST / name
        want, have = files_under(src), files_under(dst)
        for rel in sorted(want):
            if rel not in have:
                actions.append(("add", dst / rel, src / rel))
            elif not filecmp.cmp(src / rel, dst / rel, shallow=False):
                actions.append(("update", dst / rel, src / rel))
        for rel in sorted(have - want):
            actions.append(("delete", dst / rel, None))

    for dst in sorted(SKILLS_DST.glob("yt-*")):
        if dst.is_dir() and dst.name not in sources:
            actions.append(("delete-dir", dst, None))

    return actions


def voice_state():
    if not VOICE_SRC.is_file():
        return "no-template"
    if not VOICE_DST.exists():
        return "missing"
    return "same" if filecmp.cmp(VOICE_SRC, VOICE_DST, shallow=False) else "differs"


def rel(path):
    return path.relative_to(ROOT).as_posix()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true",
                    help="change nothing; exit 1 if .claude/ is out of sync")
    ap.add_argument("--voice", action="store_true",
                    help="overwrite .claude/youtube/voice.md with templates/voice.md")
    args = ap.parse_args()

    if not SKILLS_SRC.is_dir():
        sys.exit(f"no skills/ folder at {SKILLS_SRC}")

    actions = plan()
    voice = voice_state()
    if voice == "missing" or (voice == "differs" and args.voice):
        actions.append(("update" if voice == "differs" else "add", VOICE_DST, VOICE_SRC))

    for verb, target, _ in actions:
        print(f"{'would ' + verb if args.check else verb:>16}  {rel(target)}")
    if voice == "differs" and not args.voice:
        print(f"{'kept':>16}  {rel(VOICE_DST)} (differs from the template; --voice overwrites it)")
    if voice == "no-template":
        print(f"{'skipped':>16}  {rel(VOICE_SRC)} not found")

    if args.check:
        if actions:
            print(f"\n{len(actions)} change(s) needed. Run: python3 scripts/sync_claude.py")
            return 1
        print(".claude/ is in sync.")
        return 0

    for verb, target, source in actions:
        if verb == "delete":
            target.unlink()
        elif verb == "delete-dir":
            shutil.rmtree(target)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    # Folders left empty by deletions inside a mirrored skill.
    folders = [p for d in SKILLS_DST.glob("yt-*") for p in (d, *d.rglob("*")) if p.is_dir()]
    for folder in sorted(folders, key=lambda p: len(p.parts), reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir()

    print(f"\n{len(actions)} change(s) made." if actions else ".claude/ is already in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
