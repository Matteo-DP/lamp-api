from flask import Flask
from flask_cors import CORS
import RPi.GPIO as GPIO

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

# Run function on exit
def exit_handler():
    logState(False)
    GPIO.cleanup()
    print("Successfully shut down")
atexit.register(exit_handler)
