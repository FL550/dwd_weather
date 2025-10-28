import os
from turtle import st
from simple_dwd_weatherforecast import dwdforecast
from datetime import datetime, timezone
from pprint import pprint

station = os.environ["STATION"]
mode = os.environ["MODE"]

dwd_weather = dwdforecast.Weather(station)
time_now = datetime.now(timezone.utc)
dwd_weather.update(
    force_hourly=True if mode == "hourly" else False,
)


print(f"## Station: {station}")
print(f"{dwd_weather.station}")
print("")
print(
    f"## Forecast from {dwd_weather.issue_time.isoformat(timespec='seconds')} (updated at {time_now.isoformat(timespec='seconds')})"
)
# pretty-print forecast_data (fall back to pprint if not JSON-serializable)


forecast_data = dwd_weather.forecast_data
if isinstance(forecast_data, dict):
    # Collect all unique keys from all time entries
    all_keys = set()
    for entry in forecast_data.values():
        all_keys.update(entry.keys())
    all_keys = sorted(all_keys)
    # Print GitHub Markdown table header
    header = ["timestamp"] + all_keys
    print("| " + " | ".join(header) + " |")
    print("|" + " --- |" * len(header))
    # Print each row
    for timestamp, values in forecast_data.items():
        row = [timestamp] + [str(values.get(k, "")) for k in all_keys]
        print("| " + " | ".join(row) + " |")
else:
    pprint(forecast_data, width=120)
