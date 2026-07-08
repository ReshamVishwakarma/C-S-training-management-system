# Copyright (c) 2026, C&S Electric and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestTrainingAssignment(FrappeTestCase):
    def setUp(self):
        frappe.clear_cache(doctype="Training Course")
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
                "active": 1,
                "status": "Active"
            }).insert()
        else:
            self.course = frappe.get_doc("Training Course", "Test Course Python")
            if self.course.department != "Engineering" or self.course.get("status") != "Active":
                self.course.department = "Engineering"
                self.course.status = "Active"
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
        if not frappe.db.exists("Employee", "Employee Alice Assignment"):
            self.emp_active = frappe.get_doc({
                "doctype": "Employee",
                "employee_name": "Employee Alice Assignment",
                "employee_id": "EMP-ALICE-ASSIGN",
                "department": "Engineering",
                "designation": "Developer",
                "status": "Active",
                "active": 1
            }).insert()
        else:
            self.emp_active = frappe.get_doc("Employee", "Employee Alice Assignment")

        # Create active HR employee (wrong department)
        if not frappe.db.exists("Employee", "Employee Bob Assignment"):
            self.emp_wrong_dept = frappe.get_doc({
                "doctype": "Employee",
                "employee_name": "Employee Bob Assignment",
                "employee_id": "EMP-BOB-ASSIGN",
                "department": "HR",
                "designation": "Manager",
                "status": "Active",
                "active": 1
            }).insert()
        else:
            self.emp_wrong_dept = frappe.get_doc("Employee", "Employee Bob Assignment")

        # Create inactive Engineering employee
        if not frappe.db.exists("Employee", "Employee Charlie Assignment"):
            self.emp_inactive = frappe.get_doc({
                "doctype": "Employee",
                "employee_name": "Employee Charlie Assignment",
                "employee_id": "EMP-CHARLIE-ASSIGN",
                "department": "Engineering",
                "designation": "Developer",
                "status": "Inactive",
                "active": 0
            }).insert()
        else:
            self.emp_inactive = frappe.get_doc("Employee", "Employee Charlie Assignment")

    def tearDown(self):
        # Clean up assignments and enrollments
        frappe.db.delete("Training Enrollment", {"training_session": self.session.name})
        frappe.db.delete("Training Assignment", {"training_session": self.session.name})
        frappe.db.delete("Training Session", {"name": self.session.name})
        frappe.db.delete("Training Course", {"name": self.course.name})
        frappe.db.delete("Trainer", {"name": self.trainer.name})
        frappe.db.delete("Employee", {"employee_name": ["in", ["Employee Alice Assignment", "Employee Bob Assignment", "Employee Charlie Assignment"]]})
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

    def test_assignment_wrong_department_succeeds(self):
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
        doc.submit()

        enrollment_name = f"{self.session.name}-{self.emp_wrong_dept.name}"
        self.assertTrue(frappe.db.exists("Training Enrollment", enrollment_name))

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

    def test_employee_list_advanced_filters_and_search(self):
        from training_portal.www.assign_training.index import get_employees_list

        # Set up plants, locations, types
        emp1 = frappe.get_doc("Employee", self.emp_active.name)
        emp1.plant = "Noida"
        emp1.location = "Sec 62"
        emp1.employment_type = "Full-time"
        emp1.save(ignore_permissions=True)

        emp2 = frappe.get_doc("Employee", self.emp_wrong_dept.name)
        emp2.plant = "Haridwar"
        emp2.location = "Plant 1"
        emp2.reporting_manager = self.emp_active.name
        emp2.employment_type = "Contract"
        emp2.save(ignore_permissions=True)

        # Test filter by plant
        emp_list = get_employees_list(plant="Noida")
        emp_names = [e.name for e in emp_list]
        self.assertIn(self.emp_active.name, emp_names)
        self.assertNotIn(self.emp_wrong_dept.name, emp_names)

        # Test filter by reporting manager
        emp_list = get_employees_list(reporting_manager=self.emp_active.name)
        emp_names = [e.name for e in emp_list]
        self.assertIn(self.emp_wrong_dept.name, emp_names)
        self.assertNotIn(self.emp_active.name, emp_names)

        # Test search term by ID
        emp_list = get_employees_list(search_term="EMP-ALICE")
        emp_names = [e.name for e in emp_list]
        self.assertIn(self.emp_active.name, emp_names)
        self.assertNotIn(self.emp_wrong_dept.name, emp_names)

        # Test search term by name
        emp_list = get_employees_list(search_term="Bob")
        emp_names = [e.name for e in emp_list]
        self.assertIn(self.emp_wrong_dept.name, emp_names)
        self.assertNotIn(self.emp_active.name, emp_names)

    def test_phase3_catalog_scheduling_and_status_rules(self):
        import json
        from training_portal.www.create_training.index import create_new_course
        from training_portal.www.assign_training.index import bulk_schedule_and_assign

        # 1. Test before_insert hook of Training Course (auto code generation and active status)
        new_course_doc = frappe.get_doc({
            "doctype": "Training Course",
            "course_name": "Autocode Generated Course",
            "department": "Engineering"
        })
        new_course_doc.insert(ignore_permissions=True)
        self.assertTrue(new_course_doc.course_code.startswith("TC-ENG-"))
        self.assertEqual(new_course_doc.status, "Active")

        # 2. Test status-based scheduling rules
        # Create an Inactive course
        inactive_course = frappe.get_doc({
            "doctype": "Training Course",
            "course_name": "Inactive Course Templates",
            "course_code": "TC-INACTIVE-101",
            "department": "Engineering",
            "status": "Inactive"
        }).insert(ignore_permissions=True)

        # Attempt to schedule Inactive course -> Should fail with Inactive status error message
        future_date = frappe.utils.add_days(frappe.utils.today(), 5)
        res = bulk_schedule_and_assign(
            course=inactive_course.name,
            trainer=self.trainer.name,
            training_date=future_date,
            start_time="10:00:00",
            duration_hours=2.0,
            training_mode="Online",
            employees=json.dumps([self.emp_active.name])
        )
        self.assertEqual(res.get("status"), "error")
        self.assertIn("Only Active courses can be scheduled", res.get("message"))

        # Create an Archived course
        archived_course = frappe.get_doc({
            "doctype": "Training Course",
            "course_name": "Archived Course Templates",
            "course_code": "TC-ARCHIVED-101",
            "department": "Engineering",
            "status": "Archived"
        }).insert(ignore_permissions=True)

        # Attempt to schedule Archived course -> Should fail
        res = bulk_schedule_and_assign(
            course=archived_course.name,
            trainer=self.trainer.name,
            training_date=future_date,
            start_time="10:00:00",
            duration_hours=2.0,
            training_mode="Online",
            employees=json.dumps([self.emp_active.name])
        )
        self.assertEqual(res.get("status"), "error")
        self.assertIn("Only Active courses can be scheduled", res.get("message"))

        # Test direct insertion validation in Training Session DocType
        session_doc = frappe.new_doc("Training Session")
        session_doc.course = inactive_course.name
        session_doc.trainer = self.trainer.name
        session_doc.training_date = future_date
        session_doc.start_time = "10:00:00"
        session_doc.duration_hours = 2.0
        session_doc.training_mode = "Online"
        session_doc.meeting_link = "https://teams.microsoft.com/test3"
        session_doc.status = "Scheduled"
        self.assertRaises(frappe.ValidationError, session_doc.insert)

        # 3. Test bulk scheduling and enrollment successfully
        print("DEBUG COURSE IN MEMORY STATUS:", self.course.get("status"))
        print("DEBUG COURSE IN DB STATUS:", frappe.db.get_value("Training Course", self.course.name, "status"))
        res = bulk_schedule_and_assign(
            course=self.course.name,
            trainer=self.trainer.name,
            training_date=future_date,
            start_time="10:00:00",
            duration_hours=2.0,
            training_mode="Online",
            meeting_link="https://teams.microsoft.com/test2",
            employees=json.dumps([self.emp_active.name])
        )
        print("DEBUG bulk_schedule_and_assign RESULT:", res)
        self.assertEqual(res.get("status"), "success")
        new_session_name = res.get("session_id")
        self.assertTrue(frappe.db.exists("Training Session", new_session_name))
        
        # Check if enrollment is created
        self.assertTrue(frappe.db.exists("Training Enrollment", f"{new_session_name}-{self.emp_active.name}"))

        # Cleanup
        frappe.db.delete("Training Enrollment", {"training_session": new_session_name})
        frappe.db.delete("Training Session", {"name": new_session_name})
        frappe.db.delete("Training Course", {"name": ["in", [new_course_doc.name, inactive_course.name, archived_course.name]]})

    def test_trainer_dropdown_removal_and_dynamic_subcategories(self):
        import json
        from training_portal.www.create_training.index import create_new_subcategory, get_active_subcategories
        from training_portal.www.assign_training.index import bulk_schedule_and_assign

        # 1. Create a User and Trainer to map
        trainer_user_email = "test_alice_trainer@example.com"
        if not frappe.db.exists("User", trainer_user_email):
            user_doc = frappe.get_doc({
                "doctype": "User",
                "email": trainer_user_email,
                "first_name": "Alice",
                "last_name": "Trainer",
                "roles": [{"role": "Trainer"}]
            }).insert(ignore_permissions=True)
            
        if not frappe.db.exists("Trainer", {"user": trainer_user_email}):
            trainer_doc = frappe.get_doc({
                "doctype": "Trainer",
                "trainer_name": "Alice Trainer",
                "user": trainer_user_email,
                "department": "Engineering",
                "active": 1,
                "trainer_type": "Internal"
            }).insert(ignore_permissions=True)
        else:
            trainer_doc = frappe.get_doc("Trainer", {"user": trainer_user_email})

        # Set user as our trainer
        old_user = frappe.session.user
        frappe.set_user(trainer_user_email)

        session_id = None
        try:
            # 2. Test create_new_subcategory API
            sub_res = create_new_subcategory(
                subcategory_name="Engineering Core",
                department="Engineering",
                description="Engineering courses subcategory"
            )
            self.assertEqual(sub_res.get("status"), "success")
            sub_name = sub_res.get("subcategory_name")
            self.assertTrue(frappe.db.exists("Training Subcategory", sub_name))

            # Audit check for Subcategory
            sub_doc = frappe.get_doc("Training Subcategory", sub_name)
            self.assertEqual(sub_doc.created_by, trainer_user_email)
            self.assertIsNotNone(sub_doc.created_on)
            self.assertIsNotNone(sub_doc.last_modified)

            # Try to create subcategory for HR (should return error status because trainer is in Engineering)
            hr_sub_res = create_new_subcategory("HR Core", "HR", "HR courses")
            self.assertEqual(hr_sub_res.get("status"), "error")
            self.assertIn("Access Violation", hr_sub_res.get("message"))

            # 3. Test bulk_schedule_and_assign with automatic trainer lookup
            future_date = frappe.utils.add_days(frappe.utils.today(), 4)
            assign_res = bulk_schedule_and_assign(
                course=self.course.name,
                training_date=future_date,
                start_time="11:00:00",
                duration_hours=2.0,
                training_mode="Online",
                meeting_link="https://teams.microsoft.com/test3",
                employees=json.dumps([self.emp_active.name])
            )
            self.assertEqual(assign_res.get("status"), "success")
            session_id = assign_res.get("session_id")
            
            # Verify trainer was mapped to our logged-in trainer automatically
            session_doc = frappe.get_doc("Training Session", session_id)
            self.assertEqual(session_doc.trainer, trainer_doc.name)
        finally:
            # 4. Clean up and restore user
            frappe.set_user(old_user)
            if session_id:
                frappe.db.delete("Training Enrollment", {"training_session": session_id})
                frappe.db.delete("Training Session", {"name": session_id})
            frappe.db.delete("Training Subcategory", {"name": "Engineering Core"})
            frappe.db.delete("Trainer", {"name": trainer_doc.name})
            frappe.db.delete("User", {"email": trainer_user_email})


