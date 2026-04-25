from __future__ import annotations

PEOPLE = [
    "Ehab",
    "Camille",
    "Candy",
    "Harley",
    "Maria",
    "Mark",
    "Sandy",
    "Sophia",
    "Tiffany",
]

COMPANY_EMAIL_DOMAIN = "zenith-ecs.com"

PEOPLE_EMAIL_MAP = {
    person: f"{person.lower()}@{COMPANY_EMAIL_DOMAIN}" for person in PEOPLE
}

EMAIL_TO_PERSON = {email.lower(): person for person, email in PEOPLE_EMAIL_MAP.items()}

RECORD_TYPES = ["Sales", "Operation"]
PRIORITIES = ["High", "Medium", "Low"]

SALES_PHASES = [
    "Inquiry",
    "Sourcing",
    "Quotation",
    "Sampling",
    "Closing",
    "Closed",
]

OPERATION_PHASES = [
    "Order Open",
    "Payment",
    "Planning",
    "Execution",
    "Shipment",
    "Closure",
]

HEALTH_STATUSES = [
    "On Track",
    "Waiting Client",
    "Waiting Supplier",
    "Waiting Internal",
    "Blocked",
    "Need Alignment",
    "Need Decision",
    "On Hold",
    "Delayed",
    "Due Soon",
    "Reopened",
    "Done",
]

SALES_RESULTS = ["No Decision Yet", "Won", "Lost"]
OPERATION_RESULTS = ["In Progress", "Partial Shipped", "Complete Shipped", "Paid Closed", "Cancelled"]

REQUEST_TYPES = ["None", "Decision", "Alignment", "Support", "Approval", "Information"]

REQUEST_TYPE_DISPLAY = {
    "None": "None",
    "Decision": "Decision needed",
    "Alignment": "Alignment needed",
    "Support": "Support needed",
    "Approval": "Approval needed",
    "Information": "Info only",
}

REQUEST_TYPE_DISPLAY_VALUES = [
    REQUEST_TYPE_DISPLAY["Decision"],
    REQUEST_TYPE_DISPLAY["Alignment"],
    REQUEST_TYPE_DISPLAY["Support"],
    REQUEST_TYPE_DISPLAY["Approval"],
    REQUEST_TYPE_DISPLAY["Information"],
    REQUEST_TYPE_DISPLAY["None"],
]

DEFAULT_SALES_PHASE = "Inquiry"
DEFAULT_OPERATION_PHASE = "Order Open"
DEFAULT_HEALTH = "On Track"
DEFAULT_SALES_RESULT = "No Decision Yet"
DEFAULT_OPERATION_RESULT = "In Progress"

MEETING_POOL_HEALTH = {"Blocked", "Need Decision", "Need Alignment", "Delayed", "Due Soon"}

SALES_BOARD_ACTIONS = [
    "Quote Sent",
    "Quote Revised",
    "Sample Sent",
    "Sample Feedback NG",
    "Waiting Client",
    "Waiting Supplier",
    "Need Decision",
    "Need Alignment",
    "Close Won",
    "Close Lost",
    "Add to This Week Meeting",
]

OPERATION_BOARD_ACTIONS = [
    "Prepayment Received",
    "Production Started",
    "Delay Confirmed",
    "Partial Shipment",
    "Complete Shipment",
    "Shipment Paid",
    "Waiting Supplier",
    "Waiting Internal",
    "Need Decision",
    "Mark Blocked",
    "Add to This Week Meeting",
]
