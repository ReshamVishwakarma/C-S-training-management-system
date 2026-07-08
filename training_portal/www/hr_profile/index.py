import frappe
from frappe import _
from training_portal.training_portal.access_control import check_portal_permission

def get_context(context):
    check_portal_permission()

    roles = frappe.get_roles()
    is_admin = any(r in roles for r in ["System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User", "HR Administrator"])
    if not is_admin:
        frappe.throw(_("Not permitted to view HR profile."), frappe.PermissionError)

    user_id = frappe.session.user
    context.user = user_id

    user_doc = frappe.get_doc("User", user_id)
    
    context.user_info = {
        "full_name": user_doc.full_name or user_doc.first_name or "HR User",
        "email": user_doc.email,
        "username": user_doc.username or "-",
        "user_type": user_doc.user_type,
        "enabled": user_doc.enabled,
        "last_login": user_doc.last_login or "-",
        "creation": user_doc.creation,
        "time_zone": user_doc.time_zone or "UTC",
        "language": user_doc.language or "en",
        "mobile_no": user_doc.mobile_no or user_doc.phone or "-"
    }

    target_key_roles = {"HR Administrator", "System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"}
    key_roles = sorted([r for r in roles if r in target_key_roles])
    other_roles = sorted([r for r in roles if r not in target_key_roles and r not in ["All", "Guest"]])

    if not key_roles and other_roles:
        key_roles = [other_roles.pop(0)]

    context.key_roles = key_roles
    context.other_roles = other_roles

    return context
