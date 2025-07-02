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

        # ✅ Optional SNS notification
        # sns.publish(
        #     TopicArn='your-sns-topic-arn',
        #     Message=f"Booking confirmed for {name} on {slot_id}",
        #     Subject="New Booking Alert"
        # )

        flash("Booking confirmed successfully!", "success")
        return redirect(url_for('success'))

    return render_template('booking.html')


@app.route('/success')
def success():
    return render_template('success.html')


if __name__ == '__main__':
    print("Flask server starting on http://localhost:5000")
    app.run(debug=True)
