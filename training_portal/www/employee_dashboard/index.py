import frappe
from frappe import _
from training_portal.training_portal.access_control import check_portal_permission

def get_context(context):
    check_portal_permission()

    user_id = frappe.session.user
    context.user = user_id

    # Resolve Employee record
    employee = frappe.db.get_value("Employee", {"user": user_id}, ["name", "employee_name", "employee_id"], as_dict=True)
    if not employee and user_id == "Administrator":
        employee = frappe.db.get_value("Employee", {"user": "priya@test.com"}, ["name", "employee_name", "employee_id"], as_dict=True)

    if employee:
        context.employee_name = employee.employee_name
        context.employee_id = employee.employee_id
        context.employee_key = employee.name
    else:
        context.employee_name = "Guest User"
        context.employee_id = "-"
        context.employee_key = None

    # Fetch active courses for filters
    context.courses = frappe.get_all(
        "Training Course",
        filters={"active": 1},
        fields=["name", "course_name"],
        order_by="course_name ASC"
    )

    return context


@frappe.whitelist()
def get_employee_dashboard_data():
    check_portal_permission()

    user_id = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user": user_id}, ["name"], as_dict=True)
    if not employee and user_id == "Administrator":
        employee = frappe.db.get_value("Employee", {"user": "priya@test.com"}, ["name"], as_dict=True)

    if not employee:
        return {
            "total_assigned": 0,
            "completed_count": 0,
            "attendance_pct": 100.0,
            "total_hours": 0.0,
            "recent_trainings": [],
            "upcoming_trainings": []
        }

    employee_key = employee.name

    # 1. Total Assigned count
    total_assigned = frappe.db.count("Training Enrollment", {"employee": employee_key})

    # 2. Completed count (present/late)
    completed_count = frappe.db.sql("""
        SELECT COUNT(*) 
        FROM `tabAttendance detail` det 
        INNER JOIN `tabTraining Attendance` att ON det.parent = att.name 
        WHERE att.docstatus = 1 
          AND det.employee = %s 
          AND det.attendance_status IN ('Present', 'Late')
    """, (employee_key,))[0][0] or 0

    # 3. Total Attendance Sessions (for PCT calculation)
    total_sessions = frappe.db.sql("""
        SELECT COUNT(*) 
        FROM `tabAttendance detail` det 
        INNER JOIN `tabTraining Attendance` att ON det.parent = att.name 
        WHERE att.docstatus = 1 
          AND det.employee = %s
    """, (employee_key,))[0][0] or 0

    attendance_pct = 100.0
    if total_sessions > 0:
        attendance_pct = round((completed_count / total_sessions) * 100.0, 1)

    # 4. Total Training Hours
    total_hours = frappe.db.sql("""
        SELECT SUM(sess.duration_hours) 
        FROM `tabAttendance detail` det 
        INNER JOIN `tabTraining Attendance` att ON det.parent = att.name 
        INNER JOIN `tabTraining Session` sess ON att.training_session = sess.name 
        WHERE att.docstatus = 1 
          AND det.employee = %s 
          AND det.attendance_status IN ('Present', 'Late')
    """, (employee_key,))[0][0] or 0.0

    # 5. Recent completed sessions (limit 5)
    recent_trainings = frappe.db.sql("""
        SELECT
            sess.name AS session_id,
            sess.training_name,
            course.category AS category,
            sess.trainer,
            sess.training_date AS scheduled_date,
            sess.duration_hours AS duration,
            det.attendance_status
        FROM
            `tabAttendance detail` det
        INNER JOIN
            `tabTraining Attendance` att ON det.parent = att.name
        INNER JOIN
            `tabTraining Session` sess ON att.training_session = sess.name
        INNER JOIN
            `tabTraining Course` course ON sess.course = course.name
        WHERE
            att.docstatus = 1
            AND det.employee = %s
        ORDER BY
            sess.training_date DESC
        LIMIT 5
    """, (employee_key,), as_dict=True)

    # 6. Upcoming sessions (limit 5)
    upcoming_trainings = frappe.db.sql("""
        SELECT
            sess.name AS session_id,
            sess.training_name,
            course.category AS category,
            sess.trainer,
            sess.training_date AS scheduled_date,
            sess.start_time,
            sess.duration_hours AS duration,
            sess.training_mode,
            sess.location,
            sess.meeting_link
        FROM
            `tabTraining Enrollment` enroll
        INNER JOIN
            `tabTraining Session` sess ON enroll.training_session = sess.name
        INNER JOIN
            `tabTraining Course` course ON sess.course = course.name
        WHERE
            enroll.employee = %s
            AND sess.status = 'Scheduled'
            AND sess.training_date >= CURDATE()
        ORDER BY
            sess.training_date ASC, sess.start_time ASC
        LIMIT 5
    """, (employee_key,), as_dict=True)

    return {
        "total_assigned": total_assigned,
        "completed_count": completed_count,
        "attendance_pct": attendance_pct,
        "total_hours": round(total_hours, 1),
        "recent_trainings": recent_trainings,
        "upcoming_trainings": upcoming_trainings
    }


@frappe.whitelist()
def get_employee_trainings_data(start_date=None, end_date=None, training_name=None, status=None):
    check_portal_permission()

    user_id = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user": user_id}, ["name"], as_dict=True)
    if not employee and user_id == "Administrator":
        employee = frappe.db.get_value("Employee", {"user": "priya@test.com"}, ["name"], as_dict=True)

    if not employee:
        return {"report_data": [], "kpis": {"total_assigned": 0}}

    employee_key = employee.name
    conditions = ["enroll.employee = %(employee)s"]
    params = {"employee": employee_key}

    if start_date:
        conditions.append("sess.training_date >= %(start_date)s")
        params["start_date"] = start_date
    if end_date:
        conditions.append("sess.training_date <= %(end_date)s")
        params["end_date"] = end_date
    if training_name:
        conditions.append("(sess.training_name = %(training_name)s OR sess.course = %(training_name)s)")
        params["training_name"] = training_name
    if status:
        if status == "Upcoming":
            conditions.append("sess.training_date > CURDATE() AND sess.status != 'Cancelled'")
        elif status == "Today":
            conditions.append("sess.training_date = CURDATE() AND sess.status != 'Cancelled'")
        elif status == "Completed":
            conditions.append("(sess.status = 'Completed' OR enroll.completion_status = 'Completed')")

    where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            sess.name AS session_id,
            sess.training_name,
            course.category AS category,
            sess.trainer,
            sess.training_date AS scheduled_date,
            sess.start_time,
            sess.duration_hours AS duration,
            sess.training_mode,
            sess.location,
            sess.meeting_link,
            enroll.completion_status,
            sess.status AS session_status
        FROM
            `tabTraining Enrollment` enroll
        INNER JOIN
            `tabTraining Session` sess ON enroll.training_session = sess.name
        INNER JOIN
            `tabTraining Course` course ON sess.course = course.name
        {where_clause}
        ORDER BY
            sess.training_date DESC
    """
    results = frappe.db.sql(query, params, as_dict=True)

    # Calculate status dynamically
    for r in results:
        # Check completion
        if r.session_status == "Completed" or r.completion_status == "Completed":
            r["calculated_status"] = "Completed"
        elif r.scheduled_date == frappe.utils.today():
            r["calculated_status"] = "Today"
        elif r.scheduled_date > frappe.utils.today():
            r["calculated_status"] = "Upcoming"
        else:
            r["calculated_status"] = "Completed"

    total_assigned = len(results)

    return {
        "report_data": results,
        "kpis": {
            "total_assigned": total_assigned
        }
    }


@frappe.whitelist()
def get_employee_attendance_data(start_date=None, end_date=None, attendance_status=None, training_name=None):
    check_portal_permission()

    user_id = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user": user_id}, ["name"], as_dict=True)
    if not employee and user_id == "Administrator":
        employee = frappe.db.get_value("Employee", {"user": "priya@test.com"}, ["name"], as_dict=True)

    if not employee:
        return {"report_data": [], "kpis": {"present": 0, "absent": 0, "attendance_pct": 100.0}}

    employee_key = employee.name
    conditions = ["att.docstatus = 1", "det.employee = %(employee)s"]
    params = {"employee": employee_key}

    if start_date:
        conditions.append("sess.training_date >= %(start_date)s")
        params["start_date"] = start_date
    if end_date:
        conditions.append("sess.training_date <= %(end_date)s")
        params["end_date"] = end_date
    if training_name:
        conditions.append("(sess.training_name = %(training_name)s OR sess.course = %(training_name)s)")
        params["training_name"] = training_name
    if attendance_status:
        conditions.append("det.attendance_status = %(attendance_status)s")
        params["attendance_status"] = attendance_status

    where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            sess.training_name,
            sess.training_date,
            sess.trainer,
            det.attendance_status,
            sess.duration_hours AS duration,
            det.remarks
        FROM
            `tabAttendance detail` det
        INNER JOIN
            `tabTraining Attendance` att ON det.parent = att.name
        INNER JOIN
            `tabTraining Session` sess ON att.training_session = sess.name
        {where_clause}
        ORDER BY
            sess.training_date DESC
    """
    results = frappe.db.sql(query, params, as_dict=True)

    present = sum(1 for r in results if r.attendance_status in ["Present", "Late"])
    absent = sum(1 for r in results if r.attendance_status == "Absent")
    total = len(results)
    attendance_pct = 100.0
    if total > 0:
        attendance_pct = round((present / total) * 100.0, 1)

    return {
        "report_data": results,
        "kpis": {
            "present": present,
            "absent": absent,
            "attendance_pct": attendance_pct
        }
    }


@frappe.whitelist()
def get_employee_hours_data(start_date=None, end_date=None, training_name=None):
    check_portal_permission()

    user_id = frappe.session.user
    employee = frappe.db.get_value("Employee", {"user": user_id}, ["name"], as_dict=True)
    if not employee and user_id == "Administrator":
        employee = frappe.db.get_value("Employee", {"user": "priya@test.com"}, ["name"], as_dict=True)

    if not employee:
        return {"report_data": [], "kpis": {"total_hours": 0.0, "total_attended": 0, "avg_hours": 0.0}}

    employee_key = employee.name
    conditions = ["att.docstatus = 1", "det.employee = %(employee)s", "det.attendance_status IN ('Present', 'Late')"]
    params = {"employee": employee_key}

    if start_date:
        conditions.append("sess.training_date >= %(start_date)s")
        params["start_date"] = start_date
    if end_date:
        conditions.append("sess.training_date <= %(end_date)s")
        params["end_date"] = end_date
    if training_name:
        conditions.append("(sess.training_name = %(training_name)s OR sess.course = %(training_name)s)")
        params["training_name"] = training_name

    where_clause = "WHERE " + " AND ".join(conditions)

    query = f"""
        SELECT
            sess.training_name,
            course.category,
            1 AS sessions_attended,
            sess.duration_hours AS training_hours,
            sess.trainer,
            sess.training_date
        FROM
            `tabAttendance detail` det
        INNER JOIN
            `tabTraining Attendance` att ON det.parent = att.name
        INNER JOIN
            `tabTraining Session` sess ON att.training_session = sess.name
        INNER JOIN
            `tabTraining Course` course ON sess.course = course.name
        {where_clause}
        ORDER BY
            sess.training_date DESC
    """
    results = frappe.db.sql(query, params, as_dict=True)

    total_hours = sum(r.training_hours or 0.0 for r in results)
    total_attended = len(results)
    avg_hours = 0.0
    if total_attended > 0:
        avg_hours = round(total_hours / total_attended, 1)

    return {
        "report_data": results,
        "kpis": {
            "total_hours": round(total_hours, 1),
            "total_attended": total_attended,
            "avg_hours": avg_hours
        }
    }
