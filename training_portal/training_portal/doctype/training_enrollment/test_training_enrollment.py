# Copyright (c) 2026, C&S Electric and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestTrainingEnrollment(FrappeTestCase):
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
                "department": "Engineering",
                "active": 1
            }).insert()
        else:
            self.course = frappe.get_doc("Training Course", "Test Course Python")
            if self.course.department != "Engineering":
                self.course.department = "Engineering"
                self.course.save()

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
        if not frappe.db.exists("Employee", "Employee Alice Enrollment"):
            self.emp_active = frappe.get_doc({
                "doctype": "Employee",
                "employee_name": "Employee Alice Enrollment",
                "employee_id": "EMP-ALICE-ENROLL",
                "department": "Engineering",
                "designation": "Developer",
                "status": "Active",
                "active": 1
            }).insert()
        else:
            self.emp_active = frappe.get_doc("Employee", "Employee Alice Enrollment")

        # Create active HR employee (wrong department)
        if not frappe.db.exists("Employee", "Employee Bob Enrollment"):
            self.emp_wrong_dept = frappe.get_doc({
                "doctype": "Employee",
                "employee_name": "Employee Bob Enrollment",
                "employee_id": "EMP-BOB-ENROLL",
                "department": "HR",
                "designation": "Manager",
                "status": "Active",
                "active": 1
            }).insert()
        else:
            self.emp_wrong_dept = frappe.get_doc("Employee", "Employee Bob Enrollment")

        # Create inactive Engineering employee
        if not frappe.db.exists("Employee", "Employee Charlie Enrollment"):
            self.emp_inactive = frappe.get_doc({
                "doctype": "Employee",
                "employee_name": "Employee Charlie Enrollment",
                "employee_id": "EMP-CHARLIE-ENROLL",
                "department": "Engineering",
                "designation": "Developer",
                "status": "Inactive",
                "active": 0
            }).insert()
        else:
            self.emp_inactive = frappe.get_doc("Employee", "Employee Charlie Enrollment")

    def tearDown(self):
        # Clean up enrollments and created test docs
        frappe.db.delete("Training Enrollment", {"training_session": self.session.name})
        frappe.db.delete("Training Session", {"name": self.session.name})
        frappe.db.delete("Training Course", {"name": self.course.name})
        frappe.db.delete("Trainer", {"name": self.trainer.name})
        frappe.db.delete("Employee", {"employee_name": ["in", ["Employee Alice Enrollment", "Employee Bob Enrollment", "Employee Charlie Enrollment"]]})
        frappe.db.delete("Department", {"name": ["in", ["Engineering", "HR"]]})

    def test_valid_enrollment(self):
        doc = frappe.get_doc({
            "doctype": "Training Enrollment",
            "training_session": self.session.name,
            "employee": self.emp_active.name,
            "completion_status": "Assigned"
        }).insert()
        
        self.assertTrue(frappe.db.exists("Training Enrollment", doc.name))

    def test_inactive_employee_enrollment(self):
        doc = frappe.new_doc("Training Enrollment")
        doc.training_session = self.session.name
        doc.employee = self.emp_inactive.name
        doc.completion_status = "Assigned"

        self.assertRaises(frappe.ValidationError, doc.insert)

    def test_department_mismatch_enrollment(self):
        doc = frappe.get_doc({
            "doctype": "Training Enrollment",
            "training_session": self.session.name,
            "employee": self.emp_wrong_dept.name,
            "completion_status": "Assigned"
        })
        doc.insert()
        self.assertTrue(frappe.db.exists("Training Enrollment", doc.name))
