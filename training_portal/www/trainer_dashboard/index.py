import frappe

def get_context(context):

    if "Trainer" not in frappe.get_roles():
       frappe.throw("Not Permitted")

    context.user = frappe.session.user