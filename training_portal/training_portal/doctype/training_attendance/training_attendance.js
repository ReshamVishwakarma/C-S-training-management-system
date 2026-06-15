function fetch_enrollments(frm) {

    if (!frm.doc.training_session) {
        return;
    }

    frappe.call({
        method: "training_portal.training_portal.doctype.training_attendance.training_attendance.fetch_enrollments",
        args: {
            training_session: frm.doc.training_session
        },
        callback: function(r) {

            frm.clear_table("attendance_details");

            (r.message || []).forEach(row => {

                let child = frm.add_child("attendance_details");

                child.employee = row.employee;
                child.employee_name = row.employee_name;
                child.attendance_status = row.attendance_status;
            });

            frm.doc.total_participants = frm.doc.attendance_details.length;

            frm.refresh_field("attendance_details");
            frm.refresh_field("total_participants");
        }
    });
}

frappe.ui.form.on("Training Attendance", {

    training_session(frm) {
        fetch_enrollments(frm);
    },

    refresh(frm) {

        frm.add_custom_button("Fetch Enrollments", function () {
            fetch_enrollments(frm);
        });

    }
});
