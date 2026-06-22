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
        context.certificates = 0
        context.attendance_percentage = 0
        context.present_sessions = 0
        context.absent_sessions = 0
        context.upcoming_trainings = []
        context.my_trainings = []

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

    present_sessions = frappe.db.count(
        "Attendance detail",
        {
            "employee": employee.name,
            "attendance_status": ["in", ["Present", "Late"]]
        }
    )

    absent_sessions = frappe.db.count(
        "Attendance detail",
        {
            "employee": employee.name,
            "attendance_status": "Absent"
        }
    )

    total_sessions = present_sessions + absent_sessions

    if total_sessions:
        context.attendance_percentage = round(
            (present_sessions / total_sessions) * 100,
            2
        )
    else:
        context.attendance_percentage = 0

    context.present_sessions = present_sessions
    context.absent_sessions = absent_sessions

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

    context.attendance_history = frappe.get_all(
        "Attendance detail",
        filters={
            "employee": employee.name
        },
        fields=[
            "parent",
            "attendance_status"
        ]
    )

    return context
