# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from training_portal.training_portal.access_control import get_trainer_department, check_portal_permission


def get_context(context):
    check_portal_permission()

    user = frappe.session.user
    context.user = user

    trainer = frappe.db.get_value(
        "Trainer",
        {"user": user},
        ["name", "trainer_name", "department"],
        as_dict=True
    )
    context.trainer = trainer

    trainer_dept = get_trainer_department()
    context.trainer_dept = trainer_dept

    # Fetch all departments
    context.departments = frappe.get_all(
        "Department",
        fields=["name", "department_name"]
    )

    # Fetch active subcategories dynamically (restricted by department)
    if trainer_dept:
        context.subcategories = frappe.get_all(
            "Training Subcategory",
            filters=[
                ["is_active", "=", 1],
                ["department", "in", [trainer_dept, "", None]]
            ],
            fields=["name", "subcategory_name"]
        )
    else:
        context.subcategories = frappe.get_all(
            "Training Subcategory",
            filters={"is_active": 1},
            fields=["name", "subcategory_name"]
        )

    return context


@frappe.whitelist()
def create_new_course(course_name, category, description, department):
    check_portal_permission()

    try:
        # Department Validation
        trainer_dept = get_trainer_department()
        if trainer_dept:
            if department != trainer_dept:
                frappe.throw(_("Access Violation: You are not authorized to create courses for departments outside your own ({0}).").format(trainer_dept))

        doc = frappe.new_doc("Training Course")
        doc.course_name = course_name
        doc.category = category
        doc.description = description
        doc.department = department
        doc.active = 1
        doc.status = "Active"

        doc.insert(ignore_permissions=True)
        return {
            "status": "success",
            "message": _("Training Course '{0}' created successfully in catalog.").format(course_name)
        }
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Create Course Error")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist()
def create_new_subcategory(subcategory_name, department=None, description=None):
    check_portal_permission()

    try:
        trainer_dept = get_trainer_department()
        if trainer_dept:
            # Enforce department checks for Trainer users
            if department and department != trainer_dept:
                frappe.throw(_("Access Violation: You are not authorized to create subcategories for departments outside your own ({0}).").format(trainer_dept))
            # Set to trainer's department automatically
            department = trainer_dept

        doc = frappe.new_doc("Training Subcategory")
        doc.subcategory_name = subcategory_name
        doc.department = department
        doc.description = description
        doc.is_active = 1
        doc.insert(ignore_permissions=True)

        return {
            "status": "success",
            "message": _("Training Subcategory '{0}' created successfully.").format(subcategory_name),
            "subcategory_name": doc.name
        }
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Create Subcategory Error")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist()
def get_active_subcategories():
    check_portal_permission()

    try:
        trainer_dept = get_trainer_department()
        if trainer_dept:
            subcategories = frappe.get_all(
                "Training Subcategory",
                filters=[
                    ["is_active", "=", 1],
                    ["department", "in", [trainer_dept, "", None]]
                ],
                fields=["name", "subcategory_name"]
            )
        else:
            subcategories = frappe.get_all(
                "Training Subcategory",
                filters={"is_active": 1},
                fields=["name", "subcategory_name"]
            )

        return {
            "status": "success",
            "subcategories": subcategories
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
