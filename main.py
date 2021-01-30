from flask import Flask, render_template, request, redirect, session, url_for,send_file
import sqlite3
import requests
import os
import g
from functools import wraps
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime, timedelta
from pytz import timezone
import nexmo
import pytz
from ics import Calendar, Event

app = Flask(__name__)
secretkey = os.urandom(24)
app.secret_key = secretkey

##SMS STUFF
client = nexmo.Client(key='882a6dc9', secret='6mgKLjFQbKIxGdtg')


#session settings
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

DATABASE = 'database.db'

##allows for easy querying of database
def query_db(query, args=(), one=False):
  connection = sqlite3.connect(DATABASE, check_same_thread=False)
  cur = connection.cursor() 
  cur.execute(query, args)
  data = cur.fetchall()
  connection.commit()
  connection.close()
  return (data[0] if data else None) if one else data

##closes database when website closes
@app.teardown_appcontext
def close_connection(exception):
  db = getattr(g, '_database', None)
  if db is not None:
    db.close()


#login required function
# use @login_required
def login_required(f):
  """
  Decorate routes to require login.

  http://flask.pocoo.org/docs/1.0/patterns/viewdecorators/
  """
  @wraps(f)
  def decorated_function(*args, **kwargs):
    if session.get("user_id") is None:
        return redirect("/login")
    return f(*args, **kwargs)
  return decorated_function

@app.route('/delete/<int:item>',methods=["GET","POST"])
@login_required
def deleteItem(item):
  if request.method == "GET":
    query_db("DELETE FROM events WHERE id=?",[item])
    found_events = query_db("SELECT * FROM events WHERE user_id=?", [session["user_id"]]) 

    return render_template("index.html",events = found_events, loggedin=True)
  if request.method == "POST":
    return render_template("index.html", loggedin=True)

@app.route('/viewDesc/<int:item>',methods=["GET","POST"])
@login_required
def viewDesc(item):
  if request.method == "GET":
    event=query_db("SELECT * FROM events WHERE id=?",[item])
    description = event[0][2]
    title = event[0][1]
    eventDate = event[0][3]
    startTime = event[0][8]
    item_id=event[0][0]
    found_events = query_db("SELECT * FROM events WHERE user_id=?", [session["user_id"]]) 

    return render_template("index.html",events = found_events, description=description,title=title, eventDate=eventDate, startTime=startTime,item_id=item_id,loggedin=True)
  if request.method == "POST":
    return render_template("index.html",loggedin=True)
##main page
@app.route('/', methods=["GET","POST"])
@login_required #have to login
def index():
  if request.method == "GET":

    #query_db("CREATE TABLE events(id INTEGER PRIMARY KEY, name TEXT, description TEXT, date DATETIME, creation_date DATETIME, complete BOOLEAN)")
    #query_db("ALTER TABLE events ADD user_id INTEGER")
    #query_db("ALTER TABLE users ADD phone TEXT")
    found_events = query_db("SELECT * FROM events WHERE user_id=?", [session["user_id"]])
    #phone = query_db("SELECT phone FROM users WHERE user_id=?",[session["user_id"]])
    #print(phone)
    return render_template('index.html', events = found_events,loggedin=True)
  if request.method == "POST":
    # using two submit buttons
    # single being for adding an event
    # one for each being for labelling as complete


    #event_name, event_date, description, repeat_weekly, end_date, length#
    ##add length column

    event_name = request.form.get("event_name")
    event_date = request.form.get("event_date")
    description = request.form.get("description")
    repeat_weekly = bool(request.form.get("repeat_weekly"))
    end_date = request.form.get("end_date")
    length = request.form.get("length")
    start_time=request.form.get("start_time")
    
    found_events = query_db("SELECT * FROM events WHERE user_id=?", [session["user_id"]])
    if not event_name:
      return render_template('index.html', events = found_events, error="add event name!",loggedin=True)
    if not event_date:
      return render_template('index.html', events = found_events, error="add event date!",loggedin=True)
    if repeat_weekly:
      if not end_date:
        return render_template('index.html', events = found_events, error="add a date to end the repeating!",loggedin=True)
    if start_time and not length:
      return render_template('index.html', events = found_events, error="add a reminder time!",loggedin=True)
    #print(event_name)
    #print(start_time)
    query_db("INSERT INTO events (user_id, name, description, date, creation_date, complete, length, time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",[session["user_id"],event_name, description, event_date, datetime.today().strftime('%Y-%m-%d'), False, length, start_time])

    if repeat_weekly:
      end_date = datetime(int(end_date[0:4]),int(end_date[5:7]),int(end_date[8:]))
    
    event_date = datetime(int(event_date[0:4]),int(event_date[5:7]),int(event_date[8:]))

    if repeat_weekly:
      while (event_date + timedelta(7)) <= end_date:
        #modify event date by adding 7 days to it
        event_date = event_date + timedelta(7)
        current = event_date.strftime('%Y-%m-%d')
        query_db("INSERT INTO events (user_id, name, description, date, creation_date, complete, length, time) VALUES (?, ?, ?, ?, ?, ?,?,?)",[session["user_id"], event_name, description, current, datetime.today().strftime('%Y-%m-%d'), False, length, start_time])

    #yyyy-mm-dd#
    #print(query_db("SELECT * FROM events"))
    ##add events to database
    return redirect("/")

@app.route('/logout', methods=["GET", "POST"])
def logout():
  session.clear()
  return redirect("/login")
##login
@app.route('/login', methods=["GET","POST"])
def login():
  if request.method == "GET":

    #query_db("CREATE TABLE users(user_id INTEGER PRIMARY KEY, username TEXT, password TEXT,phone TEXT)")
    #query_db("CREATE TABLE events(id INTEGER PRIMARY KEY, name TEXT, description TEXT, date DATETIME, creation_date DATETIME, complete BOOLEAN, user_id INTEGER, length INTEGER, time TEXT)")
    #query_db("DELETE FROM events")

    return render_template('login.html',loggedin=False)
  if request.method == "POST":
    username = request.form.get("username")
    password = request.form.get("password")

  matches = query_db("SELECT * FROM users WHERE username=?", [username])

  if not matches:
    return render_template("login.html", error = "Your account does not exist",loggedin=False)

  if not check_password_hash(matches[0][2], password):
    return render_template("login.html", error = "Your password was incorrect",loggedin=False)

  current_id = query_db("SELECT user_id FROM users WHERE username=?",[username])
  #print(current_id)
  session["user_id"] = current_id[0][0]

  ##check phone num
  found_events = query_db("SELECT * FROM events WHERE user_id=?", [session["user_id"]])
  phone = query_db("SELECT phone FROM users WHERE user_id=?",[session["user_id"]])

  if found_events:
    for x in found_events:
      event_time=x[8]
      #print(event_time)
      if event_time:
        #eastern standard
        est = timezone('EST')
        #print(datetime.now(est))
        now = datetime.now(est)
        current_time = now.strftime("%H:%M")
        eventInMins = int(event_time[0:2])*60+int(event_time[3:])
        currentInMins = (int(current_time[0:2]))*60 + int(current_time[3:])
        differenceOfMins = eventInMins - currentInMins
        if (x[3] == now.strftime('%Y-%m-%d')) and (differenceOfMins <= int(x[7])) and (differenceOfMins > 0):
          client.send_message({
            'from': '14166286953',
            'to': '1'+ phone[0][0],
            'text': 'There is '+str(differenceOfMins)+" minutes until your "+str(x[1])+" event!"})

  return redirect("/")

##register  
@app.route('/register', methods=["GET","POST"])
def register():
  if request.method == "GET":
    return render_template('register.html',loggedin=False)
  if request.method == "POST":
    username = request.form.get("username")
    password = request.form.get("password")
    passwordConfirm = request.form.get("password-confirm")
    phoneNumber = request.form.get("phoneNumber")

    if not username:
      return render_template("register.html", error = "Please enter a username")
    if not password:
      return render_template("register.html", error = "Please enter a password")
    elif not passwordConfirm:
      return render_template("register.html", error = "Please confirm a password")
    if not phoneNumber:
      return render_template("register.html", error = "Please enter a phone number")

    matches = query_db("SELECT * FROM users WHERE username=?",[username])
    #print(matches)
    if matches:
      return render_template("register.html", error = "Username not unique",loggedin=False)
    
    #TODO: see if passwords matches
    if password != passwordConfirm:
      return render_template("register.html", error = "Passwords do not match!",loggedin=False)

    #add them to database
    query_db("INSERT INTO users (username, password, phone) VALUES (?,?,?)", [username, generate_password_hash(password),phoneNumber])

    ##add temporary User
    #query_db("INSERT INTO users (username, password) VALUES (?,?)",["testusername","testpassword"])
    #print(query_db("SELECT * FROM users"))
    current_id = query_db("SELECT user_id FROM users WHERE username=?",[username]) 
    session["user_id"] = current_id[0][0]

    return redirect("/")

##settings page 
@app.route('/settings', methods=["GET", "POST"])
@login_required
def settings():
  if request.method =="GET":
    return render_template("settings.html", loggedin = True)
  if request.method=="POST":
    new_number = request.form.get("phone")
    query_db("UPDATE users SET phone=? WHERE user_id=?", (new_number,session['user_id']))
    return render_template("settings.html", loggedin = True)

@app.route('/download', methods=["GET", "POST"])
@login_required
def download():
  if request.method =="GET":
    c = Calendar()

    events=query_db("SELECT * FROM events WHERE user_id=?",[session["user_id"]])

    for x in events:
      utc=pytz.utc
      eastern=pytz.timezone('US/Eastern')
      if x[8]:
        local_datetime = datetime(int(x[3][0:4]), int(x[3][5:7]), int(x[3][8:]),int(x[8][0:2]),int(x[8][3:5]))
      else:
        local_datetime = datetime(int(x[3][0:4]), int(x[3][5:7]), int(x[3][8:]))
      date_eastern=eastern.localize(local_datetime,is_dst=None)
      date_utc=date_eastern.astimezone(utc)

      e = Event()
      e.name = x[1]
      e.begin = date_utc.strftime('%Y-%m-%d %H:%M:%S') #x[3] + " " + x[8] + ":00"
      c.events.add(e)

    with open('calendars/'+str(session["user_id"])+'.ics', 'w') as f:
      f.write(str(c))
    
    ##download file
    path = "calendars/"+str(session["user_id"])+".ics"
    
    return send_file(path, as_attachment=True, cache_timeout=0)
  if request.method=="POST":
    return redirect("/")




app.run(host='0.0.0.0', port=8080)