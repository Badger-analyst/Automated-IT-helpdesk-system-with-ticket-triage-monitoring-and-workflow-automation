"""
azure_function_handler.py
========================
Proof-of-Concept Azure Function wrapper for the Smart Helpdesk Triage Engine.

This script demonstrates how to expose the `ticket_engine` logic as a 
serverless HTTP API using the Azure Functions Python Programming Model v2.

Prerequisites:
  pip install azure-functions
"""

import azure.functions as func
import json
import logging
import sys
import os

# Add the local scripts/python directory to the path so we can import ticket_engine
sys.path.insert(0, os.path.dirname(__file__))

import ticket_engine

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

@app.route(route="triage")
def triage_ticket(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
             "Invalid JSON in request body",
             status_code=400
        )

    if not req_body:
        return func.HttpResponse(
             "Please pass ticket data in the request body",
             status_code=400
        )

    # req_body should be a single ticket dict, e.g.:
    # {
    #   "ticket_id": "TKT-999",
    #   "user": "cloud.admin@azure.com",
    #   "department": "IT",
    #   "subject": "Azure VM is unresponsive",
    #   "body": "My web server is not responding to requests.",
    #   "submitted_at": "2024-01-15T12:00:00"
    # }
    
    try:
        # Re-use the existing core logic
        enriched_ticket = ticket_engine.classify_ticket(req_body)
        
        return func.HttpResponse(
            json.dumps(enriched_ticket, indent=2),
            mimetype="application/json",
            status_code=200
        )
    except Exception as e:
        logging.error(f"Error during classification: {str(e)}")
        return func.HttpResponse(
            f"Internal error: {str(e)}",
            status_code=500
        )

if __name__ == "__main__":
    print("This file is intended to be run by the Azure Functions host.")
    print("Example request body expected at /api/triage:")
    print(json.dumps({
        "ticket_id": "TKT-001",
        "user": "test@company.com",
        "department": "Finance",
        "subject": "Need password reset",
        "body": "I forgot my password",
        "submitted_at": "2024-01-15T09:00:00"
    }, indent=2))
