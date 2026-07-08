# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe import _
import json
from training_portal.training_portal.access_control import get_trainer_department, check_portal_permission


def get_context(context):
    check_portal_permission()

    user = frappe.session.user
    context.user = user

    trainer = frappe.db.get_value(
        "Trainer",
        {"user": user},
        ["name", "trainer_name", "department"],
        as_dict=True
    )
    context.trainer = trainer

    trainer_dept = get_trainer_department()
    context.trainer_dept = trainer_dept

    # Fetch active courses (filtered by trainer's department)
    course_filters = {"status": "Active"}
    trainer_filters = {"active": 1}
    if trainer_dept:
        course_filters["department"] = trainer_dept
        trainer_filters["department"] = trainer_dept

    context.courses = frappe.get_all(
        "Training Course",
        filters=course_filters,
        fields=["name", "course_name", "duration_hours", "description"]
    )

    # Fetch all departments
    context.departments = frappe.get_all(
        "Department",
        fields=["name", "department_name"]
    )

    # Fetch unique designations
    designation_records = frappe.db.sql(
        "select distinct designation from tabEmployee where designation is not null and designation != '' order by designation asc",
        as_dict=True
    )
    context.designations = [r.designation for r in designation_records]

    # Fetch unique plants
    plant_records = frappe.db.sql(
        "select distinct plant from tabEmployee where plant is not null and plant != '' order by plant asc",
        as_dict=True
    )
    context.plants = [r.plant for r in plant_records]

    # Fetch unique locations
    location_records = frappe.db.sql(
        "select distinct location from tabEmployee where location is not null and location != '' order by location asc",
        as_dict=True
    )
    context.locations = [r.location for r in location_records]

    # Fetch distinct assigned managers
    manager_records = frappe.db.sql(
        """
        select distinct e.reporting_manager as name, m.employee_name
        from tabEmployee e
        join tabEmployee m on e.reporting_manager = m.name
        where e.reporting_manager is not null and e.reporting_manager != ''
        order by m.employee_name asc
        """,
        as_dict=True
    )
    context.managers = manager_records

    # Static employee statuses
    context.statuses = ["Active", "Inactive", "On Leave", "Resigned", "Transferred"]

    return context


@frappe.whitelist()
def get_employees_list(department=None, designation=None, plant=None, location=None, reporting_manager=None, status=None, search_term=None):
    check_portal_permission()

    filters = {}
    if department:
        filters["department"] = department
    if designation:
        filters["designation"] = designation
    if plant:
        filters["plant"] = plant
    if location:
        filters["location"] = location
    if reporting_manager:
        filters["reporting_manager"] = reporting_manager
    if status:
        filters["status"] = status

    or_filters = None
    if search_term:
        search_term = f"%{search_term}%"
        or_filters = [
            ["name", "like", search_term],
            ["employee_name", "like", search_term],
            ["employee_id", "like", search_term],
            ["email", "like", search_term]
        ]

    employees = frappe.get_all(
        "Employee",
        filters=filters,
        or_filters=or_filters,
        fields=[
            "name",
            "employee_name",
            "employee_id",
            "email",
            "department",
            "designation",
            "plant",
            "location",
            "reporting_manager",
            "status"
        ],
        order_by="employee_name asc"
    )

    # Fetch manager name mappings for readable display
    manager_ids = [e.reporting_manager for e in employees if e.reporting_manager]
    manager_map = {}
    if manager_ids:
        managers = frappe.get_all(
            "Employee",
            filters={"name": ["in", manager_ids]},
            fields=["name", "employee_name"]
        )
        manager_map = {m.name: m.employee_name for m in managers}

    for emp in employees:
        emp["reporting_manager_name"] = manager_map.get(emp.reporting_manager) or emp.reporting_manager or "-"

    return employees


@frappe.whitelist()
def bulk_schedule_and_assign(course, training_date, start_time, duration_hours, training_mode, employees, location=None, meeting_link=None, trainer=None):
    check_portal_permission()

    if isinstance(employees, str):
        employees = json.loads(employees)

    if not employees:
        return {"status": "error", "message": _("No employees selected.")}

    try:
        if not trainer:
            trainer = frappe.db.get_value("Trainer", {"user": frappe.session.user}, "name")
        if not trainer:
            frappe.throw(_("Session Trainer Error: Current logged-in user is not mapped to any Trainer record."))

        # Validate that course exists and is Active
        course_doc = frappe.get_doc("Training Course", course)
        if course_doc.get("status") != "Active":
            frappe.throw(_("Catalog Entry Error: Only Active courses can be scheduled. Current status is '{0}'.").format(course_doc.get("status") or "Inactive"))

        # Department Validation
        trainer_dept = get_trainer_department()
        if trainer_dept:
            course_dept = course_doc.department
            if course_dept != trainer_dept:
                frappe.throw(_("Access Violation: You are not authorized to schedule sessions for courses outside your department."))

            selected_trainer_dept = frappe.db.get_value("Trainer", trainer, "department")
            if selected_trainer_dept != trainer_dept:
                frappe.throw(_("Access Violation: Selected trainer does not belong to your department."))

        # 1. Create the Training Session
        session_doc = frappe.new_doc("Training Session")
        session_doc.course = course
        session_doc.trainer = trainer
        session_doc.training_date = training_date
        session_doc.start_time = start_time
        session_doc.duration_hours = float(duration_hours or 0)
        session_doc.training_mode = training_mode
        session_doc.status = "Scheduled"

        if training_mode == "Online":
            session_doc.meeting_link = meeting_link
        else:
            session_doc.location = location

        session_doc.insert(ignore_permissions=True)
        session_id = session_doc.name

        # 2. Bulk enroll employees into this session
        created_count = 0
        skipped_count = 0
        status_errors = []

        for emp_id in employees:
            enrollment_name = f"{session_id}-{emp_id}"
            
            # Check eligibility at backend
            emp_status = frappe.db.get_value("Employee", emp_id, "status")
            if emp_status != "Active":
                status_errors.append(emp_id)
                continue

            if not frappe.db.exists("Training Enrollment", enrollment_name):
                doc = frappe.new_doc("Training Enrollment")
                doc.training_session = session_id
                doc.employee = emp_id
                doc.assignment_date = frappe.utils.today()
                doc.completion_status = "Assigned"
                doc.insert(ignore_permissions=True)
                created_count += 1
            else:
                skipped_count += 1

        # Format results message
        msg = _("Successfully scheduled session {0} and assigned {1} employees.").format(session_id, created_count)
        if skipped_count > 0:
            msg += _(" {0} duplicates skipped.").format(skipped_count)
        if status_errors:
            msg += _(" {0} inactive skipped.").format(len(status_errors))

        return {
            "status": "success",
            "message": msg,
            "session_id": session_id,
            "enrolled_count": created_count,
            "skipped_count": skipped_count,
            "status_errors_count": len(status_errors)
        }
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Bulk Schedule & Assign Error")
        return {"status": "error", "message": str(e)}
