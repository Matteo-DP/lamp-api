print("[*] Starting... Please wait for MatPlotLib initialisation")

from flask import Flask
from flask import request
from flask import send_file
from flask_cors import CORS
import sqlite3
from sqlite3 import Error
import RPi.GPIO as GPIO
import matplotlib.pyplot as plt
import datetime
import atexit
import json

# --------------------------------------------------------
# INITIALISATION
# --------------------------------------------------------

app = Flask(__name__)
# Prevents CORS errors
CORS(app)

# define the relay pin
relay_pin = 24
# Set the pin counting mode to gpio pin numbers
GPIO.setmode(GPIO.BCM)
# Set the pin mode to output
GPIO.setup(relay_pin, GPIO.OUT)

# --------------------------------------------------------
# LAMP CLASS
# --------------------------------------------------------

class Lamp():
    def __init__(self):
        self.isOn = False
        self.latestLog = {}

    def changeState(self):

        self.isOn = not self.isOn
        # Generate and save log if necessary
        log = logState(self.isOn, self.latestLog)
        # Change latest log AFTER save log expression
        self.latestLog = log

        if self.isOn == True:
            GPIO.output(relay_pin, GPIO.HIGH)
        if self.isOn == False:
            GPIO.output(relay_pin, GPIO.LOW)

        return { "state": self.isOn, "log": log }

    def readState(self):

        state = GPIO.input(relay_pin)
        if state == 1:
            stateBool = True
        else:
            stateBool = False
        return { "state": stateBool, "log": self.latestLog }

def sql_connection(file): 
    # Create SQLITE persistent connection
    try:
        conn = sqlite3.connect(file, check_same_thread=False)
        print("[*] SQLITE Connection established -- " + sqlite3.version)
        return conn
    except Error as e:
        print(e)
        return None

def logState(state, latestLog):
    #try:
    ts = datetime.datetime.now().timestamp()

    # with open("data.json", "r") as f:
    #     data = json.load(f)
    #log = {
    #    "timestamp": ts,
    #    "state": state
    #}
    # data["data"].append(log)
    # data["entries"] = len(data["data"])
    # with open("data.json", "w") as f:
    #     json.dump(data, f, indent=4)

    # SQL TABLE TIMES
    # start_time TEXT | end_time TEXT | delta REAL |

    try:
        if latestLog["log"]:
            start = datetime.datetime.fromtimestamp(latestLog["timestamp"])
            end = datetime.datetime.now()
            delta = end - start
            query='''
                INSERT INTO times (start_time, end_time, delta)
                VALUES ('{start}', '{end}', {delta})
            '''.format(start=str(start.isoformat()), end=str(end.isoformat()), delta=delta.total_seconds())
            conn.execute(query)
            conn.commit()
            print(f"[*] LOG SAVED TO TABLE TIMES: {start} - {end} ({delta})")
    except Exception as e:
        print("[X ERROR IN LOG:")
        print(e)

    print("[*] LOG " + str(ts) + " GENERATED: state " + str(state))
    return { "response": "ok", "log": state, "timestamp": ts }

    #except:
    #    print("[X] LOG " + str(ts) + " ERROR")
    #    return { "response": "error", "log": state, "timestamp": ts }

# --------------------------------------------------------
# CLASS AND FUNCTION INITIALISATION
# --------------------------------------------------------

lamp = Lamp()
if not lamp.readState()["state"]:
    lamp.changeState()
conn = sql_connection("data.db")

# --------------------------------------------------------
# ROUTES
# --------------------------------------------------------

# --------------------------------------------------------
# INTERFACE
# --------------------------------------------------------

# Change lamp state dynamically
@app.route('/')
def web_changeState():
    res = lamp.changeState()

    if res["state"]:
        return "Lamp has been turned ON"
    else:
        return "Lamp has been turned OFF"

# Read lamp state
@app.route('/state')
def web_readState():
    res = lamp.readState()

    if res["state"]:
        return "Lamp is currently ON"
    else:
        return "Lamp is currently OFF"

# --------------------------------------------------------
# API ROUTES
# --------------------------------------------------------

# Return database data
@app.route('/api/data')
def api_data():
    # REPLACE WITH SQL DATA
    with open("data.json", "r") as f:
        data = json.load(f)

    return data

# Return current state in log format
@app.route("/api/state")
def api_state():
    res = lamp.readState()

    return res
# Toggle state and return log format
@app.route("/api/toggle")
def api_toggle():
    res = lamp.changeState()

    return res

# Generate time graph
@app.route("/api/plt")
def api_plt():

    start_time = datetime.datetime.now()

    day = request.args.get("day")
    month = request.args.get("month")

    if (not day) or (not month):
        return {"status": 404, "message": "Invalid request"}

    try:
        day = int(day)
        month = int(month)
    except:
        return {"status": 404, "message": "Invalid request"}

    with open("data.json", "r") as file:
        data = json.load(file)

    startTimes = []
    endTimes = []
    y = []
    x = []

    for element in data["data"]:
        date = datetime.datetime.fromtimestamp(element["timestamp"])
        if date.day == day and date.month == month:
            if element["state"]:
                startTimes.append(date)
            else:
                endTimes.append(date)

    i = 0
    while i < len(startTimes):
        time1 = startTimes[i]
        if i < len(endTimes):
            time2 = endTimes[i]
        else:
            time2 = datetime.datetime.now()

        deltaTime = time2 - time1
        deltaSeconds = deltaTime.total_seconds()
        deltaMinutes = deltaSeconds / 60

        if deltaMinutes > 60:
            a = 0
            while deltaMinutes > 0:
                if not time1.hour + a > 24:
                    x.append(time1.hour + a)
                    if deltaMinutes < 60:
                        y.append(deltaMinutes)
                    else:
                        y.append(60)

                    deltaMinutes = deltaMinutes - 60
                    a += 1
                else:
                    deltaMinutes = 0
        else:
            x.append(time1.hour)
            y.append(deltaMinutes)
        i += 1

    if len(x) == 0 or len(y) == 0:
        print("[X] ERROR 400: Empty plot " + str(day) + "/" + str(month))
        return {"status": 400, "message": "Empty plot", "day": day, "month": month, "execution": (datetime.datetime.now() - start_time).total_seconds()}

    plt.xlim(0, 24)
    plt.ylim(0, 60)
    plt.xticks([0, 6, 12, 18, 24])
    plt.yticks([0, 15, 30, 45, 60])
    plt.ylabel("Duration")
    plt.xlabel("Time")
    plt.bar(x, height=y, width=1)

    plt.savefig("plt" + str(day) + str(month) + ".png")
    plt.close()

    print("[*] PLOT GENERATED" + str(day) + "/" + str(month))
    return {"status": "ok", "message": "Plot saved", "day": day, "month": month, "execution": (datetime.datetime.now() - start_time).total_seconds()}

# Return time graph
@app.route("/api/plt/img")
def api_plt_img():
    day = request.args.get("day")
    month = request.args.get("month")

    if (not day) or (not month):
        print("[X] Received invalid request")
        return {"status": 404, "message": "Invalid request"}

    try:
        day = int(day)
        month = int(month)
    except:
        print("[X] Received invalid request")
        return {"status": 404, "message": "Invalid request"}

    return send_file("plt" + str(day) + str(month) + ".png")

# --------------------------------------------------------
# ATEXIT
# --------------------------------------------------------

# Run function on exit
def exit_handler():
    logState(False, lamp.latestLog)
    GPIO.cleanup()
    print("[*] Successfully shut down")
    conn.close()
    print("[*] Closed SQL connection")
    print("[*] Cleanup successful")
    print("[*] Exiting...")
atexit.register(exit_handler)
