import frappe

def get_context(context):

    roles = frappe.get_roles(frappe.session.user)

    if "HR Administrator" in roles:
        frappe.local.flags.redirect_location = "/hr_dashboard"
        raise frappe.Redirect

    elif "Department Manager" in roles:
        frappe.local.flags.redirect_location = "/manager_dashboard"
        raise frappe.Redirect

    elif "Trainer" in roles:
        frappe.local.flags.redirect_location = "/trainer_dashboard"
        raise frappe.Redirect

    else:
        frappe.local.flags.redirect_location = "/employee_dashboard"
        raise frappe.Redirect