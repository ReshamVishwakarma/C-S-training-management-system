import frappe


def get_context(context):

    if "Trainer" not in frappe.get_roles():
        frappe.throw("Not Permitted")

    attendance_name = frappe.form_dict.get("attendance")

    if not attendance_name:
        frappe.throw("Attendance record not found")

    attendance = frappe.get_doc(
        "Training Attendance",
        attendance_name
    )

    details = []

    present_count = 0
    absent_count = 0

    for row in attendance.attendance_details:

        details.append({
            "employee_name": row.employee_name,
            "attendance_status": row.attendance_status,
            "remarks": row.remarks
        })

        if row.attendance_status == "Present":
            present_count += 1

        elif row.attendance_status == "Absent":
            absent_count += 1

    context.attendance = attendance
    context.details = details

    context.present_count = present_count
    context.absent_count = absent_count

    return context