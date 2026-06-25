# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe.utils import today
from training_portal.training_portal.access_control import get_trainer_department, check_portal_permission


def get_context(context):
    check_portal_permission()

    user = frappe.session.user
    context.user = user

    # 1. Fetch trainer record if it exists
    trainer = frappe.db.get_value(
        "Trainer",
        {"user": user},
        ["name", "trainer_name", "department", "designation", "expertise"],
        as_dict=True
    )
    context.trainer = trainer

    # 2. Get department restriction (returns None if Admin/HR)
    trainer_dept = get_trainer_department()
    context.trainer_dept = trainer_dept

    # 3. Calculate metrics based on department access
    if trainer_dept:
        # Restricted trainer view
        courses = [c.name for c in frappe.get_all("Training Course", filters={"department": trainer_dept})]
        
        context.assigned_trainings = frappe.db.count(
            "Training Session",
            {"course": ["in", courses]}
        )
        context.today_sessions = frappe.db.count(
            "Training Session",
            {"course": ["in", courses], "training_date": today()}
        )
        context.upcoming_sessions = frappe.db.count(
            "Training Session",
            {"course": ["in", courses], "training_date": [">=", today()]}
        )
        
        sessions = [s.name for s in frappe.get_all("Training Session", filters={"course": ["in", courses]})]
        if sessions:
            context.total_trainees = frappe.db.count(
                "Training Enrollment",
                {"training_session": ["in", sessions]}
            )
        else:
            context.total_trainees = 0
            
        context.recent_sessions = frappe.get_all(
            "Training Session",
            filters={"course": ["in", courses]},
            fields=["name", "training_name", "training_date", "training_mode", "status"],
            order_by="training_date desc",
            limit=10
        )
    else:
        # Full admin / HR view
        context.assigned_trainings = frappe.db.count("Training Session")
        context.today_sessions = frappe.db.count("Training Session", {"training_date": today()})
        context.upcoming_sessions = frappe.db.count("Training Session", {"training_date": [">=", today()]})
        context.total_trainees = frappe.db.count("Training Enrollment")
        
        context.recent_sessions = frappe.get_all(
            "Training Session",
            fields=["name", "training_name", "training_date", "training_mode", "status"],
            order_by="training_date desc",
            limit=10
        )

    return context