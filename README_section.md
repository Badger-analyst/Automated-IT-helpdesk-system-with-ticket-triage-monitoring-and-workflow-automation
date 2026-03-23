# 🧠 Smart Helpdesk – Data Labeling & Classification Component

> **Component:** Data Labeling & Classification  
> **Role:** Junior Data Analyst  
> **Status:** ✅ Complete  

---

## 📌 Overview

This component forms the **data foundation** of the Smart Helpdesk system. Before any automation or triage logic can run, raw ticket data must be cleaned, categorized, and labeled into a structured format that machines can learn from.

This covers how ticket categories were defined, how labeling rules were built, how raw data was structured into labeled datasets, and how those datasets feed into triage automation.

---

## 1. 🗂️ Defined Ticket Categories

### Incident Types
Tickets were classified into the following incident categories:

| Category Code | Incident Type         | Description                                              |
|---------------|-----------------------|----------------------------------------------------------|
| `INC-HW`      | Hardware              | Physical device failures, peripheral issues              |
| `INC-SW`      | Software              | Application crashes, installation errors, bugs           |
| `INC-NET`     | Network & Connectivity| VPN failures, internet outages, slow connections         |
| `INC-ACC`     | Access & Permissions  | Login failures, account lockouts, access requests        |
| `INC-SEC`     | Security              | Phishing reports, malware alerts, data breach concerns   |
| `INC-DATA`    | Data & Reporting      | Missing data, broken dashboards, incorrect reports       |
| `INC-GEN`     | General Inquiry       | How-to questions, non-urgent requests                    |

### Priority Levels
Each ticket was assigned a priority level based on business impact and urgency:

| Priority | Label      | SLA Target  | Criteria                                                  |
|----------|------------|-------------|-----------------------------------------------------------|
| `P1`     | Critical   | 1 hour      | Full system outage, security breach, business stopped     |
| `P2`     | High       | 4 hours     | Major feature broken, multiple users affected             |
| `P3`     | Medium     | 8 hours     | Partial impact, workaround available                      |
| `P4`     | Low        | 24 hours    | Minor inconvenience, single user, no business impact      |
| `P5`     | Informational | 72 hours | General questions, no active issue                        |

---

## 2. 📏 Labeling Rules for Classification

To ensure consistency and reduce human error, the following **rule-based labeling logic** was applied before any ML model training:

### Keyword Mapping Rules
```
IF ticket_description CONTAINS ["can't log in", "locked out", "password reset"]
  → Category = INC-ACC, Priority = P3

IF ticket_description CONTAINS ["ransomware", "phishing", "data breach", "suspicious email"]
  → Category = INC-SEC, Priority = P1

IF ticket_description CONTAINS ["internet down", "VPN not connecting", "no network"]
  → Category = INC-NET, Priority = P2

IF ticket_description CONTAINS ["Excel crashing", "app not opening", "software error"]
  → Category = INC-SW, Priority = P3

IF ticket_description CONTAINS ["dashboard broken", "report wrong", "data missing"]
  → Category = INC-DATA, Priority = P3
```

### Escalation Override Rules
- Any ticket with **≥ 5 users affected** → auto-escalate to `P1` regardless of category
- Any ticket open for **> 2 hours without assignment** → escalate priority by one level
- Tickets flagged by VIP users → minimum `P2`

### Conflict Resolution
When a ticket matches multiple categories, the **highest-priority category** takes precedence. All ambiguous tickets were manually reviewed and labeled by a human analyst before inclusion in training data.

---

## 3. 🗃️ Structured Raw Ticket Data into Labeled Datasets

### Raw Data Schema (Before Labeling)
```
ticket_id | submitted_at | user_id | department | raw_description | attachment_flag
```

### Labeled Dataset Schema (After Processing)
```
ticket_id | submitted_at | user_id | department | cleaned_description | 
incident_type | priority_level | affected_users | resolution_time_hrs | 
label_source | label_confidence
```

### Key Transformations Applied

| Step | Action | Tool Used |
|------|--------|-----------|
| 1 | Removed PII (names, emails, IPs) from descriptions | Python – `re`, `pandas` |
| 2 | Lowercased and stripped special characters | Python – `str.lower()`, regex |
| 3 | Applied keyword-based labeling rules | Python – conditional logic |
| 4 | Flagged low-confidence labels for human review | Label confidence score < 0.75 |
| 5 | Exported final labeled dataset to `.csv` | `pandas.to_csv()` |

### Dataset Split
```
Total Labeled Tickets : 4,200
├── Training Set       : 2,940  (70%)
├── Validation Set     :   630  (15%)
└── Test Set           :   630  (15%)
```

---

## 4. 🤖 Using Labeled Data to Support Triage Automation

The labeled dataset produced in Step 3 directly powers the helpdesk's automated triage pipeline:

```
Raw Ticket Submitted
        │
        ▼
  Text Preprocessing
  (clean, normalize)
        │
        ▼
  Classification Model
  (trained on labeled data)
        │
        ▼
  Predicted: Category + Priority
        │
        ▼
  Auto-Route to Correct Queue
        │
        ▼
  SLA Timer Starts Automatically
```

### Automation Benefits Enabled by Labeling
- ✅ **Auto-routing** – tickets go directly to the right team without manual reading
- ✅ **SLA enforcement** – priority labels trigger automatic countdown timers
- ✅ **Backlog reduction** – triage time reduced from ~15 min to < 30 seconds per ticket
- ✅ **Pattern analysis** – labeled data enables trend reporting in Power BI dashboards
- ✅ **Model retraining** – new labeled tickets continuously improve classification accuracy

### Power BI Integration
The labeled dataset feeds directly into Power BI reports for:
- Ticket volume by category and priority
- SLA breach analysis per incident type
- Team workload distribution
- First-contact resolution rates by category

---

## 📁 Related Files

```
smart-helpdesk/
├── data/
│   ├── raw_tickets.csv              # Original unprocessed ticket dump
│   ├── labeled_tickets.csv          # Final labeled dataset
│   └── labeling_rules.json          # Exportable rule definitions
├── scripts/
│   ├── label_tickets.py             # Labeling automation script
│   └── preprocess.py                # Text cleaning functions
├── notebooks/
│   └── labeling_analysis.ipynb      # Exploratory labeling QA
└── README.md
```

---

## 👤 Author

**Badger Analyst**  
Junior Power BI Data Analyst  
[GitHub](https://github.com/Badger-analyst)

---

*Last updated: March 2026*
