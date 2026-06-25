# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _


class TrainingAssignment(Document):
    def validate(self):
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
                    _("Access Violation: You are mapped to the '{0}' department, and cannot create or edit training assignments for sessions belonging to the '{1}' department.").format(
                        trainer_dept, course_dept or "No Department"
                    ),
                    frappe.ValidationError
                )

    def on_submit(self):
        created_enrollments = 0
        for emp in self.employees:
            # Check if enrollment already exists to prevent duplicate enrollment errors
            enrollment_name = f"{self.training_session}-{emp.employee}"
            if not frappe.db.exists("Training Enrollment", enrollment_name):
                doc = frappe.new_doc("Training Enrollment")
                doc.training_session = self.training_session
                doc.employee = emp.employee
                doc.assignment_date = self.assignment_date
                doc.completion_status = "Assigned"
                doc.insert(ignore_permissions=True)
                created_enrollments += 1
        
        frappe.msgprint(_("Successfully created {0} Training Enrollments.").format(created_enrollments))

    def on_cancel(self):
        cancelled_enrollments = 0
        for emp in self.employees:
            enrollment_name = f"{self.training_session}-{emp.employee}"
            if frappe.db.exists("Training Enrollment", enrollment_name):
                doc = frappe.get_doc("Training Enrollment", enrollment_name)
                # Only delete if status is still 'Assigned' to prevent deleting completed training logs
                if doc.completion_status == "Assigned":
                    doc.delete(ignore_permissions=True)
                    cancelled_enrollments += 1
        
        frappe.msgprint(_("Successfully removed {0} pending Training Enrollments.").format(cancelled_enrollments))


@frappe.whitelist()
def fetch_employees_for_assignment(assignment_type, department=None, designation=None):
    filters = {"status": "Active"}
    if assignment_type == "By Department" and department:
        filters["department"] = department
    elif assignment_type == "By Designation" and designation:
        filters["designation"] = designation
    elif assignment_type == "All Employees":
        pass
    else:
        return []
        
    employees = frappe.get_all(
        "Employee",
        filters=filters,
        fields=["name as employee", "employee_name", "department"]
    )
    return employees
