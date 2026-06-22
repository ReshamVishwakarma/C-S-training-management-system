# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def get_context(context):
    if "Trainer" not in frappe.get_roles():
        frappe.throw(_("Not Permitted"), frappe.PermissionError)

    user = frappe.session.user
    context.user = user

    # Get active trainer profile
    trainer = frappe.db.get_value(
        "Trainer",
        {"user": user},
        ["name", "trainer_name", "department"],
        as_dict=True
    )
    context.trainer = trainer

    # Fetch courses
    context.courses = frappe.get_all(
        "Training Course",
        filters={"active": 1},
        fields=["name", "course_name", "duration_hours", "description"]
    )

    # Fetch trainers
    context.trainers = frappe.get_all(
        "Trainer",
        filters={"active": 1},
        fields=["name", "trainer_name"]
    )

    return context


@frappe.whitelist()
def create_new_session(course, training_date, start_time, duration_hours, training_mode, trainer, meeting_link=None, location=None, description=None, max_participants=0):
    if "Trainer" not in frappe.get_roles():
        frappe.throw(_("Not Permitted"), frappe.PermissionError)
        
    try:
        doc = frappe.new_doc("Training Session")
        doc.course = course
        doc.training_date = training_date
        doc.start_time = start_time
        doc.duration_hours = float(duration_hours or 0)
        doc.training_mode = training_mode
        doc.trainer = trainer
        doc.status = "Scheduled"  # New sessions are scheduled
        
        if training_mode == "Online":
            doc.meeting_link = meeting_link
        else:
            doc.location = location
            
        doc.description = description
        doc.max_participants = int(max_participants or 0)
        
        doc.insert(ignore_permissions=True)
        return {
            "status": "success",
            "message": _("Training session {0} created successfully.").format(doc.name)
        }
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Create Session Error")
        return {
            "status": "error",
            "message": str(e)
        }
