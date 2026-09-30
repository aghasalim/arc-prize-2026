"""Every number in paper/PAPER.md must also appear in a source the other checks
already verify: the README, the methods notes or the split statistics."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
paper = (ROOT / "paper" / "PAPER.md").read_text().split("## References")[0]
paper = re.sub(r"^#+ .*$", "", paper, flags=re.M)  # section numbers are not claims
sources = "".join((ROOT / f).read_text() for f in ("README.md", "notes/METHODS.md", "reports/split_stats.csv"))
nums = set(re.findall(r"(?<![\w.])\d[\d,]*(?:\.\d+)?%?", paper))
small = {str(i) for i in range(10)}
missing = sorted(n for n in nums - small if n not in sources and n.rstrip("%") not in sources)
if missing:
    sys.exit(f"numbers in the paper that no checked source contains: {missing}")
print(f"{len(nums)} numbers in the paper, all found in checked sources")
