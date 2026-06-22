# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
import datetime
from frappe.utils import now_datetime


def auto_update_session_statuses():
    # Fetch all active sessions (Scheduled or Ongoing)
    sessions = frappe.get_all(
        "Training Session",
        filters={"status": ["in", ["Scheduled", "Ongoing"]]},
        fields=["name", "training_date", "start_time", "duration_hours", "status"]
    )
    
    now = now_datetime()
    
    # Strip timezone for datetime calculations if now is timezone-aware
    if now.tzinfo:
        now = now.replace(tzinfo=None)
        
    updated_count = 0
    for s in sessions:
        if not s.training_date or not s.start_time or not s.duration_hours:
            continue
            
        start_time = s.start_time
        if isinstance(start_time, str):
            parts = list(map(int, start_time.split(':')))
            if len(parts) == 3:
                start_time = datetime.timedelta(hours=parts[0], minutes=parts[1], seconds=parts[2])
            elif len(parts) == 2:
                start_time = datetime.timedelta(hours=parts[0], minutes=parts[1])
            elif len(parts) == 1:
                start_time = datetime.timedelta(hours=parts[0])
        elif isinstance(start_time, datetime.time):
            start_time = datetime.timedelta(hours=start_time.hour, minutes=start_time.minute, seconds=start_time.second)
            
        # Combine date and time
        start_dt = datetime.datetime.combine(s.training_date, datetime.time(0, 0)) + start_time
        end_dt = start_dt + datetime.timedelta(hours=float(s.duration_hours))
        
        new_status = None
        if start_dt <= now < end_dt:
            if s.status == "Scheduled":
                new_status = "Ongoing"
        elif now >= end_dt:
            if s.status in ["Scheduled", "Ongoing"]:
                new_status = "Completed"
                
        if new_status and new_status != s.status:
            # Set value and commit immediately for each update to keep DB in sync
            frappe.db.set_value("Training Session", s.name, "status", new_status)
            frappe.db.commit()

            if new_status == "Ongoing":
                frappe.db.set_value(
                    "Training Enrollment",
                    {"training_session": s.name, "completion_status": "Assigned"},
                    "completion_status",
                    "In Progress"
                )
                frappe.db.commit()

            updated_count += 1
            
    return updated_count
