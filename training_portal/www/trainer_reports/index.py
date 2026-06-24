# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def get_context(context):
    roles = frappe.get_roles()
    if not (any(r in roles for r in ["Trainer", "System Manager", "HR Manager", "HR User", "HR Administrator"])):
        frappe.throw(_("Not Permitted"), frappe.PermissionError)

    trainer_user = frappe.session.user
    context.user = trainer_user

    is_admin = any(r in roles for r in ["System Manager", "HR Manager", "HR User"])
    context.is_admin = is_admin

    # Fetch departments for filters
    context.departments = frappe.get_all("Department", fields=["name"])

    # Fetch trainers for filters
    if is_admin:
        context.trainers = frappe.get_all("Trainer", filters={"active": 1}, fields=["name", "trainer_name"])
    else:
        trainer = frappe.db.get_value(
            "Trainer",
            {"user": trainer_user},
            ["name", "trainer_name", "department"],
            as_dict=True
        )
        context.trainer = trainer
        context.trainers = [{"name": trainer.name, "trainer_name": trainer.trainer_name}] if trainer else []

    return context


@frappe.whitelist()
def get_reports_data(report_type, department=None, trainer=None, start_date=None, end_date=None):
    roles = frappe.get_roles()
    if not (any(r in roles for r in ["Trainer", "System Manager", "HR Manager", "HR User"])):
        frappe.throw(_("Not Permitted"), frappe.PermissionError)

    is_admin = any(r in roles for r in ["System Manager", "HR Manager", "HR User"])
    trainer_user = frappe.session.user

    # Enforce permission filtering: Trainers can only query their own data
    if not is_admin:
        trainer_name = frappe.db.get_value("Trainer", {"user": trainer_user})
        trainer = trainer_name
    
    if report_type == "session":
        return get_session_report(department, trainer, start_date, end_date)
    elif report_type == "employee":
        return get_employee_report(department, trainer, start_date, end_date)
    elif report_type == "department":
        return get_department_report(department, trainer, start_date, end_date)
    elif report_type == "trainer":
        return get_trainer_report(department, trainer, start_date, end_date)
    else:
        return []


def get_session_report(department, trainer, start_date, end_date):
    filters = {}
    if trainer:
        filters["trainer"] = trainer
    if department:
        filters["department"] = department
    if start_date and end_date:
        filters["training_date"] = ["between", [start_date, end_date]]
    elif start_date:
        filters["training_date"] = [">=", start_date]
    elif end_date:
        filters["training_date"] = ["<=", end_date]

    sessions = frappe.get_all(
        "Training Session",
        filters=filters,
        fields=["name", "training_name", "trainer", "department", "training_date", "attendance_percentage", "status"]
    )

    data = []
    for s in sessions:
        attn = frappe.db.get_value("Training Attendance", {"training_session": s.name, "docstatus": 1}, ["total_participants", "present_count"], as_dict=True)
        data.append({
            "session_id": s.name,
            "session_name": s.training_name,
            "trainer": s.trainer,
            "department": s.department or "All",
            "date": str(s.training_date),
            "participants": attn.total_participants if attn else 0,
            "present": attn.present_count if attn else 0,
            "rate": round(s.attendance_percentage or 0, 1),
            "status": s.status
        })
    return data


def get_employee_report(department, trainer, start_date, end_date):
    session_filters = {}
    if trainer:
        session_filters["trainer"] = trainer
    if start_date and end_date:
        session_filters["training_date"] = ["between", [start_date, end_date]]
    elif start_date:
        session_filters["training_date"] = [">=", start_date]
    elif end_date:
        session_filters["training_date"] = ["<=", end_date]

    # Department filter in session filters refers to session target department
    # Wait, the user wants the report to support department filters.
    # For employees, filtering by department means the employee's department!
    # So we shouldn't filter the session targets by department, unless they specify department target.
    # Let's filter employee records by department.

    session_names = [s.name for s in frappe.get_all("Training Session", filters=session_filters)]
    if not session_names:
        return []

    enroll_filters = {"training_session": ["in", session_names]}
    if department:
        enroll_filters["department"] = department

    enrollments = frappe.get_all(
        "Training Enrollment",
        filters=enroll_filters,
        fields=["employee", "completion_status", "department"]
    )

    emp_data = {}
    for e in enrollments:
        emp_id = e.employee
        if emp_id not in emp_data:
            emp_data[emp_id] = {"enrolled": 0, "attended": 0}
        emp_data[emp_id]["enrolled"] += 1
        if e.completion_status == "Completed":
            emp_data[emp_id]["attended"] += 1

    data = []
    for emp_id, stats in emp_data.items():
        emp_name, dept, designation = frappe.db.get_value("Employee", emp_id, ["employee_name", "department", "designation"])
        rate = (stats["attended"] / stats["enrolled"] * 100) if stats["enrolled"] > 0 else 0
        data.append({
            "employee_id": emp_id,
            "employee_name": emp_name,
            "department": dept or "No Department",
            "designation": designation or "No Designation",
            "enrolled": stats["enrolled"],
            "attended": stats["attended"],
            "rate": round(rate, 1)
        })
    return data


def get_department_report(department, trainer, start_date, end_date):
    session_filters = {}
    if trainer:
        session_filters["trainer"] = trainer
    if start_date and end_date:
        session_filters["training_date"] = ["between", [start_date, end_date]]
    elif start_date:
        session_filters["training_date"] = [">=", start_date]
    elif end_date:
        session_filters["training_date"] = ["<=", end_date]

    session_names = [s.name for s in frappe.get_all("Training Session", filters=session_filters)]
    if not session_names:
        return []

    enroll_filters = {"training_session": ["in", session_names]}
    if department:
        enroll_filters["department"] = department

    enrollments = frappe.get_all(
        "Training Enrollment",
        filters=enroll_filters,
        fields=["department", "completion_status"]
    )

    dept_data = {}
    for e in enrollments:
        dept = e.department or "No Department"
        if dept not in dept_data:
            dept_data[dept] = {"enrolled": 0, "attended": 0}
        dept_data[dept]["enrolled"] += 1
        if e.completion_status == "Completed":
            dept_data[dept]["attended"] += 1

    data = []
    for d_name, stats in dept_data.items():
        rate = (stats["attended"] / stats["enrolled"] * 100) if stats["enrolled"] > 0 else 0
        data.append({
            "department": d_name,
            "enrolled": stats["enrolled"],
            "attended": stats["attended"],
            "rate": round(rate, 1)
        })
    return data


def get_trainer_report(department, trainer, start_date, end_date):
    trainer_filters = {}
    if trainer:
        trainer_filters["name"] = trainer
    if department:
        trainer_filters["department"] = department

    trainers = frappe.get_all("Trainer", filters=trainer_filters, fields=["name", "trainer_name", "department", "attendance_percentage"])

    data = []
    for t in trainers:
        session_filters = {"trainer": t.name, "status": ["!=", "Cancelled"]}
        if start_date and end_date:
            session_filters["training_date"] = ["between", [start_date, end_date]]
        elif start_date:
            session_filters["training_date"] = [">=", start_date]
        elif end_date:
            session_filters["training_date"] = ["<=", end_date]

        sessions = frappe.get_all("Training Session", filters=session_filters, fields=["name"])
        session_names = [s.name for s in sessions]

        total_participants = 0
        total_present = 0

        if session_names:
            attendances = frappe.get_all(
                "Training Attendance",
                filters={"training_session": ["in", session_names], "docstatus": 1},
                fields=["total_participants", "present_count"]
            )
            total_participants = sum(a.total_participants or 0 for a in attendances)
            total_present = sum(a.present_count or 0 for a in attendances)

        rate = (total_present / total_participants * 100) if total_participants > 0 else (t.attendance_percentage or 0)

        data.append({
            "trainer_id": t.name,
            "trainer_name": t.trainer_name,
            "department": t.department,
            "sessions_count": len(session_names),
            "participants": total_participants,
            "present": total_present,
            "rate": round(rate, 1)
        })
    return data
