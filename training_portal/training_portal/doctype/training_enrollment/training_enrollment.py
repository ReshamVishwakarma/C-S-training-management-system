# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TrainingEnrollment(Document):
    def autoname(self):
        self.name = f"{self.training_session}-{self.employee}"

    def validate(self):
        # 1. Check if the employee is already enrolled in this training session
        exists = frappe.db.exists(
            "Training Enrollment",
            {
                "training_session": self.training_session,
                "employee": self.employee,
                "name": ["!=", self.name]
            }
        )
        if exists:
            frappe.throw(
                _("Employee {0} is already enrolled in Training Session {1}").format(
                    self.employee, self.training_session
                )
            )

        # 2. Fetch employee details (status, department, name)
        emp_details = frappe.db.get_value(
            "Employee",
            self.employee,
            ["status", "department", "employee_name"],
            as_dict=True
        )

        if not emp_details:
            frappe.throw(_("Employee {0} does not exist.").format(self.employee))

        # 3. Check active-status validation
        if emp_details.status != "Active":
            frappe.throw(
                _("Employee Status Error: Trainee '{0}' ({1}) is currently inactive and cannot be enrolled.").format(
                    emp_details.employee_name, self.employee
                )
            )

        # 4. Check department eligibility validation
        session_dept = frappe.db.get_value("Training Session", self.training_session, "department")
        if session_dept and emp_details.department != session_dept:
            frappe.throw(
                _("Department Eligibility Violation: Trainee '{0}' belongs to '{1}' department, but training session '{2}' is restricted to '{3}' department.").format(
                    emp_details.employee_name, emp_details.department or "No Department", self.training_session, session_dept
                )
            )
