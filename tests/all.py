"""Run every test file in one command. Exit nonzero if any test fails."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests import _seams, test_llmsnitch, test_notify, test_scan_notify  # noqa: E402

code = 0
for mod in (test_llmsnitch, test_notify, test_scan_notify):
    print(f"== {mod.__name__} ==")
    code |= _seams.run(vars(mod))
sys.exit(code)
