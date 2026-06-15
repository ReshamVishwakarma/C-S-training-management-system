import frappe

@frappe.whitelist(allow_guest=True)
def get_portal_stats():
    return {
        "total_sessions": frappe.db.count("Training Session"),
        "total_courses": frappe.db.count("Training Course"),
        "total_trainers": frappe.db.count("Trainer")
    }

@frappe.whitelist(allow_guest=True)
def get_training_sessions():
    return frappe.get_all(
        "Training Session",
        filters={"status": ["in", ["Scheduled", "Ongoing"]]},
        fields=["name", "training_name", "training_date",
                "training_mode", "trainer", "department", "status"]
    )
