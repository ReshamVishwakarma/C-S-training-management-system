# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from training_portal.training_portal.access_control import get_trainer_department, check_portal_permission


def get_context(context):
    check_portal_permission()

    roles = frappe.get_roles()
    trainer_user = frappe.session.user
    context.user = trainer_user

    # Fetch trainer details if they are a Trainer
    trainer = None
    is_admin = any(r in roles for r in ["System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"])
    context.is_admin = is_admin

    if "Trainer" in roles:
        trainer = frappe.db.get_value(
            "Trainer",
            {"user": trainer_user},
            ["name", "trainer_name", "department"],
            as_dict=True
        )
        context.trainer = trainer

    trainer_dept = get_trainer_department()
    context.trainer_dept = trainer_dept

    # Define session filters based on role
    session_filters = {"status": ["in", ["Scheduled", "Ongoing", "Completed", "Cancelled"]]}
    if trainer:
        session_filters["trainer"] = trainer.name

    # Sessions list for marking
    context.sessions_to_mark = frappe.get_all(
        "Training Session",
        filters=session_filters,
        fields=["name", "training_name", "training_date", "trainer", "status"],
        order_by="training_date desc"
    )

    # Unique years for filters
    years = sorted(list(set(
        frappe.utils.getdate(s.training_date).year 
        for s in context.sessions_to_mark 
        if s.training_date
    )), reverse=True)
    if not years:
        import datetime
        years = [datetime.datetime.now().year]
    context.years = years

    context.months = [
        {"value": 1, "label": "January"},
        {"value": 2, "label": "February"},
        {"value": 3, "label": "March"},
        {"value": 4, "label": "April"},
        {"value": 5, "label": "May"},
        {"value": 6, "label": "June"},
        {"value": 7, "label": "July"},
        {"value": 8, "label": "August"},
        {"value": 9, "label": "September"},
        {"value": 10, "label": "October"},
        {"value": 11, "label": "November"},
        {"value": 12, "label": "December"}
    ]

    # Fetch attendance summaries for dashboard KPI and registry table
    attendance_filters = {}
    if trainer:
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