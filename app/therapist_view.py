from app import app

from flask import session
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
from flask import flash
import re
import mysql.connector
import connect
from flask_hashing import Hashing
import os
from werkzeug.utils import secure_filename

hashing = Hashing(app)
dbconn = None
connection = None

# Define a dictionary to order weekdays
weekday_order = {
        'Monday': 1,
        'Tuesday': 2,
        'Wednesday': 3,
        'Thursday': 4,
        'Friday': 5,
        'Saturday': 6,
        'Sunday': 7
        }

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


def get_therapist_image_path():
    username = session.get('username')
    if username is None:
        return 'default.png'  # Return just the filename or relative path

    cursor = getCursor()
    try:
        cursor.execute("SELECT Image FROM therapist WHERE username = %s", (username,))
        result = cursor.fetchone()
        
        if result and result[0] not in ['default.png', None, '']:
            # Return just the filename or the relative path within the static folder
            image_path = result[0]
            
        else:
            image_path = 'default.png'
    except Exception as e:
        print(f"Error retrieving therapist image: {e}")
        image_path = 'default.png'
    
    return image_path  # No need to prepend '/static/', it's handled by url_for




@app.route("/therapist/profile")
def therapist_profile():
    username = session.get('username')
    if not username:
        # Redirect to login page if not logged in
        return redirect(url_for('login'))
    
    cursor = getCursor()
    # Fetching the therapist's profile details using username
    cursor.execute('SELECT * FROM therapist WHERE username = %s', (username,))
    therapist_details = cursor.fetchone()


    session['therapist_image'] = get_therapist_image_path()

    return render_template("./therapist/therapist_view_profile.html", therapist=therapist_details, therapist_image=session['therapist_image'],role='therapist')


@app.route('/therapist/update_profile', methods=['POST','GET'])
def update_therapist_profile():
    # Ensure the therapist is logged in
    username = session.get('username')
    if not username:
        flash('Please log in to update your profile.', 'warning')
        return redirect(url_for('login'))
    
    # Retrieve form data
    title = request.form.get('title')
    first_name = request.form.get('first_name')
    last_name = request.form.get('last_name')
    email = request.form.get('email')
    specialty = request.form.get('specialty')
    phone_number = request.form.get('phone_number')
    
    # Initialize the image_path with the default or existing path
    
    image_path = get_therapist_image_path() # Adjust this function call if necessary

    # Handle the profile image upload
    if 'profile_image' in request.files:
        file = request.files['profile_image']

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            image_path = filename  # Update with the new filename (not the whole path)

    # Update the therapist's information in the database
    try:
        cursor = getCursor()
        cursor.execute("""
            UPDATE therapist SET 
            Title = %s, 
            First_name = %s, 
            Last_name = %s, 
            Email = %s, 
            Specialty = %s, 
            Phone_number = %s, 
            Image = %s
            WHERE username = %s
        """, (title, first_name, last_name, email, specialty, phone_number, image_path, username))
        flash('Your profile has been updated successfully.', 'success')
    except mysql.connector.Error as err:
        flash('Failed to update profile: {}'.format(err), 'danger')

    return redirect(url_for('therapist_profile'))


@app.route('/therapist/change_password', methods=['GET', 'POST'])
def change_therapist_password():
    # Ensure the therapist is logged in
    if 'username' not in session:
        flash('Please log in to change your password.', 'warning')
        return redirect(url_for('login'))

    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_new_password = request.form['confirm_new_password']

        if new_password != confirm_new_password:
            flash('New passwords do not match.', 'danger')
            return redirect(url_for('change_therapist_password'))

        # Retrieve the current hashed password from the database for the logged-in therapist
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

    return render_template("./therapist/change_password.html", role='therapist')


@app.route('/therapist/class-timetable')
def class_timetable():

    if 'loggedin' in session and 'username' in session:
      
        # Fetch class timetable data from the database
        cursor = getCursor()
        cursor.execute("""SELECT t.Day,c.Class_name,c.Room_num,e.First_name,e.Last_name,c.Class_id
                   from timetable as t join class as c on t.Class_id=c.Class_id 
                   join therapist as e on c.Therapist_id = e.Therapist_id""")
        timetables = cursor.fetchall()

        # Sort the timetable data based on weekdays
        sort_timetable = sorted(timetables, key=lambda x: weekday_order[x[0]])
        return render_template('./therapist/class_timetable.html',classes=sort_timetable,role='therapist')

    return redirect(url_for('login'))


@app.route('/therapist/my-class-timetable')
def my_class_timetable():

    if 'loggedin' in session and 'username' in session:
        username = session['username']

        # Fetch the therapist's ID using their username
        connection = getCursor()
        connection.execute(
        "SELECT Therapist_id from therapist where username=%s;", (username,))
        therapist_id = connection.fetchone()[0]
      
        # Fetch classes assigned to the therapist from the database
        connection = getCursor()
        connection.execute(
        """SELECT t.Day,c.Class_id,c.Class_name,e.Therapist_id,e.First_name,e.Last_name,c.Room_num
        from timetable as t join class as c on t.Class_id=c.Class_id 
        join therapist as e on c.Therapist_id = e.Therapist_id 
        where e.Therapist_id = %s """, (therapist_id,))
        myClasses = connection.fetchall()

        # Sort the fetched classes based on weekdays
        my_sorted_classes = sorted(myClasses, key=lambda x: weekday_order[x[0]]) 

        return render_template('./therapist/my_class_timetable.html',myClasses =my_sorted_classes,role='therapist')
    
    return redirect(url_for('login'))


@app.route('/therapist_class_detail/<class_id>')
def class_detail(class_id):

    # Get the class details based on the provided class_id
    connection = getCursor()
    connection.execute(
    "SELECT * from class where Class_id= %s ;", (class_id,))
    class_detail = connection.fetchone()

    return render_template('./therapist/class_detail.html',class_detail=class_detail,role='therapist')


@app.route('/therapist/class-attendance',methods=['POST','GET'])
def class_attendance():

    username = session['username']

    # Get the therapist_id based on the username
    connection = getCursor()
    connection.execute(
    "SELECT Therapist_id from therapist where username=%s;", (username,))
    therapist_id = connection.fetchone()[0]

    # Fetch class attendance data for classes conducted by the therapist
    connection = getCursor()
    connection.execute(
    """select b.Date,c.Class_name,count(a.Booking_id),b.Class_id,C.Room_num from attendance as a
    join booking as b on a.Booking_id = b.Booking_id
    join class as c on c.Class_id = b.Class_id
    where b.Type='class' and c.Therapist_id = %s
    group by b.Date,c.Class_name,c.Therapist_id
    """, (therapist_id,))
    class_attendance = connection.fetchall()

    return render_template('./therapist/class_attendance.html',role='therapist',classes=class_attendance)


@app.route('/therapist/class-attendance_record/<class_id>',methods=['POST','GET'])
def therapist_class_attendance_record(class_id):
        
    username = session['username']

    # Get the therapist_id based on the username
    connection = getCursor()
    connection.execute(
    "SELECT Therapist_id from therapist where username=%s;", (username,))
    therapist_id = connection.fetchone()[0]

    # Fetch class attendance records for the specified class and therapist
    connection = getCursor()
    connection.execute(
    """ select c.Class_name,b.Date,C.Room_num,m.First_name,m.Last_name,a.Attendent,a.Booking_id,b.Class_id from booking as b 
     join members as m on b.Member_id = m.Member_id
      join Class as c on b.Class_id = C.class_id
       join attendance as a on b.Booking_id = a.Booking_id
        where b.Type = 'class' and b.Class_id = %s and c.Therapist_id = %s """,(class_id,therapist_id))
    class_attendance = connection.fetchall()
    
    return render_template('./therapist/class_attendance_record.html',role='therapist',classes=class_attendance)

@app.route('/therapist/class-attendance_update/<booking_id>',methods=['POST','GET'])
def therapist_class_attendance_update(booking_id):

    # Get the 'attendent' value and 'class_id' from the form submitted
    attenent = request.form.get('attendent')
    class_id = request.form.get('class_id')

    # Update the 'Attendent' value in the attendance table for the specified booking_id
    connection = getCursor()
    connection.execute(
    """ Update attendance set Attendent = %s 
        where Booking_id = %s """,(attenent,booking_id))
    flash("Record updated successfully.", 'success')

    return redirect(f'/therapist/class-attendance_record/{class_id}')


@app.route('/therapist/session-attendance',methods=['POST','GET'])
def session_attendance():

    username = session['username']

    # Get the therapist_id based on the username
    connection = getCursor()
    connection.execute(
    "SELECT Therapist_id from therapist where username=%s;", (username,))
    therapist_id = connection.fetchone()[0]

    # Fetch session attendance details for the therapist
    connection = getCursor()
    connection.execute(
    """SELECT b.Date,b.Booking_id,s.Session_name,s.Session_id,s.Room_num,count(b.Booking_id) from booking as b 
        join session as s on b.Session_id = s.Session_id
        join members as m on b.Member_id = m.Member_id
        where b.Type = 'session' and s.Therapist_id = %s
        group by s.Session_name""", (therapist_id,))
    session_attendance = connection.fetchall()

    return render_template('./therapist/session_attendance.html',role='therapist',sessions=session_attendance) 


@app.route('/therapist/session-attendance_record/<session_id>',methods=['POST','GET'])
def therapist_session_attendance_record(session_id):

    username = session['username']

    # Get the therapist_id based on the username
    connection = getCursor()
    connection.execute(
    "SELECT Therapist_id from therapist where username=%s;", (username,))
    therapist_id = connection.fetchone()[0]

    # Fetch session attendance details for the therapist and session_id
    connection = getCursor()
    connection.execute(
    """ select s.Session_name,b.Date,s.Room_num,m.First_name,m.Last_name,a.Attendent,a.Booking_id,S.Session_id from booking as b 
     join members as m on b.Member_id = m.Member_id
      join session as s on b.Session_id = s.Session_id
       join attendance as a on b.Booking_id = a.Booking_id
        where b.Type = 'session' and b.Session_id = %s and s.Therapist_id = %s""",(session_id,therapist_id))
    session_attendance = connection.fetchall()
 
    return render_template('./therapist/session_attendance_record.html',role='therapist',sessions=session_attendance)


@app.route('/therapist/session-attendance_update/<booking_id>',methods=['POST','GET'])
def therapist_session_attendance_update(booking_id):

    # Get the 'attendent' value from the form
    attenent = request.form.get('attendent')

    # Get the 'session_id' from the form
    session_id = request.form.get('session_id')

    # Update the attendance in the database for the specified 'booking_id'
    connection = getCursor()
    connection.execute(
    """ Update attendance set Attendent = %s 
        where Booking_id = %s """,(attenent,booking_id))
    
    flash("Record updated successfully.", 'success')

    return redirect(f'/therapist/session-attendance_record/{session_id}')


@app.route('/therapist/my_sessions', methods=['GET', 'POST'])
def my_sessions():
    if 'username' not in session:
        # Redirect to login if the user is not logged in
        return redirect(url_for('login'))

    username = session['username']
    connection = getCursor()
    try:
        # Fetch sessions associated with the logged-in therapist
        connection.execute("""
            SELECT s.Session_id, s.Session_name, s.Description, s.Room_num, s.Duration, s.Fee
            FROM session s
            JOIN therapist t ON s.Therapist_id = t.Therapist_id
            WHERE t.username = %s
            ORDER BY s.Session_name
        """, (username,))
        sessions = connection.fetchall()

    except Exception as e:
        flash(f"An error occurred while fetching sessions: {e}", 'danger')
        sessions = []

    return render_template('therapist/my_sessions.html', sessions=sessions, role='therapist')

@app.route('/therapist/add_new_session', methods=['GET', 'POST'])
def therapist_new_session():

    if request.method =='POST':

        # Get form data from the POST request
        new_name = request.form.get('new_name')
        new_description = request.form.get('new_description')
        new_fee = request.form.get('new_fee')
        new_duration = request.form.get('new_duration')
        new_room = request.form.get('new_room')

        username = session['username']

        # Get the therapist's ID from the database using their username
        connection = getCursor()
        connection.execute("""
           select Therapist_id from therapist 
            WHERE username = %s
        """, (username,))
        therapistId = connection.fetchone()

        # Insert a new session for the therapist ID into the database
        connection = getCursor()
        connection.execute("""Insert into session 
                           (Session_name,Description,Fee,Duration,Therapist_id,Room_num)
                           values (%s,%s,%s,%s,%s,%s)
        """, (new_name,new_description,new_fee,new_duration,therapistId[0],new_room))

        return redirect(url_for('my_sessions'))

    return render_template('therapist/session_new.html',role='therapist')


@app.route('/therapist/set_fees/<int:session_id>', methods=['GET', 'POST'])
def set_fees(session_id):

    if request.method == 'POST':

         # Get the new fee amount from the form
        new_fee = request.form.get('new_fee')
        if not new_fee:
            flash('Please enter a valid fee amount.', 'danger')
            return redirect(url_for('edit_session', session_id=session_id))

        try:

            # Update the session's fee in the database
            connection = getCursor()
            connection.execute("""
                UPDATE session
                SET Fee = %s
                WHERE Session_id = %s
            """, (new_fee, session_id))
            flash('Session fee updated successfully.', 'success')
        except Exception as e:
            flash(f'Failed to update session fee: {e}', 'danger')

        return redirect(url_for('my_sessions'))

    # GET request or initial page load
    session_details = None
    try:
        # Fetch session details from the database
        connection = getCursor()
        connection.execute("""
            SELECT Session_name, Fee
            FROM session
            WHERE Session_id = %s
        """, (session_id,))
        session_details = connection.fetchone()
    except Exception as e:
        flash(f'Failed to fetch session details: {e}', 'danger')

    return render_template('therapist/set_fees.html', session_id=session_id, session=session_details, role='therapist')


@app.route('/therapist/edit_session/<session_id>', methods=['GET', 'POST'])
def therapist_edit_session(session_id):   

    if request.method=='POST':
        
        # Get updated session details from the form
        new_name = request.form.get('new_name')
        new_description = request.form.get('new_description')
        new_duration = request.form.get('new_duration')

        # Update session details in the database
        connection = getCursor()
        connection.execute("""
            Update session set Session_name =%s,Description = %s, Duration =%s
            WHERE Session_id = %s
        """, (new_name,new_description,new_duration,session_id,))
        flash('Session updated successfully.', 'success')

        return redirect(url_for('my_sessions'))

    # Handle GET request (initial page load)
    connection = getCursor()
    connection.execute("""
        SELECT Session_id,Session_name, Description,Duration
        FROM session
        WHERE Session_id = %s
    """, (session_id,))
    session_details = connection.fetchone()
     
    return render_template('/therapist/session_edit.html',role='therapist',session_details=session_details)            

@app.route('/therapist/delete_session/<session_id>', methods=['GET', 'POST'])
def therapist_delete_session(session_id):

    # Execute an SQL DELETE query to remove the session
    connection = getCursor()
    connection.execute("""Delete from session where Session_id = %s """,(session_id,))
    flash('Session deleted successfully.', 'success')

    return redirect(url_for('my_sessions'))


@app.route('/therapist/view_bookings')
def therapist_view_bookings():
    if 'loggedin' in session and session['role'] == 'therapist':
        username = session['username']  

        # Fetch the therapist ID using the therapist's username
        cursor = getCursor()
        cursor.execute("SELECT Therapist_id FROM therapist WHERE username = %s", (username,))
        therapist_id = cursor.fetchone()[0]  # Fetch the therapist ID from the query result
        
        # Fetch all sessions assigned to the logged-in therapist
        cursor.execute("""
            SELECT s.Session_id, s.Session_name, s.Description, s.Fee, s.Duration, s.Room_num, 
                   b.Date, b.Booking_id, m.First_name, m.Last_name,m.Member_id
            FROM session s
            JOIN booking b ON s.Session_id = b.Session_id
            JOIN members m ON b.Member_id = m.Member_id
            WHERE s.Therapist_id = %s AND b.Type = 'session'
            ORDER BY b.Date
        """, (therapist_id,))
        session_bookings = cursor.fetchall()
        
        cursor.close()
        return render_template('/therapist/therapist_view_bookings.html', session_bookings=session_bookings, role='therapist')
    else:
        flash('You need to be logged in as a therapist to view your bookings.', 'warning')
        return redirect(url_for('login'))
    
@app.route('/therapist/booking_details/<int:member_id>')
def therapist_booking_details(member_id):
    if 'loggedin' in session and session['role'] == 'therapist':
        cursor = getCursor()
        
        # Fetch booking details based on the member ID
        cursor.execute("""
            SELECT * from members where Member_id = %s
        """, (member_id,))
        booking_details = cursor.fetchone()
        cursor.close()
        
        if booking_details:
            return render_template('therapist/booking_details.html', booking=booking_details, role='therapist')
        else:
            flash('Booking details not found.', 'warning')
            return redirect(url_for('therapist_view_bookings'))
    else:
        flash('You need to be logged in as a therapist to view booking details.', 'warning')
        return redirect(url_for('login'))


def get_news():
    news_list = []

    # Execute an SQL query to fetch news articles, sorted by date in descending order
    connection = getCursor()
    connection.execute("SELECT * FROM news ORDER BY Date DESC")
    news_records = connection.fetchall()

    # Iterate through each news record and organize them into dictionaries
    for news_record in news_records:
        news = {
            'news_id': news_record[0],
            'news_title': news_record[1],
            'news_content': news_record[2],
            'date': news_record[3]
        }
        news_list.append(news)
    return news_list


@app.route('/therapist_view_news')
def therapist_view_news():
    if 'loggedin' in session and session['role'] == 'therapist':

        # Call the get_news() function to fetch news articles
        news = get_news()
        return render_template('/therapist/therapist_view_news.html', news=news, role='therapist')
    else:
        flash('You need to be logged in as a therapist to view this page.', 'warning')
        return redirect(url_for('login'))


@app.route('/therapist_view_news_detail/<news_id>')
def therapist_view_news_detail(news_id):
   
    # Execute an SQL query to fetch details of a specific news article based on news_id
    cursor = getCursor()
    cursor.execute("SELECT * FROM news WHERE News_id = %s", (news_id,))
    newsDetail = cursor.fetchone()

    return render_template('/therapist/therapist_view_news_detail.html',role='therapist',newsDetail=newsDetail)