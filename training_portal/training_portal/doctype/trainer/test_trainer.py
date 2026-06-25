# Copyright (c) 2026, C&S Electric and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from training_portal.training_portal.access_control import get_trainer_department, filter_courses_by_dept


class TestTrainerAccess(FrappeTestCase):
    def setUp(self):
        # Create test departments
        for dept in ["IT", "HR"]:
            if not frappe.db.exists("Department", dept):
                frappe.get_doc({
                    "doctype": "Department",
                    "department_name": dept
                }).insert(ignore_permissions=True)

        # Create IT Trainer User & Profile
        if not frappe.db.exists("User", "it_trainer@test.com"):
            user_it = frappe.get_doc({
                "doctype": "User",
                "email": "it_trainer@test.com",
                "first_name": "IT",
                "last_name": "Trainer",
                "send_welcome_email": 0,
                "roles": [{"role": "Trainer"}]
            }).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("User", "it_trainer@test.com", "enabled", 1)
        
        if not frappe.db.exists("Trainer", {"user": "it_trainer@test.com"}):
            frappe.get_doc({
                "doctype": "Trainer",
                "trainer_name": "IT Trainer Alice",
                "user": "it_trainer@test.com",
                "department": "IT",
                "active": 1,
                "trainer_type": "Internal"
            }).insert(ignore_permissions=True)

        # Create HR Trainer User & Profile
        if not frappe.db.exists("User", "hr_trainer@test.com"):
            user_hr = frappe.get_doc({
                "doctype": "User",
                "email": "hr_trainer@test.com",
                "first_name": "HR",
                "last_name": "Trainer",
                "send_welcome_email": 0,
                "roles": [{"role": "Trainer"}]
            }).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("User", "hr_trainer@test.com", "enabled", 1)
        
        if not frappe.db.exists("Trainer", {"user": "hr_trainer@test.com"}):
            frappe.get_doc({
                "doctype": "Trainer",
                "trainer_name": "HR Trainer Bob",
                "user": "hr_trainer@test.com",
                "department": "HR",
                "active": 1,
                "trainer_type": "Internal"
            }).insert(ignore_permissions=True)

        # Create test courses
        if not frappe.db.exists("Training Course", "Python for IT"):
            frappe.get_doc({
                "doctype": "Training Course",
                "course_name": "Python for IT",
                "course_code": "PYIT101",
                "duration_hours": 3.0,
                "department": "IT",
                "active": 1
            }).insert(ignore_permissions=True)

        if not frappe.db.exists("Training Course", "HR Policy Orientation"):
            frappe.get_doc({
                "doctype": "Training Course",
                "course_name": "HR Policy Orientation",
                "course_code": "HRPO101",
                "duration_hours": 1.5,
                "department": "HR",
                "active": 1
            }).insert(ignore_permissions=True)

    def tearDown(self):
        # Restore session user to Administrator
        frappe.db.set_value("User", "it_trainer@test.com", "enabled", 0)
        frappe.db.set_value("User", "hr_trainer@test.com", "enabled", 0)
        frappe.set_user("Administrator")

        # Cleanup
        frappe.db.delete("Training Session", {"course": ["in", ["Python for IT", "HR Policy Orientation"]]})
        frappe.db.delete("Training Course", {"name": ["in", ["Python for IT", "HR Policy Orientation"]]})
        frappe.db.delete("Trainer", {"trainer_name": ["in", ["IT Trainer Alice", "HR Trainer Bob"]]})
        frappe.db.delete("User", {"email": ["in", ["it_trainer@test.com", "hr_trainer@test.com"]]})
        frappe.db.delete("Department", {"name": ["in", ["IT", "HR"]]})

    def test_department_filters_applied_to_trainer(self):
        # 1. Login as IT Trainer
        frappe.set_user("it_trainer@test.com")
        dept = get_trainer_department()
        self.assertEqual(dept, "IT")

        filters = filter_courses_by_dept({}, dept)
        courses = frappe.get_all("Training Course", filters=filters, pluck="name")
        self.assertIn("Python for IT", courses)
        self.assertNotIn("HR Policy Orientation", courses)

        # 2. Login as HR Trainer
        frappe.set_user("hr_trainer@test.com")
        dept = get_trainer_department()
        self.assertEqual(dept, "HR")

        filters = filter_courses_by_dept({}, dept)
        courses = frappe.get_all("Training Course", filters=filters, pluck="name")
        self.assertIn("HR Policy Orientation", courses)
        self.assertNotIn("Python for IT", courses)

    def test_admin_bypasses_filters(self):
        # Login as Admin (Administrator)
        frappe.set_user("Administrator")
        dept = get_trainer_department()
        self.assertIsNone(dept)

        filters = filter_courses_by_dept({}, dept)
        courses = frappe.get_all("Training Course", filters=filters, pluck="name")
        self.assertIn("Python for IT", courses)
        self.assertIn("HR Policy Orientation", courses)

    def test_unauthorized_save_throws_error(self):
        # Login as IT Trainer
        frappe.set_user("it_trainer@test.com")

        # Trying to create a course in the HR department should fail
        doc = frappe.new_doc("Training Course")
        doc.course_name = "New HR Course by IT"
        doc.course_code = "NHRCT1"
        doc.department = "HR"
        doc.duration_hours = 2.0
        doc.active = 1

        self.assertRaises(frappe.ValidationError, doc.insert, ignore_permissions=True)

        # Trying to create a session for an HR course should fail
        doc_session = frappe.new_doc("Training Session")
        doc_session.course = "HR Policy Orientation"
        doc_session.training_date = frappe.utils.add_days(frappe.utils.today(), 5)
        doc_session.start_time = "10:00:00"
        doc_session.duration_hours = 2.0
        doc_session.training_mode = "Online"
        doc_session.meeting_link = "https://teams.microsoft.com/hr"
        doc_session.status = "Scheduled"
        # We need a trainer profile name. Let's get Alice's name
        trainer_name = frappe.db.get_value("Trainer", {"user": "it_trainer@test.com"})
        doc_session.trainer = trainer_name

        self.assertRaises(frappe.ValidationError, doc_session.insert, ignore_permissions=True)
