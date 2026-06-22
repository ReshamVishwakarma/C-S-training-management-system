import frappe
from frappe.utils import today


def get_context(context):

    #if "Trainer" not in frappe.get_roles():
    #    frappe.throw("Not Permitted")

    user = frappe.session.user
    context.user = user

    trainer = frappe.db.get_value(
        "Trainer",
        {"user": user},
        [
            "name",
            "trainer_name",
            "department",
            "designation",
            "expertise"
        ],
        as_dict=True
    )

    context.trainer = trainer

    if not trainer:

        context.assigned_trainings = 0
        context.today_sessions = 0
        context.upcoming_sessions = 0
        context.total_trainees = 0
        context.recent_sessions = []

        return context

    # Assigned Trainings

    context.assigned_trainings = frappe.db.count(
        "Training Session",
        {
            "trainer": trainer.name
        }
    )

    # Today's Sessions

    context.today_sessions = frappe.db.count(
        "Training Session",
        {
            "trainer": trainer.name,
            "training_date": today()
        }
    )

    # Upcoming Sessions

    context.upcoming_sessions = frappe.db.count(
        "Training Session",
        {
            "trainer": trainer.name,
            "training_date": [">=", today()]
        }
    )

    # Training Sessions handled by trainer

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

    # Recent Sessions Table

    context.recent_sessions = frappe.get_all(
        "Training Session",
        filters={
            "trainer": trainer.name
        },
        fields=[
            "name",
            "training_name",
            "training_date",
            "training_mode",
            "status"
        ],
        order_by="training_date desc",
        limit=10
    )

    return context