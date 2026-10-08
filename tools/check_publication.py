"""Check local README links and equivalent executable examples in both languages."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def check() -> int:
    english = (ROOT / "README.md").read_text(encoding="utf-8")
    chinese = (ROOT / "README.zh-CN.md").read_text(encoding="utf-8")
    command = re.compile(r"^(?:python |git clone |cd |source |\.\\\.venv).*", re.MULTILINE)
    if command.findall(english) != command.findall(chinese):
        raise ValueError("The bilingual executable examples differ")
    for value in ("3.11.9", "836", "576", "180", "0.26775524691778746",
                  "0.10416666666666666", "0.015625", "0.00390625"):
        if value not in english or value not in chinese:
            raise ValueError(f"A bilingual version is missing the shared value {value}")
    count = 0
    for document in (ROOT / "README.md", ROOT / "README.zh-CN.md", *sorted((ROOT / "docs").glob("*.md"))):
        text = document.read_text(encoding="utf-8")
        for target in re.findall(r"\[[^\]]*\]\(([^)]+)\)", text):
            target = target.strip("<>").split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            if not (document.parent / target).exists():
                raise ValueError(f"Broken local link in {document.name}: {target}")
            count += 1
    print(f"Documentation PASS: {count} local links and bilingual commands/results.")
    return count


if __name__ == "__main__":
    check()
