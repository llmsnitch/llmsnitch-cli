"""Run every test file in one command. Exit nonzero if any test fails."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests import (_seams, test_click, test_depaudit,  # noqa: E402
                   test_depaudit_bulletin, test_depaudit_intake, test_digest,
                   test_fs_coil_cli, test_hook_state, test_llmsnitch,
                   test_notify, test_notify_outlets, test_scan_notify,
                   test_scan_scope, test_scan_waivers)

code = 0
for mod in (test_llmsnitch, test_notify, test_scan_notify,
            test_depaudit_intake, test_depaudit_bulletin, test_depaudit,
            test_notify_outlets, test_digest, test_fs_coil_cli,
            test_hook_state, test_scan_scope, test_scan_waivers, test_click):
    print(f"== {mod.__name__} ==")
    code |= _seams.run(vars(mod))
sys.exit(code)
