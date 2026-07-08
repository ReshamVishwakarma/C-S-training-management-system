# Copyright (c) 2026, C&S Electric and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def get_trainer_department():
    roles = frappe.get_roles()
    # Admins/Managers bypass restrictions
    if any(r in roles for r in ["System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"]):
        return None

    if "Trainer" in roles:
        trainer_user = frappe.session.user
        trainer_name = frappe.db.get_value("Trainer", {"user": trainer_user})
        if not trainer_name:
            trainer_name = frappe.db.get_value("Trainer", {"email": trainer_user})
        if not trainer_name and "@" not in trainer_user:
            user_email = frappe.db.get_value("User", trainer_user, "email")
            if user_email:
                trainer_name = frappe.db.get_value("Trainer", {"user": user_email}) or frappe.db.get_value("Trainer", {"email": user_email})
        if not trainer_name:
            trainer_name = frappe.db.get_value("Trainer", {"name": trainer_user})

        trainer_dept = None
        if trainer_name:
            trainer_dept = frappe.db.get_value("Trainer", trainer_name, "department")

        if not trainer_dept:
            frappe.throw(_("Trainer profile not mapped to a department. Contact Administrator."), frappe.PermissionError)
        return trainer_dept

    return None

def check_portal_permission():
    if frappe.session.user == "Guest":
        frappe.local.flags.redirect_location = "/login"
        raise frappe.Redirect

    roles = frappe.get_roles()
    request_path = frappe.request.path if (frappe.request and hasattr(frappe.request, "path")) else ""

    is_hr_route = "hr_" in request_path
    is_employee_route = "employee_" in request_path
    is_trainer_route = any(x in request_path for x in ["trainer", "assign_training", "create_training", "edit_training"])

    if is_hr_route:
        is_hr_admin = any(r in roles for r in ["HR Administrator", "System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"])
        if not is_hr_admin:
            frappe.throw(_("Access Denied: HR Admin privileges required."), frappe.PermissionError)

    elif is_employee_route:
        is_employee = "Employee" in roles or "Trainee" in roles
        is_admin = any(r in roles for r in ["System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"])
        if not (is_employee or is_admin):
            frappe.throw(_("Access Denied: Employee privileges required."), frappe.PermissionError)

    elif is_trainer_route:
        is_trainer = "Trainer" in roles
        is_admin = any(r in roles for r in ["System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"])
        if not (is_trainer or is_admin):
            frappe.throw(_("Access Denied: Trainer privileges required."), frappe.PermissionError)

    else:
        if not (any(r in roles for r in ["Trainer", "System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User", "Employee", "Trainee"])):
            frappe.throw(_("Not Permitted"), frappe.PermissionError)


def filter_courses_by_dept(filters, trainer_dept):
    if trainer_dept:
        filters["department"] = trainer_dept
    return filters

def filter_sessions_by_dept(filters, trainer_dept):
    if trainer_dept:
        courses = [c.name for c in frappe.get_all("Training Course", filters={"department": trainer_dept})]
        filters["course"] = ["in", courses]
    return filters

def filter_enrollments_by_dept(filters, trainer_dept):
    if trainer_dept:
        courses = [c.name for c in frappe.get_all("Training Course", filters={"department": trainer_dept})]
        sessions = [s.name for s in frappe.get_all("Training Session", filters={"course": ["in", courses]})]
        filters["training_session"] = ["in", sessions]
    return filters

def filter_attendances_by_dept(filters, trainer_dept):
    if trainer_dept:
        courses = [c.name for c in frappe.get_all("Training Course", filters={"department": trainer_dept})]
        sessions = [s.name for s in frappe.get_all("Training Session", filters={"course": ["in", courses]})]
        filters["training_session"] = ["in", sessions]
    return filters


# === Authentication & Authorization APIs ===

import random
import datetime
from frappe.utils.password import check_password

@frappe.whitelist(allow_guest=True)
def authenticate_login(email, password, selected_role):
    try:
        check_password(email, password)
    except frappe.AuthenticationError:
        frappe.throw(_("Invalid email or password."), frappe.AuthenticationError)

    roles = frappe.get_roles(email)
    
    role_valid = False
    if selected_role == "Trainer":
        role_valid = "Trainer" in roles
    elif selected_role == "Employee":
        role_valid = "Employee" in roles or "Trainee" in roles
    elif selected_role == "HR Admin":
        role_valid = any(r in roles for r in ["HR Administrator", "System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"])

    if not role_valid:
        frappe.throw(_("The user is not authorized for the selected role: {0}").format(selected_role), frappe.PermissionError)

    otp = "".join([str(random.randint(0, 9)) for _ in range(6)])

    # Log to terminal for development/testing
    print(f"OTP for {email} : {otp}", flush=True)
    frappe.logger().info(f"OTP for {email} : {otp}")

    frappe.cache().set_value(
        f"login_otp:{email}",
        {
            "otp": otp, 
            "role": selected_role, 
            "expires": (frappe.utils.datetime.datetime.now() + frappe.utils.datetime.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S.%f")
        },
        expires_in_sec=300
    )

    subject = "LMS Login OTP Verification"
    message = f"""
    <div style='font-family: Arial, sans-serif; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;'>
        <h2 style='color: #1a3c5e;'>LMS OTP Verification</h2>
        <p>Dear User,</p>
        <p>Your one-time password (OTP) to log into the C&S Electric LMS Portal as a <b>{selected_role}</b> is:</p>
        <div style='background-color: #f1f5f9; padding: 12px 24px; font-size: 24px; font-weight: 800; color: #1a3c5e; display: inline-block; border-radius: 6px; letter-spacing: 2px;'>{otp}</div>
        <p style='color: #64748b; font-size: 13px; margin-top: 20px;'>This OTP is valid for 5 minutes and is valid for one-time use only.</p>
    </div>
    """
    
    try:
        frappe.sendmail(
            recipients=email,
            subject=subject,
            message=message
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "LMS OTP Email Failed")

    return {"status": "success", "email": email, "role": selected_role}


@frappe.whitelist(allow_guest=True)
def verify_login_otp(email, otp):
    cache_key = f"login_otp:{email}"
    data = frappe.cache().get_value(cache_key)

    if not data:
        frappe.throw(_("OTP has expired or was not requested. Please try logging in again."), frappe.ValidationError)

    expires = data.get("expires")
    if isinstance(expires, str):
        expires = frappe.utils.datetime.datetime.strptime(expires, "%Y-%m-%d %H:%M:%S.%f")

    if frappe.utils.datetime.datetime.now() > expires:
        frappe.cache().delete_value(cache_key)
        frappe.throw(_("OTP has expired. Please request a new one."), frappe.ValidationError)

    stored_otp = data.get("otp")
    selected_role = data.get("role")

    print(f"Received OTP: {otp}", flush=True)
    print(f"Stored OTP: {stored_otp}", flush=True)
    frappe.logger().info(f"Received OTP: {otp}")
    frappe.logger().info(f"Stored OTP: {stored_otp}")

    if str(stored_otp) != str(otp):
        print("OTP mismatch.", flush=True)
        frappe.logger().info("OTP mismatch.")
        frappe.throw(_("Incorrect OTP code. Please try again."), frappe.ValidationError)

    print("OTP matched.", flush=True)
    print("Creating session...", flush=True)
    frappe.logger().info("OTP matched.")
    frappe.logger().info("Creating session...")
    
    frappe.local.login_manager.login_as(email)
    
    frappe.cache().delete_value(cache_key)

    redirect_url = "/employee_dashboard"
    if selected_role == "Trainer":
        redirect_url = "/trainer_dashboard"
    elif selected_role == "HR Admin":
        redirect_url = "/hr_dashboard"

    print(f"Redirecting to {redirect_url.strip('/')}", flush=True)
    frappe.logger().info(f"Redirecting to {redirect_url.strip('/')}")

    return {"status": "success", "redirect_url": redirect_url}


@frappe.whitelist(allow_guest=True)
def resend_login_otp(email, selected_role):
    roles = frappe.get_roles(email)
    role_valid = False
    if selected_role == "Trainer":
        role_valid = "Trainer" in roles
    elif selected_role == "Employee":
        role_valid = "Employee" in roles or "Trainee" in roles
    elif selected_role == "HR Admin":
        role_valid = any(r in roles for r in ["HR Administrator", "System Manager", "HR Admin", "Training Admin", "HR Manager", "HR User"])

    if not role_valid:
        frappe.throw(_("The user is not authorized for the selected role."), frappe.PermissionError)

    otp = "".join([str(random.randint(0, 9)) for _ in range(6)])

    # Log to terminal for development/testing
    print(f"OTP for {email} : {otp}", flush=True)
    frappe.logger().info(f"OTP for {email} : {otp}")

    frappe.cache().set_value(
        f"login_otp:{email}",
        {
            "otp": otp, 
            "role": selected_role, 
            "expires": (frappe.utils.datetime.datetime.now() + frappe.utils.datetime.timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S.%f")
        },
        expires_in_sec=300
    )

    message = f"""
    <div style='font-family: Arial, sans-serif; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;'>
        <h2 style='color: #1a3c5e;'>LMS OTP Verification (Resent)</h2>
        <p>Dear User,</p>
        <p>Your new one-time password (OTP) to log into the C&S Electric LMS Portal is:</p>
        <div style='background-color: #f1f5f9; padding: 12px 24px; font-size: 24px; font-weight: 800; color: #1a3c5e; display: inline-block; border-radius: 6px; letter-spacing: 2px;'>{otp}</div>
        <p style='color: #64748b; font-size: 13px; margin-top: 20px;'>This OTP is valid for 5 minutes and is valid for one-time use only.</p>
    </div>
    """
    try:
        frappe.sendmail(
            recipients=email,
            subject="LMS Login OTP Verification (Resent)",
            message=message
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "LMS OTP Email Failed")

    return {"status": "success"}


@frappe.whitelist(allow_guest=True)
def request_password_reset(email):
    if not frappe.db.exists("User", email):
        frappe.throw(_("User with this email does not exist."), frappe.ValidationError)

    otp = "".join([str(random.randint(0, 9)) for _ in range(6)])

    frappe.cache().set_value(
        f"reset_otp:{email}",
        {"otp": otp, "expires": frappe.utils.datetime.datetime.now() + frappe.utils.datetime.timedelta(minutes=5)},
        expires_in_sec=300
    )

    message = f"""
    <div style='font-family: Arial, sans-serif; padding: 20px; border: 1px solid #e2e8f0; border-radius: 8px;'>
        <h2 style='color: #1a3c5e;'>LMS Password Reset Request</h2>
        <p>Dear User,</p>
        <p>We received a request to reset your password. Use the following OTP code to proceed:</p>
        <div style='background-color: #f1f5f9; padding: 12px 24px; font-size: 24px; font-weight: 800; color: #1a3c5e; display: inline-block; border-radius: 6px; letter-spacing: 2px;'>{otp}</div>
        <p style='color: #64748b; font-size: 13px; margin-top: 20px;'>This OTP is valid for 5 minutes. If you did not request this, please ignore this email.</p>
    </div>
    """
    try:
        frappe.sendmail(
            recipients=email,
            subject="LMS Password Reset OTP",
            message=message
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "LMS OTP Email Failed")

    return {"status": "success"}


@frappe.whitelist(allow_guest=True)
def reset_password(email, otp, new_password):
    cache_key = f"reset_otp:{email}"
    data = frappe.cache().get_value(cache_key)

    if not data:
        frappe.throw(_("OTP has expired or was not requested. Please try again."), frappe.ValidationError)

    expires = data.get("expires")
    if isinstance(expires, str):
        expires = frappe.utils.datetime.datetime.strptime(expires, "%Y-%m-%d %H:%M:%S.%f")

    if frappe.utils.datetime.datetime.now() > expires:
        frappe.cache().delete_value(cache_key)
        frappe.throw(_("OTP has expired. Please request a new one."), frappe.ValidationError)

    if str(data.get("otp")) != str(otp):
        frappe.throw(_("Incorrect OTP code."), frappe.ValidationError)

    user_doc = frappe.get_doc("User", email)
    user_doc.new_password = new_password
    user_doc.save(ignore_permissions=True)
    frappe.db.commit()

    frappe.cache().delete_value(cache_key)

    return {"status": "success"}


@frappe.whitelist(allow_guest=True)
def check_user_has_password(email):
    if not frappe.db.exists("User", email):
        return {"has_password": True}
        
    res = frappe.db.sql("select password from `__Auth` where doctype='User' and name=%s and fieldname='password'", (email,))
    has_pwd = len(res) > 0 and res[0][0] is not None
    return {"has_password": has_pwd}


@frappe.whitelist(allow_guest=True)
def setup_user_password(email, password):
    if not frappe.db.exists("User", email):
        frappe.throw(_("User does not exist."), frappe.DoesNotExistError)
        
    res = frappe.db.sql("select password from `__Auth` where doctype='User' and name=%s and fieldname='password'", (email,))
    if len(res) > 0 and res[0][0] is not None:
        frappe.throw(_("Password is already set for this account. Please use Forgot Password to reset it."), frappe.PermissionError)
        
    from frappe.utils.password import update_password
    update_password(user=email, pwd=password)
    frappe.db.commit()
    
    return {"status": "success"}
