import frappe

no_cache = 1

def get_context(context):
    context.email = frappe.form_dict.get("email") or ""
    return context
