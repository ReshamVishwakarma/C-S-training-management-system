import frappe
from training_portal.training_portal.access_control import get_trainer_department, check_portal_permission


def get_context(context):
    check_portal_permission()

    user = frappe.session.user
    context.user = user

    trainer = frappe.db.get_value(
        "Trainer",
        {"user": user},
        ["name", "trainer_name", "department"],
        as_dict=True
    )
    context.trainer = trainer

    trainer_dept = get_trainer_department()
    context.trainer_dept = trainer_dept

    session_filters = {}
    if trainer and trainer_dept:
        # Restricted Trainer: filter by their department courses
        courses = [c.name for c in frappe.get_all("Training Course", filters={"department": trainer_dept})]
        session_filters["course"] = ["in", courses]
    elif trainer:
        # Admin Trainer: default to their own sessions
        session_filters["trainer"] = trainer.name
    else:
        # Admin with no trainer profile: show all sessions
        pass

    sessions = frappe.get_all(
        "Training Session",
        filters=session_filters,
        pluck="name"
    )

    if not sessions:
        context.enrollments = []
        context.total_enrollments = 0
        context.assigned = 0
        context.completed = 0
        context.in_progress = 0
        return context

    enrollments = frappe.get_all(
        "Training Enrollment",
        filters={
            "training_session": ["in", sessions]
        },
        fields=[
            "name",
            "training_session",
            "employee",
            "department",
            "completion_status"
        ]
    )

    context.enrollments = enrollments
    context.total_enrollments = len(enrollments)

    context.assigned = len([
        e for e in enrollments
        if e.completion_status == "Assigned"
    ])

    context.completed = len([
        e for e in enrollments
        if e.completion_status == "Completed"
    ])

    context.in_progress = len([
        e for e in enrollments
        if e.completion_status == "In Progress"
    ])

    return context