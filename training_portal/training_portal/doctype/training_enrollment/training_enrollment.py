# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class TrainingEnrollment(Document):
    def autoname(self):
        self.name = f"{self.training_session}-{self.employee}"

    def validate(self):
        self.validate_department_access()
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
                _("Employee Status Error: Trainee '{0}' ({1}) is currently '{2}' and cannot be enrolled.").format(
                    emp_details.employee_name, self.employee, emp_details.status or "Inactive"
                )
            )

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
                    _("Access Violation: You are mapped to the '{0}' department, and cannot enroll participants in sessions belonging to the '{1}' department.").format(
                        trainer_dept, course_dept or "No Department"
                    ),
                    frappe.ValidationError
                )
