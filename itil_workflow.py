"""
itil_workflow.py
================
ITIL v4-aligned workflow layer for the Smart IT Helpdesk Automation System.

Adds:
  - ITIL ticket type classification  (Incident / Service Request / Problem / Change)
  - Ticket lifecycle state machine   (New → Assigned → In Progress → Pending → Resolved → Closed)
  - Impact × Urgency priority matrix (replaces flat priority scoring)
  - Problem Record detection         (flags recurring incidents for root-cause review)
  - Escalation rules                 (auto-escalate when SLA breach is imminent)

ITIL Concept Map
----------------
  Incident        → Unplanned interruption that needs fast restoration
  Service Request → Standard request with no negative impact (e.g. new access)
  Problem         → Root cause of one or more recurring incidents
  Change          → Planned modification to the IT environment

Author : Badger-analyst
"""

from datetime import datetime, timedelta
from collections import Counter


# ── ITIL Ticket Types ─────────────────────────────────────────────────────────

ITIL_TYPE_RULES = {
    "incident": {
        "keywords": [
            "crash", "error", "broken", "not working", "offline", "down",
            "cannot access", "failed", "failure", "issue", "problem",
            "slow", "freeze", "freezing", "locked out", "no connection",
            "disk full", "disk space", "network", "wifi", "internet"
        ],
        "description": "Unplanned interruption or degradation of an IT service.",
        "target_restore_hours": 4
    },
    "service_request": {
        "keywords": [
            "request", "need access", "please provide", "new joiner",
            "onboarding", "grant", "set up", "install", "create account",
            "password reset", "reset password", "new laptop"
        ],
        "description": "Standard, pre-approved request with no service impact.",
        "target_restore_hours": 24
    },
    "problem": {
        "keywords": [
            "recurring", "keeps happening", "third time", "again", "still broken",
            "root cause", "underlying", "multiple users", "everyone", "team affected"
        ],
        "description": "Root cause behind one or more recurring incidents.",
        "target_restore_hours": 72
    },
    "change": {
        "keywords": [
            "upgrade", "update", "migration", "deploy", "rollout", "patch",
            "change request", "maintenance", "scheduled", "change window"
        ],
        "description": "Planned modification to IT infrastructure or services.",
        "target_restore_hours": 48
    }
}


# ── ITIL Lifecycle States ──────────────────────────────────────────────────────
#
#   NEW → ASSIGNED → IN_PROGRESS ──► RESOLVED → CLOSED
#                        │
#                     PENDING  (waiting on user / 3rd party)
#                        │
#                   IN_PROGRESS
#
# State transitions are enforced by `advance_lifecycle_state()` below.

LIFECYCLE_STATES = [
    "NEW",
    "ASSIGNED",
    "IN_PROGRESS",
    "PENDING",
    "RESOLVED",
    "CLOSED"
]

# Valid transitions: state → set of allowed next states
VALID_TRANSITIONS = {
    "NEW":         {"ASSIGNED"},
    "ASSIGNED":    {"IN_PROGRESS", "PENDING"},
    "IN_PROGRESS": {"PENDING", "RESOLVED"},
    "PENDING":     {"IN_PROGRESS", "RESOLVED"},
    "RESOLVED":    {"CLOSED", "IN_PROGRESS"},  # re-open if user rejects resolution
    "CLOSED":      set()                        # terminal state
}

# Who/what triggers each transition
TRANSITION_ACTOR = {
    "NEW":         "System (auto-ingestion)",
    "ASSIGNED":    "System (auto-triage) or Analyst",
    "IN_PROGRESS": "Analyst or Automation Script",
    "PENDING":     "Analyst (awaiting user or 3rd party)",
    "RESOLVED":    "Script or Analyst",
    "CLOSED":      "System (user confirms) or auto-close after 5 days"
}


# ── Impact × Urgency Priority Matrix (ITIL standard) ─────────────────────────
#
#             │  LOW urgency  │  MEDIUM urgency  │  HIGH urgency  │
#  ───────────┼───────────────┼──────────────────┼────────────────┤
#  HIGH impact│    HIGH       │    CRITICAL      │   CRITICAL     │
#  MED impact │    MEDIUM     │    HIGH          │   HIGH         │
#  LOW impact │    LOW        │    MEDIUM        │   MEDIUM       │

PRIORITY_MATRIX = {
    ("HIGH",   "HIGH"):   "CRITICAL",
    ("HIGH",   "MEDIUM"): "CRITICAL",
    ("HIGH",   "LOW"):    "HIGH",
    ("MEDIUM", "HIGH"):   "HIGH",
    ("MEDIUM", "MEDIUM"): "HIGH",
    ("MEDIUM", "LOW"):    "MEDIUM",
    ("LOW",    "HIGH"):   "MEDIUM",
    ("LOW",    "MEDIUM"): "MEDIUM",
    ("LOW",    "LOW"):    "LOW",
}

PRIORITY_TO_LEVEL = {"CRITICAL": 1, "HIGH": 2, "MEDIUM": 3, "LOW": 4}

# Keywords that raise IMPACT
HIGH_IMPACT_KEYWORDS  = ["server", "infrastructure", "whole team", "entire department",
                          "everyone", "business critical", "production", "multiple users"]
MEDIUM_IMPACT_KEYWORDS = ["team", "shared", "several users", "department"]

# Keywords that raise URGENCY
HIGH_URGENCY_KEYWORDS   = ["urgent", "asap", "immediately", "critical", "deadline",
                            "meeting in", "cannot work", "blocked"]
MEDIUM_URGENCY_KEYWORDS = ["today", "soon", "waiting", "important"]

# High-priority departments also raise impact
HIGH_IMPACT_DEPARTMENTS = ["IT", "Finance", "Legal", "Executive", "Security"]


# ── Problem Record Tracking ───────────────────────────────────────────────────
# Holds a simple in-memory registry of ticket categories seen.
# In production this would query your ITSM database.

_incident_registry: list[dict] = []


def register_incident(ticket: dict) -> None:
    """Add a resolved ticket to the incident registry for problem detection."""
    _incident_registry.append({
        "ticket_id": ticket.get("ticket_id"),
        "category":  ticket.get("category"),
        "user":      ticket.get("user"),
        "submitted": ticket.get("submitted_at")
    })


def detect_problem_record(category: str, threshold: int = 3) -> dict:
    """
    Flag a Problem Record if the same category has recurred >= threshold times.

    Returns a dict with:
        - is_problem (bool)
        - recurrence_count (int)
        - recommendation (str)
    """
    counts = Counter(i["category"] for i in _incident_registry)
    count  = counts.get(category, 0) + 1  # +1 for current ticket

    return {
        "is_problem":        count >= threshold,
        "recurrence_count":  count,
        "recommendation":    (
            f"⚠️  PROBLEM RECORD CANDIDATE — '{category}' has occurred {count} times. "
            f"Raise a Problem ticket to investigate root cause."
            if count >= threshold
            else f"Recurrence count: {count} (threshold: {threshold})"
        )
    }


# ── Core ITIL Functions ───────────────────────────────────────────────────────

def classify_itil_type(ticket: dict) -> str:
    """
    Classify a ticket into one of the four ITIL types:
    Incident, Service Request, Problem, or Change.
    First match wins; defaults to 'incident'.
    """
    text = (ticket.get("subject", "") + " " + ticket.get("body", "")).lower()

    for itil_type, rules in ITIL_TYPE_RULES.items():
        if any(kw in text for kw in rules["keywords"]):
            return itil_type

    return "incident"  # Safe default — unclassified disruptions are incidents


def calculate_impact_urgency(ticket: dict) -> tuple[str, str]:
    """
    Derive IMPACT and URGENCY from ticket text and metadata.
    Returns a tuple: (impact_level, urgency_level) — each "HIGH"/"MEDIUM"/"LOW".
    """
    text = (ticket.get("subject", "") + " " + ticket.get("body", "")).lower()
    dept = ticket.get("department", "")

    # IMPACT
    if any(kw in text for kw in HIGH_IMPACT_KEYWORDS) or dept in HIGH_IMPACT_DEPARTMENTS:
        impact = "HIGH"
    elif any(kw in text for kw in MEDIUM_IMPACT_KEYWORDS):
        impact = "MEDIUM"
    else:
        impact = "LOW"

    # URGENCY
    if any(kw in text for kw in HIGH_URGENCY_KEYWORDS):
        urgency = "HIGH"
    elif any(kw in text for kw in MEDIUM_URGENCY_KEYWORDS):
        urgency = "MEDIUM"
    else:
        urgency = "LOW"

    return impact, urgency


def apply_itil_priority(ticket: dict) -> dict:
    """
    Apply the ITIL Impact × Urgency matrix to a ticket.
    Adds: itil_type, impact, urgency, itil_priority, itil_priority_level.
    """
    itil_type        = classify_itil_type(ticket)
    impact, urgency  = calculate_impact_urgency(ticket)
    itil_priority    = PRIORITY_MATRIX[(impact, urgency)]
    priority_level   = PRIORITY_TO_LEVEL[itil_priority]
    problem_info     = detect_problem_record(ticket.get("category", "general"))

    return {
        **ticket,
        "itil_type":           itil_type,
        "itil_type_desc":      ITIL_TYPE_RULES[itil_type]["description"],
        "impact":              impact,
        "urgency":             urgency,
        "itil_priority":       itil_priority,
        "itil_priority_level": priority_level,
        "lifecycle_state":     "NEW",
        "problem_flag":        problem_info["is_problem"],
        "problem_info":        problem_info["recommendation"],
        "itil_enriched_at":    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


def advance_lifecycle_state(ticket: dict, new_state: str, actor: str = "System") -> dict:
    """
    Transition a ticket to a new lifecycle state.
    Enforces valid transitions — raises ValueError on illegal moves.

    Parameters
    ----------
    ticket    : enriched ticket dict (must have 'lifecycle_state')
    new_state : target state (must be in LIFECYCLE_STATES)
    actor     : who/what triggered this transition (for audit trail)

    Returns updated ticket dict with 'lifecycle_state' and 'state_history'.
    """
    new_state   = new_state.upper()
    current     = ticket.get("lifecycle_state", "NEW").upper()

    if new_state not in LIFECYCLE_STATES:
        raise ValueError(f"'{new_state}' is not a valid ITIL lifecycle state. "
                         f"Choose from: {LIFECYCLE_STATES}")

    if new_state not in VALID_TRANSITIONS.get(current, set()):
        raise ValueError(
            f"Illegal state transition: {current} → {new_state}. "
            f"Allowed next states from '{current}': {VALID_TRANSITIONS[current]}"
        )

    history_entry = {
        "from":      current,
        "to":        new_state,
        "actor":     actor,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    history = ticket.get("state_history", [])
    history.append(history_entry)

    return {
        **ticket,
        "lifecycle_state": new_state,
        "state_history":   history
    }


def check_sla_breach_risk(ticket: dict, warning_buffer_minutes: int = 30) -> dict:
    """
    Check whether a ticket is approaching or has breached its SLA deadline.

    Returns a dict with:
        - sla_status   : "OK" | "WARNING" | "BREACHED"
        - minutes_left : int (negative if breached)
        - escalate     : bool
    """
    try:
        deadline = datetime.strptime(ticket["sla_deadline"], "%Y-%m-%d %H:%M")
    except (KeyError, ValueError):
        return {"sla_status": "UNKNOWN", "minutes_left": None, "escalate": False}

    now          = datetime.now()
    minutes_left = int((deadline - now).total_seconds() / 60)

    if minutes_left < 0:
        status  = "BREACHED"
        escalate = True
    elif minutes_left <= warning_buffer_minutes:
        status  = "WARNING"
        escalate = True
    else:
        status  = "OK"
        escalate = False

    return {
        "sla_status":   status,
        "minutes_left": minutes_left,
        "escalate":     escalate
    }


def run_itil_enrichment(tickets: list[dict]) -> list[dict]:
    """
    Apply full ITIL enrichment to a list of already-classified tickets.
    Call this after ticket_engine.process_all_tickets().

    Steps per ticket:
      1. Classify ITIL type
      2. Apply Impact × Urgency priority matrix
      3. Set initial lifecycle state to NEW
      4. Check SLA breach risk
      5. Auto-advance state based on auto_resolve flag
    """
    enriched = []

    for ticket in tickets:
        # Step 1-3: ITIL type + priority + lifecycle state
        t = apply_itil_priority(ticket)

        # Step 4: SLA breach check
        sla_check = check_sla_breach_risk(t)
        t.update({
            "sla_status":   sla_check["sla_status"],
            "sla_escalate": sla_check["escalate"],
            "minutes_left": sla_check["minutes_left"]
        })

        # Step 5: Advance state — auto-resolve tickets move to IN_PROGRESS immediately
        if t.get("auto_resolve"):
            t = advance_lifecycle_state(t, "ASSIGNED",    actor="System (auto-triage)")
            t = advance_lifecycle_state(t, "IN_PROGRESS", actor="Automation Engine")
        else:
            t = advance_lifecycle_state(t, "ASSIGNED", actor="System (auto-triage)")

        # Register for problem detection
        register_incident(t)
        enriched.append(t)

    return enriched


# ── Reporting ─────────────────────────────────────────────────────────────────

def print_itil_report(tickets: list[dict]) -> None:
    """Print an ITIL-enriched triage report to the terminal."""

    state_icons = {
        "NEW":         "🆕",
        "ASSIGNED":    "📋",
        "IN_PROGRESS": "⚙️ ",
        "PENDING":     "⏳",
        "RESOLVED":    "✅",
        "CLOSED":      "🔒"
    }
    priority_icons = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
    sla_icons      = {"OK": "✅", "WARNING": "⚠️ ", "BREACHED": "🚨", "UNKNOWN": "❓"}
    type_badges    = {
        "incident":       "🔥 INCIDENT",
        "service_request":"📝 SERVICE REQUEST",
        "problem":        "🔍 PROBLEM",
        "change":         "🔧 CHANGE"
    }

    print("\n" + "═" * 70)
    print("  🏢  ITIL-ENRICHED HELPDESK REPORT")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("═" * 70)

    for t in tickets:
        p_icon = priority_icons.get(t.get("itil_priority", "LOW"), "⚪")
        s_icon = state_icons.get(t.get("lifecycle_state", "NEW"), "⚪")
        sla_i  = sla_icons.get(t.get("sla_status", "UNKNOWN"), "❓")
        badge  = type_badges.get(t.get("itil_type", "incident"), "❓ UNKNOWN")

        print(f"\n  {p_icon} [{t.get('itil_priority','?')}]  {t.get('ticket_id','?')}  |  {badge}")
        print(f"     User       : {t.get('user','?')} ({t.get('department','?')})")
        print(f"     Subject    : {t.get('subject','?')}")
        print(f"     Category   : {t.get('category','?').replace('_',' ').title()}")
        print(f"     Impact     : {t.get('impact','?')}  |  Urgency: {t.get('urgency','?')}")
        print(f"     Lifecycle  : {s_icon} {t.get('lifecycle_state','?')}")
        print(f"     SLA Status : {sla_i} {t.get('sla_status','?')}  "
              f"(deadline: {t.get('sla_deadline','?')})")

        if t.get("problem_flag"):
            print(f"     {t.get('problem_info','')}")

        if t.get("sla_escalate"):
            print(f"     🚨 ESCALATION REQUIRED — SLA at risk!")

    # Summary
    type_counts  = Counter(t.get("itil_type", "?")   for t in tickets)
    state_counts = Counter(t.get("lifecycle_state","?") for t in tickets)
    pri_counts   = Counter(t.get("itil_priority","?") for t in tickets)

    print("\n" + "─" * 70)
    print("  ITIL SUMMARY")
    print(f"  By Type    : " + "  |  ".join(f"{k.replace('_',' ').title()}: {v}" for k,v in type_counts.items()))
    print(f"  By State   : " + "  |  ".join(f"{k}: {v}" for k,v in state_counts.items()))
    print(f"  By Priority: " + "  |  ".join(f"{k}: {v}" for k,v in sorted(pri_counts.items())))
    print(f"  Escalations: {sum(1 for t in tickets if t.get('sla_escalate'))}")
    print(f"  Problem Flags: {sum(1 for t in tickets if t.get('problem_flag'))}")
    print("═" * 70 + "\n")


# ── Quick demo ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Minimal demo without needing the full pipeline
    demo_tickets = [
        {
            "ticket_id":    "TKT-001",
            "user":         "john.smith@company.com",
            "department":   "Finance",
            "subject":      "Cannot log into my computer — password expired",
            "body":         "I have an urgent deadline and cannot work.",
            "submitted_at": "2024-01-15T09:00:00",
            "category":     "password_reset",
            "auto_resolve": True,
            "sla_deadline": "2024-01-15 10:00"
        },
        {
            "ticket_id":    "TKT-002",
            "user":         "ops-team@company.com",
            "department":   "IT",
            "subject":      "Server disk usage at 94% — whole team affected",
            "body":         "This keeps happening — third time this month.",
            "submitted_at": "2024-01-15T08:55:00",
            "category":     "disk_space",
            "auto_resolve": True,
            "sla_deadline": "2024-01-15 09:55"
        },
        {
            "ticket_id":    "TKT-003",
            "user":         "new.joiner@company.com",
            "department":   "HR",
            "subject":      "New joiner — please grant access to shared drive",
            "body":         "Starting today, need access set up.",
            "submitted_at": "2024-01-15T09:10:00",
            "category":     "access_request",
            "auto_resolve": False,
            "sla_deadline": "2024-01-15 17:10"
        }
    ]

    enriched = run_itil_enrichment(demo_tickets)
    print_itil_report(enriched)
