# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from training_portal.training_portal.access_control import get_trainer_department, check_portal_permission


def get_context(context):
    check_portal_permission()

    roles = frappe.get_roles()
    trainer_user = frappe.session.user
    context.user = trainer_user

    is_admin = any(r in roles for r in ["System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"])
    context.is_admin = is_admin

    trainer_dept = get_trainer_department()
    context.trainer_dept = trainer_dept

    # Fetch departments for filters
    if trainer_dept:
        context.departments = [{"name": trainer_dept}]
    else:
        context.departments = frappe.get_all("Department", fields=["name"])

    # Fetch plants for filters
    context.plants = sorted(list(set(
        p.plant for p in frappe.get_all("Employee", fields=["plant"]) if p.plant
    )))

    # Fetch trainers for filters
    trainer = frappe.db.get_value(
        "Trainer",
        {"user": trainer_user},
        ["name", "trainer_name", "department"],
        as_dict=True
    )
    context.trainer = trainer

    if is_admin:
        context.trainers = frappe.get_all("Trainer", filters={"active": 1}, fields=["name", "trainer_name"])
    else:
        context.trainers = [{"name": trainer.name, "trainer_name": trainer.trainer_name}] if trainer else []

    # Fetch employees for filters (restrict to trainer's department if restricted)
    emp_filters = {"status": "Active"}
    if trainer_dept:
        emp_filters["department"] = trainer_dept
    context.employees = frappe.get_all(
        "Employee",
        filters=emp_filters,
        fields=["name", "employee_id", "employee_name"],
        order_by="employee_name ASC"
    )

    # Fetch training names/courses for filters
    course_filters = {"active": 1}
    if trainer_dept:
        course_filters["department"] = trainer_dept
    context.courses = frappe.get_all(
        "Training Course",
        filters=course_filters,
        fields=["name", "course_name"],
        order_by="course_name ASC"
    )

    # Fetch categories (Training Subcategory) for Report 2 specific filter
    context.categories = frappe.get_all("Training Subcategory", fields=["name"], order_by="name ASC")

    return context


@frappe.whitelist()
def get_reports_data(report_type, start_date=None, end_date=None, department=None, plant=None, trainer=None, employee=None, training_name=None, attendance_status=None, training_mode=None, category=None, is_hr=False):
    check_portal_permission()

    roles = frappe.get_roles()
    is_admin = any(r in roles for r in ["System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"])
    
    if int(is_hr or 0) and not is_admin:
        frappe.throw(_("Not permitted to view HR reports."), frappe.PermissionError)

    trainer_user = frappe.session.user

    # Only apply trainer restrictions if NOT HR reports
    if not int(is_hr or 0):
        trainer_dept = get_trainer_department()
        if trainer_dept:
            department = trainer_dept

        if not is_admin:
            trainer_name = frappe.db.get_value("Trainer", {"user": trainer_user})
            trainer = trainer_name

    if report_type == "employee_monthly":
        return get_employee_monthly_report(start_date, end_date, department, plant, trainer, employee, training_name, category)
    elif report_type == "detailed_attendance":
        return get_detailed_attendance_report(start_date, end_date, department, plant, trainer, employee, training_name, attendance_status, training_mode, category)
    elif report_type == "training_summary":
        return get_training_summary_report(start_date, end_date, department, plant, trainer, employee, training_name, category)
    else:
        return {"report_data": [], "kpis": {}}


def get_employee_monthly_report(start_date, end_date, department, plant, trainer, employee, training_name, category=None):
    conditions = []
    params = {}

    if start_date:
        conditions.append("sess.training_date >= %(start_date)s")
        params["start_date"] = start_date
    if end_date:
        conditions.append("sess.training_date <= %(end_date)s")
        params["end_date"] = end_date
    if training_name:
        conditions.append("(sess.training_name = %(training_name)s OR sess.course = %(training_name)s)")
        params["training_name"] = training_name
    if department:
        conditions.append("emp.department = %(department)s")
        params["department"] = department
    if category:
        conditions.append("course.category = %(category)s")
        params["category"] = category
    if plant:
        conditions.append("emp.plant = %(plant)s")
        params["plant"] = plant
    if trainer:
        conditions.append("sess.trainer = %(trainer)s")
        params["trainer"] = trainer
    if employee:
        conditions.append("(emp.name = %(employee)s OR emp.employee_id = %(employee)s)")
        params["employee"] = employee

    where_clause = ""
    if conditions:
        where_clause = "AND " + " AND ".join(conditions)

    query = f"""
        SELECT
            emp.employee_id AS employee_code,
            emp.employee_name,
            COUNT(DISTINCT sess.name) AS trainings_attended,
            SUM(sess.duration_hours) AS total_hours
        FROM
            `tabAttendance detail` det
        INNER JOIN
            `tabTraining Attendance` att ON det.parent = att.name
        INNER JOIN
            `tabTraining Session` sess ON att.training_session = sess.name
        INNER JOIN
            `tabEmployee` emp ON det.employee = emp.name
        INNER JOIN
            `tabTraining Course` course ON sess.course = course.name
        WHERE
            att.docstatus = 1
            AND det.attendance_status = 'Present'
            {where_clause}
        GROUP BY
            emp.name
        ORDER BY
            emp.employee_name ASC
    """
    results = frappe.db.sql(query, params, as_dict=True)

    # Calculate KPIs
    employees_trained = len(results)
    total_hours = sum(r.get("total_hours") or 0 for r in results)
    avg_hours = round(total_hours / employees_trained, 2) if employees_trained > 0 else 0.0

    # Unique enrolled employees query
    enrolled_conditions = []
    enrolled_params = {}
    if start_date:
        enrolled_conditions.append("sess.training_date >= %(start_date)s")
        enrolled_params["start_date"] = start_date
    if end_date:
        enrolled_conditions.append("sess.training_date <= %(end_date)s")
        enrolled_params["end_date"] = end_date
    if training_name:
        enrolled_conditions.append("(sess.training_name = %(training_name)s OR sess.course = %(training_name)s)")
        enrolled_params["training_name"] = training_name
    if department:
        enrolled_conditions.append("emp.department = %(department)s")
        enrolled_params["department"] = department
    if category:
        enrolled_conditions.append("course.category = %(category)s")
        enrolled_params["category"] = category
    if plant:
        enrolled_conditions.append("emp.plant = %(plant)s")
        enrolled_params["plant"] = plant
    if trainer:
        enrolled_conditions.append("sess.trainer = %(trainer)s")
        enrolled_params["trainer"] = trainer
    if employee:
        enrolled_conditions.append("(emp.name = %(employee)s OR emp.employee_id = %(employee)s)")
        enrolled_params["employee"] = employee

    enrolled_where = ""
    if enrolled_conditions:
        enrolled_where = "WHERE " + " AND ".join(enrolled_conditions)

    joins = []
    if department or plant or employee:
        joins.append("INNER JOIN `tabEmployee` emp ON enroll.employee = emp.name")
    if category:
        joins.append("INNER JOIN `tabTraining Course` course ON sess.course = course.name")

    joins_str = " ".join(joins)

    enrolled_query = f"""
        SELECT COUNT(DISTINCT enroll.employee)
        FROM `tabTraining Enrollment` enroll
        INNER JOIN `tabTraining Session` sess ON enroll.training_session = sess.name
        {joins_str}
        {enrolled_where}
    """
    unique_employees = frappe.db.sql(enrolled_query, enrolled_params)[0][0] or 0

    return {
        "report_data": results,
        "kpis": {
            "employees_trained": employees_trained,
            "total_hours": round(total_hours, 1),
            "avg_hours": avg_hours,
            "unique_employees": unique_employees
        }
    }


def get_detailed_attendance_report(start_date, end_date, department, plant, trainer, employee, training_name, attendance_status, training_mode, category):
    conditions = []
    params = {}

    if start_date:
        conditions.append("sess.training_date >= %(start_date)s")
        params["start_date"] = start_date
    if end_date:
        conditions.append("sess.training_date <= %(end_date)s")
        params["end_date"] = end_date
    if department:
        conditions.append("emp.department = %(department)s")
        params["department"] = department
    if plant:
        conditions.append("emp.plant = %(plant)s")
        params["plant"] = plant
    if trainer:
        conditions.append("sess.trainer = %(trainer)s")
        params["trainer"] = trainer
    if employee:
        conditions.append("(emp.name = %(employee)s OR emp.employee_id = %(employee)s)")
        params["employee"] = employee
    if training_name:
        conditions.append("(sess.training_name = %(training_name)s OR sess.course = %(training_name)s)")
        params["training_name"] = training_name
    if attendance_status:
        conditions.append("det.attendance_status = %(attendance_status)s")
        params["attendance_status"] = attendance_status
    if training_mode:
        conditions.append("sess.training_mode = %(training_mode)s")
        params["training_mode"] = training_mode
    if category:
        conditions.append("course.category = %(category)s")
        params["category"] = category

    where_clause = ""
    if conditions:
        where_clause = "AND " + " AND ".join(conditions)

    query = f"""
        SELECT
            sess.name AS session_id,
            emp.employee_id AS employee_code,
            emp.employee_name,
            emp.email,
            emp.department,
            emp.designation,
            emp.plant,
            emp.location,
            emp.reporting_manager,
            sess.training_name,
            course.category AS training_category,
            sess.training_date,
            sess.duration_hours AS duration,
            sess.trainer,
            sess.training_mode,
            det.attendance_status,
            det.remarks
        FROM
            `tabAttendance detail` det
        INNER JOIN
            `tabTraining Attendance` att ON det.parent = att.name
        INNER JOIN
            `tabTraining Session` sess ON att.training_session = sess.name
        INNER JOIN
            `tabEmployee` emp ON det.employee = emp.name
        INNER JOIN
            `tabTraining Course` course ON sess.course = course.name
        WHERE
            att.docstatus = 1
            {where_clause}
        ORDER BY
            sess.training_date DESC, emp.employee_name ASC
    """
    results = frappe.db.sql(query, params, as_dict=True)
    return {
        "report_data": results,
        "kpis": {}
    }


def get_training_summary_report(start_date, end_date, department, plant, trainer, employee, training_name, category=None):
    conditions = []
    params = {}

    if start_date:
        conditions.append("sess.training_date >= %(start_date)s")
        params["start_date"] = start_date
    if end_date:
        conditions.append("sess.training_date <= %(end_date)s")
        params["end_date"] = end_date
    if trainer:
        conditions.append("sess.trainer = %(trainer)s")
        params["trainer"] = trainer
    if training_name:
        conditions.append("(sess.training_name = %(training_name)s OR sess.course = %(training_name)s)")
        params["training_name"] = training_name
    if category:
        conditions.append("course.category = %(category)s")
        params["category"] = category

    # Filter based on employee links if department/plant/employee filters exist
    if department or plant or employee:
        conditions.append("""
            EXISTS (
                SELECT 1 
                FROM `tabAttendance detail` d2 
                 INNER JOIN `tabTraining Attendance` a2 ON d2.parent = a2.name 
                INNER JOIN `tabEmployee` e2 ON d2.employee = e2.name
                WHERE a2.training_session = sess.name 
                  AND a2.docstatus = 1
                  AND d2.attendance_status = 'Present'
                  """ + 
                  (" AND e2.department = %(department)s" if department else "") +
                  (" AND e2.plant = %(plant)s" if plant else "") +
                  (" AND (e2.name = %(employee)s OR e2.employee_id = %(employee)s)" if employee else "") +
                  ")"
        )
        if department:
            params["department"] = department
        if plant:
            params["plant"] = plant
        if employee:
            params["employee"] = employee

    where_clause = ""
    if conditions:
        where_clause = "AND " + " AND ".join(conditions)

    query = f"""
        SELECT
            sess.training_name,
            course.category AS training_category,
            COUNT(DISTINCT sess.name) AS sessions_conducted,
            AVG(sess.duration_hours) AS average_duration,
            ROUND(AVG(
                (SELECT COUNT(*) 
                 FROM `tabAttendance detail` det 
                 INNER JOIN `tabTraining Attendance` att2 ON det.parent = att2.name
                 WHERE att2.training_session = sess.name 
                   AND att2.docstatus = 1 
                   AND det.attendance_status = 'Present')
            ), 1) AS employees_attended,
            SUM(
                sess.duration_hours * 
                (SELECT COUNT(*)                  FROM `tabAttendance detail` det 
                  INNER JOIN `tabTraining Attendance` att2 ON det.parent = att2.name
                 WHERE att2.training_session = sess.name 
                   AND att2.docstatus = 1 
                   AND det.attendance_status = 'Present')
            ) AS total_training_hours,
            AVG(sess.attendance_percentage) AS average_attendance
        FROM
            `tabTraining Session` sess
        INNER JOIN
            `tabTraining Course` course ON sess.course = course.name
        WHERE
            sess.status != 'Cancelled'
            AND EXISTS (
                SELECT 1 FROM `tabTraining Attendance` att
                WHERE att.training_session = sess.name AND att.docstatus = 1
            )
            {where_clause}
        GROUP BY
            sess.course
        ORDER BY
            sess.training_name ASC
    """
    results = frappe.db.sql(query, params, as_dict=True)

    # Calculate KPIs
    unique_trainings = len(results)
    sessions_conducted = sum(r.get("sessions_conducted") or 0 for r in results)
    employees_trained = sum(r.get("employees_attended") or 0 for r in results)
    total_hours_delivered = sum(r.get("total_training_hours") or 0 for r in results)

    return {
        "report_data": results,
        "kpis": {
            "unique_trainings": unique_trainings,
            "sessions_conducted": sessions_conducted,
            "employees_trained": employees_trained,
            "total_hours_delivered": round(total_hours_delivered, 1)
        }
    }

