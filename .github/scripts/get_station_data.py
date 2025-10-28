import os
from simple_dwd_weatherforecast import dwdforecast
from datetime import datetime, timezone
from pprint import pprint

station = os.environ["STATION"]
mode = os.environ.get("MODE", "daily")  # default to 'daily' when unset

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
    # Use fixed mapping for table columns
    key_mapping = [
        ("condition", "condition"),
        ("TTT", "dry_bulb_temp"),
        ("Td", "dew_point"),
        ("PPPP", "pressure"),
        ("FF", "wind"),
        ("DD", "wind_dir"),
        ("FX1", "wind_gusts"),
        ("RR1c", "precip"),
        ("wwP", "precip_prob"),
        ("DRR1", "precip_dur"),
        ("N", "cloud_cover"),
        ("VV", "visibility"),
        ("SunD1", "sunshine_dur"),
        ("Rad1h", "radiation"),
        ("wwM", "fog_prop"),
        ("humidity", "rel_humidity"),
        ("PEvap", "evaporation"),
    ]

    # Build a mapping from original key to display name
    key_map = {orig: disp for orig, disp in key_mapping}

    all_keys = set()
    for entry in forecast_data.values():
        all_keys.update(entry.keys())
    # Order keys according to key_mapping; unmapped keys come after, sorted alphabetically
    order = {orig: idx for idx, (orig, _) in enumerate(key_mapping)}
    all_keys = list(all_keys)
    all_keys.sort(key=lambda k: (order.get(k, len(order)), k))

    # Replace header entries using key_map if present
    header = ["timestamp"] + [key_map.get(k, k) for k in all_keys]
    print("| " + " | ".join(header) + " |")
    print("|" + " --- |" * len(header))
    # Sort forecast_data by timestamp for consistent output
    for timestamp in sorted(forecast_data.keys()):
        values = forecast_data[timestamp]
        row = [timestamp]
        for k in all_keys:
            if k == "condition":
                code = str(values.get("condition", ""))
                cond = ""
                if code and hasattr(dwd_weather, "weather_codes"):
                    cond = dwd_weather.weather_codes.get(code, ("", ""))[0]
                row.append(cond)
            else:
                row.append(str(values.get(k, "")))
        print("| " + " | ".join(row) + " |")
else:
    pprint(forecast_data, width=120)
