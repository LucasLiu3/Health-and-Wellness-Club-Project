
from app import app

from flask import session
from flask import render_template
from flask import request
from flask import redirect
from flask import url_for
import mysql.connector
import connect
from flask_hashing import Hashing
import re
from datetime import date, timedelta,datetime

hashing = Hashing(app)
app.config['SECRET_KEY'] = '5203'


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


@app.route("/login",methods=['GET','POST'])
def login():

    msg=''

    if request.method=='POST':
        
        if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
            username = request.form['username']
            user_password = request.form['password']
            
            # get all account details about this user
            cursor = getCursor()
            cursor.execute('SELECT * FROM account WHERE username = %s', (username,))
            account = cursor.fetchone()
        
            # if username exits, then check the password is correct or not.
            if account is not None:

                password = account[2]
                role=account[4]

                # if the input password and password in database are matched in hasing method,
                # then session would store the loggedin, username, role for this username, and redirct to home page.
                if hashing.check_value(password, user_password, salt='abcd'):

                    session['loggedin'] = True
                    session['username'] = account[1]
                    session['role'] =role
                    return redirect(url_for('home'))
                
                # if password is incrorrect, will create the error message
                else:
                    msg = 'Incorrect password!'

            # if username is incrorrect, will create the error message
            else:
                msg = 'Incorrect username'

    return render_template("./basic/login.html",msg=msg)


@app.route("/logout",methods=['GET','POST'])
def logout():
   
   #when users logged out, the session will delete related data to prevent insecure login.
   session.pop('loggedin', None)
   session.pop('username', None)
   session.pop('role', None)
   return redirect(url_for('login'))


@app.route('/register',methods=['GET','POST'])
def register():

    # Initialize an empty message variable
    msg = ''

    # Check if the request method is POST
    if request.method=='POST':

        # Check if username, password, and email are in the form data
        if 'username' in request.form and 'password' in request.form and 'email' in request.form: 

             # Get form data for username, password, confirmed password, and email from the submitted form
            username = request.form['username']
            password = request.form['password']
            confirmedPassword = request.form['conpassword']
            email = request.form['email']

            # Check if the username already exists in the database
            cursor = getCursor()
            cursor.execute('SELECT * FROM account WHERE username = %s', (username,))
            account = cursor.fetchone()

            # Check if the email already exists in the database
            cursor = getCursor()
            cursor.execute('select * from account where email = %s', (email,))
            exitEmail = cursor.fetchone()

            # Define a regex pattern for password validation
            has_digit = re.search(r'\d', password)
            has_alpha = re.search(r'[A-Za-z]', password)

             # Check various conditions for validity and uniqueness
            if account:
                msg = 'Account already exits'
            elif exitEmail:
                msg = 'Email already exits'
            elif password != confirmedPassword:
                msg = 'Passwords should same'

            # if email does not meet the standard, then creat the error message
            elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
                msg = 'Invalid email address!'

            # if username does not meet the standard, then will create the error message
            elif not re.match(r'[A-Za-z0-9]+', username):
                msg = 'Username must contain only characters and numbers!'

            # if password does not meet the input standard, then will create  the error message. 
            elif len(password) <8:
                msg = 'Password should be 8 characters long'

            elif not (has_digit and has_alpha):
                msg ='Password should contain at least numbers and letters.'


            else:

                # Hash the password and insert user data into the database
                hashed = hashing.hash_value(password, salt='abcd')
                cursor = getCursor()
                cursor.execute('INSERT INTO account (username, password, email) VALUES (%s, %s, %s)', (username, hashed, email,))
                connection.commit()

                 # Set session variables and render a success template
                session['loggedin'] = True
                session['username'] = username
                session['role'] ='member'

                return render_template('./basic/register.html', username=username,email=email,step=2)
        
        # Check if first_name, last_name, and birth are in the form data
        elif 'first_name' in request.form and 'last_name' in request.form and 'birth' in request.form:

            # Get member details from the form data
            title = request.form['title']
            savedemail = request.form['email']
            savedusername = request.form['username']
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            position = request.form['position']
            phone = request.form['phone']
            address =request.form['address']
            birth = request.form['birth']

            # Insert member details into the database
            cursor = getCursor()
            cursor.execute(f"""insert into members (Title, First_name, Last_name, Position,Email,Phone_number,Address,date_of_birth,username)
                         values ('{title}','{first_name}','{last_name}','{position}','{savedemail}','{phone}','{address}','{birth}','{savedusername}');
                         """)
            connection.commit()

            return render_template('./basic/register.html',step=3,username=savedusername)
        
         # Check if plan and price are in the form data
        elif 'plan' in request.form and 'price' in request.form:
            
            username = request.form['username']
            cursor=getCursor()
            cursor.execute(f"""select Member_id from members where username ='{username}'""")
            memeber_id =cursor.fetchone()[0]   #get member_id from this sql query

            #get details about memebership from from data.
            plan= request.form['plan']
            price = request.form['price']
            start_time= date.today()

            # Calculate expiration time based on the selected plan
            if plan =='monthly':
                expire_time = start_time + timedelta(days=30)
            elif plan =='annual':
                expire_time= start_time+ timedelta(days=365)
            
            # Format start and expire times as strings
            start_time_str = start_time.strftime('%Y-%m-%d')
            expire_time_str = expire_time.strftime('%Y-%m-%d')

            # Insert payment and membership details into the database
            cursor = getCursor()
            cursor.execute("""INSERT INTO payment ( Amount, Type, Date, Status) VALUES (%s, %s, %s, %s);""", ( price, 'membership',start_time_str, 'successful'))
            cursor.execute("SELECT LAST_INSERT_ID();")
            payment_id = cursor.fetchone()[0]   #get payment_id from this sql select
            cursor = getCursor()
            cursor.execute("""INSERT INTO membership (Member_id, Type, Fee, Start_time, Expire_time,Payment_id) VALUES (%s, %s, %s, %s, %s,%s);""", (memeber_id, plan, price, start_time_str, expire_time_str,payment_id))

            return redirect(url_for('home'))

    return render_template('./basic/register.html',msg=msg,step =1)


@app.route('/home')
def home():
    
    # Check if the user is logged in
    if 'loggedin' in session:

        # Get the user's role and username from the session
        role = session['role']
        username = session['username']

        # Depending on the user's role, fetch their details from the database
        if role =='member':
            # Fetch member details and associated reminders
            cursor = getCursor()
            cursor.execute('select * from members where username = %s', (username,))
            reuslt = cursor.fetchone()
            detail = reuslt[9]   #Get image path from member's data
            member_id = reuslt[0] #Get member id from member's data
            
            # Insert subscription reminder for user if their membership is expired or next to expired 
            cursor = getCursor()
            cursor.execute('select * from reminder where Member_id = %s', (member_id,))
            message = cursor.fetchall()
   
            return render_template('layout.html',role=role,username=username,detail=detail,message=message)
        
        elif role =='therapist':
            # Fetch therapist details
            cursor = getCursor()
            cursor.execute('select * from therapist where username = %s', (username,))
            reuslt = cursor.fetchone()
            detail = reuslt[9]  #Get image path from therapist's data

        elif role =='manager':
            # Fetch manager details
            cursor = getCursor()
            cursor.execute('select * from manager where username = %s', (username,))
            reuslt = cursor.fetchone()
            detail = reuslt[7]  #Get image path from manager's data

 
        return render_template('layout.html',role=role,username=username,detail=detail)

    return render_template("./basic/login.html")



