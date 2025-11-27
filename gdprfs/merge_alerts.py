import json
from pathlib import Path

MERGE_ALERT_FILE = Path("/home/ann20010929/MA3/Building_a_GDPR-compliant_file_system/instrlib/merge_alerts.json")

def save_merge_alerts_for_ui(file_path, alerts):
    MERGE_ALERT_FILE.write_text(json.dumps({
        "file": file_path,
        "alerts": alerts
    }, indent=2))


