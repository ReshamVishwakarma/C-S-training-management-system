# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json

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

    # Fetch active sessions (Draft, Scheduled, Ongoing) led by this trainer
    context.sessions = frappe.get_all(
        "Training Session",
        filters={
            "trainer": trainer.name,
            "status": ["in", ["Draft", "Scheduled", "Ongoing"]]
        },
        fields=["name", "training_name", "training_date"]
    )

    # Fetch all departments
    context.departments = frappe.get_all(
        "Department",
        fields=["name", "department_name"]
    )

    # Fetch unique designations
    designation_records = frappe.db.sql(
        "select distinct designation from tabEmployee where designation is not null and designation != ''",
        as_dict=True
    )
    context.designations = [r.designation for r in designation_records]

    return context


@frappe.whitelist()
def get_employees_list(department=None, designation=None):
    if "Trainer" not in frappe.get_roles():
        frappe.throw(_("Not Permitted"), frappe.PermissionError)

    filters = {"status": "Active"}
    if department:
        filters["department"] = department
    if designation:
        filters["designation"] = designation

    employees = frappe.get_all(
        "Employee",
        filters=filters,
        fields=["name", "employee_name", "department", "designation"]
    )
    return employees


@frappe.whitelist()
def bulk_assign(session, employees):
    if "Trainer" not in frappe.get_roles():
        frappe.throw(_("Not Permitted"), frappe.PermissionError)

    if isinstance(employees, str):
        employees = json.loads(employees)

    if not employees:
        return {"status": "error", "message": _("No employees selected.")}

    try:
        created_count = 0
        for emp_id in employees:
            enrollment_name = f"{session}-{emp_id}"
            if not frappe.db.exists("Training Enrollment", enrollment_name):
                doc = frappe.new_doc("Training Enrollment")
                doc.training_session = session
                doc.employee = emp_id
                doc.assignment_date = frappe.utils.today()
                doc.completion_status = "Assigned"
                doc.insert(ignore_permissions=True)
                created_count += 1
                
        return {
            "status": "success",
            "message": _("Successfully assigned {0} employees to session {1}.").format(created_count, session)
        }
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Bulk Assign Error")
        return {"status": "error", "message": str(e)}
