## Lamp control API

flask run --host:0.0.0.0

### Routes:

| Route | Info |
--- | ---
/ | Toggles lights, returns state
/state | Returns the current state
/api/data | Returns all DB data
/api/state | Returns the current state in log format
/api/toggle | Toggles lights, returns state in log format
/api/plt | Generates time plot with month & day query params, returns status in log format
/api/plt/img | Returns the specified plot with month & day query params