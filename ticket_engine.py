"""
ticket_engine.py
================
Core classifier for the Smart IT Helpdesk Automation System.

Reads incoming ticket JSON, applies keyword-based categorisation,
assigns SLA-driven priority, and routes to the correct handler.

Author : Badger-analyst
"""

import json
import re
from datetime import datetime


# ── Category Rules ────────────────────────────────────────────────────────────
# Each category maps to a list of keywords to match against subject + body.
# Order matters — first match wins.

CATEGORY_RULES = {
    "password_reset": {
        "keywords": ["password", "expired", "locked out", "cannot log", "can't log",
                     "reset password", "account locked", "login failed", "credentials"],
        "auto_resolve": True,
        "sla_hours": 1,
        "script": "scripts/powershell/reset_password.ps1"
    },
    "network": {
        "keywords": ["internet", "network", "wifi", "wi-fi", "no connection", "169.254",
                     "cannot connect", "vpn", "dns", "ping", "ip address", "offline"],
        "auto_resolve": False,
        "sla_hours": 2,
        "script": "scripts/powershell/network_diagnostics.ps1"
    },
    "software_crash": {
        "keywords": ["crash", "crashing", "error code", "not responding", "freezing",
                     "reinstall", "teams", "outlook", "office", "application", "0x"],
        "auto_resolve": False,
        "sla_hours": 4,
        "script": "scripts/powershell/repair_software.ps1"
    },
    "disk_space": {
        "keywords": ["disk", "storage", "capacity", "space", "full", "94%", "90%",
                     "low disk", "drive full", "disk usage"],
        "auto_resolve": True,
        "sla_hours": 1,
        "script": "scripts/powershell/clear_disk_space.ps1"
    },
    "access_request": {
        "keywords": ["access", "permission", "shared drive", "folder access", "need access",
                     "new joiner", "onboarding", "grant access", "drive q:", "drive p:"],
        "auto_resolve": False,
        "sla_hours": 8,
        "script": None   # Requires human approval
    },
    "performance": {
        "keywords": ["slow", "sluggish", "freezes", "boot", "startup", "hanging",
                     "performance", "running slow", "lagging"],
        "auto_resolve": False,
        "sla_hours": 8,
        "script": "scripts/powershell/performance_check.ps1"
    },
    "general": {
        "keywords": [],           # Catch-all
        "auto_resolve": False,
        "sla_hours": 24,
        "script": None
    }
}

# ── Priority Rules ────────────────────────────────────────────────────────────
# Priority is determined by category SLA + department + urgency keywords.

PRIORITY_MAP = {
    1: "CRITICAL",   # System-wide / server / infrastructure
    2: "HIGH",       # Single user blocked from working
    3: "MEDIUM",     # Degraded but workaround exists
    4: "LOW"         # Request / cosmetic / non-urgent
}

URGENCY_KEYWORDS = ["urgent", "critical", "asap", "immediately", "deadline",
                    "meeting in", "cannot work", "whole team", "everyone affected"]

HIGH_PRIORITY_DEPARTMENTS = ["IT", "Finance", "Legal", "Executive"]

CATEGORY_BASE_PRIORITY = {
    "disk_space":      1,
    "password_reset":  2,
    "network":         2,
    "software_crash":  3,
    "performance":     3,
    "access_request":  4,
    "general":         4
}


# ── Functions ─────────────────────────────────────────────────────────────────

def load_tickets(filepath: str) -> list:
    """Load raw ticket data from a JSON file."""
    with open(filepath, "r") as f:
        return json.load(f)


def classify_ticket(ticket: dict) -> dict:
    """
    Classify a single ticket.

    Returns an enriched ticket dict with:
        - category
        - priority_level (int)
        - priority_label (str)
        - auto_resolve (bool)
        - sla_deadline (str)
        - assigned_script (str or None)
        - classified_at (str)
    """
    text = (ticket.get("subject", "") + " " + ticket.get("body", "")).lower()

    # Step 1 — Categorise
    matched_category = "general"
    for category, rules in CATEGORY_RULES.items():
        if any(kw in text for kw in rules["keywords"]):
            matched_category = category
            break

    rules = CATEGORY_RULES[matched_category]

    # Step 2 — Calculate priority
    base_priority = CATEGORY_BASE_PRIORITY[matched_category]

    # Escalate if urgency keywords present
    if any(kw in text for kw in URGENCY_KEYWORDS):
        base_priority = max(1, base_priority - 1)

    # Escalate if high-priority department
    if ticket.get("department") in HIGH_PRIORITY_DEPARTMENTS:
        base_priority = max(1, base_priority - 1)

    # Step 3 — SLA deadline
    submitted = datetime.fromisoformat(ticket["submitted_at"])
    from datetime import timedelta
    sla_deadline = submitted + timedelta(hours=rules["sla_hours"])

    return {
        **ticket,
        "category":        matched_category,
        "priority_level":  base_priority,
        "priority_label":  PRIORITY_MAP[base_priority],
        "auto_resolve":    rules["auto_resolve"],
        "sla_hours":       rules["sla_hours"],
        "sla_deadline":    sla_deadline.strftime("%Y-%m-%d %H:%M"),
        "assigned_script": rules["script"],
        "classified_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def process_all_tickets(filepath: str) -> list:
    """Load and classify all tickets. Returns list of enriched dicts."""
    raw = load_tickets(filepath)
    classified = [classify_ticket(t) for t in raw]

    # Sort: CRITICAL first, then by submitted time
    classified.sort(key=lambda t: (t["priority_level"], t["submitted_at"]))
    return classified


def print_ticket_summary(tickets: list):
    """Print a formatted triage summary to the terminal."""
    print("\n" + "=" * 65)
    print("  SMART HELPDESK — TICKET TRIAGE SUMMARY")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    priority_icons = {1: "🔴", 2: "🟠", 3: "🟡", 4: "🟢"}

    for t in tickets:
        icon = priority_icons.get(t["priority_level"], "⚪")
        auto = "✓ AUTO-RESOLVE" if t["auto_resolve"] else "→ MANUAL REVIEW"
        print(f"\n  {icon} [{t['priority_label']}] {t['ticket_id']}")
        print(f"     User     : {t['user']} ({t['department']})")
        print(f"     Subject  : {t['subject']}")
        print(f"     Category : {t['category'].replace('_', ' ').title()}")
        print(f"     SLA Due  : {t['sla_deadline']}  ({t['sla_hours']}h SLA)")
        print(f"     Action   : {auto}")
        if t["assigned_script"]:
            print(f"     Script   : {t['assigned_script']}")

    # Stats
    from collections import Counter
    cat_counts = Counter(t["category"] for t in tickets)
    pri_counts = Counter(t["priority_label"] for t in tickets)
    auto_count = sum(1 for t in tickets if t["auto_resolve"])

    print("\n" + "-" * 65)
    print(f"  TOTALS: {len(tickets)} tickets  |  {auto_count} auto-resolvable"
          f"  |  {len(tickets)-auto_count} need human review")
    print(f"  PRIORITY BREAKDOWN: " +
          "  ".join(f"{k}: {v}" for k, v in sorted(pri_counts.items())))
    print(f"  BY CATEGORY: " +
          "  ".join(f"{k.replace('_',' ').title()}: {v}" for k, v in cat_counts.items()))
    print("=" * 65 + "\n")


if __name__ == "__main__":
    tickets = process_all_tickets("data/sample_tickets.json")
    print_ticket_summary(tickets)
