import frappe


def get_context(context):

    roles = frappe.get_roles()

    if (
      "Trainer" not in roles and
      "HR Administrator" not in roles
    ):
      frappe.throw("Not Permitted")

    user = frappe.session.user

    trainer = frappe.db.get_value(
        "Trainer",
        {"user": user},
        ["name", "trainer_name", "department"],
        as_dict=True
    )

    context.trainer = trainer

    if not trainer:
        context.enrollments = []
        context.total_enrollments = 0
        context.assigned = 0
        context.completed = 0
        context.in_progress = 0
        return context

    sessions = frappe.get_all(
        "Training Session",
        filters={
            "trainer": trainer.name
        },
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