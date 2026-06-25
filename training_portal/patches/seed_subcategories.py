import frappe

def execute():
    # 1. Ensure default subcategories are created
    defaults = ["Technical", "Soft Skills", "Safety", "Compliance", "Leadership"]
    for cat in defaults:
        if not frappe.db.exists("Training Subcategory", cat):
            doc = frappe.new_doc("Training Subcategory")
            doc.subcategory_name = cat
            doc.is_active = 1
            doc.description = "System default subcategory"
            doc.insert(ignore_permissions=True)
            print(f"Created seed subcategory: {cat}")
    
    # 2. Find any custom categories used in existing courses and create subcategories for them
    existing_categories = frappe.db.sql_list("select distinct category from `tabTraining Course` where category is not null and category != ''")
    for cat in existing_categories:
        if not frappe.db.exists("Training Subcategory", cat):
            doc = frappe.new_doc("Training Subcategory")
            doc.subcategory_name = cat
            doc.is_active = 1
            doc.description = "Migrated from existing course category"
            doc.insert(ignore_permissions=True)
            print(f"Migrated existing course category: {cat}")
            
    frappe.db.commit()
