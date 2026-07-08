import frappe
from frappe.www.login import get_context as frappe_login_get_context

no_cache = 1

def get_context(context):
    frappe_login_get_context(context)
    context.template = "www/login.html"
    return context
