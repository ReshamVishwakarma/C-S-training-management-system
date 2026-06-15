# import frappe

# def get_context(context):

#     if "HR Administrator" not in frappe.get_roles():
#         frappe.throw("Not Permitted")
        
#     context.user = frappe.session.user

#     context.total_employees = frappe.db.count("Employee")
#     context.total_trainers = frappe.db.count("Trainer")
#     context.total_courses = frappe.db.count("Training Course")

import frappe

def get_context(context):

    if "HR Administrator" not in frappe.get_roles():
        frappe.throw("Not Permitted")

    context.user = frappe.session.user

    context.total_employees = frappe.db.count("Employee")
    context.total_trainers = frappe.db.count("Trainer")
    context.total_courses = frappe.db.count("Training Course")
    context.total_sessions = frappe.db.count("Training Session")
    context.total_departments = frappe.db.count("Department")

    context.recent_sessions = frappe.get_all(
    "Training Session",
    fields=[
        "name",
        "training_name",
        "training_date",
        "status"
    ],
    order_by="creation desc",
    limit=5
   )
    
    context.departments = frappe.get_all(
       "Department",
       fields=["department_name"],
       order_by="department_name"
    )

    context.upcoming_sessions = frappe.get_all(
       "Training Session",
       filters={
       "status": "Scheduled"
       },
       fields=[
        "training_name",
        "training_date",
        "trainer",
        "department"
       ],
       order_by="training_date asc",
       limit=5
    )