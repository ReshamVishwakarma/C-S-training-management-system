import frappe
from frappe import _
from training_portal.training_portal.access_control import check_portal_permission

def get_context(context):
    check_portal_permission()

    user_id = frappe.session.user
    context.user = user_id

    # Resolve Employee profile
    employee_key = frappe.db.get_value("Employee", {"user": user_id})
    if not employee_key and user_id == "Administrator":
        employee_key = frappe.db.get_value("Employee", {"user": "priya@test.com"})

    if employee_key:
        emp_doc = frappe.get_doc("Employee", employee_key)
        context.employee_name = emp_doc.employee_name
        context.employee_id = emp_doc.employee_id
        
        # Display Employee profile info
        context.profile_type = "Employee"
        context.profile_info = {
            "full_name": emp_doc.employee_name,
            "employee_id": emp_doc.employee_id or "-",
            "email": emp_doc.email or "-",
            "department": emp_doc.department or "-",
            "designation": emp_doc.designation or "-",
            "mobile_no": emp_doc.mobile_number or "-",
            "location": emp_doc.location or "-",
            "plant": emp_doc.plant or "-",
            "reporting_manager": emp_doc.reporting_manager or "-",
            "employment_type": emp_doc.employment_type or "-",
            "date_of_joining": emp_doc.date_of_joining,
            "status": emp_doc.status or "Active",
            "active": 1 if emp_doc.status == "Active" else 0
        }
    else:
        # Fallback to User document
        user_doc = frappe.get_doc("User", user_id)
        context.employee_name = user_doc.full_name or user_doc.first_name or "Employee User"
        context.employee_id = "-"
        
        context.profile_type = "User"
        context.profile_info = {
            "full_name": user_doc.full_name or user_doc.first_name or "Employee User",
            "employee_id": "-",
            "email": user_doc.email or "-",
            "department": "-",
            "designation": "-",
            "mobile_no": user_doc.mobile_no or user_doc.phone or "-",
            "location": "-",
            "plant": "-",
            "reporting_manager": "-",
            "employment_type": "-",
            "date_of_joining": None,
            "status": "Active" if user_doc.enabled else "Inactive",
            "active": user_doc.enabled
        }

    return context
