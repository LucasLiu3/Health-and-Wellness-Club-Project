import datetime
from app import app
import os, json, time

from flask import session, make_response, flash
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
import re
import mysql.connector
import connect
from flask_hashing import Hashing
from datetime import date, timedelta,datetime
from flask import flash
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

UPLOAD_FOLDER = 'static/'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def get_manager_image_path():
    username = session.get('username')
    if username is None:
        return 'default.png'  # Return just the filename or relative path

    cursor = getCursor()
    try:
        cursor.execute("SELECT Image FROM manager WHERE username = %s", (username,))
        result = cursor.fetchone()
        
        if result and result[0] not in ['default.png', None, '']:
            # Return just the filename or the relative path within the static folder
            image_path = result[0]
            
        else:
            image_path = 'default.png'
    except Exception as e:
        print(f"Error retrieving manager image: {e}")
        image_path = 'default.png'
    
    return image_path  # No need to prepend '/static/', it's handled by url_for

@app.route("/manager/profile")
def manager_profile():
    username = session.get('username')
    if not username:
        # Redirect to login page if not logged in
        return redirect(url_for('login'))
    
    cursor = getCursor()
    # Fetching the therapist's profile details using username
    cursor.execute('SELECT * FROM manager WHERE username = %s', (username,))
    manager_details = cursor.fetchone()

    session['manager_image'] = get_manager_image_path()

    return render_template("./manager/profile.html", manager=manager_details, manager_image=session['manager_image'], role='manager')

@app.route('/manager/update_profile', methods=['POST','GET'])
def update_manager_profile():
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
    position = request.form.get('position')
    phone_number = request.form.get('phone_number')
    
   
    # Initialize the image_path with the default or existing path
    image_path = get_manager_image_path() # Adjust this function call if necessary

    # Handle the profile image upload
    if 'profile_image' in request.files:
        file = request.files['profile_image']

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            image_path = filename  # Update with the new filename (not the whole path)

    try:

        cursor = getCursor()
        cursor.execute("""
            UPDATE manager SET 
            Title = %s, 
            First_name = %s, 
            Last_name = %s, 
            Email = %s, 
            Postion = %s, 
            Phone_number = %s, 
            Image = %s
            WHERE username = %s
        """, (title, first_name, last_name, email, position, phone_number, image_path, username))
        flash('Your profile has been updated successfully.', 'success')

    except mysql.connector.Error as err:
        flash('Failed to update profile: {}'.format(err), 'danger')

    return redirect(url_for('manager_profile'))

@app.route('/manager/change_password', methods=['GET', 'POST'])
def change_manager_password():
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
            return redirect(url_for('change_manager_password'))

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

    return render_template("./manager/updatePssword.html", role='manager')


@app.route("/manager/members", methods=['GET', 'POST'])
def manager_members():
    user_name = session['username']

    # Establish a database connection and execute a SQL query to fetch member data
    connection = getCursor()
    connection.execute(
        "select account.username,Title,First_name,Last_name,Position,members.Email,Phone_number,Address,date_of_Birth,Status from account left join members on members.username=account.username where role='member';")
    records = connection.fetchall()

    # Loop through fetched records and replace None values with empty strings
    index = 0
    for record in records:
        record = [i if i else "" for i in record]
        records[index] = record
        index += 1

    return render_template('./manager/Member.html', user_name=user_name, members=records,role='manager')


@app.route("/manager/member_update", methods=['GET', 'POST'])
def member_update():

    # Default values for a member record
    record = {
        "username": "",
        "password": "",
        "Title": "Mr.",
        "First_name": "",
        "Last_name": "",
        "Position": "",
        "Email": "",
        "Phone_number": "",
        "Address": "",
        "date_of_Birth": "",
        "Image": "",
        "Heath_Information": "",
        "Status": "active",
    }


    if request.method == "POST":

        # Handle form submission for updating or inserting a member record
        ori_username = request.args.get('username')
        username = request.form.get('username')
        password = request.form.get('password')
        Title = request.form.get('Title')
        First_name = request.form.get('First_name')
        Last_name = request.form.get('Last_name')
        Position = request.form.get('Position')
        Email = request.form.get('Email')
        Phone_number = request.form.get('Phone_number')
        Address = request.form.get('Address')
        date_of_Birth = request.form.get('date_of_Birth')
        Image = request.form.get('UploadImage')
        Heath_Information = request.form.get('Heath_Information')
        Status = request.form.get('Status')

         # Handle the profile image upload
        if 'UploadImage' in request.files:
            file = request.files['UploadImage']

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                image_path = filename  # Update with the new filename (not the whole path)

        connection = getCursor()
        if not ori_username:
           # Insert new member record
            connection.execute(
                "SELECT * from account where username=%s;", (username,))
            res = connection.fetchone()
            if res:
                flash(message="User name already exists")
                return render_template('./manager/Member_Update.html', record=record,role='manager')
            
            # Insert into account table
            connection.execute(
                "insert into account (username,password,email,role) values(%s,%s,%s,'member')",
                (username, password, Email))
            
            # Insert into members table
            connection.execute(
                "insert into members (Title,First_name,Last_name,Position,Email,Phone_number,Address,date_of_Birth,Image,Heath_Information,Status,username) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);",
                (Title, First_name, Last_name, Position, Email, Phone_number, Address, date_of_Birth, image_path,
                 Heath_Information, Status, username,))
            return redirect('/manager/members')
        else:

            # Update existing member record
            connection.execute(
                "SELECT * from account where username=%s;", (ori_username,))
            res = connection.fetchone()
            record = {
                "username": ori_username,
                "password": password,
                "Title": Title,
                "First_name": First_name,
                "Last_name": Last_name,
                "Position": Position,
                "Email": Email,
                "Phone_number": Phone_number,
                "Address": Address,
                "date_of_Birth": date_of_Birth,
                "Image": image_path,
                "Heath_Information": Heath_Information,
                "Status": Status,
            }

            # Check if username has changed and if it already exists
            if res[1] != username:
                connection.execute(
                    "SELECT id from account where username=%s;", (username,))

                if connection.fetchone():
                    flash(message="User name already exists")
                    return render_template('./manager/Member_Update.html',
                                           record=record,role='manager')

            # Update password in the account table
            connection.execute(
                "update account set password=%s where username=%s",
                (password, res[1]))
            connection.execute(
                "SELECT * from members where username=%s;", (res[1],))
            res = connection.fetchone()

            if not res:
                # Insert into members table if record does not exist
                connection.execute(
                    "insert into members (Title,First_name,Last_name,Position,Email,Phone_number,Address,date_of_Birth,Image,Heath_Information,Status,username) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);",
                    (Title, First_name, Last_name, Position, Email, Phone_number, Address, date_of_Birth, image_path,
                     Heath_Information, Status, username,))

            else:
                # Update existing record in members table
                connection.execute(
                    "update  members set Title=%s,First_name=%s,Last_name=%s,Position=%s,Email=%s,Phone_number=%s,Address=%s,date_of_Birth=%s,Image=%s,Heath_Information=%s,Status=%s where username=%s;",
                    (Title, First_name, Last_name, Position, Email, Phone_number, Address, date_of_Birth, image_path,
                     Heath_Information, Status, ori_username,))
            flash(
                message="update successful")
            
            return render_template('./manager/Member_Update.html',
                                   record=record,role='manager')
    else:
        # Handle GET request to fetch or create a member record
        username = request.args.get('username', '')
        if username:
            connection = getCursor()
            connection.execute(
                "SELECT * from account where username=%s;", (username,))
            res = connection.fetchone()
            if not res:
                res = [1, 2, 3]  # Dummy data if account does not exist
            connection.execute(
                "SELECT * from members where username=%s;", (username,))
            record = connection.fetchone()
            if not record:
                record = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # Dummy data if member record does not exist

            # Prepare record data for rendering the form
            record = {
                "Title": record[1] if record[1] else "Mr.",
                "First_name": record[2] if record[2] else "",
                "Last_name": record[3] if record[3] else "",
                "Position": record[4] if record[4] else "",
                "Email": record[5] if record[5] else "",
                "Phone_number": record[6] if record[6] else "",
                "Address": record[7] if record[7] else "",
                "date_of_Birth": record[8] if record[8] else "",
                "Image": record[9] if record[9] else "",
                "Heath_Information": record[10] if record[10] else "",
                "Status": record[11] if record[11] else "active",
                "username": res[1],
                "password": res[2]
            }
        return render_template('./manager/Member_Update.html',
                               record=record, username=username,role='manager')


@app.route("/manager/member_delete", methods=['GET', 'POST'])
def member_delete():
    username = request.args.get('username')

    # Delete the member record from the 'members' table
    connection = getCursor()
    connection.execute(
        "delete from members where username=%s;", (username,))
    
    # Delete the corresponding account from the 'account' table
    connection.execute(
        "delete from account where username=%s;", (username,))

    return redirect('/manager/members')


@app.route("/manager/member_detail", methods=['GET', 'POST'])
def member_detail():
    username = request.args.get('username')

    # Fetch account details for the given username
    connection = getCursor()
    connection.execute(
        "SELECT * from account where username=%s;", (username,))
    res = connection.fetchone()

    # If account not found, provide default values
    if not res:
        res = [1, 2, 3] # Dummy data

    # Fetch member details for the given username
    connection.execute(
        "SELECT * from members where username=%s;", (username,))
    record = connection.fetchone()

    # If member record not found, provide default values
    if not record:
        record = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]  # Dummy data
 
    # Prepare the result dictionary for rendering the template
    result = {
        "Title": record[1] if record[1] else "Mr.",
        "First_name": record[2] if record[2] else "",
        "Last_name": record[3] if record[3] else "",
        "Position": record[4] if record[4] else "",
        "Email": record[5] if record[5] else "",
        "Phone_number": record[6] if record[6] else "",
        "Address": record[7] if record[7] else "",
        "date_of_Birth": record[8] if record[8] else "",
        "Image": record[9] if record[9] else "",
        "Heath_Information": record[10] if record[10] else "",
        "Status": record[11] if record[11] else "active",
        "username": res[1],
        "password": res[2]
    }

    return render_template('./manager/Member_Detail.html', record=result,role='manager')


@app.route("/manager/therapist", methods=['GET', 'POST'])
def therapist_therapist():
    user_name = session['username']
    
    # Establish a database connection and execute a SQL query to fetch therapist data
    connection = getCursor()
    connection.execute(
        "select account.username,Title,First_name,Last_name,Postion,therapist.Email,Specialty,Phone_number,status from account left join therapist on therapist.username=account.username where role='therapist';")
    records = connection.fetchall()

    # Loop through fetched records and replace None values with empty strings

    index = 0
    for record in records:
        record = [i if i else "" for i in record]
        records[index] = record
        index += 1

    return render_template('./manager/Therapist.html', user_name=user_name, therapists=records,role='manager')

@app.route("/manager/therapist_update", methods=['GET', 'POST'])
def therapist_update():

    # Default values for a therapist record
    record = {
        "username": "",
        "password": "",
        "Title": "Mr.",
        "First_name": "",
        "Last_name": "",
        "Postion": "",
        "Email": "",
        "Specialty": "",
        "Phone_number": "",
        "Image": "",
        "status": "active",
    }
    if request.method == "POST":

        # Handle form submission for updating or inserting a therapist record
        ori_username = request.args.get('username') # Original username if updating
        username = request.form.get('username')
        username = request.form.get('username')
        password = request.form.get('password')
        Title = request.form.get('Title')
        First_name = request.form.get('First_name')
        Last_name = request.form.get('Last_name')
        Postion = request.form.get('Postion')
        Email = request.form.get('Email')
        Phone_number = request.form.get('Phone_number')
        Specialty = request.form.get('Specialty')
        Image = request.form.get('Image')
        status = request.form.get('status')

        # Handle the profile image upload
        if 'UploadImage' in request.files:
            file = request.files['UploadImage']

            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                image_path = filename  # Update with the new filename

        connection = getCursor()
        if not ori_username:

            # Insert new therapist record
            connection.execute(
                "SELECT * from account where username=%s;", (username,))
            res = connection.fetchone()
            if res:
                flash(message="User name already exists")
                return render_template('./manager/Therapist_Update.html', record=record)
            
            # Insert into account table
            connection.execute(
                "insert into account (username,password,email,role) values(%s,%s,%s,'therapist')",
                (username, password, Email))
            
            # Insert into therapist table
            connection.execute(
                "insert into therapist (Title,First_name,Last_name,Postion,Email,Specialty,Phone_number,Status,Image,username) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);",
                (Title, First_name, Last_name, Postion, Email, Phone_number, Specialty, status,
                 image_path, username,))
            return redirect('/manager/therapist')
        else:
            # Update existing therapist record
            connection.execute(
                "SELECT * from account where username=%s;", (ori_username,))
            res = connection.fetchone()
            record = {
                "username": ori_username,
                "password": password,
                "Title": Title,
                "First_name": First_name,
                "Last_name": Last_name,
                "Postion": Postion,
                "Email": Email,
                "Specialty": Specialty,
                "Phone_number": Phone_number,
                "Image": image_path,
                "status": status,
            }

            # Check if username has changed and if it already exists
            if res[1] != username:
                connection.execute(
                    "SELECT id from account where username=%s;", (username,))
                res = connection.fetchone()
                if res:
                    flash(message="User name already exists")
                    return render_template('./manager/Therapist_Update.html',
                                           record=record,role='manager')
            connection.execute(
                "SELECT * from therapist where username=%s;", (ori_username,))
            res = connection.fetchone()
            if not res:

                # Insert into therapist table if record does not exist
                connection.execute(
                    "insert into therapist (Title,First_name,Last_name,Postion,Email,Specialty,Phone_number,status,Image,username) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);",
                    (Title, First_name, Last_name, Postion, Email, Phone_number, Specialty,
                     status, image_path, username,))

            else:
                # Update existing record in therapist table               
                connection.execute(
                    "update  therapist set Title=%s,First_name=%s,Last_name=%s,Postion=%s,Email=%s,Phone_number=%s,Specialty=%s,Image=%s,status=%s where username=%s;",
                    (Title, First_name, Last_name, Postion, Email, Phone_number, Specialty, image_path,
                     status, ori_username,))
                
            connection.execute(
                "update account set password=%s where username=%s",
                (password, ori_username))
            flash(
                message="update successful")
            return render_template('./manager/Therapist_Update.html',
                                   record=record,role='manager')
    else:

        # Handle GET request to fetch or create a therapist record
        username = request.args.get('username', '')

        if username:
            connection = getCursor()
            connection.execute(
                "SELECT * from account where username=%s;", (username,))
            res = connection.fetchone()
            if not res:
                res = [1, 2, 3]  # Dummy data if account not found
            connection.execute(
                "SELECT * from therapist where username=%s;", (username,))
            record = connection.fetchone()
            if not record:
                record = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
            record = {
                "Title": record[1] if record[1] else "Mr.",
                "First_name": record[2] if record[2] else "",
                "Last_name": record[3] if record[3] else "",
                "Postion": record[4] if record[4] else "",
                "Email": record[5] if record[5] else "",
                "Specialty": record[6] if record[6] else "",
                "Phone_number": record[7] if record[7] else "",
                "status": record[8] if record[8] else "",
                "Image": record[9] if record[9] else "",
                "username": res[1],
                "password": res[2]
            }

        return render_template('./manager/Therapist_Update.html',
                               record=record, username=username,role='manager')

@app.route("/manager/therapist_delete", methods=['GET', 'POST'])
def therapist_delete():
    username = request.args.get('username')

    connection = getCursor()

    # Delete the therapist record from the 'therapist' table
    connection.execute(
        "delete from therapist where username=%s;", (username,))
    
    # Delete the corresponding account from the 'account' table   
    connection.execute(
        "delete from account where username=%s;", (username,))
    
    return redirect('/manager/therapist')


@app.route("/manager/therapist_detail", methods=['GET', 'POST'])
def therapist_detail():
    username = request.args.get('username')

    # Fetch account details for the given username
    connection = getCursor()
    connection.execute(
        "SELECT * from account where username=%s;", (username,))
    res = connection.fetchone()

    # If account not found, provide default values
    if not res:
        res = [1, 2, 3] # Dummy data

    # Fetch therapist details for the given username    
    connection.execute(
        "SELECT * from therapist where username=%s;", (username,))
    record = connection.fetchone()

    # If therapist record not found, provide default values
    if not record:
        record = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

    # Prepare the result dictionary for rendering the template
    result = {
        "Title": record[1] if record[1] else "Mr.",
        "First_name": record[2] if record[2] else "",
        "Last_name": record[3] if record[3] else "",
        "Postion": record[4] if record[4] else "",
        "Email": record[5] if record[5] else "",
        "Specialty": record[6] if record[6] else "",
        "Phone_number": record[7] if record[7] else "",
        "status": record[8] if record[8] else "",
        "Image": record[9] if record[9] else "",
        "username": res[1],
        "password": res[2]
    }
    return render_template('./manager/Therapist_Detail.html', record=result,role='manager')



@app.route('/manager/session-schedules',methods=['POST','GET'])
def session_schedules():

    if request.method=='GET':

        # Handle GET request to fetch session schedules
        connection = getCursor()
        connection.execute(
            """select s.Session_id,s.Session_name,t.First_name,t.Last_name from session as s 
            join therapist as t on s.Therapist_id = t.Therapist_id order by s.Session_id""")
        sessions = connection.fetchall()  # Fetch all session schedules

        return render_template('./manager/session_schedules.html',sessions=sessions,role='manager')

    if request.method == 'POST':

        # Handle POST request to update session schedule
        sessionId= request.form['sessionId']
        therapistId = request.form['therapist_id']
        roomId = request.form['room_id']    

        connection = getCursor()
        # Update the session with the new therapist and room
        connection.execute(f"""Update session set Therapist_id={therapistId},Room_num={roomId} where Session_id={sessionId} """)
        flash("Session schedule updated successfully.", 'success')
        return redirect('/manager/session-schedules')


@app.route("/manager/session_schedule_detail", methods=['GET', 'POST'])
def session_schedule_detail():

    session_id = request.args.get('id')

    # Fetch detailed information about the session with the given ID
    connection = getCursor()
    connection.execute(
        """select s.*, t.First_name,t.Last_name,t.Email from session as s 
        join therapist as t on s.Therapist_id = t.Therapist_id
        where s.Session_id=%s;""", (session_id,))
    res = connection.fetchone()

    return render_template('./manager/session_schedules_detail.html',role='manager',detail=res)


@app.route('/manager/session-schedules-edit',methods=['POST','GET'])
def session_schedules_edit():

    session_id= request.args.get('id')

    # Fetch detailed information about the session with the given ID
    connection = getCursor()
    connection.execute(
        """select s.*, t.First_name,t.Last_name,t.Email from session as s 
        join therapist as t on s.Therapist_id = t.Therapist_id
        where s.Session_id=%s;""", (session_id,))
    sessions = connection.fetchall()

    # Fetch all therapists from the database
    connection =getCursor()
    connection.execute(f"""select Therapist_id,First_name,Last_name
                       from therapist;
        """)
    therapists= connection.fetchall()
    
    # Extract therapist IDs and names into a list for rendering in the template   
    therapist_list = []
    for therapist in therapists:
        therapist_list.append(therapist)

    # Fetch all rooms of type 'Therapy' from the database
    connection = getCursor()
    connection.execute(f"""select Room_id from room where Room_type ='Therapy'""")
    rooms=connection.fetchall()

    # Extract room IDs into a list for rendering in the template
    room_list =[]
    for room in rooms:
        room_list.append(room[0])

    return render_template('./manager/session_schedules_edit.html',sessions = sessions,room_list=room_list,therapist_list=therapist_list,role='manager')
 

@app.route('/manager/session-schedules-cancel',methods=['POST','GET'])
def session_schedules_cancel():

    sessionId  =request.args.get('id')

    # Delete the session with the given ID from the 'session' table
    connection = getCursor()
    connection.execute(f"""Delete from session where Session_id ={sessionId} """)
    flash("Session schedule deleted successfully.", 'success')
    
    return redirect('/manager/session-schedules')


@app.route('/manager/add-new-session',methods=['POST','GET'])
def add_new_session():

    # Handle GET request to fetch necessary data for adding a new session
    if request.method=='GET':

        # Fetch all existing sessions
        connection = getCursor()
        connection.execute(f"""SELECT Session_id,Session_name,Description from session """)
        sessionAll= connection.fetchall()

        # Fetch all therapists
        connection = getCursor()
        connection.execute(f"""SELECT Therapist_id,Last_name,First_name from therapist """)
        therapists= connection.fetchall()

        # Fetch all therapy rooms
        connection = getCursor()
        connection.execute(f"""select Room_id from room where Room_type ='Therapy'""")
        rooms=connection.fetchall()

        # Extract room IDs into a list for rendering in the template
        room_list =[]
        for room in rooms:
            room_list.append(room[0])

        return render_template('./manager/session_schedules_add.html',therapists=therapists ,sessionAll = sessionAll,role='manager',room_list=room_list)

    
    # Handle POST request to add a new session
    elif request.method=='POST':

        therapistId = request.form.get('therapistId')
        sessionId = request.form.get('sessionId')
        roomId = request.form.get('roomId')
    
        # Fetch the session name and description based on the selected session ID
        connection = getCursor()
        connection.execute(f"""select Session_name from session where Session_id ='{sessionId}'""")
        name=connection.fetchone()[0]

        connection = getCursor()
        connection.execute(f"""select Description from session where Session_id ='{sessionId}'""")
        Description=connection.fetchone()[0]

        # Insert the new session into the database
        connection = getCursor()
        connection.execute("""INSERT INTO session (Session_name,Description,Fee,Duration,Therapist_id,Room_num) VALUES (%s,%s,'120','45',%s,%s);""",
                            (name,Description,therapistId,roomId))

        flash("New session schedule added successfully.", 'success')

        return redirect('/manager/session-schedules')

    
@app.route("/manager/timetable", methods=['GET', 'POST'])
def manager_timetable():
    user_name = session['username']

    # Fetch timetable information from the database
    connection = getCursor()
    connection.execute(
        """select id,Day,Class_name,Duration,Room_num,therapist.First_name,therapist.Last_name from timetable 
        join class on timetable.Class_id=class.Class_id
         join therapist on class.Therapist_id = therapist.Therapist_id """)
    records = connection.fetchall()

    # Loop through each record in the records list
    index = 0
    for record in records:
        record = [i if i else "" for i in record]
        records[index] = record
        index += 1

    # Sort the timetable records by weekday order
    weekday_order = {
        'Monday': 1,
        'Tuesday': 2,
        'Wednesday': 3,
        'Thursday': 4,
        'Friday': 5,
        'Saturday': 6,
        'Sunday': 7
        }
    sorted_class = sorted(records, key=lambda x: weekday_order[x[1]]) 


    # Handle POST request to update class timetable
    if request.method =='POST':
        
        # Extract data from the form
        timetableId = request.form.get('timetableId')
        classId = request.form.get('classId')
        weekday = request.form.get('weekday')
        therapistId = request.form['therapist_id']
        roomId = request.form['room_id']    
        
        # Update the timetable with the new weekday
        connection = getCursor()
        connection.execute(f"""Update timetable set Day="{weekday}" where id={timetableId} """)

        # Update the class with new therapist and room assignments
        connection = getCursor()
        connection.execute(f"""Update class set Therapist_id={therapistId},Room_num={roomId} where Class_id={classId} """)
        
        flash("Class timetable updated successfully.", 'success')

        return redirect('/manager/timetable')

    return render_template('./manager/timetable.html', user_name=user_name, timetables=sorted_class, role='manager')


@app.route("/manager/timetable_detail", methods=['GET', 'POST'])
def timetable_detail():
    record_id = request.args.get('record_id')

    # Fetch the details for the timetable record using the record_id
    connection = getCursor()
    connection.execute(
        "select id,Day,Class_name,Duration,Room_num,MaxCapacity,First_name,Last_name,Email,Description from timetable left join class on  timetable.Class_id=class.Class_id left join therapist on therapist.Therapist_id=class.Therapist_id where id=%s;", (record_id,))
    res = connection.fetchone()

    # Create a result dictionary with the fetched details
    result = {
        "Day": res[1],
        "Class_name": res[2],
        "MaxCapacity": res[5],
        "Duration": res[3],
        "First_name": res[6],
        "Last_name": res[7],
        "Email": res[8],
        "Room_num": res[4],
        "Description": res[9],
    }

    return render_template('./manager/timetable_detail.html', record=result, role='manager')


@app.route("/manager/timetable_add", methods=['GET', 'POST'])
def timetable_add():

    # Fetch all available classes
    connection = getCursor()
    connection.execute(f"""SELECT Class_id,Class_name from class """)
    classALL= connection.fetchall()

    # Fetch all therapists
    connection = getCursor()
    connection.execute(f"""SELECT Therapist_id,Last_name,First_name from therapist """)
    therapists= connection.fetchall()

    # Fetch all rooms suitable for classes
    connection = getCursor()
    connection.execute(f"""select Room_id from room where Room_type ='Class'""")
    rooms=connection.fetchall()

    # Extract room IDs into a list
    room_list =[]
    for room in rooms:
        room_list.append(room[0])



    if request.method =='POST':

        # Get form data from POST request
        weekday = request.form.get('weekday')
        classId = request.form.get('classId')
        therapistId = request.form.get('therapistId')
        roomId = request.form.get('roomId')

        # Fetch class details based on classId
        connection = getCursor()
        connection.execute(f"""select Class_name,Description from class where Class_id ='{classId}'""")
        classDetail=connection.fetchone()   

        # Insert new class with details into the database
        connection = getCursor()
        connection.execute("""INSERT INTO class (Class_name,Description,MaxCapacity,Duration,Therapist_id,Room_num) 
                           VALUES (%s, %s,'15','60',%s,%s);""", (classDetail[0],classDetail[1],therapistId,roomId))  # classDetail[0] is Class_name,classDeatil[1] is Description

        # Get the ID of the newly inserted class
        connection.execute("SELECT LAST_INSERT_ID();")
        class_id = connection.fetchone()[0]

        # Insert new timetable entry for the clas
        connection = getCursor()
        connection.execute("""INSERT INTO timetable (Day,class_id) VALUES (%s, %s);""", (weekday,class_id))

        flash("New class timetable added successfully.", 'success')

        return redirect('/manager/timetable')

    return render_template('./manager/timetable_add.html',role='manager',classALL=classALL,therapists=therapists,room_list=room_list)


@app.route("/manager/timetable_edit", methods=['GET', 'POST'])
def timetable_edit():

    record_id = request.args.get('record_id')

    # Fetch details of the timetable record with the given record_id
    connection = getCursor()
    connection.execute(
        """select t.id,t.Day,
           c.Class_id,c.Class_name,c.Room_num,
           t1.First_name,t1.Last_name from timetable as t
           join class as c on t.Class_id = c.Class_id
           join therapist as t1 on c.Therapist_id = t1.Therapist_id
           where t.id=%s;""", (record_id,))
    class_detail = connection.fetchall()

    # Fetch all therapists for the dropdown list
    connection =getCursor()
    connection.execute(f"""select Therapist_id,First_name,Last_name
                       from therapist;
        """)
    therapists= connection.fetchall()
    
    # Create a list of therapists for the dropdown list
    therapist_list = []
    for therapist in therapists:
        therapist_list.append(therapist)

    # Fetch all rooms suitable for classes for the dropdown list
    connection = getCursor()
    connection.execute(f"""select Room_id from room where Room_type ='Class'""")
    rooms=connection.fetchall()

    # Create a list of room IDs for the dropdown list
    room_list =[]
    for room in rooms:
        room_list.append(room[0])

    return render_template('./manager/timetable_edit.html',classes=class_detail,room_list=room_list,therapist_list=therapist_list,role='manager')



@app.route("/manager/timetable_delete", methods=['GET', 'POST'])
def timetable_delete():

    timetableId = request.args.get('record_id')

    # Connect to the database and execute the delete query
    connection = getCursor()
    connection.execute(
        "delete from timetable where id=%s;", (timetableId,))
    
    flash("Class timetable deleted successfully.", 'success')

    return redirect('/manager/timetable')



@app.route('/manager/therapeutic_sessions', methods=['POST', 'GET'])
def manager_therapeutic_sessions():

    connection = getCursor()
    # SQL query to fetch sessions along with therapist details
    query = """
    SELECT s.Session_id, s.Session_name, s.Description, CONCAT(t.First_name, ' ', t.Last_name) AS Therapist, s.Room_num
    FROM session AS s
    JOIN therapist AS t ON s.Therapist_id = t.Therapist_id
    order by s.Session_id
    """

    try:
        # Execute the query
        connection.execute(query)

        # Fetch all the sessions
        sessions = connection.fetchall()

    except Exception as e:

        # If an error occurs, flash an error message and set sessions to an empty list
        flash(f"An error occurred while fetching sessions: {e}", 'danger')
        sessions = []

    return render_template('./manager/manager_therapeutic_session.html', sessions=sessions, role='manager')


@app.route('/manager/view_update_session/<int:session_id>', methods=['GET', 'POST'])
def view_update_session(session_id):

    if request.method == 'POST':

        # Get new session name and description from the form
        new_name = request.form.get('name')
        new_description = request.form.get('description')

        try:
            # Execute an SQL update query to update session details
            connection = getCursor()
            connection.execute(
                "UPDATE session SET Session_name = %s,Description = %s WHERE Session_id = %s",
                (new_name,new_description, session_id)
            )
            flash("Session detail updated successfully.", 'success')

        except Exception as e:

            # Flash an error message if an exception occurs during the update
            flash(f"An error occurred while updating the session: {e}", 'danger')
        return redirect(url_for('view_update_session', session_id=session_id))

    # GET method: Fetch session details to display in the form
    try:

        # Execute an SQL query to fetch session name and description
        connection = getCursor()
        connection.execute(
            "SELECT Session_name, Description FROM session WHERE Session_id = %s",
            (session_id,)
        )
        details = connection.fetchone()          # Fetch the session details

    except Exception as e:

        # Flash an error message if an exception occurs during the fetch
        flash(f"An error occurred while fetching the session description: {e}", 'danger')
        description = ""
    
    return render_template('./manager/view_update_session.html', details=details, role='manager')



@app.route('/manager/class_timetable')
def manager_class_timetable():
    if 'loggedin' in session and 'username' in session:

        # Execute an SQL query to fetch all classes
        connection = getCursor()
        connection.execute(
            "SELECT * FROM  class ") 
        classes = connection.fetchall()          # Fetch all classes from the database

        return render_template('./manager/class_timetable.html', classes=classes, role='manager')

    return redirect(url_for('login'))


@app.route('/manager/class_details/<int:class_id>', methods=['GET', 'POST'])
def manager_class_detail(class_id):
    if 'loggedin' in session and 'username' in session:

        # Execute an SQL query to fetch details of the specified class_id
        connection = getCursor()
        connection.execute("SELECT * FROM class WHERE Class_id = %s", (class_id,))
        class_detail = connection.fetchone()

        if request.method == 'POST':
            # Handle form submission for updating class details
            # Assuming form fields are named accordingly
            class_name = request.form['class_name']
            description = request.form['description']
            max_capacity = request.form['max_capacity']
            duration = request.form['duration']
       
            # Update the class details in the database
            connection.execute("UPDATE class SET Class_name = %s, Description = %s, MaxCapacity = %s, Duration = %s WHERE Class_id = %s", (class_name, description, max_capacity, duration, class_id))
            flash('Class details updated successfully!', 'success')
            return redirect(url_for('manager_class_detail', class_id=class_id))

        return render_template('./manager/class_details.html', class_detail=class_detail, role='manager')

    return redirect(url_for('login'))


@app.route('/manager/edit_class/<class_id>', methods=['GET', 'POST'])
def edit_class(class_id):

    if request.method == 'GET':

        # Execute an SQL query to fetch details of the specified class_id
        connection = getCursor()
        connection.execute(
            "SELECT * FROM class WHERE Class_id = %s;", (class_id,))
        class_detail = connection.fetchone()

        return render_template('./manager/edit_class.html', class_detail=class_detail,role='manager')
    
    elif request.method == 'POST':
        # Update class details in the database
        # Fetch form data and update the class record
        class_name = request.form['class_name']
        description = request.form['description']
        room_num = request.form['room_num']
        # Update other class details similarly
        
        connection = getCursor()
        connection.execute(
            "UPDATE class SET Class_name = %s, Description = %s, Room_num = %s WHERE Class_id = %s;",
            (class_name, description, room_num, class_id)
        )
        # Commit changes to the database
        connection.commit()
        # Flash message for successful update
        flash('Class details updated successfully!', 'success')
        
        return redirect(url_for('manager_class_timetable'))

    return redirect(url_for('login'))



@app.route('/manager/class-attendance',methods=['POST','GET'])
def manager_class_attendance():

    # Execute an SQL query to fetch class attendance details
    connection = getCursor()
    connection.execute(
    """ select b.Date,c.Class_name,count(a.Booking_id),b.Class_id,C.Room_num from attendance as a
        join booking as b on a.Booking_id = b.Booking_id
        join class as c on c.Class_id = b.Class_id
        where b.Type='class'
        group by b.Date,c.Class_name,c.Therapist_id
       """)
    class_attendance = connection.fetchall()      # Fetch all class attendance records

    return render_template('./manager/class_attendance.html',role='manager',classes=class_attendance)



@app.route('/manager/class-attendance_record/<class_id>',methods=['POST','GET'])
def manager_class_attendance_record(class_id):

    # Execute an SQL query to fetch class attendance records for a specific class
    connection = getCursor()
    connection.execute(
    """ select c.Class_name,b.Date,C.Room_num,m.First_name,m.Last_name,a.Attendent,a.Booking_id,b.Class_id from booking as b 
     join members as m on b.Member_id = m.Member_id
      join Class as c on b.Class_id = C.class_id
       join attendance as a on b.Booking_id = a.Booking_id
        where b.Type = 'class' and b.Class_id = %s """,(class_id,))
    
    class_attendance = connection.fetchall()     # Fetch all class attendance records for the specified class
    
    return render_template('./manager/class_attendance_record.html',role='manager',classes=class_attendance)


@app.route('/manager/class-attendance_update/<booking_id>',methods=['POST','GET'])
def manager_class_attendance_update(booking_id):

    attenent = request.form.get('attendent')       # Get the value of 'attendent' from the form data
    class_id = request.form.get('class_id')        # Get the value of 'class_id' from the form data

    # Execute an SQL query to update the attendance record for the specified booking_id
    connection = getCursor()
    connection.execute(
    """ Update attendance set Attendent = %s 
        where Booking_id = %s """,(attenent,booking_id))
    
    flash("Record updated successfully.", 'success')

    return redirect(f'/manager/class-attendance_record/{class_id}')



@app.route('/manager/session-attendance',methods=['POST','GET'])
def manager_session_attendance():

    # Execute SQL query to fetch session attendance details
    connection = getCursor()
    connection.execute(
    """SELECT b.Date,b.Booking_id,s.Session_name,s.Session_id,s.Room_num,count(b.Booking_id) from booking as b 
    join session as s on b.Session_id = s.Session_id
    join members as m on b.Member_id = m.Member_id
    where b.Type = 'session'
    group by s.Session_name""")
    session_attendance = connection.fetchall()      # Fetch all records from the query result


    return render_template('./manager/session_attendance.html',role='manager',sessions=session_attendance) 


@app.route('/manager/session-attendance_record/<session_id>',methods=['POST','GET'])
def manager_session_attendance_record(session_id):

    # Execute SQL query to fetch session attendance details for a specific session ID
    connection = getCursor()
    connection.execute(
    """ select s.Session_name,b.Date,s.Room_num,m.First_name,m.Last_name,a.Attendent,a.Booking_id,S.Session_id from booking as b 
     join members as m on b.Member_id = m.Member_id
      join session as s on b.Session_id = s.Session_id
       join attendance as a on b.Booking_id = a.Booking_id
        where b.Type = 'session' and b.Session_id = %s """,(session_id,))
    session_attendance = connection.fetchall()      # Fetch all records from the query result
 
    return render_template('./manager/session_attendance_record.html',role='manager',sessions=session_attendance)


@app.route('/manager/session-attendance_update/<booking_id>',methods=['POST','GET'])
def manager_session_attendance_update(booking_id):

    attenent = request.form.get('attendent')      # Fetch the attendance value from the form
    session_id = request.form.get('session_id')   # Fetch the session ID from the form

    # Execute SQL query to update the attendance for a specific booking ID
    connection = getCursor()
    connection.execute(
    """ Update attendance set Attendent = %s 
        where Booking_id = %s """,(attenent,booking_id))

    flash("Record updated successfully.", 'success')

    return redirect(f'/manager/session-attendance_record/{session_id}')
    

@app.route('/manager/pricing', methods=['GET', 'POST'])
def manage_pricing():

    # Check if the user is logged in and has manager role
    if 'loggedin' in session and session['role'] == 'manager':

        # Fetch sessions from the database
        cursor = getCursor()
        cursor.execute("SELECT Session_id, Session_name, Description, Fee FROM session")
        sessions = cursor.fetchall()

        # Only select unique membership types with an example fee
        cursor.execute("SELECT DISTINCT Type, Fee FROM membership")
        memberships = cursor.fetchall()
        return render_template('./manager/manage_pricing.html', sessions=sessions, memberships=memberships, role='manager')
    else:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))


@app.route('/manager/update_prices', methods=['POST'])
def update_prices():
    if 'loggedin' in session and session['role'] == 'manager':
        cursor = getCursor()  # Directly get cursor as connection is handled in getCursor with autocommit

        try:
            # Processing form data for price updates
            for key, value in request.form.items():
                if key.startswith('new_price_session_'):
                    session_id = key.split('_')[-1]
                    cursor.execute("UPDATE session SET Fee = %s WHERE Session_id = %s", (value, session_id))
                elif key.startswith('new_price_membership_'):
                    membership_type = key.split('_')[-1]
                    cursor.execute("UPDATE membership SET Fee = %s WHERE Type = %s", (value, membership_type))
            
            flash('Prices updated successfully.', 'success')
        except Exception as e:
            flash(f'Failed to update prices: {str(e)}', 'danger')
        finally:
            cursor.close()
            connection.close()  # Ensure resources are closed

        return redirect(url_for('manage_pricing'))
    else:
        flash('Unauthorized access.', 'danger')
        return redirect(url_for('login'))


@app.route('/manager/membership-management',methods=['POST','GET'])
def membership_management():

    # Execute a complex SQL query using a Common Table Expression (CTE) to fetch the latest subscription details for each member
    connection = getCursor()
    connection.execute("""
                        WITH ranked_data AS (
                            SELECT
                                *,
                                ROW_NUMBER() OVER(PARTITION BY Member_Id ORDER BY Membership_id) AS rank_time
                            FROM
                                membership
                        )
                        SELECT a.*,m.First_name,m.Last_name
                        FROM ranked_data a
                        INNER JOIN (
                            SELECT Member_Id, MAX(rank_time) AS max_rank_time
                            FROM ranked_data
                            GROUP BY Member_Id
                        ) b ON a.Member_Id = b.Member_Id AND a.rank_time = b.max_rank_time
                        inner join members as m on a.Member_id = m.Member_id
                        """)
    subscription_list = connection.fetchall()     # Fetch the subscription data

    start_time= date.today()      # Get the current date

    return render_template('./manager/membership_management.html',subscription_list=subscription_list,role='manager',start_time=start_time)


@app.route('/manager/expired_subscription',methods=['POST','GET'])
def expired_subscription():

    # Execute a SQL query using a Common Table Expression (CTE) to fetch expired or expiring subscriptions
    connection = getCursor()
    connection.execute("""
                        WITH ranked_data AS (
                            SELECT
                                *,
                                ROW_NUMBER() OVER(PARTITION BY Member_Id ORDER BY Membership_id) AS rank_time
                            FROM
                                membership
                        )
                        SELECT a.*,m.First_name,m.Last_name
                        FROM ranked_data a
                        INNER JOIN (
                            SELECT Member_Id, MAX(rank_time) AS max_rank_time
                            FROM ranked_data
                            GROUP BY Member_Id
                        ) b ON a.Member_Id = b.Member_Id AND a.rank_time = b.max_rank_time
                        inner join members as m on a.Member_id = m.Member_id
                       WHERE
                        a.Expire_time < CURRENT_DATE  
                        OR (a.Expire_time >= CURRENT_DATE AND a.Expire_time <= CURRENT_DATE + INTERVAL '1' MONTH);
                        """)

    # Fetch the list of expired or expiring subscriptions
    subscription_list = connection.fetchall()
    start_time= date.today()       # Get the current date

    return render_template('./manager/membership_expired.html',role='manager',subscription_list=subscription_list,start_time=start_time)



@app.route('/manager/reminder',methods=['POST','GET'])
def reminder():

    # Get member_id and status from the form submission
    member_id = request.form.get('member_id')
    status = request.form.get('status')

    # Get today's date in the format YYYY-MM-DD
    today_date = date.today().strftime('%Y-%m-%d')

    # Create a reminder message for expired subscriptions
    if status.strip() =='Expired':
            
            # Insert the reminder into the database
            message ='Your subscription is expired, please renew it.'
            connection = getCursor()
            connection.execute("""Insert into reminder (Member_id,Reminder_content,Date) 
                               values(%s,%s,%s) """,(member_id,message,today_date))

    # Create a reminder message for subscriptions near expiration
    elif status.strip() =='Near to expire':
          
          # Insert the reminder into the database
          message ='Your subscription will expire soon, please renew it.'
          connection = getCursor()
          connection.execute("""Insert into reminder (Member_id,Reminder_content,Date) 
                               values(%s,%s,%s) """,(member_id,message,today_date))
 
    return redirect(url_for('expired_subscription'))


@app.route('/manager/payments')
def view_payments():

    # Query to retrieve payment details along with member names
    cursor = getCursor()
    cursor.execute("""with details as (SELECT Payment_id, Amount, Type, Date, STATUS
                    FROM payment),
                    fulldetails as (
                    select d.*, b.Member_id from details as d  JOIN booking b ON d.Payment_id = b.Payment_id union
                    select d.*, m.Member_id from details as d join membership as m on d.Payment_id = m.Payment_id)

                    select f.*,m.First_name,m.Last_name from fulldetails as f join members as m on f.Member_id = m.Member_id
                    order by f.Date desc;""")
    payments = cursor.fetchall()       # Fetch all payment records along with member details

    cursor.close()
    return render_template('./manager/payments.html', payments=payments,role='manager')


@app.route("/manager/report", methods=['GET', 'POST'])
def manager_report():
    user_name = session['username']

    # Query to select all records from the report table
    connection = getCursor()
    connection.execute(
        "select * from report")
    records = connection.fetchall()

    today_date = date.today().strftime('%Y-%m-%d')

    # Iterate through the fetched records to handle empty values
    index = 0
    for record in records:
        record = [i if i else "" for i in record]
        records[index] = record
        index += 1

    return render_template('./manager/Report.html', day=today_date,user_name=user_name, reports=records, role='manager')


@app.route('/manager/overall_record', methods=['GET', 'POST'])
def overall_record():

    user_name = session['username']      # Get the username from the session
    connection = getCursor()
    Member_ids = []        # Initialize an empty list to store Member_ids
    Member_name = request.args.get('Member_name', '')       # Check if there's a query parameter named 'Member_name' in the request

    # If Member_name is provided, fetch the Member_id(s) corresponding to the name from the database
    if Member_name:
        connection.execute("select Member_id from members where First_name=%s or Last_name=%s",
                           (Member_name, Member_name,))
        Member_ids = [i[0] for i in connection.fetchall()]

        # If no Member_ids are found, render the template with empty records
        if not Member_ids:
            return render_template('./manager/overall_record.html', user_name=user_name, records=[],
                                   Member_name=Member_name,
                                   role='manager')
        
    # Fetch records from the booking and attendance tables where the status is 'successful'
    connection.execute(
        "select Member_id,Type,Date,Class_id,Session_id,a.attendent from booking as b join attendance as a on b.Booking_id = a.Booking_id where Status='successful'")
    records = connection.fetchall()


    res = []

    # Iterate through fetched records
    for record in records:

        Member_id = record[0]

        # If Member_ids are provided, filter records based on them
        if Member_ids:
            if Member_id not in Member_ids:
                continue

        # Extract record details
        Type = record[1]
        Date = record[2]
        Class_id = record[3]
        Session_id = record[4]
        attendent = record[5]

        # Fetch member details from the members table
        connection.execute("select First_name,Last_name,Email,Phone_number from members where Member_id=%s",
                           (Member_id,))
        First_name, Last_name, Email, Phone_number = connection.fetchone()

        # Construct result list with relevant details       
        result = []
        result.append(First_name)
        result.append(Last_name)
        result.append(Email)
        result.append(Phone_number)
        result.append(Type)
        result.append(Date)
        result.append(attendent)

        # Determine whether to fetch class name or session name based on Class_id or Session_id
        if Class_id:
            connection.execute("select Class_name from class where Class_id=%s", (Class_id,))
        else:
            connection.execute("select Session_name from session where Session_id=%s", (Session_id,))
        result.append(connection.fetchone()[0])

        # Ensure all elements in the result list are non-empty
        result = [i if i else "" for i in result]
        res.append(result)
 
    return render_template('./manager/overall_record.html', user_name=user_name, records=res, role='manager',
                           Member_name=Member_name)


@app.route('/manager/popular_class', methods=['GET', 'POST'])
def popular_class():
    
    # Execute SQL query to fetch the number of bookings for each class and their names
    connection = getCursor()
    connection.execute(
        """select Class_id,Class_name,num, dense_rank() over(order by num desc) 
        from (select b.Class_id, count(b.Member_id) as num, c.Class_name 
        from booking as b 
            join class as c on b.Class_id = c.Class_id
            where b.Type = 'class'
            group by Class_id) as unknow
         """)
    classRank = connection.fetchall()      # Fetch all rows from the query result

    # Convert the fetched data into a format suitable for rendering in the template
    popular_class = [{'label': row[1], 'value': float(row[2])} for row in classRank]

    return render_template('./manager/report_popular_class.html',role='manager',popular_class=popular_class)



@app.route('/manager/financial_report', methods=['GET', 'POST'])
def financial_report():

    # Execute SQL query to get the total amount for each payment type
    connection = getCursor()
    connection.execute(
        """select Type, sum(Amount) as total from payment
           group by Type
         """)
    typeTotal = connection.fetchall()      # Fetch all rows from the query result

    # Convert the fetched data into a format suitable for rendering in the template
    chart_type = [{'label': row[0], 'value': float(row[1])} for row in typeTotal]
   
    # Execute SQL query to get the total amount for each month
    connection = getCursor()
    connection.execute(
        """select DATE_FORMAT(Date, '%Y-%m') AS formatted_date, 
        sum(Amount) as total from payment
           group by formatted_date;
         """)
    monthTotal = connection.fetchall()      # Fetch all rows from the query result

    # Convert the fetched data into a format suitable for rendering in the template
    chart_month = [{'label': row[0], 'value': float(row[1])} for row in monthTotal]

    # Execute SQL query to get the total amount for each year
    connection = getCursor()
    connection.execute(
        """select DATE_FORMAT(Date, '%Y') AS formatted_date, 
        sum(Amount) as total from payment
           group by formatted_date;
         """)
    yearaTotal = connection.fetchall()      # Fetch all rows from the query result

    # Convert the fetched data into a format suitable for rendering in the template
    chart_year = [{'label': row[0], 'value': float(row[1])} for row in yearaTotal]

    return render_template('./manager/report_financial_report.html',role='manager',chart_type=chart_type,chart_month=chart_month,chart_year=chart_year)


@app.route('/manager/news_management',methods=['POST','GET'])
def news_management():

    # Execute SQL query to fetch all news
    connection = getCursor()
    connection.execute("""select * from news""")
    news= connection.fetchall()     # Fetch all news from the query result

    return render_template('./manager/news_management.html',role='manager',news_list=news)


@app.route('/manager/creat-news',methods=['POST','GET'])
def creat_news():

    # If the request method is POST, it means the form is submitted
    if request.method =='POST':
        
        # Get the news title and content from the form
        newsTitle = request.form.get('newsTitle')
        newsContent = request.form.get('newsContent')
        today_date = date.today().strftime('%Y-%m-%d')          # Get today's date

        # Insert the new news entry into the database
        connection = getCursor()
        connection.execute("""insert into news (News_title,News_content,Date) values(%s,%s,%s)""",
                           (newsTitle,newsContent,today_date))

        return redirect(url_for('news_management'))
    
    return render_template('./manager/news_creat.html',role='manager')


@app.route('/manager/edit_news/<id>',methods=['POST','GET'])
def edit_news(id):

    if request.method=='POST':

        # Get the news title and content from the form
        newsTitle = request.form.get('newsTitle')
        newsContent = request.form.get('newsContent')
        today_date = date.today().strftime('%Y-%m-%d')

        # Update the news entry in the database
        connection = getCursor()
        connection.execute("""Update news set News_title =%s,News_content =%s,Date =%s
                           where News_id =%s""",
                           (newsTitle,newsContent,today_date,id))

        return redirect(url_for('news_management'))

    # If the request method is GET, it means the user is accessing the edit form
    # Fetch the details of the news entry with the given ID
    connection = getCursor()
    connection.execute("""select * from news where News_id = %s""",(id,))
    newsDetail = connection.fetchone()    

    return render_template('./manager/news_details.html',newsDetail=newsDetail,role='manager')



@app.route('/manager/delete_news/<id>',methods=['POST','GET'])
def delete_news(id):

    # Delete the news entry from the database based on the provided ID
    connection = getCursor()
    connection.execute("""Delete from news where News_id = %s""",(id,))

    return redirect(url_for('news_management'))

    
@app.route("/manager/room", methods=['GET', 'POST'])
def manager_room():

    user_name = session['username']

    # Fetch all room records from the database
    connection = getCursor()
    connection.execute(
        "select Room_id,Room_type,Room_name from room")
    records = connection.fetchall()

    # Modify each record to replace None values with empty strings
    index = 0
    for record in records:
        record = [i if i else "" for i in record]
        records[index] = record
        index += 1

    return render_template('./manager/Room.html', user_name=user_name, records=records, role='manager')


@app.route("/manager/room_update", methods=['GET', 'POST'])
def room_update():

    # Initialize a record dictionary with empty values
    record = {
        "Room_id": "",
        "Room_type": "",
        "Room_name": "",
    }

    if request.method == "POST":

        # If the request is a POST method (form submission)
        # Get the record_id from the request arguments
        record_id = request.args.get('record_id')
        Room_name = request.form.get('Room_name')
        Room_type = request.form.get('Room_type')
        connection = getCursor()

        if not record_id:
            # If record_id is not provided, it's a new record to be inserted
            connection.execute(
                "insert into room (Room_type,Room_name) values(%s,%s)",
                (Room_type, Room_name))
            return redirect('/manager/room')
        
        else:
            # If record_id is provided, it's an existing record to be updated
            connection.execute(
                "update  room set Room_type=%s,Room_name=%s where Room_id=%s;",
                (Room_type, Room_name, record_id))
            return redirect('/manager/room')
        
    else:
        # If the request is a GET method (initial load or edit)
        # Get the record_id from the request arguments
        record_id = request.args.get('record_id')
        connection = getCursor()

        if record_id:
            # If record_id is provided, fetch the existing record from the database
            connection.execute(
                "SELECT * from room where Room_id=%s;", (record_id,))
            res = connection.fetchone()

            if not res:
                res = ['', '', '', '', ''] # Handle if record doesn't exist
            record = {
                "Room_id": res[0] if res[0] else "",
                "Room_type": res[1] if res[1] else "",
                "Room_name": res[2] if res[2] else "",

            }

        # Provide Room_types for selection
        Room_types = ["Therapy", "Class"]

        return render_template('./manager/room_Update.html', Room_types=Room_types, Room_type=record.get('Room_type'),
                               record=record, role='manager')


@app.route("/manager/room_delete", methods=['GET', 'POST'])
def room_delete():

    # Execute the delete operation in the database
    record_id = request.args.get('record')
    connection = getCursor()
    connection.execute(
        "delete from room where Room_id=%s;", (record_id,))

    return redirect('/manager/room')



