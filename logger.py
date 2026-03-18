"""
logger.py
=========
Appends classified ticket records to a rolling JSON log file.
Provides a summary report of ticket history.

Author : Badger-analyst
"""

import json
import os
from datetime import datetime


LOG_FILE = "logs/ticket_log.json"


def load_log() -> list:
    """Load existing log or return empty list."""
    if not os.path.exists(LOG_FILE):
        return []
    with open(LOG_FILE, "r") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_log(records: list):
    """Overwrite log file with updated records."""
    os.makedirs("logs", exist_ok=True)
    with open(LOG_FILE, "w") as f:
        json.dump(records, f, indent=2)


def log_tickets(tickets: list):
    """
    Append a batch of classified tickets to the log.
    Adds a 'logged_at' timestamp and default 'status' of 'open'.
    """
    log = load_log()
    existing_ids = {r["ticket_id"] for r in log}
    new_count = 0

    for ticket in tickets:
        if ticket["ticket_id"] in existing_ids:
            continue   # Skip duplicates

        record = {
            **ticket,
            "status":    "auto_resolved" if ticket["auto_resolve"] else "open",
            "logged_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "resolved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                           if ticket["auto_resolve"] else None,
            "notes": "Auto-resolved by remediation script" if ticket["auto_resolve"] else None
        }
        log.append(record)
        new_count += 1

    save_log(log)
    print(f"[Logger] {new_count} new tickets logged → {LOG_FILE}")
    return log


def generate_report(log: list):
    """Print a plain-text performance report from the log."""
    if not log:
        print("[Logger] No tickets in log yet.")
        return

    total = len(log)
    resolved = sum(1 for t in log if t["status"] == "auto_resolved")
    open_tickets = sum(1 for t in log if t["status"] == "open")

    print("\n" + "=" * 55)
    print("  HELPDESK LOG REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 55)
    print(f"  Total logged     : {total}")
    print(f"  Auto-resolved    : {resolved}  ({resolved/total*100:.0f}%)")
    print(f"  Open / manual    : {open_tickets}  ({open_tickets/total*100:.0f}%)")

    # By category
    from collections import Counter
    cats = Counter(t["category"] for t in log)
    print("\n  By Category:")
    for cat, count in cats.most_common():
        print(f"    {cat.replace('_', ' ').title():<20} {count} tickets")

    # SLA breach check (simple: compare logged_at vs sla_deadline)
    breaches = []
    for t in log:
        if t.get("sla_deadline") and t.get("logged_at"):
            try:
                sla = datetime.strptime(t["sla_deadline"], "%Y-%m-%d %H:%M")
                logged = datetime.strptime(t["logged_at"], "%Y-%m-%d %H:%M:%S")
                if logged > sla and t["status"] == "open":
                    breaches.append(t["ticket_id"])
            except ValueError:
                pass

    if breaches:
        print(f"\n  ⚠️  SLA BREACHES DETECTED: {', '.join(breaches)}")
    else:
        print("\n  ✓  No SLA breaches detected")

    print("=" * 55 + "\n")


if __name__ == "__main__":
    # Demo: load the log and print the report
    log = load_log()
    generate_report(log)
