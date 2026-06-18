# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def get_context(context):
    roles = frappe.get_roles()
    if not (any(r in roles for r in ["Trainer", "System Manager", "HR Manager", "HR User"])):
        frappe.throw(_("Not Permitted"), frappe.PermissionError)

    trainer_user = frappe.session.user
    context.user = trainer_user

    # Fetch trainer details if they are a Trainer
    trainer = None
    is_admin = any(r in roles for r in ["System Manager", "HR Manager", "HR User"])
    context.is_admin = is_admin

    if "Trainer" in roles:
        trainer = frappe.db.get_value(
            "Trainer",
            {"user": trainer_user},
            ["name", "trainer_name", "department"],
            as_dict=True
        )
        context.trainer = trainer

    # Define session filters based on role
    session_filters = {"status": ["in", ["Scheduled", "Ongoing", "Completed"]]}
    if not is_admin and trainer:
        session_filters["trainer"] = trainer.name

    # Sessions list for marking
    context.sessions_to_mark = frappe.get_all(
        "Training Session",
        filters=session_filters,
        fields=["name", "training_name", "training_date", "trainer", "status"],
        order_by="training_date desc"
    )

    # Fetch attendance summaries for dashboard KPI and registry table
    attendance_filters = {}
    if not is_admin and trainer:
        attendance_filters["trainer"] = trainer.name

    records = frappe.get_all(
        "Training Attendance",
        filters=attendance_filters,
        fields=[
            "name",
            "training_session",
            "date",
            "trainer",
            "total_participants",
            "present_count",
            "absent_count"
        ],
        order_by="date desc"
    )

    context.records = records

    total_participants = 0
    total_present = 0
    total_absent = 0

    for row in records:
        total_participants += row.total_participants or 0
        total_present += row.present_count or 0
        total_absent += row.absent_count or 0

    attendance_percentage = 0
    if total_participants:
        attendance_percentage = round((total_present / total_participants) * 100, 2)

    context.total_participants = total_participants
    context.total_present = total_present
    context.total_absent = total_absent
    context.attendance_percentage = attendance_percentage

    return context