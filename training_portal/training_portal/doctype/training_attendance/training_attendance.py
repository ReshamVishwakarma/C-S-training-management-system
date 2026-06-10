import frappe
from frappe.model.document import Document


class TrainingAttendance(Document):
    pass


@frappe.whitelist()
def fetch_enrollments(training_session):
    enrollments = frappe.get_all(
        "Training Enrollment",
        filters={"training_session": training_session},
        fields=["employee"]
    )

    rows = []

    for enrollment in enrollments:
        employee_name = frappe.db.get_value(
            "Employee",
            enrollment.employee,
            "employee_name"
        )

        rows.append({
            "employee": enrollment.employee,
            "employee_name": employee_name,
            "attendance_status": "Present"
        })

    return rows
