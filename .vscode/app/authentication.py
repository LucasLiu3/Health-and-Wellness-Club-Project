
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
   session.pop('loggedin', None)
   session.pop('username', None)
   session.pop('role', None)
   return redirect(url_for('login'))


@app.route('/register',methods=['GET','POST'])
def register():

    msg = ''
    if request.method=='POST':


        if 'username' in request.form and 'password' in request.form and 'email' in request.form: 

            username = request.form['username']
            password = request.form['password']
            confirmedPassword = request.form['conpassword']
            email = request.form['email']


            cursor = getCursor()
            cursor.execute('SELECT * FROM account WHERE username = %s', (username,))
            account = cursor.fetchone()

            cursor = getCursor()
            cursor.execute('select * from account where email = %s', (email,))
            exitEmail = cursor.fetchone()

            pattern = re.compile(r'^(?:(\d)|([a-zA-Z])|([@$!%*?&]))(?!.*\1\1)[\dA-Za-z@$!%*?&]{8,}$')

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

            elif not re.match(pattern,password):
                msg ='Password should be different character types'


            else:
                hashed = hashing.hash_value(password, salt='abcd')
                cursor = getCursor()
                cursor.execute('INSERT INTO account (username, password, email) VALUES (%s, %s, %s)', (username, hashed, email,))
                connection.commit()
                session['loggedin'] = True
                session['username'] = username
                session['role'] ='member'

                return render_template('./basic/register.html', username=username,email=email,step=2)
        
        elif 'first_name' in request.form and 'last_name' in request.form and 'birth' in request.form:

            title = request.form['title']
            savedemail = request.form['email']
            savedusername = request.form['username']
            first_name = request.form['first_name']
            last_name = request.form['last_name']
            position = request.form['position']
            phone = request.form['phone']
            address =request.form['address']
            birth = request.form['birth']

            
            cursor = getCursor()
            cursor.execute(f"""insert into members (Title, First_name, Last_name, Position,Email,Phone_number,Address,date_of_birth,username)
                         values ('{title}','{first_name}','{last_name}','{position}','{savedemail}','{phone}','{address}','{birth}','{savedusername}');
                         """)
            connection.commit()

            return render_template('./basic/register.html',step=3,username=savedusername)
        
        elif 'plan' in request.form and 'price' in request.form:
            
            username = request.form['username']

        
            cursor=getCursor()
            cursor.execute(f"""select Member_id from members where username ='{username}'""")
            memeber_id =cursor.fetchone()[0]

  
            plan= request.form['plan']
            price = request.form['price']
            start_time= date.today()

            if plan =='monthly':
                expire_time = start_time + timedelta(days=30)
            elif plan =='annual':
                expire_time= start_time+ timedelta(days=365)

            start_time_str = start_time.strftime('%Y-%m-%d')
            expire_time_str = expire_time.strftime('%Y-%m-%d')

            cursor = getCursor()
            cursor.execute("""INSERT INTO payment ( Amount, Type, Date, Status) VALUES (%s, %s, %s, %s);""", ( price, 'Membership',start_time_str, 'successful'))
        

            cursor.execute("SELECT LAST_INSERT_ID();")
            payment_id = cursor.fetchone()[0]

            cursor = getCursor()
            cursor.execute("""INSERT INTO membership (Member_id, Type, Fee, Start_time, Expire_time,Payment_id) VALUES (%s, %s, %s, %s, %s,%s);""", (memeber_id, plan, price, start_time_str, expire_time_str,payment_id))

            return redirect(url_for('home'))

    return render_template('./basic/register.html',msg=msg,step =1)


@app.route('/home')
def home():

    if 'loggedin' in session:
        role = session['role']
        username = session['username']

        if role =='member':
            cursor = getCursor()
            cursor.execute('select * from members where username = %s', (username,))
            detail = cursor.fetchone()[9]
        elif role =='therapist':
            cursor = getCursor()
            cursor.execute('select * from therapist where username = %s', (username,))
            detail = cursor.fetchone()[9]
        elif role =='manager':
            cursor = getCursor()
            cursor.execute('select * from manager where username = %s', (username,))
            detail = cursor.fetchone()[7]

 
        return render_template('layout.html',role=role,username=username,detail=detail)

    return render_template("./basic/login.html")