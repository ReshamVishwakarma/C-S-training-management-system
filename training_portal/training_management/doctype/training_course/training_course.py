# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from training_portal.training_portal.access_control import get_trainer_department


class TrainingCourse(Document):
    def before_insert(self):
        if not self.get("course_code"):
            dept_code = "".join([c for c in (self.department or "GEN") if c.isalnum()]).upper()[:3]
            name_code = "".join([w[0].upper() for w in (self.course_name or "TC").split() if w.isalnum()])[:4]
            random_str = frappe.generate_hash(length=4).upper()
            self.course_code = f"TC-{dept_code}-{name_code}-{random_str}"
        if not self.get("status"):
            self.status = "Active"
        self.created_by = frappe.session.user
        self.created_on = frappe.utils.now_datetime()
        self.last_modified = frappe.utils.now_datetime()

    def before_save(self):
        self.last_modified = frappe.utils.now_datetime()

    def validate(self):
        trainer_dept = get_trainer_department()
        if trainer_dept:
            if self.department != trainer_dept:
                frappe.throw(
                    _("Access Violation: You are mapped to the '{0}' department, and cannot create or edit courses for the '{1}' department.").format(
                        trainer_dept, self.department or "No Department"
                    ),
                    frappe.ValidationError
                )
