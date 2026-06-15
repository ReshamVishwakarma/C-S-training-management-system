import frappe

def get_context(context):

    if "HR Administrator" not in frappe.get_roles():
        frappe.throw("Not Permitted")
        
    context.user = frappe.session.user

    context.total_employees = frappe.db.count("Employee")
    context.total_trainers = frappe.db.count("Trainer")
    context.total_courses = frappe.db.count("Training Course")