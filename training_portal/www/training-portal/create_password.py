import frappe

no_cache = 1

def get_context(context):
    context.email = frappe.form_dict.get("email") or ""
    context.role = frappe.form_dict.get("role") or ""
    
    # If email already has a password, redirect to login page
    if context.email:
        res = frappe.db.sql("select password from `__Auth` where doctype='User' and name=%s and fieldname='password'", (context.email,))
        if len(res) > 0 and res[0][0] is not None:
            frappe.local.flags.redirect_location = "/training-portal/login"
            raise frappe.Redirect
            
    return context
