# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import today
from training_portal.training_portal.access_control import get_trainer_department, check_portal_permission


def get_context(context):
    check_portal_permission()

    user = frappe.session.user
    trainer = frappe.db.get_value(
        "Trainer",
        {"user": user},
        ["name", "trainer_name", "department"],
        as_dict=True
    )
    context.trainer = trainer

    trainer_dept = get_trainer_department()
    context.trainer_dept = trainer_dept

    # Build filters based on role
    filters = {}
    if trainer_dept:
        courses = [c.name for c in frappe.get_all("Training Course", filters={"department": trainer_dept})]
        filters["course"] = ["in", courses]

    # Total Sessions
    context.total_sessions = frappe.db.count("Training Session", filters)

    # Today's Sessions
    today_filters = filters.copy()
    today_filters["training_date"] = today()
    context.today_sessions = frappe.db.count("Training Session", today_filters)

    # Upcoming Sessions
    upcoming_filters = filters.copy()
    upcoming_filters["training_date"] = [">", today()]
    context.upcoming_sessions = frappe.db.count("Training Session", upcoming_filters)

    # Completed Sessions
    completed_filters = filters.copy()
    completed_filters["status"] = "Completed"
    context.completed_sessions = frappe.db.count("Training Session", completed_filters)

    # Sessions List
    context.sessions = frappe.get_all(
        "Training Session",
        filters=filters,
        fields=[
            "name",
            "training_name",
            "training_date",
            "training_mode",
            "status"
        ],
        order_by="training_date desc"
    )

    return context