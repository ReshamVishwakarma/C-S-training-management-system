import frappe

def execute():
    # 1. Map existing Training Sessions to Training Courses
    sessions = frappe.get_all("Training Session", fields=["name", "training_name", "course"])
    for session in sessions:
        if not session.get("course"):
            # Find a matching course based on name prefix or exact match
            courses = frappe.get_all("Training Course", fields=["name", "course_name"])
            matched_course = None
            for course in courses:
                if course.course_name.lower() in session.training_name.lower():
                    matched_course = course.name
                    break
            
            if matched_course:
                frappe.db.set_value("Training Session", session.name, "course", matched_course)
                frappe.db.commit()
                print(f"Mapped session '{session.name}' to course '{matched_course}'")

    # 2. Rename existing Training Enrollments to {training_session}-{employee}
    enrollments = frappe.get_all("Training Enrollment", fields=["name", "training_session", "employee"])
    for enrollment in enrollments:
        expected_name = f"{enrollment.training_session}-{enrollment.employee}"
        if enrollment.name != expected_name:
            if not frappe.db.exists("Training Enrollment", expected_name):
                # Use rename_doc to update references
                frappe.rename_doc("Training Enrollment", enrollment.name, expected_name, force=True)
                frappe.db.commit()
                print(f"Renamed enrollment '{enrollment.name}' to '{expected_name}'")
