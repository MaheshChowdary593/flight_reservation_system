from flask import Flask, render_template, request, redirect, url_for, session, flash, get_flashed_messages
from supabase import create_client, Client
from functools import wraps
import re
from uuid import uuid4
from amadeus import Client, ResponseError
import os
from dotenv import load_dotenv
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

app = Flask(__name__)
app.secret_key = "Saikumar@277"  # Use environment variable in production
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

# Supabase configuration
SUPABASE_URL = "https://yjndrsaktxqfsqohtaol.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlqbmRyc2FrdHhxZnNxb2h0YW9sIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NDQzMTE5NDcsImV4cCI6MjA1OTg4Nzk0N30.lnoDSoU4kw9Auf_2uxCDIIzE93ihUVH9rcP60fJMEOI"
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Amadeus configuration
load_dotenv('a.env')
amadeus = Client(
    client_id=os.getenv('AMADEUS_CLIENT_ID'),
    client_secret=os.getenv('AMADEUS_CLIENT_SECRET')
)

# Email configuration (assuming these are defined in your .env file)
EMAIL_ADDRESS = os.getenv('EMAIL_ADDRESS')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')

# Helper functions
def is_valid_email(email):
    return re.match(r"^[^\s@]+@[^\s@]+\.[^\s@]+$", email)

def is_valid_password(password):
    return bool(re.match(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$", password))

def is_valid_fullname(name):
    return bool(re.match(r"^[A-Za-z\s]{2,}$", name))

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session.get('role') != 'admin':
            flash("Admin access required.", "danger")
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# Authentication routes
@app.route("/")
def landing_page():
    return redirect(url_for('login_signup'))

@app.route("/login", methods=["GET", "POST"])
def login_signup():
    if 'user' in session:
        return redirect(url_for('home'))

    if request.method == "POST":
        # Handle login
        if "login" in request.form:
            email = request.form["email"].strip()
            password = request.form["password"]

            if not is_valid_email(email) or not is_valid_password(password):
                flash("Invalid email or password format.", "danger")
                return render_template("login.html")

            try:
                result = supabase.auth.sign_in_with_password({"email": email, "password": password})
                if getattr(result, "session", None):
                    user_data = supabase.table('users').select('*').eq('email', email).execute()
                    if user_data.data:
                        session.update({
                            'user': email,
                            'user_id': user_data.data[0]['user_id'],
                            'fullname': user_data.data[0]['fullname'],
                            'role': user_data.data[0].get('role', 'user')
                        })
                    flash('Login successful!', 'success')
                    return redirect(url_for('home'))
                else:
                    flash('Invalid credentials or email not confirmed.', 'danger')
            except Exception as e:
                flash(f"Login failed: {str(e)}", 'danger')

        # Handle signup
        elif "signup" in request.form:
            fullname = request.form["fullname"].strip()
            email = request.form["email"].strip()
            password = request.form["password"]

            if not all([is_valid_fullname(fullname), is_valid_email(email), is_valid_password(password)]):
                return render_template("login.html")

            try:
                result = supabase.auth.sign_up({"email": email, "password": password})
                user = getattr(result, "user", None)
                if user and user.id:
                    supabase.table('users').insert({
                        "user_id": user.id,
                        "email": email,
                        "fullname": fullname,
                        "role": "user"
                    }).execute()
                    flash('Account created! Please check your email.', 'success')
                    return redirect(url_for('login_signup'))
                else:
                    flash('Signup failed: Unable to create user.', 'danger')
            except Exception as e:
                flash(f"Signup failed: {str(e)}", 'danger')

    return render_template("login.html")

@app.route("/login/google")
def login_google():
    try:
        res = supabase.auth.sign_in_with_oauth({
            "provider": "google",
            "options": {"redirect_to": "http://localhost:3000/login/callback"}
        })
        return redirect(res.url)
    except Exception as e:
        flash(f"Google login failed: {str(e)}", "danger")
        return redirect(url_for('login_signup'))

@app.route("/login/callback")
def login_callback():
    try:
        code = request.args.get('code')
        if not code:
            raise ValueError("Missing authorization code")

        # Exchange code for session
        res = supabase.auth.exchange_code_for_session({"auth_code": code})
        user = res.user

        # Sync with database
        user_data = supabase.table('users').select('*').eq('user_id', user.id).execute()
        if not user_data.data:
            supabase.table('users').insert({
                "user_id": user.id,
                "email": user.email,
                "fullname": user.user_metadata.get('full_name', ''),
                "role": "user"
            }).execute()

        session.update({
            'user': user.email,
            'user_id': user.id,
            'fullname': user.user_metadata.get('full_name', 'User'),
            'role': "user"
        })
        flash('Logged in with Google!', 'success')
        return redirect(url_for('home'))
    except Exception as e:
        flash(f"Google login failed: {str(e)}", "danger")
        return redirect(url_for('login_signup'))

@app.route("/logout")
def logout():
    supabase.auth.sign_out()
    session.clear()
    flash('Logged out successfully!', 'success')
    return redirect(url_for('login_signup'))

# Core application routes
@app.route("/home")
def home():
    if 'user' not in session:
        return redirect(url_for('login_signup'))
    return render_template("home.html")

@app.route("/admin")
@admin_required
def admin_dashboard():
    try:
        users = supabase.table('users').select('*').execute().data
        bookings = supabase.table('bookings').select('*').execute().data
    except Exception as e:
        flash(f"Error loading admin data: {str(e)}", "danger")
        users = []
        bookings = []
    
    return render_template("admin_dashboard.html", users=users, bookings=bookings)

@app.route('/search-flights', methods=['GET'])
def search_flights():
    if 'user' not in session:
        flash("Please login to search flights", "warning")
        return redirect(url_for('login_signup'))

    origin = request.args.get('from', '').strip().upper()
    destination = request.args.get('to', '').strip().upper()
    date = request.args.get('date', '').strip()

    flights = []
    error_message = None

    if origin and destination and date:
        try:
            response = amadeus.shopping.flight_offers_search.get(
                originLocationCode=origin,
                destinationLocationCode=destination,
                departureDate=date,
                adults=1
            )
            offers = response.data
            if not offers:
                flash("No flights found for the given search.", "warning")
            else:
                for offer in offers:
                    itinerary = offer['itineraries'][0]['segments'][0]
                    flights.append({
                        'airline': itinerary['carrierCode'],
                        'flight_number': itinerary['number'],
                        'departure_time': itinerary['departure']['at'],
                        'arrival_time': itinerary['arrival']['at'],
                        'price': offer['price']['total'] + " " + offer['price']['currency']
                    })
        except ResponseError as error:
            error_message = str(error)
            flash(f"Error searching flights: {error_message}", "danger")
    else:
        flash("Please provide origin, destination, and date.", "danger")

    return render_template('search_results.html', flights=flights, error_message=error_message)

@app.route('/book-flight', methods=['POST'])
def book_flight():
    if 'user' not in session:
        flash("Please login to book flights", "warning")
        return redirect(url_for('login_signup'))

    flight_details = {
        'airline': request.form['airline'],
        'flight_number': request.form['flight_number'],
        'departure_time': request.form['departure_time'],
        'arrival_time': request.form['arrival_time'],
        'price': request.form['price']
    }
    print(f"Flight Details: {flight_details}")  # Debugging flight details

    return render_template('book_flight.html', flight=flight_details)

@app.route('/confirm-booking', methods=['POST'])
def confirm_booking():
    if 'user' not in session:
        flash("Please login to book flights", "warning")
        return redirect(url_for('login_signup'))

    # Clear existing flash messages
    get_flashed_messages()

    required_fields = ['airline', 'flight_number', 'departure_time', 'arrival_time', 'base_price', 'seats']
    if not all(field in request.form for field in required_fields):
        flash("Missing required booking details", "danger")
        return redirect(url_for('home'))

    try:
        seats = int(request.form['seats'])
        if seats < 1 or seats > 10:
            flash("Number of seats must be between 1 and 10", "danger")
            return redirect(url_for('home'))

        # Extract base price and currency
        base_price_str = request.form['base_price']
        price_match = re.match(r"([\d.]+)\s*(\w+)", base_price_str)
        if not price_match:
            flash("Invalid price format", "danger")
            return redirect(url_for('home'))

        base_price = float(price_match.group(1))
        currency = price_match.group(2)
        total_price = f"{base_price * seats:.2f} {currency}"

        booking_id = str(uuid4())
        booking_data = {
            "booking_id": booking_id,
            "user_id": session['user_id'],
            "airline": request.form['airline'],
            "flight_number": request.form['flight_number'],
            "departure_time": request.form['departure_time'],
            "arrival_time": request.form['arrival_time'],
            "price": total_price,
            "seats": seats,
            "status": "Booked"
        }
        print(f"Booking Data: {booking_data}")  # Debugging

        # Insert booking into Supabase
        supabase.table('bookings').insert(booking_data).execute()

        # Fetch user email
        user_response = supabase.table('users').select('email').eq('user_id', session['user_id']).execute()
        if user_response.data and len(user_response.data) > 0:
            user_email = user_response.data[0]['email']
            # Send confirmation email
            if send_booking_confirmation_email(user_email, booking_data):
                flash("Booking successful! A confirmation email has been sent.", "success")
            else:
                flash("Booking successful, but failed to send confirmation email.", "warning")
        else:
            flash("Booking successful, but user email not found.", "warning")

        return redirect(url_for('booking_success', booking_id=booking_id))
    except Exception as e:
        print(f"Supabase Error: {str(e)}")  # Debugging
        flash(f"Booking failed: {str(e)}", "danger")
        return redirect(url_for('home'))

@app.route('/booking-success')
def booking_success():
    booking_id = request.args.get('booking_id')
    return render_template('booking_success.html', booking_id=booking_id)

def send_booking_confirmation_email(user_email, booking_data):
    try:
        # Create the email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'FlightReserve - Booking Confirmation'
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = user_email

        # HTML email template
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; }}
                .container {{ max-width: 600px; margin: 20px auto; background: #fff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); }}
                .header {{ background: #007bff; color: #fff; padding: 10px; text-align: center; border-radius: 8px 8px 0 0; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .content {{ padding: 20px; }}
                .content p {{ margin: 10px 0; font-size: 16px; }}
                .content strong {{ color: #333; }}
                .footer {{ text-align: center; padding: 10px; font-size: 14px; color: #666; }}
                .btn {{ display: inline-block; background: #007bff; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 4px; margin-top: 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>FlightReserve</h1>
                </div>
                <div class="content">
                    <p>Dear Customer,</p>
                    <p>Your booking has been confirmed! Below are your booking details:</p>
                    <p><strong>Booking Reference:</strong> {booking_data['booking_id']}</p>
                    <p><strong>Flight:</strong> {booking_data['airline']} {booking_data['flight_number']}</p>
                    <p><strong>Departure:</strong> {booking_data['departure_time']}</p>
                    <p><strong>Arrival:</strong> {booking_data['arrival_time']}</p>
                    <p><strong>Number of Seats:</strong> {booking_data['seats']}</p>
                    <p><strong>Total Price:</strong> {booking_data['price']}</p>
                    <p><strong>Status:</strong> {booking_data['status']}</p>
                    <p>You can view or manage your bookings at any time.</p>
                    <a href="{url_for('my_bookings', _external=True)}" class="btn">View My Bookings</a>
                </div>
                <div class="footer">
                    <p>Thank you for choosing FlightReserve!</p>
                    <p>© 2025 FlightReserve. All rights reserved.</p>
                </div>
            </div>
        </body>
        </html>
        """

        # Attach HTML to email
        part = MIMEText(html, 'html')
        msg.attach(part)

        # Connect to Gmail's SMTP server
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, user_email, msg.as_string())

        print(f"Email sent to {user_email}")  # Debugging
        return True
    except Exception as e:
        print(f"Email Error: {str(e)}")  # Debugging
        return False

@app.route("/my_bookings")
def my_bookings():
    if 'user' not in session:
        flash("Please login to view bookings", "warning")
        return redirect(url_for('login_signup'))
    
    try:
        bookings = supabase.table('bookings').select('*').eq('user_id', session['user_id']).execute().data
    except Exception as e:
        flash(f"Error loading bookings: {str(e)}", "danger")
        bookings = []
    
    return render_template("my_bookings.html", bookings=bookings)

@app.route('/manage-bookings', methods=['GET'])
def manage_bookings():
    if 'user' not in session:
        flash("Please login to manage bookings", "warning")
        return redirect(url_for('login_signup'))

    booking_ref = request.args.get('booking_ref', '').strip()
    if not booking_ref:
        return redirect(url_for('my_bookings'))

    try:
        booking = supabase.table('bookings') \
            .select('*') \
            .eq('booking_id', booking_ref) \
            .eq('user_id', session['user_id']) \
            .execute().data
        if not booking:
            flash("Booking not found", "danger")
            return redirect(url_for('my_bookings'))
    except Exception as e:
        flash(f"Error retrieving booking: {str(e)}", "danger")
        return redirect(url_for('my_bookings'))

    return render_template('manage_booking.html', booking=booking[0])

@app.route('/cancel_booking', methods=['POST'])
def cancel_booking():
    booking_ref = request.form['booking_ref']

    response = supabase.table('bookings')\
        .update({'status': 'Cancelled'})\
        .eq('booking_id', booking_ref)\
        .execute()

    if response.data:
        flash('Booking cancelled successfully.')
    else:
        flash('Failed to cancel booking.')

    return redirect(url_for('my_bookings'))

@app.route('/check-in', methods=['POST'])
def check_in():
    if 'user' not in session:
        flash("Please login to check in", "warning")
        return redirect(url_for('login_signup'))

    booking_ref = request.form.get('booking_ref', '').strip()

    if not booking_ref:
        flash("Invalid booking reference", "danger")
        return redirect(url_for('my_bookings'))

    try:
        # Check if booking exists
        booking = supabase.table('bookings') \
            .select('*') \
            .eq('booking_id', booking_ref) \
            .eq('user_id', session['user_id']) \
            .execute().data
        if not booking:
            flash("Booking not found or you don't have permission to check in", "danger")
            return redirect(url_for('my_bookings'))

        # Update the booking status to "checked-in"
        supabase.table('bookings') \
            .update({'status': 'checked-in'}) \
            .eq('booking_id', booking_ref) \
            .eq('user_id', session['user_id']) \
            .execute()
        flash("Check-in successful!", "success")
    except Exception as e:
        flash(f"Check-in failed: {str(e)}", "danger")

    return redirect(url_for('my_bookings'))

# Informational pages
@app.route("/about")
def about():
    return render_template("about.html")

@app.route('/contact', methods=['GET'])
def contact():
    return render_template('contacts.html')

@app.route('/submit_contact', methods=['POST'])
def submit_contact():
    name = request.form['name']
    email = request.form['email']
    message = request.form['message']
    
    flash("Thank you for reaching out! We'll get back to you soon.")
    return redirect(url_for('contact'))

@app.route("/password_reset", methods=["GET", "POST"])
def password_reset():
    if request.method == "POST":
        email = request.form["email"].strip()
        if not is_valid_email(email):
            flash("Invalid email format", "danger")
            return render_template("password_reset.html")
        
        try:
            supabase.auth.reset_password_for_email(email)
            flash('Password reset email sent', 'info')
            return redirect(url_for('login_signup'))
        except Exception as e:
            flash(f"Error sending reset email: {str(e)}", 'danger')
    
    return render_template("password_reset.html")

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=3000)