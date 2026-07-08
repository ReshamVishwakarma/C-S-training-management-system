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

        # Also add unknown employee codes
        unknown_count = 0
        unknown_logs = self.get("unknown_employee_logs")
        if unknown_logs:
            try:
                import json
                logs = json.loads(unknown_logs)
                unknown_count = len(logs)
                for log in logs:
                    status = log.get("attendance_status", "Present")
                    if status in ["Present", "Late"]:
                        present += 1
                    elif status in ["Absent", "Excused"]:
                        absent += 1
            except Exception:
                pass

        self.present_count = present
        self.absent_count = absent
        self.total_participants = len(self.attendance_details) + unknown_count

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
    
    # Gather debug info
    debug_info = {}
    debug_info["session_name"] = session_name
    debug_info["frappe.session.user"] = frappe.session.user
    debug_info["roles"] = roles
    debug_info["is_admin_or_manager"] = any(r in roles for r in ["System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"])
    
    from training_portal.training_portal.access_control import get_trainer_department
    try:
        trainer_dept = get_trainer_department()
        debug_info["get_trainer_department_result"] = trainer_dept
    except Exception as e:
        debug_info["get_trainer_department_error"] = str(e)
        trainer_dept = None
        
    session_course = frappe.db.get_value("Training Session", session_name, "course")
    debug_info["session_course"] = session_course
    if session_course:
        course_dept = frappe.db.get_value("Training Course", session_course, "department")
        debug_info["course_dept"] = course_dept
        if trainer_dept and course_dept != trainer_dept:
            debug_info["department_check_passed"] = False
        else:
            debug_info["department_check_passed"] = True

    trainer_user = frappe.session.user
    trainer_by_user = frappe.db.get_value("Trainer", {"user": trainer_user})
    trainer_by_email = frappe.db.get_value("Trainer", {"email": trainer_user})
    
    user_email = None
    trainer_by_user_email = None
    if "@" not in trainer_user:
        user_email = frappe.db.get_value("User", trainer_user, "email")
        if user_email:
            trainer_by_user_email = frappe.db.get_value("Trainer", {"user": user_email}) or frappe.db.get_value("Trainer", {"email": user_email})
    trainer_by_name = frappe.db.get_value("Trainer", {"name": trainer_user})
    
    debug_info["trainer_lookups"] = {
        "trainer_by_user": trainer_by_user,
        "trainer_by_email": trainer_by_email,
        "user_email": user_email,
        "trainer_by_user_email": trainer_by_user_email,
        "trainer_by_name": trainer_by_name
    }
    
    trainer_name = trainer_by_user or trainer_by_email or trainer_by_user_email or trainer_by_name
    debug_info["resolved_trainer_name"] = trainer_name
    
    if trainer_name:
        trainer_doc = frappe.db.get_value("Trainer", trainer_name, ["name", "trainer_name", "user", "email", "department"], as_dict=True)
        debug_info["resolved_trainer_document"] = trainer_doc
    else:
        debug_info["resolved_trainer_document"] = None
        
    session_trainer = frappe.db.get_value("Training Session", session_name, "trainer")
    session_owner = frappe.db.get_value("Training Session", session_name, "owner")
    debug_info["session_trainer"] = session_trainer
    debug_info["session_owner"] = session_owner
    
    match = False
    if trainer_name:
        if session_trainer == trainer_name:
            match = True
            debug_info["match_type"] = "exact_match"
        else:
            actual_trainer_name = frappe.db.get_value("Trainer", trainer_name, "trainer_name")
            debug_info["actual_trainer_name_field"] = actual_trainer_name
            if actual_trainer_name == session_trainer:
                match = True
                debug_info["match_type"] = "trainer_name_field_match"
                
    debug_info["match_result"] = match
    
    # Write debug to log file
    import json
    try:
        with open("/home/resham125/frappe-projects/frappe-bench/logs/permission_debug.json", "w") as f:
            json.dump(debug_info, f, indent=2)
    except Exception:
        pass

    # HR/Admin can view/edit everything
    if any(r in roles for r in ["System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"]):
        return

    if trainer_dept:
        if session_course:
            course_dept = frappe.db.get_value("Training Course", session_course, "department")
            if course_dept != trainer_dept:
                frappe.throw(_("Access Violation: You are not authorized to manage sessions outside your department."), frappe.PermissionError)

    if not match:
        frappe.throw(_("You are not authorized to manage attendance for this session."), frappe.PermissionError)


@frappe.whitelist()
def fetch_enrollments(training_session):
    check_portal_permission()
    validate_session_trainer(training_session)

    attendance_name = frappe.db.get_value("Training Attendance", {"training_session": training_session})
    existing_details = {}
    docstatus = 0
    uploaded_filename = None
    upload_timestamp = None
    unknown_employee_logs = []

    if attendance_name:
        doc = frappe.get_doc("Training Attendance", attendance_name)
        docstatus = doc.docstatus
        uploaded_filename = doc.uploaded_filename
        upload_timestamp = doc.upload_timestamp
        if doc.unknown_employee_logs:
            try:
                import json
                unknown_employee_logs = json.loads(doc.unknown_employee_logs)
            except Exception:
                unknown_employee_logs = []
        for d in doc.attendance_details:
            existing_details[d.employee] = {
                "attendance_status": d.attendance_status,
                "remarks": d.remarks or ""
            }

    enrollments = frappe.get_all(
        "Training Enrollment",
        filters={"training_session": training_session},
        fields=["employee"]
    )

    rows = []
    # 1. Load enrolled employees
    for enrollment in enrollments:
        emp = frappe.db.get_value(
            "Employee",
            enrollment.employee,
            ["name", "employee_id", "employee_name", "email", "department", "designation", "plant", "location", "reporting_manager", "status"],
            as_dict=True
        ) or {}
        
        # Look up reporting manager name
        mgr_name = "-"
        if emp.get("reporting_manager"):
            mgr_name = frappe.db.get_value("Employee", emp.reporting_manager, "employee_name") or "-"

        status = "Present"
        remarks = ""

        if enrollment.employee in existing_details:
            status = existing_details[enrollment.employee]["attendance_status"]
            remarks = existing_details[enrollment.employee]["remarks"]

        rows.append({
            "employee": enrollment.employee,
            "employee_id": emp.get("employee_id") or "-",
            "employee_name": emp.get("employee_name") or "-",
            "email": emp.get("email") or "-",
            "department": emp.get("department") or "-",
            "designation": emp.get("designation") or "-",
            "plant": emp.get("plant") or "-",
            "location": emp.get("location") or "-",
            "reporting_manager": emp.get("reporting_manager") or "-",
            "reporting_manager_name": mgr_name,
            "status": emp.get("status") or "-",
            "attendance_status": status,
            "remarks": remarks,
            "is_temporary": 0,
            "temporary_employee_code": ""
        })

    # 2. Append unknown employee logs
    for log in unknown_employee_logs:
        rows.append({
            "employee": "",
            "employee_name": "N/A",
            "email": "N/A",
            "department": "N/A",
            "designation": "N/A",
            "plant": "N/A",
            "location": "N/A",
            "reporting_manager": "N/A",
            "reporting_manager_name": "N/A",
            "status": "N/A",
            "attendance_status": log.get("attendance_status", "Present"),
            "remarks": log.get("remarks", ""),
            "is_temporary": 1,
            "temporary_employee_code": log.get("employee_code", "")
        })

    # Fetch training session metadata
    session_details = {}
    if frappe.db.exists("Training Session", training_session):
        session_doc = frappe.get_doc("Training Session", training_session)
        session_data = session_doc.as_dict()

        subcategory = frappe.db.get_value("Training Course", session_data.get("course"), "category")
        session_data["subcategory"] = subcategory or "-"

        # Calculate end time
        end_time = "-"
        start_formatted = "-"
        start_time = session_data.get("start_time")
        duration_hours = session_data.get("duration_hours")
        training_mode = session_data.get("training_mode")
        meeting_link = session_data.get("meeting_link")
        location = session_data.get("location")

        if start_time and duration_hours:
            try:
                import datetime
                if isinstance(start_time, datetime.timedelta):
                    start_sec = start_time.total_seconds()
                    start_dt = datetime.datetime.min + datetime.timedelta(seconds=start_sec)
                else:
                    start_dt = datetime.datetime.strptime(str(start_time), "%H:%M:%S")
                end_dt = start_dt + datetime.timedelta(hours=float(duration_hours))
                end_time = end_dt.strftime("%I:%M %p")
                start_formatted = start_dt.strftime("%I:%M %p")
            except Exception:
                start_formatted = str(start_time)
                end_time = "-"
        else:
            start_formatted = str(start_time or "-")

        session_data["start_time_formatted"] = start_formatted
        session_data["end_time"] = end_time
        session_data["venue_or_link"] = meeting_link if training_mode == "Online" else location

        # Convert all values to JSON-serializable formats explicitly to be absolutely safe
        serialized_details = {}
        for k, v in session_data.items():
            if hasattr(v, "strftime"):
                serialized_details[k] = str(v)
            elif hasattr(v, "total_seconds"):
                serialized_details[k] = str(v)
            else:
                serialized_details[k] = v
        session_details = serialized_details

    return {
        "rows": rows,
        "docstatus": docstatus,
        "uploaded_filename": uploaded_filename,
        "upload_timestamp": upload_timestamp,
        "session_details": session_details
    }


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
def submit_manual_attendance(session_name, attendance_data, submit=False, uploaded_filename=None, upload_timestamp=None):
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

    enrolled_rows = []
    unknown_rows = []

    for r in attendance_data:
        is_temp = int(r.get("is_temporary") or 0)
        if is_temp or not r.get("employee"):
            unknown_rows.append({
                "employee_code": r.get("temporary_employee_code") or r.get("employee"),
                "attendance_status": r.get("attendance_status", "Present"),
                "remarks": r.get("remarks", "")
            })
        else:
            enrolled_rows.append({
                "employee": r.get("employee"),
                "attendance_status": r.get("attendance_status", "Present"),
                "remarks": r.get("remarks", "")
            })

    # Save enrolled rows in child table
    for r in enrolled_rows:
        # Auto-enroll valid employees who are not enrolled
        enrollment_name = f"{session_name}-{r['employee']}"
        if not frappe.db.exists("Training Enrollment", enrollment_name):
            enrollment = frappe.new_doc("Training Enrollment")
            enrollment.training_session = session_name
            enrollment.employee = r["employee"]
            enrollment.completion_status = "Completed" if r["attendance_status"] in ["Present", "Late"] else "Not Completed"
            enrollment.save(ignore_permissions=True)

        doc.append("attendance_details", {
            "employee": r["employee"],
            "attendance_status": r["attendance_status"],
            "remarks": r["remarks"]
        })

    # Save unknown rows in Long Text JSON field
    doc.unknown_employee_logs = json.dumps(unknown_rows)
    
    # Store metadata
    doc.marked_by = frappe.session.user
    if uploaded_filename:
        doc.uploaded_filename = uploaded_filename
    if upload_timestamp:
        doc.upload_timestamp = upload_timestamp

    doc.save(ignore_permissions=True)
    if int(submit or 0):
        doc.submit()

    return {
        "status": "success",
        "message": _("Attendance saved successfully.")
    }


@frappe.whitelist()
def check_employee_codes(codes):
    import json
    if isinstance(codes, str):
        codes = json.loads(codes)
        
    results = {}
    for code in codes:
        # Check by primary key name first
        emp = frappe.db.get_value(
            "Employee",
            code,
            ["name", "employee_id", "employee_name", "email", "department", "designation", "plant", "location", "reporting_manager", "status"],
            as_dict=True
        )
        if not emp:
            # Check by employee_id field
            emp_name = frappe.db.get_value("Employee", {"employee_id": code}, "name")
            if emp_name:
                emp = frappe.db.get_value(
                    "Employee",
                    emp_name,
                    ["name", "employee_id", "employee_name", "email", "department", "designation", "plant", "location", "reporting_manager", "status"],
                    as_dict=True
                )
        if emp:
            mgr_name = "-"
            if emp.get("reporting_manager"):
                mgr_name = frappe.db.get_value("Employee", emp.reporting_manager, "employee_name") or "-"
            
            results[code] = {
                "exists": True,
                "employee": emp.name,
                "employee_name": emp.employee_name or "-",
                "email": emp.email or "-",
                "department": emp.department or "-",
                "designation": emp.designation or "-",
                "plant": emp.plant or "-",
                "location": emp.location or "-",
                "reporting_manager": emp.reporting_manager or "-",
                "reporting_manager_name": mgr_name,
                "status": emp.status or "-"
            }
        else:
            results[code] = {
                "exists": False
            }
    return results
