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

@frappe.whitelist(allow_guest=True)
def check_db_state():
    import json
    res = {
        "Employee": frappe.db.count("Employee"),
        "Trainer": frappe.db.count("Trainer"),
        "Training Course": frappe.db.count("Training Course"),
        "Training Session": frappe.db.count("Training Session"),
        "Training Enrollment": frappe.db.count("Training Enrollment"),
        "Training Attendance": frappe.db.count("Training Attendance"),
        "Department": frappe.db.count("Department")
    }
    print(json.dumps(res, indent=4))
    return res
