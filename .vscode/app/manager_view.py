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
    connection = getCursor()
    connection.execute(
        "select account.username,Title,First_name,Last_name,Position,members.Email,Phone_number,Address,date_of_Birth,Status from account left join members on members.username=account.username where role='member';")
    records = connection.fetchall()
    index = 0
    for record in records:
        record = [i if i else "" for i in record]
        records[index] = record
        index += 1

    return render_template('./manager/Member.html', user_name=user_name, members=records,role='manager')


@app.route("/manager/member_update", methods=['GET', 'POST'])
def member_update():
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
        Image = request.form.get('Image')
        Heath_Information = request.form.get('Heath_Information')
        Status = request.form.get('Status')
        connection = getCursor()
        if not ori_username:
            # insert
            connection.execute(
                "SELECT * from account where username=%s;", (username,))
            res = connection.fetchone()
            if res:
                flash(message="User name already exists")
                return render_template('./manager/Member_Update.html', record=record,role='manager')
            connection.execute(
                "insert into account (username,password,email,role) values(%s,%s,%s,'member')",
                (username, password, Email))
            connection.execute(
                "insert into members (Title,First_name,Last_name,Position,Email,Phone_number,Address,date_of_Birth,Image,Heath_Information,Status,username) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);",
                (Title, First_name, Last_name, Position, Email, Phone_number, Address, date_of_Birth, Image,
                 Heath_Information, Status, username,))
            return redirect('/manager/members')
        else:
            # update
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
                "Image": Image,
                "Heath_Information": Heath_Information,
                "Status": Status,
            }
            if res[1] != username:
                connection.execute(
                    "SELECT id from account where username=%s;", (username,))

                if connection.fetchone():
                    flash(message="User name already exists")
                    return render_template('./manager/Member_Update.html',
                                           record=record,role='manager')

            connection.execute(
                "update account set password=%s where username=%s",
                (password, res[1]))
            connection.execute(
                "SELECT * from members where username=%s;", (res[1],))
            res = connection.fetchone()
            if not res:
                connection.execute(
                    "insert into members (Title,First_name,Last_name,Position,Email,Phone_number,Address,date_of_Birth,Image,Heath_Information,Status,username) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);",
                    (Title, First_name, Last_name, Position, Email, Phone_number, Address, date_of_Birth, Image,
                     Heath_Information, Status, username,))

            else:
                connection.execute(
                    "update  members set Title=%s,First_name=%s,Last_name=%s,Position=%s,Email=%s,Phone_number=%s,Address=%s,date_of_Birth=%s,Image=%s,Heath_Information=%s,Status=%s where username=%s;",
                    (Title, First_name, Last_name, Position, Email, Phone_number, Address, date_of_Birth, Image,
                     Heath_Information, Status, ori_username,))
            flash(
                message="update successful")
            return render_template('./manager/Member_Update.html',
                                   record=record,role='manager')
    else:
        username = request.args.get('username', '')
        if username:
            connection = getCursor()
            connection.execute(
                "SELECT * from account where username=%s;", (username,))
            res = connection.fetchone()
            if not res:
                res = [1, 2, 3]
            connection.execute(
                "SELECT * from members where username=%s;", (username,))
            record = connection.fetchone()
            if not record:
                record = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
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
    connection = getCursor()
    connection.execute(
        "delete from members where username=%s;", (username,))
    connection.execute(
        "delete from account where username=%s;", (username,))

    return redirect('/manager/members')


@app.route("/manager/member_detail", methods=['GET', 'POST'])
def member_detail():
    username = request.args.get('username')
    connection = getCursor()
    connection.execute(
        "SELECT * from account where username=%s;", (username,))
    res = connection.fetchone()
    if not res:
        res = [1, 2, 3]
    connection.execute(
        "SELECT * from members where username=%s;", (username,))
    record = connection.fetchone()
    if not record:
        record = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

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
    connection = getCursor()
    connection.execute(
        "select account.username,Title,First_name,Last_name,Postion,therapist.Email,Specialty,Phone_number,status from account left join therapist on therapist.username=account.username where role='therapist';")
    records = connection.fetchall()
    index = 0
    for record in records:
        record = [i if i else "" for i in record]
        records[index] = record
        index += 1

    return render_template('./manager/Therapist.html', user_name=user_name, therapists=records,role='manager')


@app.route("/manager/therapist_update", methods=['GET', 'POST'])
def therapist_update():
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
        ori_username = request.args.get('username')
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
        connection = getCursor()
        if not ori_username:
            # insert
            connection.execute(
                "SELECT * from account where username=%s;", (username,))
            res = connection.fetchone()
            if res:
                flash(message="User name already exists")
                return render_template('./manager/Therapist_Update.html', record=record)
            connection.execute(
                "insert into account (username,password,email,role) values(%s,%s,%s,'therapist')",
                (username, password, Email))
            connection.execute(
                "insert into therapist (Title,First_name,Last_name,Postion,Email,Specialty,Phone_number,Status,Image,username) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);",
                (Title, First_name, Last_name, Postion, Email, Phone_number, Specialty, status,
                 Image, username,))
            return redirect('/manager/therapist')
        else:
            # update
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
                "Image": Image,
                "status": status,
            }
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
                connection.execute(
                    "insert into therapist (Title,First_name,Last_name,Postion,Email,Specialty,Phone_number,status,Image,username) values(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);",
                    (Title, First_name, Last_name, Postion, Email, Phone_number, Specialty,
                     status, Image, username,))

            else:
                connection.execute(
                    "update  therapist set Title=%s,First_name=%s,Last_name=%s,Postion=%s,Email=%s,Phone_number=%s,Specialty=%s,Image=%s,status=%s where username=%s;",
                    (Title, First_name, Last_name, Postion, Email, Phone_number, Specialty, Image,
                     status, ori_username,))
            connection.execute(
                "update account set password=%s where username=%s",
                (password, ori_username))
            flash(
                message="update successful")
            return render_template('./manager/Therapist_Update.html',
                                   record=record,role='manager')
    else:
        username = request.args.get('username', '')
        if username:
            connection = getCursor()
            connection.execute(
                "SELECT * from account where username=%s;", (username,))
            res = connection.fetchone()
            if not res:
                res = [1, 2, 3]
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
    connection.execute(
        "delete from therapist where username=%s;", (username,))
    connection.execute(
        "delete from account where username=%s;", (username,))

    return redirect('/manager/therapist')


@app.route("/manager/therapist_detail", methods=['GET', 'POST'])
def therapist_detail():
    username = request.args.get('username')
    connection = getCursor()
    connection.execute(
        "SELECT * from account where username=%s;", (username,))
    res = connection.fetchone()
    if not res:
        res = [1, 2, 3]
    connection.execute(
        "SELECT * from therapist where username=%s;", (username,))
    record = connection.fetchone()
    if not record:
        record = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

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
        connection = getCursor()
        connection.execute(
            f"""SELECT b.Booking_id,b.Date,b.Session_id,s.Session_name,
                s.Therapist_id,b.Member_id,t.First_name,t.Last_name,
                m.First_name,m.Last_name  FROM booking as b 
                left join session as s on b.Session_id = s.Session_id
                left join therapist as t on s.Therapist_id = t.Therapist_id
                left join members as m on b.Member_id=m.Member_id
                where b.type ='session';;""")
        sessions = connection.fetchall()

        weekday_order = {
        'Monday': 1,
        'Tuesday': 2,
        'Wednesday': 3,
        'Thursday': 4,
        'Friday': 5,
        'Saturday': 6,
        'Sunday': 7
        }

        sorted_sessions = sorted(sessions, key=lambda x: weekday_order[x[1]]) 

        return render_template('./manager/session_schedules.html',sessions=sorted_sessions,role='manager')

    if request.method == 'POST':
        
        weekday = request.form['weekday']
        bookingId =request.form['bookingId']
        sessionId= request.form['sessionId']
        therapistId = request.form['therapist_id']
        roomId = request.form['room_id']    

        connection = getCursor()
        connection.execute(f"""Update booking set Date="{weekday}" where Booking_id={bookingId} """)

        connection = getCursor()
        connection.execute(f"""Update session set Therapist_id={therapistId},Room_num={roomId} where Session_id={sessionId} """)

        return redirect('/manager/session-schedules')

@app.route('/manager/session-schedules-edit',methods=['POST','GET'])
def session_schedules_edit():

    session_id= request.args.get('id')


    connection = getCursor()
    connection.execute(
        f"""SELECT b.Booking_id,b.Date,b.Session_id,s.Session_name,
            s.Therapist_id,b.Member_id,t.First_name,t.Last_name,
            m.First_name,m.Last_name,s.Room_num  FROM booking as b 
            left join session as s on b.Session_id = s.Session_id
            left join therapist as t on s.Therapist_id = t.Therapist_id
            left join members as m on b.Member_id=m.Member_id
            where b.Booking_id ={session_id};;""")
    sessions = connection.fetchall()

    connection =getCursor()
    connection.execute(f"""select Therapist_id,First_name,Last_name
                       from therapist;
        """)
    therapists= connection.fetchall()
    
    therapist_list = []

    for therapist in therapists:
        therapist_list.append(therapist)


    connection = getCursor()
    connection.execute(f"""select Room_id from room where Room_type ='Therapy'""")
    rooms=connection.fetchall()

    room_list =[]
    for room in rooms:
        room_list.append(room[0])

    weekday_order = {
    'Monday': 1,
    'Tuesday': 2,
    'Wednesday': 3,
    'Thursday': 4,
    'Friday': 5,
    'Saturday': 6,
    'Sunday': 7
    }

    sorted_sessions = sorted(sessions, key=lambda x: weekday_order[x[1]]) 

    return render_template('./manager/session_schedules_edit.html',sessions = sorted_sessions,room_list=room_list,therapist_list=therapist_list,role='manager')
 
@app.route('/manager/session-schedules-cancel',methods=['POST','GET'])
def session_schedules_cancel():

    bookingId  =request.args.get('id')
    
    connection = getCursor()
    connection.execute(f"""Delete from booking where Booking_id ={bookingId} """)
    
    return redirect('/manager/session-schedules')

 
@app.route('/manager/add-new-session',methods=['POST','GET'])
def add_new_session():

    if request.method=='GET':

        connection = getCursor()
        connection.execute(f"""SELECT Session_id,Session_name from session """)
        sessionAll= connection.fetchall()

        connection = getCursor()
        connection.execute(f"""SELECT Member_id,Last_name,First_name from members """)
        members= connection.fetchall()

        return render_template('./manager/session_schedules_add.html',members=members ,sessionAll = sessionAll,role='manager')

    elif request.method=='POST':
        
        weekday = request.form['weekday']
        sessionId= request.form['sessionId']
        memberid = request.form['memberid']

        connection = getCursor()
        connection.execute(f"""SELECT fee from session where Session_id = {sessionId} """)
        price= connection.fetchone()[0]
        
        start_time= date.today().strftime('%Y-%m-%d')
 
        connection = getCursor()
        connection.execute("""INSERT INTO payment (Amount,Type,Date,STATUS) VALUES (%s, %s, %s, %s);""", (price, 'therapist session',start_time,'successful' ))

        connection.execute("SELECT LAST_INSERT_ID();")
        payment_id = connection.fetchone()[0]

        connection = getCursor()
        connection.execute("""insert into booking (Member_id,type,Date,Status,Class_id,Session_id,Payment_id)
                            VALUES (%s, %s, %s, %s, %s, %s, %s);""", (memberid,'session', weekday,'successful',None,sessionId,payment_id))

        return redirect('/manager/session-schedules')
    
@app.route('/manager/therapeutic_sessions', methods=['POST', 'GET'])
def manager_therapeutic_sessions():
    connection = getCursor()
    query = """
    SELECT s.Session_id, s.Session_name, s.Description, CONCAT(t.First_name, ' ', t.Last_name) AS Therapist, s.Room_num
    FROM session AS s
    JOIN therapist AS t ON s.Therapist_id = t.Therapist_id
    """

    try:
        connection.execute(query)
        sessions = connection.fetchall()
    except Exception as e:
        flash(f"An error occurred while fetching sessions: {e}", 'danger')
        sessions = []

    return render_template('./manager/manager_therapeutic_session.html', sessions=sessions, role='manager')

@app.route('/manager/view_update_session/<int:session_id>', methods=['GET', 'POST'])
def view_update_session(session_id):
    if request.method == 'POST':
        new_description = request.form.get('description')
        try:
            connection = getCursor()
            connection.execute(
                "UPDATE session SET Description = %s WHERE Session_id = %s",
                (new_description, session_id)
            )
            flash("Session description updated successfully.", 'success')
        except Exception as e:
            flash(f"An error occurred while updating the session: {e}", 'danger')
        return redirect(url_for('view_update_session', session_id=session_id))
    
    try:
        connection = getCursor()
        connection.execute(
            "SELECT Description FROM session WHERE Session_id = %s",
            (session_id,)
        )
        description = connection.fetchone()[0]
    except Exception as e:
        flash(f"An error occurred while fetching the session description: {e}", 'danger')
        description = ""
    
    return render_template('./manager/view_update_session.html', description=description, role='manager')

@app.route('/manager/edit_session/<int:session_id>', methods=['GET', 'POST'])
def edit_session(session_id):
    connection = getCursor()

    if request.method == 'POST':
        # Process the form data and update the session details
        session_name = request.form.get('session_name')
        therapist_id = request.form.get('therapist_id')
        room_num = request.form.get('room_num')

        # Update session in database
        update_query = """
            UPDATE session
            SET Session_name = %s, Therapist_id = %s, Room_num = %s
            WHERE Session_id = %s
        """
        try:
            connection.execute(update_query, (session_name, therapist_id, room_num, session_id))
            flash('Session updated successfully', 'success')
        except Exception as e:
            flash(f'Failed to update session: {e}', 'danger')

        return redirect(url_for('manager_therapeutic_sessions'))
    
    # Fetch session details for the given session_id
    try:
        connection.execute("SELECT Session_name, Description, Therapist_id, Room_num FROM session WHERE Session_id = %s", (session_id,))
        session_details = connection.fetchone()
    except Exception as e:
        session_details = None
        flash(f'Failed to fetch session details: {e}', 'danger')

    # Fetch therapists for dropdown
    try:
        connection.execute("SELECT Therapist_id, CONCAT(First_name, ' ', Last_name) AS name FROM therapist")
        therapists = connection.fetchall()
    except Exception as e:
        therapists = []
        flash(f'Failed to fetch therapists: {e}', 'danger')

    # Fetch rooms for dropdown
    try:
        connection.execute("SELECT Room_id FROM room WHERE Room_type = 'Therapy'")
        rooms = connection.fetchall()
    except Exception as e:
        rooms = []
        flash(f'Failed to fetch rooms: {e}', 'danger')

    return render_template('./manager/manager_edit_session.html', session_id=session_id, session=session_details, therapists=therapists, rooms=rooms, role='manager')


@app.route('/manager/delete_session', methods=['GET'])
def delete_session():
    session_id = request.args.get('session_id')
    if session_id:
        try:
            connection = getCursor()
            # Assuming 'session_id' is the primary key for your 'session' table
            delete_query = "DELETE FROM session WHERE Session_id = %s"
            connection.execute(delete_query, (session_id,))
            flash('Session deleted successfully', 'success')
        except Exception as e:
            # Log the error for debugging purposes
            print(f"Error deleting session: {e}")
            flash('Session deletion failed. Please try again.', 'danger')
    else:
        flash('Session ID not provided', 'danger')
    
    return redirect(url_for('manager_therapeutic_sessions'))



@app.route('/manager/class_timetable')
def manager_class_timetable():
    if 'loggedin' in session and 'username' in session:
        connection = getCursor()
        connection.execute(
            "SELECT c.Class_id, c.Class_name, t.First_name, t.Last_name, c.Room_num FROM  class as c  left join therapist as t on c.Therapist_id=t.Therapist_id ")
        classes = connection.fetchall()

        return render_template('./manager/class_timetable.html', classes=classes, role='manager')

    return redirect(url_for('login'))


@app.route('/manager/class_details/<int:class_id>', methods=['GET', 'POST'])
def manager_class_detail(class_id):
    if 'loggedin' in session and 'username' in session:
        connection = getCursor()
        connection.execute("SELECT * FROM class WHERE Class_id = %s", (class_id,))
        class_detail = connection.fetchone()
        print(class_detail)
        if request.method == 'POST':
            # Handle form submission for updating class details
            # Assuming form fields are named accordingly
            class_name = request.form['class_name']
            description = request.form['description']
            max_capacity = request.form['max_capacity']
            duration = request.form['duration']
            therapist_id = request.form['therapist_id']
            room_num = request.form['room_num']

            # Update the class details in the database
            connection.execute("UPDATE class SET Class_name = %s, Description = %s, MaxCapacity = %s, Duration = %s, Therapist_id = %s, Room_num = %s WHERE Class_id = %s", (class_name, description, max_capacity, duration, therapist_id, room_num, class_id))
            flash('Class details updated successfully!', 'success')
            return redirect(url_for('manager_class_detail', class_id=class_id))

        return render_template('./manager/class_details.html', class_detail=class_detail, role='manager')

    return redirect(url_for('login'))


@app.route('/manager/edit_class/<class_id>', methods=['GET', 'POST'])
def edit_class(class_id):

    if request.method == 'GET':
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

    if request.method=='GET':

        connection = getCursor()
        connection.execute(
        """select c.Class_id,t.Day,c.Class_name,c.Room_num,count(b.Member_id),a.attendance_number from class as c 
        left join timetable as t
        on c.Class_id = t.Class_id
        left join (select * from booking where Type='class') as b
        on c.Class_id = b.Class_id 
        left join attendance_class as a 
        on c.Class_id = a.Class_id
        group by c.Class_id,t.Day """)
        class_attendance = connection.fetchall()

        return render_template('./manager/class_attendance.html',role='manager',classes=class_attendance)

    elif request.method=='POST':

        attendance_number = request.form['attendance_number']
        class_id = request.form['class_id']

        connection = getCursor()
        connection.execute(
        "Update attendance_class set attendance_number =%s where Class_id= %s ;", (attendance_number,class_id))

        return redirect('/manager/class-attendance')

@app.route('/manager/session-attendance',methods=['POST','GET'])
def manager_session_attendance():

    
    if request.method=='GET':
    
        connection = getCursor()
        connection.execute(
        """SELECT s.Session_id,s.Session_name,s.Room_num, count(b.Member_id),a.attendance_number
        FROM session as s 
        left join booking as b on s.Session_id = b.Session_id 
        left join attendance_session as a on s.Session_id = a.Session_id
        group by s.Session_id""")
        session_attendance = connection.fetchall()

        return render_template('./manager/session_attendance.html',role='manager',sessions=session_attendance) 

    elif request.method =='POST':

        attendance_number = request.form['attendance_number']
        session_id = request.form['session_id']

        connection = getCursor()
        connection.execute(
        "Update attendance_session set attendance_number =%s where Session_id= %s ;", (attendance_number,session_id))

        return redirect('/manager/session-attendance')
