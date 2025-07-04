from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from dotenv import load_dotenv
import os
import re
import uuid
import logging

# Enable development mode (no AWS)
DEVELOPMENT_MODE = True

# Load .env variables
load_dotenv()

# Flask setup
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "fallback-secret")

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS mock setup
if not DEVELOPMENT_MODE:
    import boto3
    from botocore.exceptions import NoCredentialsError

    try:
        session_aws = boto3.Session()
        credentials = session_aws.get_credentials()
        if credentials is None:
            raise NoCredentialsError()
        dynamodb = session_aws.resource('dynamodb', region_name='us-east-1')
        sns = session_aws.client('sns', region_name='us-east-1')
        users_table = dynamodb.Table('photography_users')
        bookings_table = dynamodb.Table('photography_bookings')
        photographers_table = dynamodb.Table('photographers')
    except NoCredentialsError:
        logger.error("AWS credentials not found.")
        exit()
else:
    logger.warning("DEVELOPMENT MODE: AWS disabled.")
    users_table = None
    bookings_table = None
    photographers_table = None

# Routes
@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('home'))
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if DEVELOPMENT_MODE:
            if username == "testuser" and password == "1234":
                session['username'] = "testuser"
                session['fullname'] = "Test User"
                flash("Login successful (mock)", "success")
                return redirect(url_for('home'))
            flash("Mock login failed", "error")
        else:
            try:
                response = users_table.get_item(Key={'username': username})
                user = response.get('Item')
                if user and check_password_hash(user['password'], password):
                    session['username'] = username
                    session['fullname'] = user['fullname']
                    flash("Login successful!", "success")
                    return redirect(url_for('home'))
                flash("Invalid username or password", "error")
            except Exception as e:
                logger.error(f"Login error: {e}")
                flash("Login failed. Please try again.", "error")

    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'username' in session:
        return redirect(url_for('home'))

    if request.method == 'POST':
        fullname = request.form['fullname']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Invalid email format", "error")
            return redirect(url_for('signup'))

        if DEVELOPMENT_MODE:
            flash("Mock signup successful. Please login.", "success")
            return redirect(url_for('login'))
        else:
            try:
                response = users_table.get_item(Key={'username': username})
                if 'Item' in response:
                    flash("Username already exists.", "error")
                    return redirect(url_for('signup'))

                users_table.put_item(Item={
                    'username': username,
                    'password': generate_password_hash(password),
                    'fullname': fullname,
                    'email': email,
                    'created_at': datetime.now().isoformat()
                })

                flash("Signup successful. Please login.", "success")
                return redirect(url_for('login'))
            except Exception as e:
                logger.error(f"Signup error: {e}")
                flash("Signup failed. Try again.", "error")

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for('index'))

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('home.html', username=session['username'])

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/photographers')
def photographers():
    if DEVELOPMENT_MODE:
        photographers = [
            {
                'photographer_id': 'p1',
                'name': 'John Doe',
                'availability': ['2025-07-10-10AM', '2025-07-12-4PM']
            },
            {
                'photographer_id': 'p2',
                'name': 'Jane Smith',
                'availability': ['2025-07-15-9AM', '2025-07-18-6PM']
            }
        ]
        availability_data = {
            p['photographer_id']: p['availability'] for p in photographers
        }
        return render_template('photographers.html',
                               photographers=photographers,
                               availability_data=availability_data)
    else:
        try:
            response = photographers_table.scan()
            photographers = response.get('Items', [])
            availability_data = {
                p['photographer_id']: p.get('availability', []) for p in photographers
            }
            return render_template('photographers.html',
                                   photographers=photographers,
                                   availability_data=availability_data)
        except Exception as e:
            logger.error(f"Error fetching photographers: {e}")
            flash("Could not load photographers.", "error")
            return redirect(url_for('home'))

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if 'username' not in session:
        flash('Please login to book a photographer', 'error')
        return redirect(url_for('login'))

    if request.method == 'POST':
        print("[DEBUG] POST request received for booking")
        print("[DEBUG] Raw form data:", request.form)

        start_date = request.form.get('start_date')
        end_date = request.form.get('end_date')
        name = request.form.get('name')
        email = request.form.get('email')
        phone = request.form.get('phone')
        event_type = request.form.get('event_type')
        photographer = request.form.get('photographer')
        package = request.form.get('package')
        payment = request.form.get('payment')
        notes = request.form.get('notes', '')

        print("[DEBUG] Extracted data:", start_date, end_date, name, email, phone, event_type, photographer, package, payment)

        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash("Invalid email format", "error")
            return redirect(url_for('booking'))

        if not re.match(r"^[6-9]\d{9}$", phone):
            flash("Invalid phone number", "error")
            return redirect(url_for('booking'))

        booking_id = f"{photographer}-{uuid.uuid4()}"

        if DEVELOPMENT_MODE:
            logger.info(f"[MOCK] Booking saved for {name} | Event: {event_type}")
            flash("Mock booking successful!", "success")
            return redirect(url_for('success'))
        else:
            try:
                bookings_table.put_item(Item={
                    'booking_id': booking_id,
                    'username': session['username'],
                    'name': name,
                    'email': email,
                    'phone': phone,
                    'event_type': event_type,
                    'photographer': photographer,
                    'package': package,
                    'date_slot': f"{start_date} to {end_date}",
                    'notes': notes,
                    'payment': payment,
                    'timestamp': datetime.now().isoformat()
                })
                flash("Booking confirmed!", "success")
                return redirect(url_for('success'))
            except Exception as e:
                logger.error(f"Booking error: {e}")
                flash("Booking failed. Try again.", "error")
                return redirect(url_for('booking'))

    return render_template('booking.html')

@app.route('/success')
def success():
    return render_template('success.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

if __name__ == '__main__':
    print("Flask server running at http://localhost:5000")
    app.run(debug=True)
