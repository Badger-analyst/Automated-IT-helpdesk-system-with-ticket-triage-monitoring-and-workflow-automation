# 📘 ITIL Concepts — Applied to This Helpdesk System

> **What is ITIL?**  
> ITIL (Information Technology Infrastructure Library) is the world's most widely adopted framework for IT Service Management (ITSM). It provides a set of best practices for delivering and supporting IT services. This document maps each ITIL concept directly to code and logic in this project.

---

## 🗂️ Table of Contents

1. [The Four ITIL Ticket Types](#1-the-four-itil-ticket-types)
2. [Ticket Lifecycle State Machine](#2-ticket-lifecycle-state-machine)
3. [Impact × Urgency Priority Matrix](#3-impact--urgency-priority-matrix)
4. [SLA Management](#4-sla-management)
5. [Problem Management](#5-problem-management)
6. [Escalation Process](#6-escalation-process)
7. [How ITIL Integrates with This Codebase](#7-how-itil-integrates-with-this-codebase)
8. [ITIL Glossary](#8-itil-glossary)

---

## 1. The Four ITIL Ticket Types

ITIL distinguishes between four types of work that come into a helpdesk. Treating them the same is a common mistake — each has a different goal, SLA, and workflow.

| Type | Definition | Example in This System |
|------|------------|----------------------|
| **Incident** | Unplanned interruption or degradation of a service | WiFi down, Teams crashing, disk full |
| **Service Request** | Standard, pre-approved request — no negative impact | Password reset, new access for a joiner |
| **Problem** | Root cause investigation for recurring incidents | Disk filling up every week (3rd time) |
| **Change** | Planned modification to the IT environment | OS upgrade, patch deployment |

### Why This Matters

```
WITHOUT ITIL typing:
  → All tickets join one queue
  → Password reset (15 min fix) competes with a system outage
  → Root causes never get investigated
  → Changes sneak in untracked

WITH ITIL typing:
  → Incidents get SLA urgency  (restore service fast)
  → Service Requests get scheduled  (no urgency)
  → Problems get root-cause analysis  (prevent recurrence)
  → Changes get approval + rollback plans
```

### How It's Classified in Code

```python
# itil_workflow.py → classify_itil_type()
ITIL_TYPE_RULES = {
    "incident":        { "keywords": ["crash", "error", "down", "broken", ...] },
    "service_request": { "keywords": ["request", "need access", "new joiner", ...] },
    "problem":         { "keywords": ["recurring", "keeps happening", "third time", ...] },
    "change":          { "keywords": ["upgrade", "patch", "deploy", "migration", ...] }
}
```

---

## 2. Ticket Lifecycle State Machine

Every ITIL ticket moves through defined states. Skipping states or going backwards without rules creates chaos. This system enforces valid transitions.

### State Flow Diagram

```
                    ┌──────────┐
    Ticket arrives  │          │
    ───────────────►│   NEW    │
                    │          │
                    └────┬─────┘
                         │ Auto-triage assigns it
                         ▼
                    ┌──────────┐
                    │ ASSIGNED │◄──────────────────────┐
                    │          │                        │
                    └────┬─────┘                        │
                         │ Work begins                  │
                         ▼                              │
                    ┌──────────────┐   Waiting for  ┌──────────┐
                    │ IN_PROGRESS  │──────user ─────►│ PENDING  │
                    │              │◄────response────│          │
                    └──────┬───────┘                └──────────┘
                           │ Fix applied
                           ▼
                    ┌──────────────┐   User rejects  ┌──────────────┐
                    │   RESOLVED   │────fix ─────────►│ IN_PROGRESS  │
                    │              │                  └──────────────┘
                    └──────┬───────┘
                           │ Confirmed or auto-close after 5 days
                           ▼
                    ┌──────────┐
                    │  CLOSED  │  ← Terminal state
                    └──────────┘
```

### State Definitions

| State | Meaning | Who Sets It |
|-------|---------|-------------|
| `NEW` | Ticket received, not yet assessed | System on ingestion |
| `ASSIGNED` | Routed to a team or automation script | Auto-triage or analyst |
| `IN_PROGRESS` | Actively being worked on | Analyst or automation |
| `PENDING` | Waiting on user reply or 3rd party | Analyst |
| `RESOLVED` | Fix applied, awaiting user confirmation | Script or analyst |
| `CLOSED` | User confirmed, or auto-closed after 5 days | System or user |

### Valid Transitions (enforced in code)

```python
VALID_TRANSITIONS = {
    "NEW":         {"ASSIGNED"},
    "ASSIGNED":    {"IN_PROGRESS", "PENDING"},
    "IN_PROGRESS": {"PENDING", "RESOLVED"},
    "PENDING":     {"IN_PROGRESS", "RESOLVED"},
    "RESOLVED":    {"CLOSED", "IN_PROGRESS"},  # re-open if user rejects
    "CLOSED":      set()                        # cannot move from Closed
}
```

> **Key Rule:** You cannot jump from `NEW` directly to `RESOLVED`. Every state change is logged in `state_history` for audit purposes.

---

## 3. Impact × Urgency Priority Matrix

This is the ITIL standard for determining ticket priority. It replaces gut-feel prioritisation with a consistent, defensible matrix.

```
                URGENCY
             LOW    MEDIUM    HIGH
           ┌──────┬─────────┬──────────┐
    HIGH   │ HIGH │CRITICAL │ CRITICAL │
  I        ├──────┼─────────┼──────────┤
  M MEDIUM │ MED  │  HIGH   │   HIGH   │
  P        ├──────┼─────────┼──────────┤
  A LOW    │ LOW  │  MED    │   MED    │
  C        └──────┴─────────┴──────────┘
  T
```

### Definitions

**IMPACT** — How many users or services are affected?

| Level | Meaning | Example |
|-------|---------|---------|
| HIGH | Entire department, server, or business-critical service | "Server is down — whole team affected" |
| MEDIUM | Small team or shared service | "Our team's shared drive is inaccessible" |
| LOW | Single user, workaround available | "My Outlook is slow" |

**URGENCY** — How time-sensitive is the resolution?

| Level | Meaning | Keywords Detected |
|-------|---------|------------------|
| HIGH | Cannot wait — work is stopped | "urgent", "ASAP", "cannot work", "deadline" |
| MEDIUM | Needs attention today | "today", "soon", "waiting" |
| LOW | Can wait, no active blocker | (none of the above) |

### How Impact and Urgency Are Detected

```python
# itil_workflow.py → calculate_impact_urgency()

HIGH_IMPACT_KEYWORDS  = ["server", "whole team", "everyone", "production", ...]
MEDIUM_IMPACT_KEYWORDS = ["team", "several users", "department", ...]

HIGH_URGENCY_KEYWORDS   = ["urgent", "asap", "immediately", "cannot work", ...]
MEDIUM_URGENCY_KEYWORDS = ["today", "soon", "waiting", "important"]

# Department also affects impact:
HIGH_IMPACT_DEPARTMENTS = ["IT", "Finance", "Legal", "Executive", "Security"]
```

---

## 4. SLA Management

**SLA (Service Level Agreement)** is the contracted response/resolution time. Breaching an SLA damages trust and may have financial consequences.

### SLA Tiers in This System

| Priority | SLA Window | What Triggers It |
|----------|-----------|-----------------|
| CRITICAL | 1 hour | Server/infra down, whole team blocked |
| HIGH | 2 hours | Single user fully blocked, finance/exec dept |
| MEDIUM | 4 hours | Degraded service, workaround exists |
| LOW | 8–24 hours | Requests, cosmetic, non-urgent |

### SLA Breach Detection

The system checks remaining time at enrichment and flags tickets approaching breach:

```python
# itil_workflow.py → check_sla_breach_risk()

def check_sla_breach_risk(ticket, warning_buffer_minutes=30):
    minutes_left = (deadline - now).total_seconds() / 60

    if minutes_left < 0:
        return {"sla_status": "BREACHED", "escalate": True}
    elif minutes_left <= 30:
        return {"sla_status": "WARNING", "escalate": True}
    else:
        return {"sla_status": "OK", "escalate": False}
```

> **Best Practice:** Set your warning buffer to 20–30% of SLA time. For a 1-hour SLA, warn at 30 minutes remaining.

---

## 5. Problem Management

**Problem Management** exists to prevent recurring incidents. An "incident" fixes the symptom; a "problem record" investigates the root cause.

### Incident vs Problem

```
Incident #1:  Disk full on Server A    → Auto-resolved (clear_disk_space.ps1)
Incident #2:  Disk full on Server A    → Auto-resolved again
Incident #3:  Disk full on Server A    → 🚨 PROBLEM RECORD TRIGGERED

Problem Record: Why does disk keep filling up?
Root Cause Found: Application logs not rotating
Change Raised: Implement log rotation policy
Result: Incidents stop recurring
```

### Problem Detection in Code

```python
# itil_workflow.py → detect_problem_record()

def detect_problem_record(category, threshold=3):
    count = incident_registry.count(category)

    if count >= threshold:
        return {
            "is_problem": True,
            "recommendation": f"Raise a Problem ticket for '{category}' — occurred {count} times"
        }
```

> **Threshold Tuning:** The default is 3 recurrences. In production, tune per category — disk space might trigger at 2, general issues at 5.

---

## 6. Escalation Process

Escalation happens when a ticket is at risk of breaching its SLA or requires skills/authority beyond the current handler.

### Escalation Triggers in This System

| Trigger | Action |
|---------|--------|
| SLA breach (< 0 min left) | 🚨 `sla_escalate = True` flagged on ticket |
| SLA warning (< 30 min left) | ⚠️ `sla_status = WARNING` flagged |
| Problem record detected | Flag analyst to raise Problem ticket |
| HIGH impact + unresolved > 1h | Auto-escalate to senior analyst queue |

### Escalation Path

```
Level 1 — Automation Engine  (auto-resolve: password resets, disk clears)
    │ Cannot resolve or SLA at risk
    ▼
Level 2 — L1 Analyst         (manual triage, standard fixes)
    │ Needs specialist skill or problem investigation
    ▼
Level 3 — L2 Specialist      (network engineer, sysadmin, DBA)
    │ Needs change approval or vendor engagement
    ▼
Level 4 — Change Manager / Vendor
```

---

## 7. How ITIL Integrates with This Codebase

### Integration Flow

```
sample_tickets.json
        │
        ▼
ticket_engine.py → classify_ticket()
   - Keyword → category
   - Department + urgency → raw priority
   - SLA deadline calculated
        │
        ▼
itil_workflow.py → run_itil_enrichment()
   - classify_itil_type()       → Incident / SR / Problem / Change
   - calculate_impact_urgency() → Impact + Urgency levels
   - PRIORITY_MATRIX lookup     → CRITICAL / HIGH / MEDIUM / LOW
   - advance_lifecycle_state()  → NEW → ASSIGNED → IN_PROGRESS
   - check_sla_breach_risk()    → OK / WARNING / BREACHED
   - detect_problem_record()    → Problem flag if recurring
        │
        ▼
itil_workflow.py → print_itil_report()
   - Full enriched output with lifecycle state, ITIL type, escalation flags
```

### How to Use in `main.py`

```python
from ticket_engine   import process_all_tickets
from itil_workflow   import run_itil_enrichment, print_itil_report

# Step 1: classify tickets (existing engine)
tickets = process_all_tickets("data/sample_tickets.json")

# Step 2: apply ITIL enrichment (new layer)
itil_tickets = run_itil_enrichment(tickets)

# Step 3: print ITIL report
print_itil_report(itil_tickets)

# Step 4: manually advance a ticket state (e.g., after analyst resolves it)
from itil_workflow import advance_lifecycle_state
ticket = advance_lifecycle_state(ticket, "RESOLVED", actor="J.Smith (L1 Analyst)")
ticket = advance_lifecycle_state(ticket, "CLOSED",   actor="System (auto-close)")
```

---

## 8. ITIL Glossary

| Term | Definition |
|------|-----------|
| **ITIL** | Information Technology Infrastructure Library — a framework of IT service management best practices |
| **ITSM** | IT Service Management — the practice of managing IT services to meet business needs |
| **Incident** | Any unplanned interruption or reduction in quality of an IT service |
| **Problem** | The root cause of one or more incidents |
| **Change** | Addition, modification, or removal of anything that could affect IT services |
| **Service Request** | A formal request for something to be provided (not incident-related) |
| **SLA** | Service Level Agreement — agreed time within which a service must be restored |
| **OLA** | Operational Level Agreement — internal SLA between IT teams |
| **CMDB** | Configuration Management Database — records all IT assets and their relationships |
| **CI** | Configuration Item — any component managed in the CMDB |
| **Impact** | The effect of an incident on business operations (how many people are affected) |
| **Urgency** | How quickly the issue needs to be resolved (time sensitivity) |
| **Priority** | Impact + Urgency combined — determines queue position |
| **Escalation** | Passing a ticket to a higher skill/authority level when current handler cannot resolve it |
| **Workaround** | A temporary solution that restores service while the root cause is investigated |
| **Known Error** | A problem with an identified root cause and a workaround, documented for future reference |
| **CAB** | Change Advisory Board — a group that reviews and approves significant changes |
| **RCA** | Root Cause Analysis — investigation to find why an incident occurred |

---

> 💡 **Learning Tip for Junior Analysts:** Start by mastering the **Incident lifecycle** and the **Priority Matrix** — these two concepts govern 80% of day-to-day helpdesk work. Problem and Change Management become important as you move into senior roles.
