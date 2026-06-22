# Copyright (c) 2026, C&S Electric and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestTrainingAssignment(FrappeTestCase):
    def setUp(self):
        # Create test departments
        if not frappe.db.exists("Department", "Engineering"):
            frappe.get_doc({
                "doctype": "Department",
                "department_name": "Engineering"
            }).insert()

        if not frappe.db.exists("Department", "HR"):
            frappe.get_doc({
                "doctype": "Department",
                "department_name": "HR"
            }).insert()

        # Create test course
        if not frappe.db.exists("Training Course", "Test Course Python"):
            self.course = frappe.get_doc({
                "doctype": "Training Course",
                "course_name": "Test Course Python",
                "course_code": "TCPY101",
                "duration_hours": 2.0,
                "active": 1
            }).insert()
        else:
            self.course = frappe.get_doc("Training Course", "Test Course Python")

        # Create test trainer
        if not frappe.db.exists("Trainer", "Test Trainer Alice"):
            self.trainer = frappe.get_doc({
                "doctype": "Trainer",
                "trainer_name": "Test Trainer Alice",
                "department": "Engineering",
                "active": 1,
                "trainer_type": "Internal"
            }).insert()
        else:
            self.trainer = frappe.get_doc("Trainer", "Test Trainer Alice")

        # Create target session restricted to Engineering department
        future_date = frappe.utils.add_days(frappe.utils.today(), 2)
        session_name = "Restricted Session Test"
        if not frappe.db.exists("Training Session", session_name):
            self.session = frappe.get_doc({
                "doctype": "Training Session",
                "course": self.course.name,
                "training_name": session_name,
                "training_date": future_date,
                "start_time": "14:00:00",
                "duration_hours": 2.0,
                "trainer": self.trainer.name,
                "training_mode": "Online",
                "meeting_link": "https://teams.microsoft.com/test",
                "department": "Engineering",
                "status": "Scheduled"
            }).insert(ignore_permissions=True)
        else:
            self.session = frappe.get_doc("Training Session", session_name)

        # Create active Engineering employee
        if not frappe.db.exists("Employee", "Employee Alice"):
            self.emp_active = frappe.get_doc({
                "doctype": "Employee",
                "employee_name": "Employee Alice",
                "employee_id": "EMP-ALICE",
                "department": "Engineering",
                "designation": "Developer",
                "status": "Active",
                "active": 1
            }).insert()
        else:
            self.emp_active = frappe.get_doc("Employee", "Employee Alice")

        # Create active HR employee (wrong department)
        if not frappe.db.exists("Employee", "Employee Bob"):
            self.emp_wrong_dept = frappe.get_doc({
                "doctype": "Employee",
                "employee_name": "Employee Bob",
                "employee_id": "EMP-BOB",
                "department": "HR",
                "designation": "Manager",
                "status": "Active",
                "active": 1
            }).insert()
        else:
            self.emp_wrong_dept = frappe.get_doc("Employee", "Employee Bob")

        # Create inactive Engineering employee
        if not frappe.db.exists("Employee", "Employee Charlie"):
            self.emp_inactive = frappe.get_doc({
                "doctype": "Employee",
                "employee_name": "Employee Charlie",
                "employee_id": "EMP-CHARLIE",
                "department": "Engineering",
                "designation": "Developer",
                "status": "Inactive",
                "active": 0
            }).insert()
        else:
            self.emp_inactive = frappe.get_doc("Employee", "Employee Charlie")

    def tearDown(self):
        # Clean up assignments and enrollments
        frappe.db.delete("Training Enrollment", {"training_session": self.session.name})
        frappe.db.delete("Training Assignment", {"training_session": self.session.name})
        frappe.db.delete("Training Session", {"name": self.session.name})
        frappe.db.delete("Training Course", {"name": self.course.name})
        frappe.db.delete("Trainer", {"name": self.trainer.name})
        frappe.db.delete("Employee", {"employee_name": ["in", ["Employee Alice", "Employee Bob", "Employee Charlie"]]})
        frappe.db.delete("Department", {"name": ["in", ["Engineering", "HR"]]})

    def test_valid_assignment(self):
        # Create a training assignment document
        doc = frappe.get_doc({
            "doctype": "Training Assignment",
            "training_session": self.session.name,
            "assignment_date": frappe.utils.today(),
            "assignment_type": "By Department",
            "department": "Engineering",
            "employees": [
                {
                    "employee": self.emp_active.name,
                    "employee_name": self.emp_active.employee_name
                }
            ]
        })
        doc.insert()
        doc.submit()

        # Check if Training Enrollment was successfully created
        enrollment_name = f"{self.session.name}-{self.emp_active.name}"
        self.assertTrue(frappe.db.exists("Training Enrollment", enrollment_name))

        # Cancel assignment and check if enrollment is deleted
        doc.cancel()
        self.assertFalse(frappe.db.exists("Training Enrollment", enrollment_name))

    def test_invalid_assignment_wrong_department(self):
        doc = frappe.get_doc({
            "doctype": "Training Assignment",
            "training_session": self.session.name,
            "assignment_date": frappe.utils.today(),
            "assignment_type": "By Department",
            "department": "HR",
            "employees": [
                {
                    "employee": self.emp_wrong_dept.name,
                    "employee_name": self.emp_wrong_dept.employee_name
                }
            ]
        })
        doc.insert()

        # Submitting should throw ValidationError due to wrong department eligibility check on Training Enrollment
        self.assertRaises(frappe.ValidationError, doc.submit)

    def test_invalid_assignment_inactive_employee(self):
        doc = frappe.get_doc({
            "doctype": "Training Assignment",
            "training_session": self.session.name,
            "assignment_date": frappe.utils.today(),
            "assignment_type": "By Department",
            "department": "Engineering",
            "employees": [
                {
                    "employee": self.emp_inactive.name,
                    "employee_name": self.emp_inactive.employee_name
                }
            ]
        })
        doc.insert()

        # Submitting should throw ValidationError due to inactive status check on Training Enrollment
        self.assertRaises(frappe.ValidationError, doc.submit)
