from flask import Flask, render_template, request, redirect, url_for, session, flash
from supabase import create_client, Client
from functools import wraps
import re
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "Saikumar@277")
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Supabase configuration
SUPABASE_URL = "https://yjndrsaktxqfsqohtaol.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlqbmRyc2FrdHhxZnNxb2h0YW9sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQzMTE5NDcsImV4cCI6MjA1OTg4Nzk0N30.lnoDSoU4kw9Auf_2uxCDIIzE93ihUVH9rcP60fJMEOI"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def is_valid_email(email):
    return re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email)

def is_valid_password(password):
    return bool(re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$", password))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_user' not in session or session.get('role') != 'admin':
            flash("Admin access required", "danger")
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route("/")
def root():
    return redirect(url_for('admin_login'))

@app.route("/admin/login", methods=['GET', 'POST'])
def admin_login():
    if 'admin_user' in session:
        return redirect(url_for('admin_dashboard'))

    if request.method == 'POST':
        if 'login' in request.form:
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')

            if not is_valid_email(email) or not is_valid_password(password):
                flash("Invalid email or password format", "danger")
                return render_template("login.html")

            try:
                result = supabase.auth.sign_in_with_password({
                    "email": email,
                    "password": password
                })
                if result.session:
                    user_data = supabase.table('users').select('*').eq('email', email).eq('role', 'admin').execute()
                    if user_data.data:
                        session.update({
                            'admin_user': email,
                            'user_id': user_data.data[0]['user_id'],
                            'fullname': user_data.data[0].get('fullname', 'Admin'),
                            'role': 'admin'
                        })
                        flash("Admin login successful", "success")
                        return redirect(url_for('admin_dashboard'))
                    else:
                        flash("No admin privileges found", "danger")
                else:
                    flash("Invalid credentials or unverified email", "danger")
            except Exception as e:
                flash(f"Login failed: {str(e)}", "danger")

        elif 'signup' in request.form:
            email = request.form.get('email', '').strip()
            password = request.form.get('password', '')
            username = request.form.get('username', '').strip()

            if not all([is_valid_email(email), is_valid_password(password), len(username) >= 2]):
                flash("Invalid registration details", "danger")
                return render_template("login.html")

            try:
                existing_user = supabase.table('users').select('email').eq('email', email).execute()
                if existing_user.data:
                    flash("Email already registered", "danger")
                    return render_template("login.html")

                auth_response = supabase.auth.sign_up({
                    "email": email,
                    "password": password
                })
                if auth_response.user and auth_response.user.id:
                    supabase.table('users').insert({
                        "user_id": auth_response.user.id,
                        "email": email,
                        "fullname": username,
                        "role": "admin"
                    }).execute()
                    flash("Admin account created. Please verify your email", "success")
                    return redirect(url_for('admin_login'))
            except Exception as e:
                flash(f"Registration failed: {str(e)}", "danger")

    return render_template("login.html")

@app.route("/admin/logout")
@admin_required
def admin_logout():
    try:
        supabase.auth.sign_out()
    except Exception:
        pass
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for('admin_login'))

@app.route("/admin/forgot-password", methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        if not is_valid_email(email):
            flash("Invalid email format", "danger")
            return redirect(url_for('forgot_password'))

        try:
            supabase.auth.reset_password_email(email)
            flash("Password reset link sent to your email", "success")
            return redirect(url_for('admin_login'))
        except Exception as e:
            flash(f"Password reset failed: {str(e)}", "danger")
    
    return render_template("forgot_password.html")

@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():
    access_token = request.args.get("access_token")
    type_ = request.args.get("type")
    if not access_token or type_ != "recovery":
        flash("Invalid or expired reset link.", "danger")
        return redirect(url_for('admin_login'))

    if request.method == "POST":
        new_password = request.form.get("password")
        try:
            supabase.auth.update_user({"password": new_password}, access_token)
            flash("Password updated successfully! Please log in.", "success")
            return redirect(url_for("admin_login"))
        except Exception as e:
            flash(f"Password reset failed: {str(e)}", "danger")
            return render_template("reset_password.html", access_token=access_token)

    return render_template("reset_password.html", access_token=access_token)

@app.route("/admin/dashboard", methods=["GET", "POST"])
@admin_required
def admin_dashboard():
    try:
        users = supabase.table('users').select('*').execute().data
        bookings = supabase.table('bookings').select('*').execute().data
        try:
            payments = supabase.table('payments').select('*').execute().data
        except Exception:
            payments = []
        try:
            discounts = supabase.table('discounts').select('*').execute().data
        except Exception:
            discounts = []
        try:
            tickets = supabase.table('support_tickets').select('*').execute().data
        except Exception:
            tickets = []
        try:
            settings_data = supabase.table('settings').select('*').execute().data
            settings = settings_data[0] if settings_data else {}
        except Exception:
            settings = {}
        try:
            notifications = supabase.table('notifications').select('*').order('created_at', desc=True).execute().data
        except Exception:
            notifications = []
        report = None
        if request.args.get("type"):
            report = generate_report(request.args.get("type"), bookings, payments)
    except Exception as e:
        flash(f"Error loading data: {str(e)}", "danger")
        users = []
        bookings = []
        payments = []
        discounts = []
        tickets = []
        settings = {}
        notifications = []
        report = None

    return render_template("admin_dashboard.html",
                           users=users, bookings=bookings, payments=payments,
                           discounts=discounts, tickets=tickets, settings=settings,
                           notifications=notifications, report=report)

@app.route("/admin/send_notification", methods=["POST"])
@admin_required
def admin_send_notification():
    subject = request.form["subject"]
    message = request.form["message"]
    try:
        supabase.table('notifications').insert({
            "subject": subject,
            "message": message,
            "created_at": datetime.utcnow().isoformat()
        }).execute()
        flash("Notification stored successfully", "success")
    except Exception as e:
        flash(f"Failed to store notification: {str(e)}", "danger")
    return redirect(url_for("admin_dashboard"))

# --- Report Generation Logic ---
def generate_report(report_type, bookings, payments):
    if report_type == "sales":
        total_sales = sum(float(b.get('amount', 0)) for b in bookings if b.get('status') == 'confirmed')
        num_sales = len([b for b in bookings if b.get('status') == 'confirmed'])
        return f"Total Sales: ₹{total_sales:.2f}\nNumber of Confirmed Bookings: {num_sales}"
    elif report_type == "cancellations":
        num_cancel = len([b for b in bookings if b.get('status') == 'cancelled'])
        return f"Total Cancellations: {num_cancel}\nCancelled Booking IDs: {[b['booking_id'] for b in bookings if b.get('status') == 'cancelled']}"
    elif report_type == "trends":
        # Example: Bookings per day (simple count)
        from collections import Counter
        dates = [b.get('created_at', '')[:10] for b in bookings if b.get('created_at')]
        trends = Counter(dates)
        return "\n".join([f"{date}: {count} bookings" for date, count in sorted(trends.items())])
    elif report_type == "finance":
        total_payments = sum(float(p.get('amount', 0)) for p in payments if p.get('status') == 'completed')
        total_refunded = sum(float(p.get('amount', 0)) for p in payments if p.get('status') == 'refunded')
        return f"Total Payments Received: ₹{total_payments:.2f}\nTotal Refunded: ₹{total_refunded:.2f}"
    else:
        return "Unknown report type."

@app.route("/admin/generate_report", methods=["GET"])
@admin_required
def admin_generate_report():
    report_type = request.args.get("type")
    return redirect(url_for("admin_dashboard", type=report_type))

# --- Other CRUD routes (unchanged, as in your current file) ---
@app.route("/admin/update_user_role", methods=["POST"])
@admin_required
def admin_update_user_role():
    user_id = request.form["user_id"]
    role = request.form["role"]
    supabase.table('users').update({"role": role}).eq("user_id", user_id).execute()
    flash("User role updated", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete_user", methods=["POST"])
@admin_required
def admin_delete_user():
    user_id = request.form["user_id"]
    supabase.table('users').delete().eq("user_id", user_id).execute()
    flash("User deleted", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/update_booking_status", methods=["POST"])
@admin_required
def admin_update_booking_status():
    booking_id = request.form["booking_id"]
    status = request.form["status"]
    supabase.table('bookings').update({"status": status}).eq("booking_id", booking_id).execute()
    flash("Booking status updated", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete_booking", methods=["POST"])
@admin_required
def admin_delete_booking():
    booking_id = request.form["booking_id"]
    supabase.table('bookings').delete().eq("booking_id", booking_id).execute()
    flash("Booking deleted", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/update_payment_status", methods=["POST"])
@admin_required
def admin_update_payment_status():
    payment_id = request.form["payment_id"]
    status = request.form["status"]
    supabase.table('payments').update({"status": status}).eq("payment_id", payment_id).execute()
    flash("Payment status updated", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/create_discount", methods=["POST"])
@admin_required
def admin_create_discount():
    code = request.form["code"]
    percent = int(request.form["percent"])
    valid_until = request.form.get("valid_until")  # This will be a string like '2025-05-01'
    supabase.table('discounts').insert({
        "code": code,
        "percent": percent,
        "valid_until": valid_until if valid_until else None
    }).execute()
    flash("Discount created", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/delete_discount", methods=["POST"])
@admin_required
def admin_delete_discount():
    code = request.form["code"]
    supabase.table('discounts').delete().eq("code", code).execute()
    flash("Discount deleted", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/update_ticket_status", methods=["POST"])
@admin_required
def admin_update_ticket_status():
    ticket_id = request.form["ticket_id"]
    status = request.form["status"]
    supabase.table('support_tickets').update({"status": status}).eq("ticket_id", ticket_id).execute()
    flash("Ticket status updated", "success")
    return redirect(url_for("admin_dashboard"))

@app.route("/admin/update_settings", methods=["POST"])
@admin_required
def admin_update_settings():
    payment_gateway = request.form["payment_gateway"]
    support_email = request.form["support_email"]
    supabase.table('settings').update({"payment_gateway": payment_gateway, "support_email": support_email}).execute()
    flash("Settings updated", "success")
    return redirect(url_for("admin_dashboard"))

if __name__ == '__main__':
    app.run(debug=True, port=5001, host='0.0.0.0')
