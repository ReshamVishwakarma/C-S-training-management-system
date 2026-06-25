# Copyright (c) 2026, C&S Electric and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestTrainingAttendance(FrappeTestCase):
    def setUp(self):
        # Create test department
        if not frappe.db.exists("Department", "Engineering"):
            frappe.get_doc({
                "doctype": "Department",
                "department_name": "Engineering"
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

        # Create test session
        future_date = frappe.utils.add_days(frappe.utils.today(), 2)
        session_name = "Session Test Attendance"
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

        # Create two active employees
        if not frappe.db.exists("Employee", "Employee Alice Attendance"):
            self.emp1 = frappe.get_doc({
                "doctype": "Employee",
                "employee_name": "Employee Alice Attendance",
                "employee_id": "EMP-ALICE-ATTN",
                "department": "Engineering",
                "designation": "Developer",
                "status": "Active",
                "active": 1
            }).insert()
        else:
            self.emp1 = frappe.get_doc("Employee", "Employee Alice Attendance")

        if not frappe.db.exists("Employee", "Employee Bob Attendance"):
            self.emp2 = frappe.get_doc({
                "doctype": "Employee",
                "employee_name": "Employee Bob Attendance",
                "employee_id": "EMP-BOB-ATTN",
                "department": "Engineering",
                "designation": "Developer",
                "status": "Active",
                "active": 1
            }).insert()
        else:
            self.emp2 = frappe.get_doc("Employee", "Employee Bob Attendance")

        # Create enrollments (starts as Assigned)
        self.enroll1 = frappe.get_doc({
            "doctype": "Training Enrollment",
            "training_session": self.session.name,
            "employee": self.emp1.name,
            "completion_status": "Assigned"
        }).insert()

        self.enroll2 = frappe.get_doc({
            "doctype": "Training Enrollment",
            "training_session": self.session.name,
            "employee": self.emp2.name,
            "completion_status": "Assigned"
        }).insert()

    def tearDown(self):
        # Clean up
        frappe.db.delete("Training Enrollment", {"training_session": self.session.name})
        frappe.db.delete("Training Attendance", {"training_session": self.session.name})
        frappe.db.delete("Training Session", {"name": self.session.name})
        frappe.db.delete("Training Course", {"name": self.course.name})
        frappe.db.delete("Trainer", {"name": self.trainer.name})
        frappe.db.delete("Employee", {"employee_name": ["in", ["Employee Alice Attendance", "Employee Bob Attendance", "Employee Charlie Attendance"]]})
        frappe.db.delete("Department", {"name": "Engineering"})

    def test_attendance_lifecycle_and_metrics(self):
        # 1. Verify initial status is Assigned
        self.assertEqual(frappe.db.get_value("Training Enrollment", self.enroll1.name, "completion_status"), "Assigned")
        self.assertEqual(frappe.db.get_value("Training Enrollment", self.enroll2.name, "completion_status"), "Assigned")

        # 2. Transition Session status to Ongoing (simulating start of training)
        self.session.status = "Ongoing"
        self.session.save(ignore_permissions=True)

        # Enrollments should automatically go to "In Progress"
        self.assertEqual(frappe.db.get_value("Training Enrollment", self.enroll1.name, "completion_status"), "In Progress")
        self.assertEqual(frappe.db.get_value("Training Enrollment", self.enroll2.name, "completion_status"), "In Progress")

        # 3. Create and submit attendance (Alice Present, Bob Absent)
        attendance = frappe.get_doc({
            "doctype": "Training Attendance",
            "training_session": self.session.name,
            "attendance_details": [
                {
                    "employee": self.emp1.name,
                    "attendance_status": "Present"
                },
                {
                    "employee": self.emp2.name,
                    "attendance_status": "Absent"
                }
            ]
        })
        attendance.insert(ignore_permissions=True)
        attendance.submit()

        # Alice should be Completed, Bob should be Not Completed
        self.assertEqual(frappe.db.get_value("Training Enrollment", self.enroll1.name, "completion_status"), "Completed")
        self.assertEqual(frappe.db.get_value("Training Enrollment", self.enroll2.name, "completion_status"), "Not Completed")

        # Session percentage should be 50.0%
        self.assertEqual(frappe.db.get_value("Training Session", self.session.name, "attendance_percentage"), 50.0)

        # Employee percentages should update
        self.assertEqual(frappe.db.get_value("Employee", self.emp1.name, "attendance_percentage"), 100.0)
        self.assertEqual(frappe.db.get_value("Employee", self.emp2.name, "attendance_percentage"), 0.0)

        # Trainer percentage should update
        self.assertEqual(frappe.db.get_value("Trainer", self.trainer.name, "attendance_percentage"), 50.0)

        # 4. Cancel attendance
        attendance.cancel()

        # Enrollments should revert to "In Progress"
        self.assertEqual(frappe.db.get_value("Training Enrollment", self.enroll1.name, "completion_status"), "In Progress")
        self.assertEqual(frappe.db.get_value("Training Enrollment", self.enroll2.name, "completion_status"), "In Progress")

        # Session percentage reset to 0
        self.assertEqual(frappe.db.get_value("Training Session", self.session.name, "attendance_percentage"), 0.0)
        self.assertEqual(frappe.db.get_value("Employee", self.emp1.name, "attendance_percentage"), 0.0)
        self.assertEqual(frappe.db.get_value("Employee", self.emp2.name, "attendance_percentage"), 0.0)
        self.assertEqual(frappe.db.get_value("Trainer", self.trainer.name, "attendance_percentage"), 0.0)

    def test_duplicate_attendance_prevented(self):
        self.session.status = "Ongoing"
        self.session.save(ignore_permissions=True)

        attendance = frappe.get_doc({
            "doctype": "Training Attendance",
            "training_session": self.session.name,
            "attendance_details": [
                {
                    "employee": self.emp1.name,
                    "attendance_status": "Present"
                },
                {
                    "employee": self.emp1.name,  # Duplicate Alice
                    "attendance_status": "Late"
                }
            ]
        })
        self.assertRaises(frappe.ValidationError, attendance.insert)

    def test_non_enrolled_employee_blocked(self):
        # Create non-enrolled employee Charlie
        emp_charlie = frappe.get_doc({
            "doctype": "Employee",
            "employee_name": "Employee Charlie Attendance",
            "employee_id": "EMP-CHARLIE-ATTN",
            "department": "Engineering",
            "designation": "Developer",
            "status": "Active",
            "active": 1
        }).insert()

        self.session.status = "Ongoing"
        self.session.save(ignore_permissions=True)

        attendance = frappe.get_doc({
            "doctype": "Training Attendance",
            "training_session": self.session.name,
            "attendance_details": [
                {
                    "employee": emp_charlie.name,
                    "attendance_status": "Present"
                }
            ]
        })
        self.assertRaises(frappe.ValidationError, attendance.insert)
