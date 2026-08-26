import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Add project subpackages that are imported directly by tests.
REPORT_AGENT_PATH = ROOT / "report-agent"
if str(REPORT_AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(REPORT_AGENT_PATH))

RED_FLAG_AGENT_PATH = ROOT / "red_flag_agent"
if str(RED_FLAG_AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(RED_FLAG_AGENT_PATH))
