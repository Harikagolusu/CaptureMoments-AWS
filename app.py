from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import logging
import boto3
import uuid
from botocore.exceptions import ClientError, NoCredentialsError

app = Flask(__name__)
app.secret_key = 'your-secret-key'

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS setup with credential error handling
try:
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    sns = boto3.client('sns', region_name='us-east-1')
    users_table = dynamodb.Table('photography_users')
    bookings_table = dynamodb.Table('photography_bookings')
    photographers_table = dynamodb.Table('photographers')
except NoCredentialsError:
    print("❌ AWS credentials not found. Run `aws configure` or deploy on EC2 with IAM role.")
    exit()

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

        try:
            response = users_table.get_item(Key={'username': username})
            user = response.get('Item')

            if user and check_password_hash(user['password'], password):
                session['username'] = username
                session['fullname'] = user['fullname']
                flash('Login successful!', 'success')
                return redirect(url_for('home'))

            flash('Invalid username or password', 'error')

        except ClientError as e:
            logger.error(f"Login error: {e}")
            flash('Login failed. Please try again.', 'error')

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

        try:
            response = users_table.get_item(Key={'username': username})
            if 'Item' in response:
                flash('Username already exists.', 'error')
                return redirect(url_for('signup'))

            users_table.put_item(Item={
                'username': username,
                'password': generate_password_hash(password),
                'fullname': fullname,
                'email': email,
                'created_at': datetime.now().isoformat()
            })

            flash('Signup successful. Please log in.', 'success')
            return redirect(url_for('login'))

        except ClientError as e:
            logger.error(f"Signup error: {e}")
            flash('Signup failed. Try again.', 'error')

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
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
        return redirect(url_for('login', next=request.path))

    try:
        response = bookings_table.scan()
        booked_slots = [item['date_slot'] for item in response.get('Items', [])]
    except:
        booked_slots = []

    if request.method == 'POST':
        selected_date = request.form['selected_date']
        selected_slot = request.form['selected_slot']
        name = request.form['name']
        email = request.form['email']
        phone = request.form['phone']
        event_type = request.form['event_type']
        photographer = request.form['photographer']
        package = request.form['package']
        payment = request.form['payment']
        notes = request.form.get('notes', '')

        slot_id = f"{selected_date}-{selected_slot}"
        if slot_id in booked_slots:
            flash("Slot already booked!", "error")
            return redirect(url_for('booking'))

        booking_id = str(uuid.uuid4())
        bookings_table.put_item(Item={
            'booking_id': booking_id,
            'username': session['username'],
            'name': name,
            'email': email,
            'phone': phone,
            'event_type': event_type,
            'photographer': photographer,
            'package': package,
            'date_slot': slot_id,
            'notes': notes,
            'payment': payment,
            'timestamp': datetime.now().isoformat()
        })

        flash("Booking confirmed successfully!", "success")
        return redirect(url_for('success'))

    return render_template('booking.html')

@app.route('/success')
def success():
    return render_template('success.html')

if __name__ == '__main__':
    print("Flask server starting on http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)
