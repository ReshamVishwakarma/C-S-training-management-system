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
        frappe.db.commit()

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

