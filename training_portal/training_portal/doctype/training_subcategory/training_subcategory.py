# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe import _
from training_portal.training_portal.access_control import get_trainer_department


class TrainingSubcategory(Document):
    _DOCTYPE_NAME = "Training Subcategory"

    def before_insert(self):
        self.created_by = frappe.session.user
        self.created_on = frappe.utils.now_datetime()
        self.last_modified = frappe.utils.now_datetime()

    def before_save(self):
        self.last_modified = frappe.utils.now_datetime()

    def validate(self):
        # Enforce department restrictions for trainers
        trainer_dept = get_trainer_department()
        if trainer_dept:
            if self.department and self.department != trainer_dept:
                frappe.throw(
                    _("Access Violation: You belong to the '{0}' department, and cannot create or edit subcategories for the '{1}' department.").format(
                        trainer_dept, self.department
                    ),
                    frappe.ValidationError
                )
            # Automatically assign trainer's department if not explicitly set
            if not self.department:
                self.department = trainer_dept
