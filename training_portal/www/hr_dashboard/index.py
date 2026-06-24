import frappe
import json
import openpyxl

from frappe.utils.xlsxutils import make_xlsx
from frappe import _
from frappe.utils.response import build_response

def get_context(context):

    if "HR Administrator" not in frappe.get_roles():
        frappe.throw("Not Permitted")
    
    selected_department = frappe.form_dict.get("department")
    from_date = frappe.form_dict.get("from_date")
    to_date = frappe.form_dict.get("to_date")

    context.selected_department = selected_department
    context.from_date = from_date
    context.to_date = to_date

    training_filters = {}

    if selected_department:
      training_filters["department"] = selected_department

    if from_date and to_date:
      training_filters["training_date"] = [
        "between",
        [from_date, to_date]
    ]
     
    context.departments = frappe.get_all(
        "Department",
        pluck="name"
    )

    # KPI Cards

    context.total_trainings = frappe.db.count(
        "Training Session",
        filters=training_filters
    )

    employee_filters = {}

    if selected_department:
      employee_filters["department"] = selected_department

    context.total_employees = frappe.db.count(
      "Employee",
      filters=employee_filters
    )

    conditions = []
    values = {}

    if selected_department:
      conditions.append("department = %(department)s")
      values["department"] = selected_department

    if from_date and to_date:
      conditions.append("""
        training_date BETWEEN %(from_date)s
        AND %(to_date)s
      """)
      values["from_date"] = from_date
      values["to_date"] = to_date

    where_clause = ""

    if conditions:
      where_clause = "WHERE " + " AND ".join(conditions)

    total_hours = frappe.db.sql(f"""
      SELECT IFNULL(SUM(duration_hours),0)
      FROM `tabTraining Session`
      {where_clause}
      """, values)

    context.total_hours = total_hours[0][0]

    avg_attendance = frappe.db.sql(f"""
      SELECT IFNULL(AVG(attendance_percentage),0)
      FROM `tabTraining Session`
      {where_clause}
    """, values)

    context.avg_attendance = round(
        avg_attendance[0][0], 2
    )

    # Department Participation

    dept_conditions = []
    dept_values = {}

    if selected_department:
      dept_conditions.append(
        "department = %(department)s"
      )
      dept_values["department"] = selected_department

    dept_where = ""

    if dept_conditions:
      dept_where = (
        "WHERE " +
        " AND ".join(dept_conditions)
      )

    context.department_stats = frappe.db.sql(f"""
      SELECT
        department,
        COUNT(name) as employees
      FROM `tabEmployee`
      {dept_where}
      GROUP BY department
    """, dept_values, as_dict=True)

    context.chart_labels = json.dumps(
      [row["department"] for row in context.department_stats]
    )

    context.chart_values = json.dumps(
      [row["employees"] for row in context.department_stats]
    )

    # Employee Training Hours

    employee_conditions = []

    employee_values = {}

    if selected_department:
      employee_conditions.append(
        "e.department = %(department)s"
      )
      employee_values["department"] = selected_department

    if from_date and to_date:
      employee_conditions.append("""
        ts.training_date BETWEEN %(from_date)s
        AND %(to_date)s
      """)
      employee_values["from_date"] = from_date
      employee_values["to_date"] = to_date

    employee_where = ""

    if employee_conditions:
      employee_where = (
        "WHERE " +
        " AND ".join(employee_conditions)
      )

    context.employee_hours = frappe.db.sql(f"""
      SELECT
        e.employee_name,
        e.department,
        IFNULL(SUM(ts.duration_hours),0) as hours
      FROM `tabTraining Enrollment` te
      INNER JOIN `tabEmployee` e
        ON te.employee = e.name
      INNER JOIN `tabTraining Session` ts
        ON te.training_session = ts.name

      {employee_where}

      GROUP BY e.employee_name,e.department
      ORDER BY hours DESC
    """, employee_values, as_dict=True)


    
@frappe.whitelist()
def download_excel(
   department=None,
   from_date=None,
   to_date=None
):

      conditions = []
      values = {}

      if department:
        conditions.append(
        "e.department = %(department)s"
        )
        values["department"] = department

      if from_date and to_date:
        conditions.append("""
        ts.training_date BETWEEN
        %(from_date)s
        AND
        %(to_date)s
       """)
        values["from_date"] = from_date
        values["to_date"] = to_date

      where_clause = ""

      if conditions:
          where_clause = (
          "WHERE " +
          " AND ".join(conditions)
          )
      data = frappe.db.sql(f"""
         SELECT
          e.employee_name,
          e.department,
          IFNULL(
            SUM(ts.duration_hours),
            0
            ) as hours

            FROM `tabTraining Enrollment` te

            INNER JOIN `tabEmployee` e
              ON te.employee = e.name

            INNER JOIN `tabTraining Session` ts
              ON te.training_session = ts.name

           {where_clause}

           GROUP BY
            e.employee_name,
            e.department

           ORDER BY hours DESC
         """, values, as_dict=True)
      
      rows = [["Employee", "Department", "Training Hours"]]

      for d in data:
       rows.append([
        d["employee_name"],
        d["department"],
        d["hours"]
       ])

      xlsx_file = make_xlsx(
        rows,
       "HR Training Report"
        )

      frappe.response["filename"] = "HR_Training_Report.xlsx"
      frappe.response["filecontent"] = xlsx_file.getvalue()
      frappe.response["type"] = "binary"

      return