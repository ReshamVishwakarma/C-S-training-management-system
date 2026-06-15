import frappe

def get_context(context):

    if "Department Manager" not in frappe.get_roles():
       frappe.throw("Not Permitted")

    context.user = frappe.session.user