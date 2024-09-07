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
      
        cursor = getCursor()
        cursor.execute("""SELECT t.Day,c.Class_name,c.Room_num,e.First_name,e.Last_name,c.Class_id
                   from timetable as t join class as c on t.Class_id=c.Class_id 
                   join therapist as e on c.Therapist_id = e.Therapist_id""")
        timetables = cursor.fetchall()
        weekday_order = {
                'Monday': 1,
                'Tuesday': 2,
                'Wednesday': 3,
                'Thursday': 4,
                'Friday': 5,
                'Saturday': 6,
                'Sunday': 7
            }
        sort_timetable = sorted(timetables, key=lambda x: weekday_order[x[0]])


        return render_template('./therapist/class_timetable.html',classes=sort_timetable,role='therapist')

    return redirect(url_for('login'))

@app.route('/therapist/my-class-timetable')
def my_class_timetable():

    if 'loggedin' in session and 'username' in session:
        username = session['username']

        connection = getCursor()
        connection.execute(
        "SELECT Therapist_id from therapist where username=%s;", (username,))
        therapist_id = connection.fetchone()[0]
      
        connection = getCursor()
        connection.execute(
        """SELECT t.Day,c.Class_id,c.Class_name,e.Therapist_id,e.First_name,e.Last_name,c.Room_num
        from timetable as t join class as c on t.Class_id=c.Class_id 
        join therapist as e on c.Therapist_id = e.Therapist_id 
        where e.Therapist_id = %s """, (therapist_id,))
        myClasses = connection.fetchall()


        weekday_order = {
        'Monday': 1,
        'Tuesday': 2,
        'Wednesday': 3,
        'Thursday': 4,
        'Friday': 5,
        'Saturday': 6,
        'Sunday': 7
        }

        my_sorted_classes = sorted(myClasses, key=lambda x: weekday_order[x[0]]) 

        return render_template('./therapist/my_class_timetable.html',myClasses =my_sorted_classes,role='therapist')
    
    return redirect(url_for('login'))

@app.route('/therapist_class_detail/<class_id>')
def class_detail(class_id):


    connection = getCursor()
    connection.execute(
    "SELECT * from class where Class_id= %s ;", (class_id,))
    class_detail = connection.fetchone()

    
    return render_template('./therapist/class_detail.html',class_detail=class_detail,role='therapist')

# @app.route('/therapist_member_detail/<member_id>')
# def class_member_detail(member_id):

#     connection = getCursor()
#     connection.execute(
#     "SELECT * from members where Member_id= %s ;", (member_id,))
#     member_detail = connection.fetchone()

#     print(member_detail)
#     return render_template('./therapist/class_detail.html',member_detail=member_detail,role='therapist')


@app.route('/therapist/class-attendance',methods=['POST','GET'])
def class_attendance():

    if request.method =='GET':

        username = session['username']
        connection = getCursor()
        connection.execute(
        "SELECT Therapist_id from therapist where username=%s;", (username,))
        therapist_id = connection.fetchone()[0]


        connection = getCursor()
        connection.execute(
        """select c.Class_id,t.Day,c.Class_name,c.Room_num,count(b.Member_id),a.attendance_number from class as c 
        left join timetable as t
        on c.Class_id = t.Class_id
        left join (select * from booking where Type='class') as b
        on c.Class_id = b.Class_id 
        left join attendance_class as a 
        on c.Class_id = a.Class_id
        where c.Therapist_id= %s 
        group by c.Class_id,t.Day """, (therapist_id,))
        class_attendance = connection.fetchall()


        weekday_order = {
            'Monday': 1,
            'Tuesday': 2,
            'Wednesday': 3,
            'Thursday': 4,
            'Friday': 5,
            'Saturday': 6,
            'Sunday': 7
            }

        sorted_classes = sorted(class_attendance, key=lambda x: weekday_order[x[1]]) 

        return render_template('./therapist/class_attendance.html',role='therapist',classes=sorted_classes)


    elif request.method=='POST':

        attendance_number = request.form['attendance_number']
        class_id = request.form['class_id']

        connection = getCursor()
        connection.execute(
        "Update attendance_class set attendance_number =%s where Class_id= %s ;", (attendance_number,class_id))

        return redirect('/therapist/class-attendance')



@app.route('/therapist/session-attendance',methods=['POST','GET'])
def session_attendance():

    if request.method=='GET':
        username = session['username']
        connection = getCursor()
        connection.execute(
        "SELECT Therapist_id from therapist where username=%s;", (username,))
        therapist_id = connection.fetchone()[0]


        connection = getCursor()
        connection.execute(
        """SELECT s.Session_id,b.Date,s.Session_name,s.Room_num, count(b.Member_id),a.attendance_number
        FROM session as s 
        join booking as b on s.Session_id = b.Session_id 
        left join attendance_session as a on s.Session_id = a.Session_id
        where s.Therapist_id= %s 
        group by s.Session_id,b.Date""", (therapist_id,))
        session_attendance = connection.fetchall()
        
        print(session_attendance)
        weekday_order = {
            'Monday': 1,
            'Tuesday': 2,
            'Wednesday': 3,
            'Thursday': 4,
            'Friday': 5,
            'Saturday': 6,
            'Sunday': 7
            }

        sorted_classes = sorted(session_attendance, key=lambda x: weekday_order[x[1]]) 

        return render_template('./therapist/session_attendance.html',role='therapist',sessions=sorted_classes) 

    elif request.method =='POST':

        attendance_number = request.form['attendance_number']
        session_id = request.form['session_id']

        connection = getCursor()
        connection.execute(
        "Update attendance_session set attendance_number =%s where Session_id= %s ;", (attendance_number,session_id))

        return redirect('/therapist/session-attendance')