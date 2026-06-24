import frappe


def get_context(context):

    roles = frappe.get_roles()

    if (
      "Trainer" not in roles and
      "HR Administrator" not in roles
    ):
      frappe.throw("Not Permitted")

    session_name = frappe.form_dict.get("session")

    if not session_name:
        frappe.throw("Session not found")

    session = frappe.get_doc(
        "Training Session",
        session_name
    )

    trainer = frappe.get_doc(
        "Trainer",
        session.trainer
    )

    enrollments = frappe.get_all(
        "Training Enrollment",
        filters={
            "training_session": session.name
        },
        fields=[
            "employee",
            "department",
            "completion_status"
        ]
    )

    context.session = session
    context.trainer = trainer
    context.enrollments = enrollments
    context.start_time = str(session.start_time).split(".")[0][:5]

    return context