// Copyright (c) 2026, C&S Electric and contributors
// For license information, please see license.txt

frappe.ui.form.on('Training Assignment', {
    onload: function(frm) {
        if (frm.is_new() && !frm.doc.assignment_date) {
            frm.set_value('assignment_date', frappe.datetime.get_today());
        }
    },
    refresh: function(frm) {
        if (frm.doc.docstatus === 0) {
            frm.add_custom_button(__('Fetch Employees'), function() {
                fetch_employees(frm);
            });
        }
    },
    assignment_type: function(frm) {
        frm.set_value('department', '');
        frm.set_value('designation', '');
        frm.clear_table('employees');
        frm.refresh_field('employees');
        if (frm.doc.assignment_type === 'All Employees') {
            fetch_employees(frm);
        }
    },
    department: function(frm) {
        if (frm.doc.assignment_type === 'By Department') {
            fetch_employees(frm);
        }
    },
    designation: function(frm) {
        if (frm.doc.assignment_type === 'By Designation') {
            fetch_employees(frm);
        }
    }
});

function fetch_employees(frm) {
    if (!frm.doc.assignment_type) return;
    
    frappe.call({
        method: 'training_portal.training_portal.doctype.training_assignment.training_assignment.fetch_employees_for_assignment',
        args: {
            assignment_type: frm.doc.assignment_type,
            department: frm.doc.department,
            designation: frm.doc.designation
        },
        callback: function(r) {
            frm.clear_table('employees');
            if (r.message && r.message.length) {
                r.message.forEach(function(row) {
                    let child = frm.add_child('employees');
                    child.employee = row.employee;
                    child.employee_name = row.employee_name;
                    child.department = row.department;
                });
            } else {
                frappe.show_alert({message: __('No active employees found matching the criteria'), color: 'orange'});
            }
            frm.refresh_field('employees');
        }
    });
}
