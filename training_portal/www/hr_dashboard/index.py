import frappe

def get_context(context):

    roles = frappe.get_roles()
    is_admin = any(r in roles for r in ["System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User", "HR Administrator"])
    if not is_admin:
        frappe.throw("Not Permitted", frappe.PermissionError)
        
    context.user = frappe.session.user

    context.total_employees = frappe.db.count("Employee")
    context.total_trainers = frappe.db.count("Trainer")
    context.total_courses = frappe.db.count("Training Course")