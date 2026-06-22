import frappe


def get_context(context):

    if "Trainer" not in frappe.get_roles():
        frappe.throw("Not Permitted")

    user = frappe.session.user

    trainer = frappe.db.get_value(
        "Trainer",
        {"user": user},
        [
            "name",
            "trainer_name",
            "department",
            "designation",
            "expertise",
            "phone_number",
            "email",
            "trainer_type",
            "active"
        ],
        as_dict=True
    )

    context.trainer = trainer

    if trainer:

        context.total_sessions = frappe.db.count(
            "Training Session",
            {
                "trainer": trainer.name
            }
        )

        sessions = frappe.get_all(
            "Training Session",
            filters={
                "trainer": trainer.name
            },
            pluck="name"
        )

        if sessions:
            context.total_trainees = frappe.db.count(
                "Training Enrollment",
                {
                    "training_session": ["in", sessions]
                }
            )
        else:
            context.total_trainees = 0

    else:
        context.total_sessions = 0
        context.total_trainees = 0

    return context