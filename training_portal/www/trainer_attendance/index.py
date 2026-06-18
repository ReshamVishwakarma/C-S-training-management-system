import frappe


def get_context(context):

    if "Trainer" not in frappe.get_roles():
        frappe.throw("Not Permitted")

    trainer_user = frappe.session.user

    trainer = frappe.db.get_value(
        "Trainer",
        {"user": trainer_user},
        ["name", "trainer_name", "department"],
        as_dict=True
    )

    context.trainer = trainer

    attendance_records = frappe.get_all(
        "Training Attendance",
        filters={
            "trainer": trainer.name
        },
        fields=[
            "name",
            "training_session",
            "date",
            "total_participants",
            "present_count",
            "absent_count"
        ],
        order_by="date desc"
    )

    context.records = attendance_records

    total_participants = 0
    total_present = 0
    total_absent = 0

    for row in attendance_records:
        total_participants += row.total_participants or 0
        total_present += row.present_count or 0
        total_absent += row.absent_count or 0

    attendance_percentage = 0

    if total_participants:
        attendance_percentage = round(
            (total_present / total_participants) * 100,
            2
        )

    context.total_participants = total_participants
    context.total_present = total_present
    context.total_absent = total_absent
    context.attendance_percentage = attendance_percentage

    return context