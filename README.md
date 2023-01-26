## Lamp control API
Python flask API which controls a relay on a RPI B+ <br />
flask run --host:0.0.0.0

### Routes:

| Route | Info | Query params
--- | --- | ---
/ | Toggles lights, returns state | /
/state | Returns the current state | /
/api/data | Returns all DB data | /
/api/state | Returns the current state in log format | /
/api/toggle | Toggles lights, returns state in log format | /
/api/plt | Generates time plot. Deprecated | Month and day
/api/plt/img | Returns the specified plot as a png. Deprecated | Month and day
/api/graphdata | Returns time dataset, Rechart readable format | Month and day
/api/monthly | Returns total usage per day, Rechart readable format | Month