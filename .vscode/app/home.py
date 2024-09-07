

from app import app

from flask import render_template
import mysql.connector
import connect
from flask import request


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



@app.route("/")
def main():
    return render_template("./basic/main.html")

@app.route("/info")
def info():

    infoname = request.args.get('search')


    cursor = getCursor()
    cursor.execute("""SELECT t.Day,c.Class_name,c.Room_num,e.First_name,e.Last_name 
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

    cursor = getCursor()
    cursor.execute('SELECT c.Class_id,c.Class_name,c.Description,c.MaxCapacity,c.Duration,t.First_name,t.Last_name FROM class as c left join therapist as t on c.Therapist_id = t.Therapist_id')
    classes = cursor.fetchall()

    cursor = getCursor()
    cursor.execute('SELECT s.Session_id,s.Session_name,s.Description,s.Fee,s.Duration,t.First_name,t.Last_name FROM session as s left join therapist as t on s.Therapist_id = t.Therapist_id')
    sessions = cursor.fetchall()

    cursor = getCursor()
    cursor.execute('SELECT * from therapist ')
    therapists = cursor.fetchall()

    return render_template("./basic/info.html",classes=classes,sessions=sessions,therapists=therapists,infoname=infoname,timetables=sort_timetable)