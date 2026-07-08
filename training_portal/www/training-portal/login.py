import frappe

no_cache = 1

def get_context(context):
    # If unauthenticated request is redirected from desk/app, send them to system-login
    redirect_to = frappe.form_dict.get("redirect-to")
    if redirect_to and any(x in redirect_to for x in ["/app", "app", "desk"]):
        frappe.local.flags.redirect_location = f"/system-login?redirect-to={frappe.utils.cstr(redirect_to)}"
        raise frappe.Redirect

    if frappe.session.user != "Guest":
        roles = frappe.get_roles(frappe.session.user)
        if any(r in roles for r in ["HR Administrator", "System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"]):
            frappe.local.flags.redirect_location = "/hr_dashboard"
            raise frappe.Redirect
        elif "Trainer" in roles:
            frappe.local.flags.redirect_location = "/trainer_dashboard"
            raise frappe.Redirect
        elif "Employee" in roles or "Trainee" in roles:
            frappe.local.flags.redirect_location = "/employee_dashboard"
            raise frappe.Redirect

    return context
