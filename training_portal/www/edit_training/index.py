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

    # Get trainer profile
    trainer = frappe.db.get_value(
        "Trainer",
        {"user": user},
        ["name", "trainer_name"],
        as_dict=True
    )
    context.trainer = trainer

    trainer_dept = get_trainer_department()
    context.trainer_dept = trainer_dept

    # Fetch lookup values for filters (for participant selector)
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
    context.statuses = ["Active", "Inactive", "On Leave", "Resigned", "Transferred"]

    # Check if a single session is being edited
    session_id = frappe.form_dict.get("session")
    if session_id:
        context.session_id = session_id
        session_doc = frappe.get_doc("Training Session", session_id)
        
        # Enforce department access validation for write operations
        if trainer_dept:
            session_course = session_doc.course
            course_dept = frappe.db.get_value("Training Course", session_course, "department")
            if course_dept != trainer_dept:
                frappe.throw(_("Access Violation: You are not authorized to view or edit sessions outside your department."), frappe.PermissionError)

        # Convert start_time and training_date to string representations
        session_dict = session_doc.as_dict()
        if session_dict.get("start_time") is not None:
            session_dict["start_time"] = str(session_dict["start_time"])
        if session_dict.get("training_date") is not None:
            session_dict["training_date"] = str(session_dict["training_date"])

        # Fetch subcategory
        session_dict["training_subcategory"] = frappe.db.get_value("Training Course", session_doc.course, "category")

        context.session_data = session_dict

        # Fetch current enrolled participants with details
        context.participants = get_session_participants_internal(session_id)
    else:
        # Fetch sessions led by this trainer, and restricted by department if applicable
        filters = {}
        if trainer:
            filters["trainer"] = trainer.name
        
        if trainer_dept:
            courses = [c.name for c in frappe.get_all("Training Course", filters={"department": trainer_dept})]
            filters["course"] = ["in", courses]

        sessions = frappe.get_all(
            "Training Session",
            filters=filters,
            fields=[
                "name",
                "training_name",
                "training_date",
                "start_time",
                "duration_hours",
                "training_mode",
                "status",
                "max_participants",
                "location",
                "meeting_link",
                "description"
            ],
            order_by="training_date desc"
        )

        for s in sessions:
            if s.get("start_time") is not None:
                s["start_time"] = str(s["start_time"])
            if s.get("training_date") is not None:
                s["training_date"] = str(s["training_date"])

        context.sessions = sessions

    return context


def get_session_participants_internal(session_name):
    # Fetch enrollments
    enrollments = frappe.get_all(
        "Training Enrollment",
        filters={"training_session": session_name},
        fields=["name", "employee"]
    )
    
    if not enrollments:
        return []
        
    emp_ids = [e.employee for e in enrollments]
    
    # Fetch details of employees
    employees = frappe.get_all(
        "Employee",
        filters={"name": ["in", emp_ids]},
        fields=[
            "name",
            "employee_name",
            "email",
            "department",
            "designation",
            "plant",
            "location",
            "reporting_manager",
            "status"
        ]
    )
    
    # Map employee details back to enrollment name
    # Fetch manager name mappings for display
    manager_ids = [emp.reporting_manager for emp in employees if emp.reporting_manager]
    manager_map = {}
    if manager_ids:
        managers = frappe.get_all(
            "Employee",
            filters={"name": ["in", manager_ids]},
            fields=["name", "employee_name"]
        )
        manager_map = {m.name: m.employee_name for m in managers}

    enrollment_map = {e.employee: e.name for e in enrollments}
    
    for emp in employees:
        emp["enrollment_id"] = enrollment_map.get(emp.name)
        emp["reporting_manager_name"] = manager_map.get(emp.reporting_manager) or emp.reporting_manager or "-"
        
    return employees


@frappe.whitelist()
def update_session_details(session_name, training_date, start_time, training_mode, status, location=None, meeting_link=None, max_participants=0, duration_hours=0):
    check_portal_permission()

    try:
        doc = frappe.get_doc("Training Session", session_name)
        
        # Enforce department access validation for write operations
        trainer_dept = get_trainer_department()
        if trainer_dept:
            session_course = frappe.db.get_value("Training Session", session_name, "course")
            course_dept = frappe.db.get_value("Training Course", session_course, "department")
            if course_dept != trainer_dept:
                frappe.throw(_("Access Violation: You are not authorized to edit sessions outside your department."), frappe.PermissionError)

        doc.training_date = training_date
        doc.start_time = start_time
        doc.training_mode = training_mode
        doc.status = status
        doc.duration_hours = float(duration_hours or 0)
        
        if training_mode == "Online":
            doc.meeting_link = meeting_link
            doc.location = None
        else:
            doc.location = location
            doc.meeting_link = None
            
        doc.max_participants = int(max_participants or 0)
        
        doc.save(ignore_permissions=True)
        return {
            "status": "success",
            "message": _("Session {0} updated successfully.").format(session_name)
        }
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Update Session Error")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist()
def cancel_training_session(session_name, reason=None):
    check_portal_permission()

    try:
        doc = frappe.get_doc("Training Session", session_name)
        
        # Enforce department access validation
        trainer_dept = get_trainer_department()
        if trainer_dept:
            session_course = frappe.db.get_value("Training Session", session_name, "course")
            course_dept = frappe.db.get_value("Training Course", session_course, "department")
            if course_dept != trainer_dept:
                frappe.throw(_("Access Violation: You are not authorized to cancel sessions outside your department."), frappe.PermissionError)

        doc.status = "Cancelled"
        doc.cancelled_by = frappe.session.user
        doc.cancelled_on = frappe.utils.now_datetime()
        doc.cancellation_reason = reason
        
        doc.save(ignore_permissions=True)
        return {
            "status": "success",
            "message": _("Session {0} has been cancelled successfully.").format(session_name)
        }
    except Exception as e:
        frappe.log_error(message=frappe.get_traceback(), title="Cancel Session Error")
        return {
            "status": "error",
            "message": str(e)
        }


@frappe.whitelist()
def get_employees_for_selector(session_name, department=None, plant=None, location=None, designation=None, reporting_manager=None, status=None, search_term=None):
    check_portal_permission()
    
    # 1. Fetch already enrolled employee IDs to exclude
    enrolled = frappe.get_all(
        "Training Enrollment",
        filters={"training_session": session_name},
        fields=["employee"]
    )
    enrolled_ids = [e.employee for e in enrolled]
    
    # 2. Build filters
    filters = {}
    if enrolled_ids:
        filters["name"] = ["not in", enrolled_ids]
        
    if department:
        filters["department"] = department
    if plant:
        filters["plant"] = plant
    if location:
        filters["location"] = location
    if designation:
        filters["designation"] = designation
    if reporting_manager:
        filters["reporting_manager"] = reporting_manager
    if status:
        filters["status"] = status
    else:
        filters["status"] = "Active"
        
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
    
    # Fetch manager name mappings for display
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
def add_participants(session_name, employees):
    check_portal_permission()
    
    if isinstance(employees, str):
        employees = json.loads(employees)
        
    if not employees:
        return {"status": "error", "message": _("No employees selected.")}
        
    # Check permissions (only for training session ownership, NOT employee enrollment departments)
    trainer_dept = get_trainer_department()
    if trainer_dept:
        session_course = frappe.db.get_value("Training Session", session_name, "course")
        course_dept = frappe.db.get_value("Training Course", session_course, "department")
        if course_dept != trainer_dept:
            frappe.throw(_("Access Violation: You are not authorized to edit sessions outside your department."), frappe.PermissionError)

    created_count = 0
    skipped_count = 0
    status_errors = []
    
    for emp_id in employees:
        enrollment_name = f"{session_name}-{emp_id}"
        
        # Check active status
        emp_status = frappe.db.get_value("Employee", emp_id, "status")
        if emp_status != "Active":
            status_errors.append(emp_id)
            continue
            
        if not frappe.db.exists("Training Enrollment", enrollment_name):
            doc = frappe.new_doc("Training Enrollment")
            doc.training_session = session_name
            doc.employee = emp_id
            doc.assignment_date = frappe.utils.today()
            doc.completion_status = "Assigned"
            doc.insert(ignore_permissions=True)
            created_count += 1
        else:
            skipped_count += 1
            
    msg = _("Successfully enrolled {0} new participants.").format(created_count)
    if skipped_count > 0:
        msg += _(" {0} duplicates skipped.").format(skipped_count)
    if status_errors:
        msg += _(" {0} inactive employees skipped.").format(len(status_errors))
        
    return {
        "status": "success",
        "message": msg,
        "enrolled_count": created_count,
        "skipped_count": skipped_count,
        "status_errors_count": len(status_errors)
    }


@frappe.whitelist()
def remove_participant(enrollment_id):
    check_portal_permission()
    
    training_session = frappe.db.get_value("Training Enrollment", enrollment_id, "training_session")
    if not training_session:
        frappe.throw(_("Enrollment not found."))
        
    # Check permissions
    trainer_dept = get_trainer_department()
    if trainer_dept:
        session_course = frappe.db.get_value("Training Session", training_session, "course")
        course_dept = frappe.db.get_value("Training Course", session_course, "department")
        if course_dept != trainer_dept:
            frappe.throw(_("Access Violation: You are not authorized to edit sessions outside your department."), frappe.PermissionError)

    frappe.delete_doc("Training Enrollment", enrollment_id, ignore_permissions=True)
    return {"status": "success", "message": _("Participant successfully removed.")}
