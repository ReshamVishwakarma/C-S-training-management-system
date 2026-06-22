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

    selected_department = frappe.form_dict.get("department")
    from_date = frappe.form_dict.get("from_date")
    to_date = frappe.form_dict.get("to_date")

    context.from_date = from_date
    context.to_date = to_date
    context.selected_department = selected_department

    filters = {}

    if selected_department:
      filters["department"] = selected_department

    if from_date and to_date:
      filters["training_date"] = ["between", [from_date, to_date]]

    context.total_employees = frappe.db.count("Employee")
    context.total_trainers = frappe.db.count("Trainer")
    context.total_courses = frappe.db.count("Training Course")
    context.total_sessions = frappe.db.count("Training Session")
    context.total_departments = frappe.db.count("Department")

    attendance_data = frappe.db.sql("""
      SELECT
        SUM(total_participants) as total_participants,
        SUM(present_count) as total_present
      FROM `tabTraining Attendance`
    """, as_dict=True)[0]

    if attendance_data.total_participants:
      context.attendance_percentage = round(
        (attendance_data.total_present /
         attendance_data.total_participants) * 100,
        1
      )
    else:
      context.attendance_percentage = 0

    context.recent_sessions = frappe.get_all(
    "Training Session",
    filters=filters,
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
       fields=["name", "department_name"],
       order_by="department_name"
    )

    upcoming_filters = {
      "status": "Scheduled"
    }

    if selected_department:
       upcoming_filters["department"] = selected_department

    if from_date and to_date:
       upcoming_filters["training_date"] = ["between", [from_date, to_date]]

    context.upcoming_sessions = frappe.get_all(
       "Training Session",
       filters=upcoming_filters,
       fields=[
           "training_name",
           "training_date",
           "trainer",
           "department"
       ],
       order_by="training_date asc",
       limit=5
    )

    if selected_department:
      context.department_summary = frappe.db.sql("""
        SELECT
            department,
            COUNT(name) as training_count
        FROM `tabTraining Session`
        WHERE department = %s
        GROUP BY department
        ORDER BY training_count DESC
      """, (selected_department,), as_dict=True)

    else:
       context.department_summary = frappe.db.sql("""
        SELECT
            department,
            COUNT(name) as training_count
        FROM `tabTraining Session`
        GROUP BY department
        ORDER BY training_count DESC
    """, as_dict=True)