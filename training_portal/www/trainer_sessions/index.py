import frappe
from frappe.utils import today


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
        [
            "name",
            "trainer_name",
            "department"
        ],
        as_dict=True
    )

    context.trainer = trainer

    if not trainer:

        context.total_sessions = 0
        context.upcoming_sessions = 0
        context.today_sessions = 0
        context.completed_sessions = 0
        context.sessions = []

        return context

    # Total Sessions

    context.total_sessions = frappe.db.count(
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
            "training_date": [">", today()]
        }
    )

    # Completed Sessions

    context.completed_sessions = frappe.db.count(
        "Training Session",
        {
            "trainer": trainer.name,
            "status": "Completed"
        }
    )

    # Sessions List

    context.sessions = frappe.get_all(
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
        order_by="training_date desc"
    )

    return context