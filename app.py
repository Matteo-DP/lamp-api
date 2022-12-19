print("[*] Starting...")

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
        self.isOn = True
        self.latestLog = {"log": True, "timestamp": datetime.datetime.now().timestamp()}

        GPIO.output(relay_pin, GPIO.HIGH)

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
    ts = datetime.datetime.now().timestamp()

    try: # TODO: check if error handling is unnecessary since the startup log error fix
        if latestLog["log"]:
            start = datetime.datetime.fromtimestamp(latestLog["timestamp"])
            end = datetime.datetime.now()
            delta = end - start
            # SQL TABLE TIMES
            # start_time BLOB | end_time BLOB | delta REAL | 
            # TODO: change BLOB to TEXT format
            # Note: !! SQL query values in quotation marks for str
            query='''
                INSERT INTO times (start_time, end_time, delta)
                VALUES ('{start}', '{end}', {delta})
            '''.format(start=str(start.isoformat()), end=str(end.isoformat()), delta=delta.total_seconds())
            conn.execute(query)
            conn.commit()
            print(f"[*] LOG SAVED TO TABLE TIMES: {start} - {end} ({delta})")
    except Exception as e:
        print("[X] ERROR IN LOG:")
        print(e)

    print("[*] LOG " + str(ts) + " GENERATED: state " + str(state))
    return { "response": "ok", "log": state, "timestamp": ts }



# --------------------------------------------------------
# CLASS AND FUNCTION INITIALISATION
# --------------------------------------------------------

lamp = Lamp()
conn = sql_connection("data.db")



# --------------------------------------------------------
# GRAPH GENERATION ALGORITHM
# --------------------------------------------------------

# Deprecated, inefficient algorithm I created :(
def generateAxis(sql_results):
    x = []
    y = []
     # Map each row's delta time to their according hour
    # Check if the hour is already in the x list
    # If it is --> Add delta to the corresponding value in the y list if the sum of the delta and the y value < 60
    # Check if remaining delta is > 60
    # Loop over appending 60 until delta < 60
    # Append remaining delta
    for row in sql_results:
        date = datetime.datetime.fromisoformat(row[0])
        hour = date.hour + 1
        delta = row[2] / 60 # Convert seconds to minutes

        if hour in x:
            # Check if sum of delta in list and current delta > 60
            index = x.index(hour)
            yvalue = y[index] # Current y value
            if yvalue + delta > 60: # Check if sum of current y value and delta > 60
                y[index] += 60 - yvalue # Add the delta - current y value - 60
                delta = delta - 60 + yvalue # Update remaining delta
                # Is the remaining delta > 60? If so --> has to be last item in list
            else:
                y[index] += delta # Add the delta
                delta = 0 # Set it to 0 so it doesnt get added again
        i = 0
        while delta > 60: # Distribute minutes with max 60
            x.append(hour + i) # Add hour to x values
            y.append(60) # Add 60 to y values
            i += 1 # Increase loop #
            delta -= 60 # Update delta

        # Append remaining delta if it exists
        if delta > 0:
            x.append(hour + i)
            y.append(delta)

    return x, y


# ChatGPT generated algorithm
# TODO: KNOWN ISSUES:
# - Minutes may exceed 60
# - Time too short?
def generateAxisBeta(sql_results): # Expected datatype is a tuple containing deltas and on off times
    x = []
    y = []

    # Initialize dictionary with 24 keys, representing the hours of the day
    hours = {i: 0 for i in range(24)}

    # Iterate over the rows in the sql_results and extract the date and delta time
    for row in sql_results:
        date = datetime.datetime.fromisoformat(row[0])
        hour = date.hour
        delta = row[2] / 60  # Convert seconds to minutes

        # Calculate the number of full hours and remaining minutes
        full_hours, remaining_minutes = divmod(delta, 60) # No clue what this does but it works for some reason

        # Add the full hours to the dictionary key for the current hour
        hours[hour] += full_hours

        # If there are remaining minutes, add them to the dictionary key for the next hour
        if remaining_minutes > 0:
            hours[(hour + 1) % 24] += remaining_minutes

    # Extract the x and y values from the dictionary
    x = list(hours.keys())
    y = list(hours.values())

    return x, y


# Generate monthly average usage time
def generateAverageUsage(sql_results): # Expected datatype is a list of tuples containing deltas anbd on off times for the corresponding month
    # Filter tuple per day
    dates_dict = {}
    for row in sql_results:
        date = datetime.datetime.fromisoformat(row[0])
        day = date.day
        if not str(day) in dates_dict.keys():
            dates_dict[str(day)] = [row]
        else:
            dates_dict[str(day)].append(row)

    # Generate graphing data for each day in the dates_dict and sum the total hours in total_hours_dict
    total_hours_dict = {i: 0 for i in range(32)} # Initialise dict with 31 days
    for day in dates_dict:
        x, y = generateAxis(dates_dict[day])
        total_hours = sum(y) / 60 # Convert minutes to hours
        total_hours_dict[int(day)] = total_hours

    return total_hours_dict


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


# Return graph data which contains usage time per day for the month and the average usage time
# TODO: KNOWN ISSUES:
# - Check whether month is 30 or 31 days long for more accurate graphing. Current algorithm assumes 31 days
@app.route("/api/monthly")
def api_monthly():
    start_time = datetime.datetime.now()

    month = request.args.get("month")
    if (not month):
        return {"status": 404, "message": "Invalid request"}
    try:
        month = int(month)
    except:
        return {"status": 404, "message": "Invalid request"}

    # Select all rows where the month corresponds to the inputted month: wrap month in -month- to make sure it doesnt interpret the month number as a day
    dateQuery = f'{month}'
    query = '''
        SELECT * FROM times
        WHERE start_time LIKE '%-{date}-%'
        '''.format(date=dateQuery)
    results = conn.execute(query)
    results = results.fetchall()

    total_hours_dict = generateAverageUsage(results)

    execution_time = (datetime.datetime.now() - start_time).total_seconds() # Calculate execution time
    total_hours = 0 # Calculate total hours
    entries = 0 # Calculate number of non-zero entries
    for day in total_hours_dict:
        total_hours += total_hours_dict[day]
        if total_hours_dict[day] > 0: # If it is a non zero value, increase the entry number by 1
            entries += 1

    if entries > 0: # Prevent division by 0 error on empty dict
        average_hours = total_hours / entries
    else:
        average_hours = 0

    # Convert total_hours_dict lists to a recharts graphable dataset
    # TODO: this is unnecessarily complicated. Fix the generateAverageUsage() function to generate the correct data format instead
    data = []
    for day in total_hours_dict:
        data.append({"day": day, "hours": total_hours_dict[day]})

    response = {
        "execution": execution_time,
        "entries": entries,
        "total_hours": total_hours,
        "average_hours": average_hours,
        "data": data
    }

    return response


# Return graph data in a format that Recharts in frontend can read
@app.route("/api/graphdata")
def api_graphdata():
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

    # Select all rows where start time contains M-D in any position
    dateQuery = f'{month}-{day}'
    query = '''
        SELECT * FROM times
        WHERE start_time LIKE '%{date}%'
        '''.format(date=dateQuery)
    results = conn.execute(query)
    results = results.fetchall()
    
    x, y = generateAxis(results)

    # Convert x and y lists to dict
    # TODO: this is useless since it is converted from dict to x and y lists in the generateAxis function
    i = 0
    data = []
    while i < 24:
        
        data.append({ "hour": i + 1 })
        if i + 1 in x:
            index = x.index(i + 1)
            data[i]["minutes"] = y[index]
        else:
            data[i]["minutes"] = 0
        i += 1

    execution_time = (datetime.datetime.now() - start_time).total_seconds()
    
    response = {
        "execution": execution_time,
        "data": data,
        "entries": len(y) + 1,
        "total_minutes": sum(y)
    }

    return response


# Return all database data
@app.route('/api/data')
def api_data():

    query = '''
        SELECT * FROM times
    '''
    data = conn.execute(query)
    data = data.fetchall()

    string = ""
    for row in data:
        string = string + str(row) + "\n"
    
    return string


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

    # Select all rows where start time contains M-D in any position
    dateQuery = f'{month}-{day}'
    query = '''
        SELECT * FROM times
        WHERE start_time LIKE '%{date}%'
        '''.format(date=dateQuery)
    results = conn.execute(query)
    results = results.fetchall()
    
    x, y = generateAxis(results)

    plt.xlim(0, 24)
    plt.ylim(0, 60)
    plt.xticks([0, 6, 12, 18, 24])
    plt.yticks([0, 15, 30, 45, 60])
    plt.ylabel("Duration")
    plt.xlabel("Time")
    plt.bar(x, height=y, width=1)

    plt.savefig("plt" + str(day) + str(month) + ".png")
    plt.close()

    execution_time = (datetime.datetime.now() - start_time).total_seconds()
    print(f"[*] PLOT {str(day)}/{str(month)} GENERATED IN {execution_time}s")
    return {"status": "ok", "message": "Plot saved", "day": day, "month": month, "execution": execution_time}


# Return time graph
@app.route("/api/plt/img")
def api_plt_img():
    day = request.args.get("day")
    month = request.args.get("month")

    if (not day) or (not month):
        print("[X] Received invalid request: missing query strings")
        return {"status": 404, "message": "Invalid request"}

    try:
        day = int(day)
        month = int(month)
    except:
        print("[X] Received invalid request: TypeError for query strings")
        return {"status": 404, "message": "Invalid request"}

    return send_file("plt" + str(day) + str(month) + ".png")



# --------------------------------------------------------
# ATEXIT
# --------------------------------------------------------


# Run function on exit
def exit_handler():
    logState(False, lamp.latestLog)
    GPIO.cleanup()
    print("[*] Cleaned up GPIO")
    conn.close()
    print("[*] Closed SQL connection")
    print("[*] Exiting...")
atexit.register(exit_handler)