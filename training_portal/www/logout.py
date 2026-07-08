import frappe

def get_context(context):
    user_email = frappe.session.user
    if user_email != "Guest":
        frappe.cache().delete_value(f"login_otp:{user_email}")
        frappe.cache().delete_value(f"reset_otp:{user_email}")
        
        # Destroy Frappe session
        frappe.local.login_manager.logout()
        
    frappe.local.flags.redirect_location = "/login"
    raise frappe.Redirect
