import frappe

def populate():
    # Fetch all employees
    employees = frappe.get_all("Employee", fields=["name", "employee_name"])
    
    # Mappings
    departments = ["Engineering", "HR", "Sales", "Support", "Finance"]
    plants = ["Noida", "Haridwar", "Guwahati", "Delhi"]
    locations = ["Block A, Noida", "Sec 62, Noida", "Haridwar Plant 1", "Guwahati Plant 2", "Delhi Head Office"]
    emp_types = ["Full-time", "Part-time", "Contract", "Intern", "Probation"]
    statuses = ["Active", "Inactive", "On Leave", "Resigned", "Transferred"]
    designations = ["Developer", "HR Executive", "Manager", "Support Lead", "Accountant"]

    # Ensure departments exist
    for d in departments:
        if not frappe.db.exists("Department", d):
            frappe.get_doc({
                "doctype": "Department",
                "department_name": d
            }).insert(ignore_permissions=True)

    # Let's create two managers first
    if not frappe.db.exists("Employee", "EMP-MGR1"):
        mgr1 = frappe.get_doc({
            "doctype": "Employee",
            "name": "EMP-MGR1",
            "employee_id": "EMP-MGR1",
            "employee_name": "John Doe Manager",
            "email": "john.mgr@example.com",
            "department": "Engineering",
            "designation": "Manager",
            "status": "Active",
            "active": 1,
            "plant": "Noida",
            "location": "Block A, Noida",
            "employment_type": "Full-time"
        }).insert(ignore_permissions=True)
    else:
        mgr1 = frappe.get_doc("Employee", "EMP-MGR1")

    if not frappe.db.exists("Employee", "EMP-MGR2"):
        mgr2 = frappe.get_doc({
            "doctype": "Employee",
            "name": "EMP-MGR2",
            "employee_id": "EMP-MGR2",
            "employee_name": "Sarah Smith HR Manager",
            "email": "sarah.mgr@example.com",
            "department": "HR",
            "designation": "Manager",
            "status": "Active",
            "active": 1,
            "plant": "Delhi",
            "location": "Delhi Head Office",
            "employment_type": "Full-time"
        }).insert(ignore_permissions=True)
    else:
        mgr2 = frappe.get_doc("Employee", "EMP-MGR2")

    # Update existing employees with dummy info
    for i, emp_summary in enumerate(employees):
        if emp_summary.name in ["EMP-MGR1", "EMP-MGR2"]:
            continue
        emp = frappe.get_doc("Employee", emp_summary.name)
        
        # Cycle through options based on index to keep it deterministic
        emp.department = departments[i % len(departments)]
        emp.designation = designations[i % len(designations)]
        emp.plant = plants[i % len(plants)]
        emp.location = locations[i % len(locations)]
        emp.employment_type = emp_types[i % len(emp_types)]
        emp.status = statuses[i % len(statuses)]
        emp.active = 1 if emp.status == "Active" else 0
        emp.reporting_manager = mgr1.name if (i % 2 == 0) else mgr2.name
        
        if not emp.email:
            emp.email = f"{emp.name.lower().replace(' ', '.').replace('-', '_')}@example.com"
            
        emp.save(ignore_permissions=True)
        
    frappe.db.commit()
    print("Successfully populated dummy employee details!")
