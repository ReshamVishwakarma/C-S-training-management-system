import frappe
from frappe.model.document import Document


class TrainingAttendance(Document):

    def validate(self):
        self.calculate_attendance_summary()

    def calculate_attendance_summary(self):

        present = 0
        absent = 0

        for row in self.attendance_details:

            if row.attendance_status in ["Present", "Late"]:
                present += 1

            elif row.attendance_status == "Absent":
                absent += 1

        self.present_count = present
        self.absent_count = absent
        self.total_participants = len(self.attendance_details)


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

def calculate_attendance_summary(self):

    present = 0
    absent = 0

    for row in self.attendance_details:

        if row.attendance_status in ["Present", "Late"]:
            present += 1

        elif row.attendance_status == "Absent":
            absent += 1

    self.present_count = present
    self.absent_count = absent
    self.total_participants = len(self.attendance_details)
