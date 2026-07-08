# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from training_portal.training_portal.access_control import get_trainer_department, check_portal_permission


def get_context(context):
    check_portal_permission()

    session_name = frappe.form_dict.get("session")
    if not session_name:
        frappe.throw("Session not found")

    session = frappe.get_doc("Training Session", session_name)

    trainer_dept = get_trainer_department()
    if trainer_dept:
        course_dept = frappe.db.get_value("Training Course", session.course, "department")
        if course_dept != trainer_dept:
            frappe.throw("Access Violation: You are not authorized to view sessions outside your department.", frappe.PermissionError)

    trainer = frappe.get_doc("Trainer", session.trainer)

    enrollments = frappe.get_all(
        "Training Enrollment",
        filters={
            "training_session": session.name
        },
        fields=[
            "employee",
            "department",
            "completion_status"
        ]
    )

    context.session = session
    context.trainer = trainer
    context.enrollments = enrollments
    context.start_time = str(session.start_time).split(".")[0][:5]

    return context