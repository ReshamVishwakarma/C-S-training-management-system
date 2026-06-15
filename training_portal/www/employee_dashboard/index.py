import frappe

def get_context(context):

    user = frappe.session.user

    context.user = user

    employee = frappe.db.get_value(
        "Employee",
        {"user": user},
        [
            "name",
            "employee_name",
            "department",
            "designation"
        ],
        as_dict=True
    )

    context.employee = employee

    if not employee:
        context.total_trainings = 0
        context.completed_trainings = 0
        context.upcoming_trainings = []
        return context

    context.total_trainings = frappe.db.count(
        "Training Enrollment",
        {
            "employee": employee.name
        }
    )

    context.completed_trainings = frappe.db.count(
        "Training Enrollment",
        {
            "employee": employee.name,
            "completion_status": "Completed"
        }
    )

    context.certificates = 0
    context.attendance_percentage = 0

    context.upcoming_trainings = frappe.get_all(
        "Training Session",
        fields=[
            "training_name",
            "training_date",
            "trainer",
            "training_mode"
        ],
        order_by="training_date asc",
        limit=5
    )

     # My Training Enrollments

    context.my_trainings = frappe.get_all(
        "Training Enrollment",
        filters={
            "employee": employee.name
        },
        fields=[
            "training_session",
            "completion_status",
            "assignment_date"
        ]
    )

    return context