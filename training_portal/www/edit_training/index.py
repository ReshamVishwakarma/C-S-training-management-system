# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def get_context(context):
    if "Trainer" not in frappe.get_roles():
        frappe.throw(_("Not Permitted"), frappe.PermissionError)

    user = frappe.session.user
    context.user = user

    # Get trainer profile
    trainer = frappe.db.get_value(
        "Trainer",
        {"user": user},
        ["name", "trainer_name"],
        as_dict=True
    )
    context.trainer = trainer

    # Fetch all sessions led by this trainer
    context.sessions = frappe.get_all(
        "Training Session",
        filters={
            "trainer": trainer.name
        },
        fields=[
            "name",
            "training_name",
            "training_date",
            "start_time",
            "duration_hours",
            "training_mode",
            "status",
            "max_participants",
            "location",
            "meeting_link",
            "description"
        ],
        order_by="training_date desc"
    )

    return context


@frappe.whitelist()
def update_session_details(session_name, training_date, start_time, training_mode, status, location=None, meeting_link=None, max_participants=0):
    if "Trainer" not in frappe.get_roles():
        frappe.throw(_("Not Permitted"), frappe.PermissionError)

    try:
        doc = frappe.get_doc("Training Session", session_name)
        
        # Only allow edits if permissions permit
        doc.training_date = training_date
        
        # Start time format handles hh:mm:ss, let's store it
        doc.start_time = start_time
        doc.training_mode = training_mode
        doc.status = status
        
        if training_mode == "Online":
            doc.meeting_link = meeting_link
            doc.location = None
        else:
            doc.location = location
            doc.meeting_link = None
            
        doc.max_participants = int(max_participants or 0)
        
        doc.save(ignore_permissions=True)
        return {
            "status": "success",
            "message": _("Session {0} updated successfully.").format(session_name)
        }
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Update Session Error")
        return {
            "status": "error",
            "message": str(e)
        }
