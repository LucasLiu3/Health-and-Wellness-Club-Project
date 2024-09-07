import datetime
import os 

from app import app

from flask import config, flash, jsonify, session
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
import re
import mysql.connector
from app.manager_view import member_detail
import connect
from flask_hashing import Hashing
from werkzeug.utils import secure_filename
from datetime import date, timedelta,datetime

hashing = Hashing(app)

dbconn = None
connection = None

def getCursor():
    global dbconn
    global connection
    connection = mysql.connector.connect(user=connect.dbuser, \
    password=connect.dbpass, host=connect.dbhost, \
    database=connect.dbname, autocommit=True)
    dbconn = connection.cursor()
    return dbconn

# Configure the path for uploaded images
UPLOAD_FOLDER = 'static/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_member_image_path():
    username = session.get('username')
    if username is None:
        return 'default.png'  # Return just the filename or relative path

    cursor = getCursor()
    try:
        cursor.execute("SELECT Image FROM members WHERE username = %s", (username,))
        result = cursor.fetchone()
        
        if result and result[0] not in ['default.png', None, '']:
            # Return just the filename or the relative path within the static folder
            image_path = result[0]
            
        else:
            image_path = 'default.png'
    except Exception as e:
        print(f"Error retrieving member image: {e}")
        image_path = 'default.png'
    
    return image_path  # No need to prepend '/static/', it's handled by url_for



@app.route("/member_view_profile")
def member_profile():
    username = session.get('username')
    if not username:
        # Redirect to login page if not logged in
        return redirect(url_for('login'))
    
    cursor = getCursor()
    # Fetching the member's profile details using username
    cursor.execute('SELECT * FROM members WHERE username = %s', (username,))
    member_details = cursor.fetchone()

    if member_details:
        # Use 'Member_id' to fetch any related information
        member_id = member_details[0]
        # Fetch other related data if needed
        
    else:
        # Handle the case where member details are not found
        flash('Member details not found.', 'danger')
        return redirect(url_for('login'))

    # Update the session with the current or default member image path
    session['member_image'] = get_member_image_path()

    return render_template("./member/member_view_profile.html", member=member_details, member_image=session['member_image'], role='member')


@app.route('/member/update_profile', methods=['POST','GET'])
def update_member_profile():
    # Ensure the member is logged in
    username = session.get('username')
    if not username:
        flash('Please log in to update your profile.', 'warning')
        return redirect(url_for('login'))
    
    # Retrieve form data
    title = request.form.get('title')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    phone_number = request.form.get('phone_number')
    address = request.form.get('address')
    health_information = request.form.get('health_information')
    
    # Initialize the image_path with the default or existing path
    image_path = get_member_image_path() # Adjust this function call if necessary

    # Handle the profile image upload
    if 'profile_image' in request.files:
        file = request.files['profile_image']

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            image_path = filename  # Update with the new filename (not the whole path)

    # Update the member's information in the database
    try:
        cursor = getCursor()
        cursor.execute("""
            UPDATE members SET 
            Title = %s, 
            First_name = %s, 
            Last_name = %s, 
            Email = %s, 
            Phone_number = %s, 
            Address = %s, 
            Image = %s,
            Heath_Information = %s
            WHERE username = %s
        """, (title, first_name, last_name,  email, phone_number, address, image_path, health_information, username))
        flash('Your profile has been updated successfully.', 'success')
    except mysql.connector.Error as err:
        flash('Failed to update profile: {}'.format(err), 'danger')

    return redirect(url_for('member_profile'))


@app.route('/member_password', methods=['GET', 'POST'])
def member_password():
    # Ensure the member is logged in
    if 'username' not in session:
        flash('Please log in to change your password.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        # Retrieve the input date about password from submitted form.
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_new_password = request.form['confirm_new_password']

        if new_password != confirm_new_password:
            flash('New passwords do not match.', 'danger')
            return redirect(url_for('member_password'))

        # Retrieve the current hashed password from the database for the logged-in member
        cursor = getCursor()
        cursor.execute('SELECT password FROM account WHERE username = %s', (session['username'],))
        account_info = cursor.fetchone()

        if account_info and hashing.check_value(account_info[0], current_password, salt='abcd'):
            # Hash the new password and update it in the database
            hashed_new_password = hashing.hash_value(new_password, salt='abcd')
            try:
                cursor.execute('UPDATE account SET password = %s WHERE username = %s', (hashed_new_password, session['username']))
                flash('Your password has been updated successfully.', 'success')
            except mysql.connector.Error as err:
                flash('Failed to update password: {}'.format(err), 'danger')
        else:
            flash('Current password is incorrect.', 'danger')

    return render_template('./member/member_password.html', role='member')



def get_therapists_with_sessions():

    therapists = []      # Initialize an empty list to store therapist information

    # Fetch all therapist records from the database
    connection = getCursor()
    connection.execute("SELECT * FROM therapist")
    therapist_records = connection.fetchall()

    # Iterate through each therapist record
    for therapist_record in therapist_records:
        therapist = {
            'therapist_id': therapist_record[0],
            'title': therapist_record[1],
            'first_name': therapist_record[2],
            'last_name': therapist_record[3],
            'position': therapist_record[4],
            'email': therapist_record[5],
            'specialty': therapist_record[6],
            'phone_number': therapist_record[7],
            'status': therapist_record[8],
            'image': therapist_record[9],
            'username': therapist_record[10],
            'sessions': []
        }

        # Fetch sessions associated with the therapist from the database
        connection.execute("SELECT * FROM session WHERE therapist_id = %s", (therapist_record[0],))
        session_records = connection.fetchall()

        # Iterate through each session record associated with the therapist
        for session_record in session_records:
            session_info = {
                'session_id': session_record[0],
                'session_name': session_record[1],
                'description': session_record[2],
                'fee': session_record[3],
                'duration': session_record[4],
                'room_num': session_record[5]
            }
            therapist['sessions'].append(session_info)
        therapists.append(therapist)

    return therapists


@app.route('/member_view_therapists')
def member_view_therapists():
    if 'loggedin' in session and session['role'] == 'member':
        # Call the function to get therapists with their sessions
        therapists = get_therapists_with_sessions()

        return render_template('./member/member_view_therapists.html', therapists=therapists, role='member')
    else:
        flash('You need to be logged in as a member to view this page.', 'warning')
        return redirect(url_for('login'))


def get_news():

    news_list = []  # Initialize an empty list to store news items

    # Fetch all news records from the database, ordered by date in descending order
    connection = getCursor()
    connection.execute("SELECT * FROM news ORDER BY Date DESC")
    news_records = connection.fetchall()

    # Iterate through each news record
    for news_record in news_records:
        news = {
            'news_id': news_record[0],
            'news_title': news_record[1],
            'news_content': news_record[2],
            'date': news_record[3]
        }
        news_list.append(news)
    return news_list


@app.route('/member_view_news')
def member_view_news():
    if 'loggedin' in session and session['role'] == 'member':

        # Call the function to get news items
        news = get_news()
        return render_template('/member/member_view_news.html', news=news, role='member')
    
    else:
        flash('You need to be logged in as a member to view this page.', 'warning')
        return redirect(url_for('login'))
    
@app.route('/member_view_news_detail/<news_id>')
def member_view_news_detail(news_id):
   
   # Execute a query to fetch the news details for the given news_id
    cursor = getCursor()
    cursor.execute("SELECT * FROM news WHERE News_id = %s", (news_id,))
    newsDetail = cursor.fetchone()

    return render_template('/member/member_view_news_detail.html',role='member',newsDetail=newsDetail)
    
    
@app.route('/member_view_bookings')
def member_view_bookings():
    if 'loggedin' in session and session['role'] == 'member':
        username = session['username']  
        cursor = getCursor()
        cursor.execute("SELECT Member_id FROM members WHERE username = %s", (username,))
        member_id = cursor.fetchone()[0]  # Fetch the member ID from the query result
        
        # Fetch class bookings for the logged-in member
        cursor.execute("SELECT booking.Booking_id, booking.Date, class.Class_name, class.Description, class.MaxCapacity, class.Duration, class.Therapist_id, class.Room_num FROM booking JOIN class ON booking.Class_id = class.Class_id WHERE booking.Member_id = %s AND booking.Type = 'class'", (member_id,))
        class_bookings = cursor.fetchall()
        
        # Fetch session bookings for the logged-in member
        cursor.execute("SELECT booking.Booking_id, booking.Date, session.Session_name, session.Description, session.Fee, session.Duration, session.Therapist_id, session.Room_num, payment.Payment_id FROM booking JOIN session ON booking.Session_id = session.Session_id LEFT JOIN payment ON booking.Payment_id = payment.Payment_id WHERE booking.Member_id = %s AND booking.Type = 'session'", (member_id,))
        session_bookings = cursor.fetchall()
        
        cursor.close()
        return render_template('/member/member_view_bookings.html', class_bookings=class_bookings, session_bookings=session_bookings, role='member')
    else:
        flash('You need to be logged in as a member to view your bookings.', 'warning')
        return redirect(url_for('login'))

    
@app.route('/cancel_booking', methods=['POST'])
def cancel_booking():
    if 'loggedin' in session and session['role'] == 'member':

        # Get the booking_id from the JSON request data
        booking_id = request.json['booking_id'] 

        # Execute a query to fetch the payment_id associated with the booking
        cursor = getCursor()
        cursor.execute("select Payment_id FROM booking WHERE Booking_id = %s", (booking_id,))
        payment_id = cursor.fetchone()[0]

        # Delete the payment entry associated with the booking
        cursor = getCursor()
        cursor.execute("DELETE from payment  WHERE Payment_id = %s", (payment_id,))

        # Delete the booking entry
        cursor = getCursor()
        cursor.execute("DELETE FROM booking WHERE Booking_id = %s", (booking_id,))
        cursor.close()

        return 'OK', 200
    else:
        flash('You need to be logged in as a member to cancel bookings.', 'warning')
        return 'Unauthorized', 401


@app.route('/manage_subscription')
def manage_subscription():
    if 'loggedin' in session and session.get('role') == 'member':
        username = session['username']
         
        # Fetch member ID based on the username
        cursor = getCursor()
        cursor.execute("SELECT Member_id FROM members WHERE username = %s", (username,))
        member_id = cursor.fetchone()
        
        if member_id:
            member_id = member_id[0]  # Fetch the member ID from the query result

            # Fetch subscription details for the logged-in member
            cursor.execute("SELECT membership.Membership_id, membership.Member_id, membership.Fee, membership.Start_time, membership.Expire_time, payment.Payment_id, payment.Amount, payment.Date FROM membership JOIN payment ON membership.Payment_id = payment.Payment_id WHERE membership.Member_id = %s", (member_id,))
            subscription_details = cursor.fetchall()
            cursor.close()
            connection.close()
            
            return render_template('/member/manage_subscription.html', subscription_details=subscription_details[-1], role='member')
        else:
            flash('Member ID not found.', 'error')
            cursor.close()
            connection.close()
            return redirect(url_for('login'))
    else:
        flash('You need to be logged in as a member to manage your subscription.', 'warning')
        return redirect(url_for('login'))

@app.route('/renew_subscription/<int:membership_id>')
def renew_subscription(membership_id):
    if 'loggedin' in session and session.get('role') == 'member':

        # Get the current date
        user_expire_time = datetime.now().strftime('%Y-%m-%d')
        # Redirect to the payment page with the membership ID
        return redirect(url_for('payment_subscription', user_expire_time=user_expire_time,membership_id=membership_id))
    else:
        flash('You need to be logged in as a member to renew your subscription.', 'warning')
        return redirect(url_for('login'))
    

@app.route('/payment_subscription/<int:membership_id>', methods=['GET', 'POST'])
def payment_subscription(membership_id):
    if 'loggedin' in session and session.get('role') == 'member':

        if request.method == 'POST':
            
            # Handle POST request for payment processing
            # Extract payment form data
            payment_amount = request.form['payment_amount']
            renewal_date = request.form['renewal_date']
            renewal_type=  request.form['renewal_period']
            
             # Convert renewal date to the correct format
            date_parts = renewal_date.split("-")  
            rearranged_date = "-".join([date_parts[2], date_parts[1], date_parts[0]])

            username = session['username']

            # Fetch member ID based on the username in the session
            cursor = getCursor()
            cursor.execute("SELECT Member_id FROM members WHERE username = %s", (username,))
            member_id = cursor.fetchone()[0]

    
            cursor = getCursor()
            # Convert the renewal date string to a datetime object
            renewal_date_obj = datetime.strptime(rearranged_date, '%Y-%m-%d')

            # Format the renewal date as a string in the 'YYYY-MM-DD' format
            formatted_renewal_date = renewal_date_obj.strftime('%Y-%m-%d')

            # Validate Card Expire Day on the server-side
            card_expire_day_str = request.form['card_expire_day']
            card_expire_day_obj = datetime.strptime(card_expire_day_str, '%m/%y')
            current_date = datetime.now()

            if card_expire_day_obj <= current_date:
                # Card expiry date is not in the future
                flash('Please enter a future date for Card Expire Day.', 'error')
                return redirect(url_for('payment_subscription', membership_id=membership_id))
            
            else:

                # Proceed with payment processing and subscription renewal
                cursor = getCursor()
                cursor.execute("select Expire_time from membership WHERE Membership_id = %s", (membership_id,))
                expire_date = cursor.fetchone()[0]
                start_time= date.today()
                start_time_str = start_time.strftime('%Y-%m-%d')

                if expire_date < start_time:

                    # Membership has expired, renew with new start time
                    # Process payment
                    cursor = getCursor()
                    cursor.execute("""INSERT INTO payment ( Amount, Type, Date, Status) VALUES (%s, %s, %s, %s);""", ( payment_amount, 'membership',start_time_str, 'successful'))
        
                    cursor.execute("SELECT LAST_INSERT_ID();")
                    payment_id = cursor.fetchone()[0]

                    cursor = getCursor()
                # Proceed with payment processing
                # Update the membership table with the new renewal date
                    cursor.execute("Insert Into membership (Member_id, Type, Fee, Start_time,Expire_time,Payment_id,Status) VALUES (%s, %s, %s, %s,%s,%s,%s);""",
                                    (member_id,renewal_type,payment_amount,start_time_str,formatted_renewal_date,payment_id,'active'))
                    connection.commit()
                    
                    cursor.close()
                    connection.close()
                    
                    # Delete any reminders for the member
                    cursor = getCursor()
                    cursor.execute("""Delete from reminder where Member_id = %s """,(member_id,))

                    flash('Payment successful! Renewal date updated.', 'success')
                    return redirect(url_for('manage_subscription'))
                
                else: 
                    
                    # Membership is active, renew from the previous start time
                    cursor = getCursor()
                    cursor.execute("select Start_time from membership WHERE Membership_id = %s", (membership_id,))
                    old_start_time = cursor.fetchone()[0]
                    old_start_time_str = old_start_time.strftime('%Y-%m-%d')

                    # Update membership with new renewal date
                    cursor = getCursor()
                    cursor.execute("""INSERT INTO payment ( Amount, Type, Date, Status) VALUES (%s, %s, %s, %s);""", ( payment_amount, 'membership',start_time_str, 'successful'))
                    cursor.execute("SELECT LAST_INSERT_ID();")
                    payment_id = cursor.fetchone()[0]
                    cursor = getCursor()
                    cursor.execute("Insert Into membership (Member_id, Type, Fee, Start_time,Expire_time,Payment_id,Status) VALUES (%s, %s, %s, %s,%s,%s,%s);""",
                                    (member_id,renewal_type,payment_amount,old_start_time_str,formatted_renewal_date,payment_id,'active'))
                    connection.commit()
                    
                    cursor.close()
                    connection.close()
                    
                    # Delete any reminders for the member
                    cursor = getCursor()
                    cursor.execute("""Delete from reminder where Member_id = %s """,(member_id,))


                    flash('Payment successful! Renewal date updated.', 'success')
                    return redirect(url_for('manage_subscription'))
                
        else:
            # Fetch the expiration date of the membership for the logged-in user
            cursor = getCursor()
            cursor.execute("SELECT Expire_time FROM membership WHERE Membership_id = %s", (membership_id,))
            expire_time = cursor.fetchone()[0]  # Extract the value from the first element of the tuple
            cursor.close()

            return render_template('/member/payment_subscription.html', expire_time=expire_time,role='member')
    else:
        flash('You need to be logged in as a member to renew your subscription.', 'warning')
        return redirect(url_for('login'))

@app.route('/payment_history/<int:member_id>', methods=['GET', 'POST'])
def payment_history(member_id):
    
    # Fetch payment history for the specified member_id
    cursor = getCursor()
    cursor.execute("""select m.payment_id,m.Type,p.Amount,p.Type,p.Date,p.STATUS from membership as m left join payment as p
                   on m.payment_id = p.payment_id
                    where Member_id = %s """,(member_id,))
    payment_list = cursor.fetchall()

    return render_template('./member/payment_history.html',role='member',payment_list=payment_list)
    
    
@app.route("/member/class", methods=['GET', 'POST'])
def member_class():
    # Get the username and role from the session
    user_name = session['username']
    role = session['role']

    # Get the member ID based on the username
    connection = getCursor()
    sql = "select Member_id from members where username=%s"
    connection.execute(sql, (user_name,))
    memberid = connection.fetchone()[0]

    # Fetch the expiration date of the membership for the member
    cursor = getCursor()
    cursor.execute('select Membership_id, Expire_time from membership where Member_id = %s',(memberid,))
    expiration = cursor.fetchall()[-1]

    # Check if booking is disabled based on membership expiration date
    today= date.today()
    disable_Booking = expiration[1]< today
    membershipId = expiration[0]

    # Fetch class details, therapist information, and booking counts
    cursor = getCursor()
    cursor.execute("""SELECT t.Day,c.Class_name,c.Description,c.MaxCapacity,c.Duration,c.Room_num,e.First_name,e.Last_name,ifnull(a.num,0),c.Class_id,b.Member_id
                   from timetable as t join class as c on t.Class_id=c.Class_id 
                   join therapist as e on c.Therapist_id = e.Therapist_id
                   left join (select Class_id, count(Member_id) as num from booking 
                   where Type = 'class'
                   group by Class_id ) as a on c.Class_id = a.Class_id
                   left join ( select Class_id, Member_id from booking where Member_id = %s) as b 
                   on c.Class_id = b.Class_id""",(memberid,))
    timetables = cursor.fetchall()

    # Define a dictionary to specify the order of weekdays
    weekday_order = {
            'Monday': 1,
            'Tuesday': 2,
            'Wednesday': 3,
            'Thursday': 4,
            'Friday': 5,
            'Saturday': 6,
            'Sunday': 7
        }
    
    # Sort timetables based on the order of weekdays
    sort_timetable = sorted(timetables, key=lambda x: weekday_order[x[0]])
    
    return render_template('./member/Class.html', user_name=user_name, class_list=sort_timetable, role=role,memberid=memberid,disable_Booking=disable_Booking,membershipId=membershipId)


@app.route("/member/class_join", methods=['GET', 'POST'])
def member_class_join():

    # Extract data from the form submission
    memberid=request.form['member_id']
    classid = request.form['class_id']
    weekday= request.form['weekday']

    # Insert the booking into the database
    connection = getCursor()
    sql = "insert into booking (Member_id,Type,Date,Status,Class_id) values(%s,'class',%s,'successful',%s)"
    connection.execute(sql, (memberid, weekday, classid))

    # Fetch the ID of the last inserted booking
    connection.execute("SELECT LAST_INSERT_ID();")
    booking_id = connection.fetchone()[0]

    # Insert attendance record for the booking
    connection = getCursor()
    connection.execute("""INSERT INTO attendance (Booking_id) VALUES (%s);""", (booking_id,))
    return redirect("/member_view_bookings")
  


@app.route("/member/session", methods=['GET', 'POST'])
def member_session():
    
    # Get the username and role from the session
    user_name = session['username']
    role = session['role']

    # Get the member ID based on the username
    connection = getCursor()
    sql = "select Member_id from members where username=%s"
    connection.execute(sql, (user_name,))
    memberid = connection.fetchone()[0]

    # Fetch the expiration date of the membership for the member
    cursor = getCursor()
    cursor.execute('select Membership_id, Expire_time from membership where Member_id = %s',(memberid,))
    expiration = cursor.fetchall()[-1]

    # Check if booking is disabled based on membership expiration date
    today= date.today()
    disable_Booking = expiration[1]< today
    membershipId = expiration[0]

    # Fetch session details and therapist information
    connection = getCursor()
    connection.execute(
        "select Session_id,Session_name,Fee,Duration,therapist.First_name,Room_num,therapist.Last_name from session left join therapist on session.Therapist_id=therapist.Therapist_id;")
    records = connection.fetchall()
    
    return render_template('./member/Session.html', user_name=user_name, session_list=records, role=role,disable_Booking=disable_Booking,membershipId =membershipId )


@app.route("/member/session_detail", methods=['GET', 'POST'])
def member_session_detail():

    # Get the username and role from the session
    user_name = session['username']
    role = session['role']

    # Get the record ID from the request parameters   
    record_id = request.args.get('record_id')

    # Fetch the member ID based on the username
    connection = getCursor()
    sql = "select Member_id from members where username=%s"
    connection.execute(sql, (user_name,))
    userid = connection.fetchone()[0]

    # Fetch detailed information about the session
    connection.execute(
        "select Session_id,Session_name,Fee,Duration,therapist.First_name,therapist.Last_name,therapist.Email,Room_num,Description from session left join therapist on therapist.Therapist_id=session.Therapist_id where Session_id=%s;",
        (record_id,))
    record = connection.fetchone()
    result = {
        "Session_id": record[0],
        "Session_name": record[1],
        "Fee": record[2],
        "Duration": record[3],
        "First_name": record[4],
        "Last_name": record[5],
        "Email": record[6],
        "Room_num": record[7],
        "Description": record[8]
    }

    return render_template('./member/Session_Detail.html', user_name=user_name, record=result,memberid=userid ,role=role)


@app.route("/member/session_join", methods=['GET', 'POST'])
def member_session_join():

    # Extract data from the form submission
    memberid=request.form['member_id']
    sessionid = request.form['session_id']
    weekday= request.form['weekday']
    fee=request.form['fee']

    # Get the current date
    start_time= date.today()
    start_time_str = start_time.strftime('%Y-%m-%d')

    # Insert payment record for the session
    connection = getCursor()
    sql = "insert into payment (Amount,Type,Date,Status) values(%s,'session',%s,'successful')"
    connection.execute(sql, (fee, start_time_str))

    # Fetch the ID of the last inserted payment
    connection.execute("SELECT LAST_INSERT_ID();")
    payment_id = connection.fetchone()[0]

    # Insert booking record for the session
    connection = getCursor()
    sql = "insert into booking (Member_id,Type,Date,Status,Session_id,Payment_id) values(%s,'session',%s,'successful',%s,%s)"
    connection.execute(sql, (memberid, weekday, sessionid,payment_id))

    # Fetch the ID of the last inserted booking
    connection.execute("SELECT LAST_INSERT_ID();")
    booking_id = connection.fetchone()[0]

    # Insert attendance record for the booking
    connection = getCursor()
    connection.execute("""INSERT INTO attendance (Booking_id) VALUES (%s);""", (booking_id,))

    return redirect("/member_view_bookings")