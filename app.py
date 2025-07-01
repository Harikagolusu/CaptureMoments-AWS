from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import logging
import boto3
import uuid
import os
from botocore.exceptions import ClientError

# Flask app setup
app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Replace with a real secret key

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize AWS services
dynamodb = boto3.resource('dynamodb', region_name='ap-south-1')
sns = boto3.client('sns', region_name='ap-south-1')

# Define DynamoDB tables
users_table = dynamodb.Table('photography_users')
bookings_table = dynamodb.Table('photography_bookings')
photographers_table = dynamodb.Table('photographers')  # ✅ Added

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
            logger.error(f"Database error during login: {e}")
            flash('An error occurred during login. Please try again.', 'error')

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
                flash('Username already exists!', 'error')
                return redirect(url_for('signup'))

            users_table.put_item(Item={
                'username': username,
                'password': generate_password_hash(password),
                'fullname': fullname,
                'email': email,
                'created_at': datetime.now().isoformat()
            })

            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))

        except ClientError as e:
            logger.error(f"Database error during signup: {e}")
            flash('An error occurred during registration. Please try again.', 'error')

    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    session.pop('fullname', None)
    flash('You have been logged out', 'info')
    return redirect(url_for('index'))

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login', next=request.path))
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
    except ClientError as e:
        logger.error(f"Error fetching photographers: {e}")
        flash("Failed to load photographers", "error")
        return redirect(url_for('home'))

@app.route('/booking', methods=['GET', 'POST'])
def booking():
    if 'username' not in session:
        flash('Please login to book a photographer', 'error')
        return redirect(url_for('login', next=request.path))

    booked_slots = []  # This could be loaded from bookings_table if needed

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

        # ✅ Save booking to DynamoDB
        booking_id = str(uuid.uuid4())
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
                'date_slot': slot_id,
                'notes': notes,
                'payment': payment,
                'timestamp': datetime.now().isoformat()
            })

            # ✅ Optional: Send SNS notification
            # sns.publish(
            #     TopicArn='your-sns-topic-arn',
            #     Message=f"New Booking by {name} on {slot_id}",
            #     Subject="New Booking Alert"
            # )

            flash("Booking confirmed successfully!", "success")
            return redirect(url_for('success'))

        except ClientError as e:
            logger.error(f"Error saving booking: {e}")
            flash("Failed to confirm booking. Try again later.", "error")

    return render_template('booking.html', booked_data=booked_slots)

@app.route('/success', methods=['GET', 'POST'])
def success():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('success.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
