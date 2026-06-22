# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, today


class TrainingSession(Document):
    def validate(self):
        self.validate_required_fields()
        self.validate_date_and_duration()
        if self.status != "Draft":
            self.validate_mode_requirements()
            self.validate_trainer_overlap()
        self.validate_status_transition()

    def validate_required_fields(self):
        if self.status != "Draft":
            if not self.training_date:
                frappe.throw(_("Training Date is required when status is not Draft."))
            if not self.start_time:
                frappe.throw(_("Start Time is required when status is not Draft."))
            if not self.duration_hours:
                frappe.throw(_("Duration is required when status is not Draft."))
            if not self.training_mode:
                frappe.throw(_("Training Mode is required when status is not Draft."))

    def validate_date_and_duration(self):
        # 1. Date must not be in the past for new training sessions
        if self.training_date and self.is_new() and getdate(self.training_date) < getdate(today()):
            frappe.throw(_("Training Date cannot be in the past."))

        # 2. Duration must be positive
        if self.duration_hours and float(self.duration_hours or 0) <= 0:
            frappe.throw(_("Duration must be a positive number of hours."))

    def validate_mode_requirements(self):
        # 3. Validate training mode fields
        if self.training_mode == "Online" and not self.meeting_link:
            frappe.throw(_("Meeting Link is required for Online training mode."))
        if self.training_mode == "Offline" and not self.location:
            frappe.throw(_("Location is required for Offline training mode."))

    def validate_trainer_overlap(self):
        # 4. Check for overlapping trainer schedules
        if not self.trainer or not self.training_date or not self.start_time or not self.duration_hours:
            return

        if self.status == "Cancelled":
            return

        import datetime

        # Parse start_time to timedelta
        self_start = self.start_time
        if isinstance(self_start, str):
            parts = list(map(int, self_start.split(':')))
            if len(parts) == 3:
                self_start = datetime.timedelta(hours=parts[0], minutes=parts[1], seconds=parts[2])
            elif len(parts) == 2:
                self_start = datetime.timedelta(hours=parts[0], minutes=parts[1])
            elif len(parts) == 1:
                self_start = datetime.timedelta(hours=parts[0])
        elif isinstance(self_start, datetime.time):
            self_start = datetime.timedelta(hours=self_start.hour, minutes=self_start.minute, seconds=self_start.second)

        self_end = self_start + datetime.timedelta(hours=float(self.duration_hours))

        # Query all overlapping sessions for the same trainer on the same date
        overlapping = frappe.get_all(
            "Training Session",
            filters={
                "trainer": self.trainer,
                "training_date": self.training_date,
                "name": ["!=", self.name],
                "status": ["in", ["Scheduled", "Ongoing"]]  # Only active sessions conflict
            },
            fields=["name", "training_name", "start_time", "duration_hours"]
        )

        for session in overlapping:
            s_start = session.start_time
            if isinstance(s_start, str):
                parts = list(map(int, s_start.split(':')))
                if len(parts) == 3:
                    s_start = datetime.timedelta(hours=parts[0], minutes=parts[1], seconds=parts[2])
                elif len(parts) == 2:
                    s_start = datetime.timedelta(hours=parts[0], minutes=parts[1])
                elif len(parts) == 1:
                    s_start = datetime.timedelta(hours=parts[0])
            elif isinstance(s_start, datetime.time):
                s_start = datetime.timedelta(hours=s_start.hour, minutes=s_start.minute, seconds=s_start.second)

            s_end = s_start + datetime.timedelta(hours=float(session.duration_hours or 0))

            # Overlap condition: (self_start < s_end) AND (s_start < self_end)
            if self_start < s_end and s_start < self_end:
                frappe.throw(
                    _("Trainer Overlap Conflict: Trainer '{0}' is already scheduled for session '{1}' ({2}) from {3} to {4}.").format(
                        self.trainer, session.training_name, session.name, str(s_start), str(s_end)
                    )
                )

    def validate_status_transition(self):
        if self.is_new():
            return

        old_status = frappe.db.get_value("Training Session", self.name, "status")
        if not old_status or old_status == self.status:
            return

        valid_transitions = {
            "Draft": ["Scheduled", "Cancelled"],
            "Scheduled": ["Ongoing", "Completed", "Cancelled"],
            "Ongoing": ["Completed", "Cancelled"],
            "Completed": [],
            "Cancelled": []
        }

        if self.status not in valid_transitions.get(old_status, []):
            frappe.throw(
                _("Invalid Status Transition: Cannot change session status from '{0}' to '{1}'.").format(
                    old_status, self.status
                )
            )

        if self.status == "Ongoing" and old_status != "Ongoing":
            frappe.db.set_value(
                "Training Enrollment",
                {"training_session": self.name, "completion_status": "Assigned"},
                "completion_status",
                "In Progress"
            )

