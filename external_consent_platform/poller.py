from asyncio import events
import requests, time, os

BASE_URL = "http://127.0.0.1:5000"
TRACE = "/home/ann20010929/MA3/Building_a_GDPR-compliant_file_system/instrlib/gdprfs/gdprfstrace.log"
INTERVAL = 6#600  # seconds

def poll_once():
    events = requests.get(f"{BASE_URL}/api/events", params={"status": "pending"}).json()
    if not events:
        print("[Poller] No pending events.")
        return 0
    
    os.makedirs(os.path.dirname(TRACE), exist_ok=True) # extracts the directory path part /home/ann20010929/MA3/Building_a_GDPR-compliant_file_system/instrlib/gdprfs and makes sure it exists
    with open(TRACE, "a", encoding="utf-8") as f: # opens the file gdprfstrace.log in append mode, or creates it first automatically if it doesn’t exist yet
        for e in events:
            payload = {"kind": e["kind"]}
            for key in ("uid", "purpose", "spCat"):
                if key in e and e[key]:
                    payload[key] = e[key]
            requests.post("http://127.0.0.1:7000/ingest", json=payload)
            
            requests.patch(f"{BASE_URL}/api/events/{e['id']}/ack") # /ack tells the server we have received and logged this Consent/Revoke event which was pending, so it can be marked as acked = done.
            print(f"[Poller] ACKed event {e['id']} ({e['kind']} for {e['uid']}:{e['purpose']})")
    return len(events) # number of processed events

if __name__ == "__main__":
    while True:
        try:
            n = poll_once()
            if n:
                print(f"[Poller] Appended {n} new event(s) to {TRACE}")
        except Exception as ex:
            print("[Poller] Error:", ex)
        time.sleep(INTERVAL)
