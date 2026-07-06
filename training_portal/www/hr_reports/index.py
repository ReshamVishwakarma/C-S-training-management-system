import frappe
from frappe import _
from training_portal.training_portal.access_control import check_portal_permission

def get_context(context):
    check_portal_permission()

    roles = frappe.get_roles()
    is_admin = any(r in roles for r in ["System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User", "HR Administrator"])
    if not is_admin:
        frappe.throw(_("Not permitted to view HR reports."), frappe.PermissionError)

    context.user = frappe.session.user
    context.is_admin = True

    # Fetch departments for filters
    context.departments = frappe.get_all("Department", fields=["name"])

    # Fetch plants for filters
    context.plants = sorted(list(set(
        p.plant for p in frappe.get_all("Employee", fields=["plant"]) if p.plant
    )))

    # Fetch trainers for filters
    context.trainers = frappe.get_all("Trainer", filters={"active": 1}, fields=["name", "trainer_name"])

    # Fetch employees for filters
    context.employees = frappe.get_all(
        "Employee",
        filters={"status": "Active"},
        fields=["name", "employee_id", "employee_name"],
        order_by="employee_name ASC"
    )

    # Fetch training names/courses for filters
    context.courses = frappe.get_all(
        "Training Course",
        filters={"active": 1},
        fields=["name", "course_name"],
        order_by="course_name ASC"
    )

    # Fetch categories (Training Subcategory)
    context.categories = frappe.get_all("Training Subcategory", fields=["name"], order_by="name ASC")

    # HR Reports page is viewed by an admin/HR user who might not have a trainer record
    trainer = frappe.db.get_value(
        "Trainer",
        {"user": frappe.session.user},
        ["name", "trainer_name", "department"],
        as_dict=True
    )
    context.trainer = trainer

    return context
