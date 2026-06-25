# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def get_trainer_department():
    roles = frappe.get_roles()
    # Admins/Managers bypass restrictions
    if any(r in roles for r in ["System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"]):
        return None

    if "Trainer" in roles:
        trainer_user = frappe.session.user
        trainer_dept = frappe.db.get_value("Trainer", {"user": trainer_user}, "department")
        if not trainer_dept:
            frappe.throw(_("Trainer profile not mapped to a department. Contact Administrator."), frappe.PermissionError)
        return trainer_dept

    return None

def check_portal_permission():
    roles = frappe.get_roles()
    if not (any(r in roles for r in ["Trainer", "System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"])):
        frappe.throw(_("Not Permitted"), frappe.PermissionError)


def filter_courses_by_dept(filters, trainer_dept):
    if trainer_dept:
        filters["department"] = trainer_dept
    return filters

def filter_sessions_by_dept(filters, trainer_dept):
    if trainer_dept:
        courses = [c.name for c in frappe.get_all("Training Course", filters={"department": trainer_dept})]
        filters["course"] = ["in", courses]
    return filters

def filter_enrollments_by_dept(filters, trainer_dept):
    if trainer_dept:
        courses = [c.name for c in frappe.get_all("Training Course", filters={"department": trainer_dept})]
        sessions = [s.name for s in frappe.get_all("Training Session", filters={"course": ["in", courses]})]
        filters["training_session"] = ["in", sessions]
    return filters

def filter_attendances_by_dept(filters, trainer_dept):
    if trainer_dept:
        courses = [c.name for c in frappe.get_all("Training Course", filters={"department": trainer_dept})]
        sessions = [s.name for s in frappe.get_all("Training Session", filters={"course": ["in", courses]})]
        filters["training_session"] = ["in", sessions]
    return filters
