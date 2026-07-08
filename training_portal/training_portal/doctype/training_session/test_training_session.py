# Copyright (c) 2026, C&S Electric and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from training_portal.training_portal.scheduler import auto_update_session_statuses


class IntegrationTestTrainingSession(FrappeTestCase):
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

    def tearDown(self):
        # Delete test sessions created in tests
        frappe.db.delete("Training Session", {"course": "Test Course Python"})
        frappe.db.delete("Department", {"name": "Engineering"})

    def test_past_date_validation(self):
        doc = frappe.new_doc("Training Session")
        doc.course = self.course.name
        doc.training_date = "2020-01-01"
        doc.start_time = "10:00:00"
        doc.duration_hours = 2.0
        doc.trainer = self.trainer.name
        doc.training_mode = "Online"
        doc.meeting_link = "https://teams.microsoft.com/test"
        doc.status = "Scheduled"

        self.assertRaises(frappe.ValidationError, doc.insert)

    def test_mode_requirements(self):
        doc = frappe.new_doc("Training Session")
        doc.course = self.course.name
        doc.training_date = frappe.utils.add_days(frappe.utils.today(), 1)
        doc.start_time = "10:00:00"
        doc.duration_hours = 2.0
        doc.trainer = self.trainer.name
        doc.training_mode = "Online"
        doc.status = "Scheduled"

        # Missing meeting link
        self.assertRaises(frappe.ValidationError, doc.insert)

        # Missing location for offline
        doc.training_mode = "Offline"
        doc.meeting_link = ""
        doc.location = ""
        self.assertRaises(frappe.ValidationError, doc.insert)

    def test_trainer_overlap(self):
        future_date = frappe.utils.add_days(frappe.utils.today(), 2)

        doc1 = frappe.get_doc({
            "doctype": "Training Session",
            "course": self.course.name,
            "training_date": future_date,
            "start_time": "10:00:00",
            "duration_hours": 2.0,
            "trainer": self.trainer.name,
            "training_mode": "Online",
            "meeting_link": "https://teams.microsoft.com/test1",
            "status": "Scheduled"
        }).insert()

        doc2 = frappe.get_doc({
            "doctype": "Training Session",
            "course": self.course.name,
            "training_date": future_date,
            "start_time": "11:00:00",
            "duration_hours": 2.0,
            "trainer": self.trainer.name,
            "training_mode": "Online",
            "meeting_link": "https://teams.microsoft.com/test2",
            "status": "Scheduled"
        })

        self.assertRaises(frappe.ValidationError, doc2.insert)

    def test_scheduler_transitions(self):
        future_date = frappe.utils.add_days(frappe.utils.today(), 5)
        doc = frappe.get_doc({
            "doctype": "Training Session",
            "course": self.course.name,
            "training_date": future_date,
            "start_time": "10:00:00",
            "duration_hours": 2.0,
            "trainer": self.trainer.name,
            "training_mode": "Online",
            "meeting_link": "https://teams.microsoft.com/test",
            "status": "Scheduled"
        }).insert()

        # Update in database directly to bypass validation for testing transition to past
        past_date = frappe.utils.add_days(frappe.utils.today(), -2)
        frappe.db.set_value("Training Session", doc.name, "training_date", past_date)

        updated = auto_update_session_statuses()
        self.assertGreaterEqual(updated, 1)

        status = frappe.db.get_value("Training Session", doc.name, "status")
        self.assertEqual(status, "Completed")

    def test_status_transitions(self):
        future_date = frappe.utils.add_days(frappe.utils.today(), 5)
        doc = frappe.get_doc({
            "doctype": "Training Session",
            "course": self.course.name,
            "training_date": future_date,
            "start_time": "10:00:00",
            "duration_hours": 2.0,
            "trainer": self.trainer.name,
            "training_mode": "Online",
            "meeting_link": "https://teams.microsoft.com/test",
            "status": "Draft"
        }).insert()

        # Draft -> Scheduled is allowed
        doc.status = "Scheduled"
        doc.save()

        # Scheduled -> Ongoing is allowed
        doc.status = "Ongoing"
        doc.save()

        # Ongoing -> Completed is allowed
        doc.status = "Completed"
        doc.save()

        # Completed -> Draft is NOT allowed
        doc.status = "Draft"
        self.assertRaises(frappe.ValidationError, doc.save)

        # Create a new session in Draft to test Cancelled transition
        doc2 = frappe.get_doc({
            "doctype": "Training Session",
            "course": self.course.name,
            "training_date": future_date,
            "start_time": "11:00:00",
            "duration_hours": 2.0,
            "trainer": self.trainer.name,
            "training_mode": "Online",
            "meeting_link": "https://teams.microsoft.com/test",
            "status": "Draft"
        }).insert()

        # Draft -> Cancelled is allowed
        doc2.status = "Cancelled"
        doc2.save()

        # Cancelled -> Scheduled is NOT allowed
        doc2.status = "Scheduled"
        self.assertRaises(frappe.ValidationError, doc2.save)

    def test_required_fields_for_non_draft(self):
        future_date = frappe.utils.add_days(frappe.utils.today(), 5)
        
        # Saving as Draft without some fields is allowed (if doc permits, but start_time and training_date are not required by json schema)
        doc = frappe.get_doc({
            "doctype": "Training Session",
            "course": self.course.name,
            "trainer": self.trainer.name,
            "status": "Draft"
        })
        doc.insert()
        self.assertTrue(frappe.db.exists("Training Session", doc.name))

        # Trying to change status to Scheduled without date/time/mode/duration should throw validation error
        doc.status = "Scheduled"
        self.assertRaises(frappe.ValidationError, doc.save)

    def test_edit_training_context_serialization(self):
        from training_portal.www.edit_training.index import get_context
        import json

        # Create a session to ensure one exists
        future_date = frappe.utils.add_days(frappe.utils.today(), 5)
        doc = frappe.get_doc({
            "doctype": "Training Session",
            "course": self.course.name,
            "training_date": future_date,
            "start_time": "10:00:00",
            "duration_hours": 2.0,
            "trainer": self.trainer.name,
            "training_mode": "Online",
            "meeting_link": "https://teams.microsoft.com/test",
            "status": "Scheduled"
        }).insert()

        # Mock session user as our trainer
        trainer_user = frappe.db.get_value("Trainer", self.trainer.name, "user")
        if not trainer_user:
            frappe.db.set_value("Trainer", self.trainer.name, "user", "Administrator")
            trainer_user = "Administrator"

        old_user = frappe.session.user
        frappe.set_user(trainer_user)

        try:
            context = get_context(frappe._dict())
            self.assertIn("sessions", context)
            
            # Check serialization of sessions in context
            for session in context.sessions:
                serialized = json.dumps(session)
                deserialized = json.loads(serialized)
                self.assertEqual(deserialized["name"], session["name"])
                self.assertIsInstance(deserialized["start_time"], str)
                self.assertIsInstance(deserialized["training_date"], str)
        finally:
            frappe.set_user(old_user)

    def test_session_cancellation_and_participant_management(self):
        from training_portal.www.edit_training.index import cancel_training_session, add_participants, remove_participant, get_employees_for_selector
        import json

        future_date = frappe.utils.add_days(frappe.utils.today(), 5)
        session = frappe.get_doc({
            "doctype": "Training Session",
            "course": self.course.name,
            "training_date": future_date,
            "start_time": "10:00:00",
            "duration_hours": 2.0,
            "trainer": self.trainer.name,
            "training_mode": "Online",
            "meeting_link": "https://teams.microsoft.com/test",
            "status": "Scheduled"
        }).insert()

        # Create two test employees
        emp1 = frappe.get_doc({
            "doctype": "Employee",
            "employee_name": "Test Emp 1",
            "employee_id": "EMP-TEST-001",
            "department": "Engineering",
            "designation": "Developer",
            "status": "Active"
        }).insert()

        emp2 = frappe.get_doc({
            "doctype": "Employee",
            "employee_name": "Test Emp 2",
            "employee_id": "EMP-TEST-002",
            "department": "HR",
            "designation": "Manager",
            "status": "Active"
        }).insert()

        # Mock trainer user
        trainer_user = frappe.db.get_value("Trainer", self.trainer.name, "user")
        if not trainer_user:
            frappe.db.set_value("Trainer", self.trainer.name, "user", "Administrator")
            trainer_user = "Administrator"

        old_user = frappe.session.user
        frappe.set_user(trainer_user)

        try:
            # 1. Test add_participants
            res_add = add_participants(session.name, json.dumps([emp1.name, emp2.name]))
            self.assertEqual(res_add.get("status"), "success")
            self.assertEqual(res_add.get("enrolled_count"), 2)

            # Confirm enrollment exists in database
            enrollment_id1 = f"{session.name}-{emp1.name}"
            enrollment_id2 = f"{session.name}-{emp2.name}"
            self.assertTrue(frappe.db.exists("Training Enrollment", enrollment_id1))
            self.assertTrue(frappe.db.exists("Training Enrollment", enrollment_id2))

            # 2. Test get_employees_for_selector excludes already enrolled
            available_employees = get_employees_for_selector(session.name, department="Engineering")
            available_names = [e.name for e in available_employees]
            self.assertNotIn(emp1.name, available_names)

            # 3. Test remove_participant
            res_rem = remove_participant(enrollment_id1)
            self.assertEqual(res_rem.get("status"), "success")
            self.assertFalse(frappe.db.exists("Training Enrollment", enrollment_id1))

            # 4. Test cancel_training_session with audit logs
            res_cancel = cancel_training_session(session.name, reason="Trainer unavailable")
            self.assertEqual(res_cancel.get("status"), "success")
            
            # Fetch updated session
            updated_session = frappe.get_doc("Training Session", session.name)
            self.assertEqual(updated_session.status, "Cancelled")
            self.assertEqual(updated_session.cancelled_by, trainer_user)
            self.assertIsNotNone(updated_session.cancelled_on)
            self.assertEqual(updated_session.cancellation_reason, "Trainer unavailable")

        finally:
            frappe.set_user(old_user)
            # Cleanup
            frappe.db.delete("Training Enrollment", {"training_session": session.name})
            frappe.db.delete("Training Session", {"name": session.name})
            frappe.db.delete("Employee", {"name": ["in", [emp1.name, emp2.name]]})

