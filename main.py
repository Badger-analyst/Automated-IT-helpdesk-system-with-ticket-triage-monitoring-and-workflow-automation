"""
main.py
=======
Entry point for the Smart IT Helpdesk Automation System.

Pipeline:
  1. Load raw tickets from JSON (simulates email / portal / monitoring)
  2. Classify and prioritise each ticket
  3. Trigger PowerShell remediation scripts for auto-resolvable tickets
  4. Log all tickets to ticket_log.json
  5. Print triage summary and log report

Usage:
    python main.py
    python main.py --tickets data/sample_tickets.json
    python main.py --report-only

Author : Badger-analyst
"""

import sys
import os
import subprocess
import argparse
from datetime import datetime

# Add scripts/python to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts", "python"))

from ticket_engine import process_all_tickets, print_ticket_summary
from logger import log_tickets, generate_report, load_log


def trigger_remediation(ticket: dict, dry_run: bool = True):
    """
    Trigger the PowerShell remediation script for an auto-resolvable ticket.

    In a real environment, dry_run=False would execute the script.
    For portfolio/demo purposes, dry_run=True just prints what would run.
    """
    script = ticket.get("assigned_script")
    if not script or not ticket.get("auto_resolve"):
        return

    if dry_run:
        print(f"  [DRY RUN] Would execute: powershell.exe -File {script}"
              f" -TicketID {ticket['ticket_id']}"
              f" -User {ticket['user']}")
    else:
        try:
            result = subprocess.run(
                ["powershell.exe", "-File", script,
                 "-TicketID", ticket["ticket_id"],
                 "-UserEmail", ticket["user"]],
                capture_output=True, text=True, timeout=60
            )
            if result.returncode == 0:
                print(f"  ✓ Script completed: {script}")
            else:
                print(f"  ✗ Script failed: {result.stderr}")
        except FileNotFoundError:
            print(f"  [SKIP] PowerShell not available on this platform.")
        except subprocess.TimeoutExpired:
            print(f"  [TIMEOUT] Script exceeded 60s: {script}")


def run_pipeline(ticket_file: str, dry_run: bool = True):
    """Run the full helpdesk automation pipeline."""

    print("\n" + "━" * 65)
    print("  🤖  SMART IT HELPDESK AUTOMATION SYSTEM")
    print(f"  Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("━" * 65)

    # Step 1 — Classify tickets
    print(f"\n[1/4] Loading and classifying tickets from: {ticket_file}")
    tickets = process_all_tickets(ticket_file)
    print(f"      {len(tickets)} tickets classified.")

    # Step 2 — Print triage summary
    print("\n[2/4] Triage summary:")
    print_ticket_summary(tickets)

    # Step 3 — Trigger remediation for auto-resolvable tickets
    auto_tickets = [t for t in tickets if t["auto_resolve"]]
    print(f"[3/4] Triggering remediation for {len(auto_tickets)} auto-resolvable ticket(s):")
    for ticket in auto_tickets:
        print(f"\n  → {ticket['ticket_id']} | {ticket['category'].replace('_', ' ').title()}")
        trigger_remediation(ticket, dry_run=dry_run)

    # Step 4 — Log everything
    print(f"\n[4/4] Logging all tickets...")
    log = log_tickets(tickets)
    generate_report(log)

    print("  Pipeline complete.\n")


def main():
    parser = argparse.ArgumentParser(description="Smart IT Helpdesk Automation")
    parser.add_argument("--tickets", default="data/sample_tickets.json",
                        help="Path to tickets JSON file")
    parser.add_argument("--report-only", action="store_true",
                        help="Only print the log report, skip processing")
    parser.add_argument("--live", action="store_true",
                        help="Actually execute PowerShell scripts (default: dry run)")
    args = parser.parse_args()

    if args.report_only:
        generate_report(load_log())
    else:
        run_pipeline(args.tickets, dry_run=not args.live)


if __name__ == "__main__":
    main()
