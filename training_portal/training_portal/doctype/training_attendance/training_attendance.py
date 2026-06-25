# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class TrainingAttendance(Document):
    def validate(self):
        self.validate_department_access()
        self.calculate_attendance_summary()
        self.validate_enrollments()

    def validate_department_access(self):
        from training_portal.training_portal.access_control import get_trainer_department
        trainer_dept = get_trainer_department()
        if trainer_dept:
            if not self.training_session:
                return
            session_course = frappe.db.get_value("Training Session", self.training_session, "course")
            if not session_course:
                return
            course_dept = frappe.db.get_value("Training Course", session_course, "department")
            if course_dept != trainer_dept:
                frappe.throw(
                    _("Access Violation: You are mapped to the '{0}' department, and cannot create or edit attendance for sessions belonging to the '{1}' department.").format(
                        trainer_dept, course_dept or "No Department"
                    ),
                    frappe.ValidationError
                )

    def calculate_attendance_summary(self):
        present = 0
        absent = 0

        for row in self.attendance_details:
            if row.attendance_status in ["Present", "Late"]:
                present += 1
            elif row.attendance_status in ["Absent", "Excused"]:
                absent += 1

        self.present_count = present
        self.absent_count = absent
        self.total_participants = len(self.attendance_details)

    def validate_enrollments(self):
        seen_employees = set()
        for row in self.attendance_details:
            if not row.employee:
                continue

            # 1. Prevent duplicate employee records in the attendance table
            if row.employee in seen_employees:
                frappe.throw(_("Employee '{0}' is listed multiple times in the attendance list.").format(row.employee))
            seen_employees.add(row.employee)

            # 2. Check if the employee is actually enrolled in this training session
            enrollment_name = f"{self.training_session}-{row.employee}"
            if not frappe.db.exists("Training Enrollment", enrollment_name):
                frappe.throw(
                    _("Employee '{0}' is not enrolled in Training Session '{1}'.").format(
                        row.employee, self.training_session
                    )
                )

    def on_submit(self):
        # 1. Update enrollment completion status
        for row in self.attendance_details:
            enrollment_name = f"{self.training_session}-{row.employee}"
            if frappe.db.exists("Training Enrollment", enrollment_name):
                enrollment = frappe.get_doc("Training Enrollment", enrollment_name)
                if row.attendance_status in ["Present", "Late"]:
                    enrollment.completion_status = "Completed"
                else:
                    enrollment.completion_status = "Not Completed"
                enrollment.save(ignore_permissions=True)

        # 2. Recalculate and store metrics
        self.update_percentage_metrics()

    def on_cancel(self):
        # 1. Revert enrollment completion status back to In Progress
        for row in self.attendance_details:
            enrollment_name = f"{self.training_session}-{row.employee}"
            if frappe.db.exists("Training Enrollment", enrollment_name):
                enrollment = frappe.get_doc("Training Enrollment", enrollment_name)
                enrollment.completion_status = "In Progress"
                enrollment.save(ignore_permissions=True)

        # 2. Recalculate and store metrics
        self.update_percentage_metrics(reset_session=True)

    def update_percentage_metrics(self, reset_session=False):
        # Calculate session percentage
        percentage = 0
        if not reset_session and self.total_participants > 0:
            percentage = (self.present_count / self.total_participants) * 100

        frappe.db.set_value("Training Session", self.training_session, "attendance_percentage", percentage)

        # Recalculate for each employee in the list
        for row in self.attendance_details:
            recalculate_employee_metrics(row.employee)

        # Recalculate for the trainer
        recalculate_trainer_metrics(self.trainer)


def recalculate_employee_metrics(employee_id):
    # Fetch all enrollments for this employee
    enrollments = frappe.get_all(
        "Training Enrollment",
        filters={"employee": employee_id},
        fields=["training_session", "completion_status"]
    )

    if not enrollments:
        frappe.db.set_value("Employee", employee_id, "attendance_percentage", 0)
        return

    # Count enrollments where attendance was submitted (status is Completed or Not Completed)
    total_evaluated = 0
    attended_count = 0
    for e in enrollments:
        if e.completion_status in ["Completed", "Not Completed"]:
            total_evaluated += 1
            if e.completion_status == "Completed":
                attended_count += 1

    percentage = (attended_count / total_evaluated * 100) if total_evaluated > 0 else 0
    frappe.db.set_value("Employee", employee_id, "attendance_percentage", percentage)


def recalculate_trainer_metrics(trainer_name):
    if not trainer_name:
        return

    # Fetch all sessions led by this trainer that have a submitted attendance record
    sessions = frappe.get_all(
        "Training Session",
        filters={
            "trainer": trainer_name,
            "status": ["!=", "Cancelled"]
        },
        fields=["name"]
    )
    session_names = [s.name for s in sessions]

    if not session_names:
        frappe.db.set_value("Trainer", trainer_name, "attendance_percentage", 0)
        return

    attendances = frappe.get_all(
        "Training Attendance",
        filters={
            "training_session": ["in", session_names],
            "docstatus": 1  # Only submitted records
        },
        fields=["total_participants", "present_count"]
    )

    total_participants = sum(a.total_participants or 0 for a in attendances)
    total_present = sum(a.present_count or 0 for a in attendances)

    percentage = (total_present / total_participants * 100) if total_participants else 0
    frappe.db.set_value("Trainer", trainer_name, "attendance_percentage", percentage)


def check_portal_permission():
    from training_portal.training_portal.access_control import check_portal_permission as check_perm
    check_perm()


def validate_session_trainer(session_name):
    roles = frappe.get_roles()
    # HR/Admin can view/edit everything
    if any(r in roles for r in ["System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"]):
        return

    from training_portal.training_portal.access_control import get_trainer_department
    trainer_dept = get_trainer_department()
    if trainer_dept:
        session_course = frappe.db.get_value("Training Session", session_name, "course")
        if session_course:
            course_dept = frappe.db.get_value("Training Course", session_course, "department")
            if course_dept != trainer_dept:
                frappe.throw(_("Access Violation: You are not authorized to manage sessions outside your department."), frappe.PermissionError)

    # Trainers can only access their own sessions
    trainer_user = frappe.session.user
    trainer_name = frappe.db.get_value("Trainer", {"user": trainer_user})
    session_trainer = frappe.db.get_value("Training Session", session_name, "trainer")

    if session_trainer != trainer_name:
        frappe.throw(_("You are not authorized to manage attendance for this session."), frappe.PermissionError)


@frappe.whitelist()
def fetch_enrollments(training_session):
    check_portal_permission()
    validate_session_trainer(training_session)

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
            "attendance_status": "Present",
            "remarks": ""
        })

    return rows


@frappe.whitelist()
def validate_attendance_csv(session_name, csv_data):
    check_portal_permission()
    validate_session_trainer(session_name)

    import csv
    from io import StringIO

    f = StringIO(csv_data)
    reader = csv.reader(f)

    headers = None
    rows = []
    errors = []

    row_idx = 0
    for csv_row in reader:
        row_idx += 1
        if not csv_row or not any(csv_row):
            continue

        csv_row = [val.strip() for val in csv_row]

        if not headers:
            headers = [h.lower() for h in csv_row]
            if not any(h in headers for h in ["employee", "employee id", "employee_id"]):
                return {
                    "status": "error",
                    "message": _("CSV is missing the employee ID column. Expected headers: employee_id, status, remarks")
                }
            continue

        emp_id = None
        status = "Present"
        remarks = ""

        for idx, h in enumerate(headers):
            if idx >= len(csv_row):
                continue
            val = csv_row[idx]

            if h in ["employee", "employee id", "employee_id"]:
                emp_id = val
            elif h in ["status", "attendance status", "attendance_status"]:
                status = val.title()
            elif h in ["remarks", "remark"]:
                remarks = val

        if not emp_id:
            errors.append(_("Row {0}: Missing Employee ID.").format(row_idx))
            continue

        if not frappe.db.exists("Employee", emp_id):
            errors.append(_("Row {0}: Employee ID '{1}' does not exist.").format(row_idx, emp_id))
            continue

        enrollment_name = f"{session_name}-{emp_id}"
        if not frappe.db.exists("Training Enrollment", enrollment_name):
            errors.append(_("Row {0}: Employee '{1}' is not enrolled in this session.").format(row_idx, emp_id))
            continue

        if status not in ["Present", "Absent", "Late", "Excused"]:
            errors.append(_("Row {0}: Invalid status '{1}' for employee '{2}'. Valid: Present, Absent, Late, Excused.").format(row_idx, status, emp_id))
            continue

        employee_name = frappe.db.get_value("Employee", emp_id, "employee_name")
        rows.append({
            "employee": emp_id,
            "employee_name": employee_name,
            "attendance_status": status,
            "remarks": remarks
        })

    if errors:
        return {
            "status": "error",
            "errors": errors
        }

    return {
        "status": "success",
        "rows": rows
    }


@frappe.whitelist()
def import_attendance_csv(session_name, rows, submit=False):
    check_portal_permission()
    validate_session_trainer(session_name)

    import json
    if isinstance(rows, str):
        rows = json.loads(rows)

    attendance_name = frappe.db.get_value("Training Attendance", {"training_session": session_name})

    if attendance_name:
        doc = frappe.get_doc("Training Attendance", attendance_name)
        if doc.docstatus == 1:
            frappe.throw(_("Attendance is already submitted for this session. Cancel it first to re-import."))
        doc.attendance_details = []
    else:
        doc = frappe.new_doc("Training Attendance")
        doc.training_session = session_name

    for r in rows:
        doc.append("attendance_details", {
            "employee": r.get("employee"),
            "attendance_status": r.get("attendance_status", "Present"),
            "remarks": r.get("remarks", "")
        })

    doc.save(ignore_permissions=True)
    if int(submit or 0):
        doc.submit()

    return {
        "status": "success",
        "message": _("Attendance uploaded successfully for {0}.").format(session_name)
    }


@frappe.whitelist()
def submit_manual_attendance(session_name, attendance_data, submit=False):
    check_portal_permission()
    validate_session_trainer(session_name)

    import json
    if isinstance(attendance_data, str):
        attendance_data = json.loads(attendance_data)

    attendance_name = frappe.db.get_value("Training Attendance", {"training_session": session_name})

    if attendance_name:
        doc = frappe.get_doc("Training Attendance", attendance_name)
        if doc.docstatus == 1:
            frappe.throw(_("Attendance has already been submitted for this session."))
        doc.attendance_details = []
    else:
        doc = frappe.new_doc("Training Attendance")
        doc.training_session = session_name

    for r in attendance_data:
        doc.append("attendance_details", {
            "employee": r.get("employee"),
            "attendance_status": r.get("attendance_status", "Present"),
            "remarks": r.get("remarks", "")
        })

    doc.save(ignore_permissions=True)
    if int(submit or 0):
        doc.submit()

    return {
        "status": "success",
        "message": _("Attendance saved successfully.")
    }
