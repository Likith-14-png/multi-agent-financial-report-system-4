import sys
from pathlib import Path

# Add report-agent to path so tests can import report_agent
REPORT_AGENT_PATH = Path(__file__).resolve().parent.parent / "report-agent"
if str(REPORT_AGENT_PATH) not in sys.path:
    sys.path.insert(0, str(REPORT_AGENT_PATH))
