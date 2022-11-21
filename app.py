from flask import Flask
from flask import request
from flask import send_file
from flask_cors import CORS

import RPi.GPIO as GPIO

import matplotlib.pyplot as plt
import datetime
import atexit
import json

app = Flask(__name__)
CORS(app)

# define the relay pin
relay_pin = 24
# Set the pin counting mode to gpio pin numbers
GPIO.setmode(GPIO.BCM)
# Set the pin mode to output
GPIO.setup(relay_pin, GPIO.OUT)


def logState(state):
    try:
        ts = datetime.datetime.now().timestamp()

        with open("data.json", "r") as f:
            data = json.load(f)

        log = {
            "timestamp": ts,
            "state": state
        }
        data["data"].append(log)
        data["entries"] = len(data["data"])

        with open("data.json", "w") as f:
            json.dump(data, f, indent=4)

        print("Log " + str(ts) + " successful")
        return { "response": "ok", "log": state, "timestamp": ts }

    except:
        print("An error has occured while logging lamp state " + str(ts))
        return { "response": "error", "log": state, "timestamp": ts }

class Lamp():
    def __init__(self):
        self.isOn = False
        self.latestLog = {}

    def changeState(self):

        self.isOn = not self.isOn
        log = logState(self.isOn)
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

# Initialisation
lamp = Lamp()
lamp.changeState()

# Flask web routes
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

@app.route('/api/data')
def api_data():
    with open("data.json", "r") as f:
        data = json.load(f)

    return data

@app.route("/api/state")
def api_state():
    res = lamp.readState()

    return res

@app.route("/api/toggle")
def api_toggle():
    res = lamp.changeState()

    return res

# https://towardsdatascience.com/timestamp-parsing-with-python-ec185536bcfc
# https://stackoverflow.com/questions/64637479/create-a-boolean-column-based-on-a-timestamp-index
# https://www.geeksforgeeks.org/time-series-plot-or-line-plot-with-pandas/
# https://pandas.pydata.org/docs/dev/getting_started/intro_tutorials/09_timeseries.html !!!!!!

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
        print("400: Empty plot " + str(day) + "/" + str(month))
        return {"status": 400, "message": "Empty plot", "day": day, "month": month, "execution": (datetime.datetime.now() - start_time).total_seconds()}

    plt.xlim(0, 24)
    plt.ylim(0, 60)
    plt.xticks([0, 6, 12, 18, 24])
    plt.yticks([0, 15, 30, 45, 60])
    plt.ylabel("Duration")
    plt.xlabel("Time")
    plt.bar(x, height=y, width=1)

    plt.savefig("plt.png")
    plt.close()

    print("ok: Generated plot " + str(day) + "/" + str(month))
    return {"status": "ok", "message": "Plot saved", "day": day, "month": month, "execution": (datetime.datetime.now() - start_time).total_seconds()}

@app.route("/api/plt/img")
def api_plt_img():
    return send_file("plt.png")

# Run function on exit
def exit_handler():
    logState(False)
    GPIO.cleanup()
    print("Successfully shut down")
atexit.register(exit_handler)
