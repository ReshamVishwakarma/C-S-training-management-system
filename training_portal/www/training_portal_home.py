# import frappe

# no_cache = 1
# sitemap = 1

# def get_context(context):
#     context.total_sessions = frappe.db.count("Training Session")
#     context.total_trainers = frappe.db.count("Trainer")
#     context.total_courses = frappe.db.count("Training Course")
#     context.training_sessions = frappe.get_all(
#         "Training Session",
#         filters={"status": ["in", ["Scheduled", "Ongoing"]]},
#         fields=["name", "training_name", "training_date",
#                 "training_mode", "trainer", "department", "status"]
#     )
import frappe

def get_context(context):

    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

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

    elif "Employee" in roles:
        frappe.local.flags.redirect_location = "/employee_dashboard"
        raise frappe.Redirect