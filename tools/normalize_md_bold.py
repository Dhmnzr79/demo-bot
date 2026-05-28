#!/usr/bin/env python3
"""Нормализация **жирного** в md/: только цифры, сроки, Этап N, пожизненн*.

Использование: python tools/normalize_md_bold.py [--write]
Без --write — только diff-preview (печатает изменённые файлы).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MD_DIR = ROOT / "md"

BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")


def _b(s: str) -> str:
    return f"**{s}**"


def strip_bold(text: str) -> str:
    return BOLD_RE.sub(r"\1", text)


def _dedupe_nested_bold(text: str) -> str:
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\*\*(\*\*[^*]+\*\*)\*\*", r"\1", text)
        text = text.replace("****", "")
    return text


def normalize_bold_in_line(line: str) -> str:
    plain = strip_bold(line)
    if "**" in plain:
        plain = strip_bold(plain)
    if not plain.strip():
        return plain

    t = plain

    t = re.sub(r"\b(Этап\s+\d+)\b", lambda m: _b(m.group(1)), t)
    t = re.sub(r"\b(пожизненн\w*)\b", lambda m: _b(m.group(1)), t, flags=re.IGNORECASE)

    t = re.sub(r"(\d[\d\s]*₽)", lambda m: _b(m.group(1)), t)
    t = re.sub(r"(\d+(?:[.,]\d+)?\s*%)", lambda m: _b(m.group(1)), t)

    duration = (
        r"лет|года|год|месяцев|месяца|месяц|дней|дня|день|дню|"
        r"недель|недели|неделю|минут|минуты|часов|часа|час|"
        r"параметров|визита|визитов|суток"
    )
    # Диапазоны целиком — до одиночных «N месяцев», иначе ломается «3–6» → «3–**6**».
    t = re.sub(rf"(\d+(?:[–\-]\d+)?\s*(?:{duration}))", lambda m: _b(m.group(1)), t)
    t = re.sub(r"(\d+\+\s*лет)", lambda m: _b(m.group(1)), t)
    t = re.sub(r"\b(за\s+\d+\s+день)\b", lambda m: _b(m.group(1)), t)
    t = re.sub(
        r"\b(более|около|до)\s+(\d+(?:[–\-]\d+)?\s*(?:лет|года|год|месяцев|месяца|месяц))\b",
        lambda m: f"{m.group(1)} {_b(m.group(2))}",
        t,
    )
    t = re.sub(
        r"\bот\s+(\d+)\s+до\s+(\d+)\s+(лет)\b",
        lambda m: f"от {_b(m.group(1))} до {_b(m.group(2))} {m.group(3)}",
        t,
    )
    t = re.sub(
        rf"(?<![–\-])\b(\d+\s+(?:{duration}))\b",
        lambda m: _b(m.group(1)),
        t,
    )

    t = re.sub(
        r"\b(\d+)\s+(имплант(?:ов|ах|а)?)\b",
        lambda m: f"{_b(m.group(1))} {m.group(2)}",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(
        r"\b(\d+)\s+(ведущих|параметр\w*)\b",
        lambda m: f"{_b(m.group(1))} {m.group(2)}",
        t,
        flags=re.IGNORECASE,
    )
    t = re.sub(r"\b(\d+\s+час(?:а|ов)?)\b", lambda m: _b(m.group(1)), t)
    t = re.sub(r"(\d{2}:\d{2}[–\-]\d{2}:\d{2})", lambda m: _b(m.group(1)), t)

    return _dedupe_nested_bold(t)


def process_file(path: Path, *, write: bool) -> bool:
    original = path.read_text(encoding="utf-8-sig")
    lines = original.splitlines(keepends=True)
    new_lines: list[str] = []
    changed = False
    fm_dashes = 0
    in_fm = False

    for line in lines:
        stripped = line.strip()
        if stripped == "---":
            fm_dashes += 1
            in_fm = fm_dashes == 1
            new_lines.append(line)
            continue
        if in_fm and fm_dashes < 2:
            new_lines.append(line)
            continue
        if fm_dashes >= 2:
            in_fm = False

        new_line = normalize_bold_in_line(line)
        new_lines.append(new_line)
        if new_line != line:
            changed = True

    if not changed:
        return False
    if write:
        path.write_text("".join(new_lines), encoding="utf-8", newline="\n")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="Записать изменения в файлы")
    args = ap.parse_args()

    paths = sorted(MD_DIR.rglob("*.md"))
    changed_files: list[Path] = []
    for p in paths:
        if process_file(p, write=args.write):
            changed_files.append(p)

    for p in changed_files:
        print(p.relative_to(ROOT))
    print(f"\n{'Updated' if args.write else 'Would update'}: {len(changed_files)} / {len(paths)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
