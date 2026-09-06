"""Calcul des durées ferroviaires. Nom de fonction legacy conservé pour compatibilité."""
import logging
import re
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COUNTRY_GROUPS = {
    "AT":"A","BE":"A","CH":"A","DE":"A","ES":"A","FR":"A","IT":"A","NL":"A",
    "CZ":"B","DK":"B","FI":"B","PL":"B","SE":"B",
    "HR":"C","HU":"C","PT":"C","RO":"C","SI":"C","SK":"C",
    "BG":"D","EE":"D","GR":"D","IE":"D","LT":"D","LV":"D",
    "CY":"E","LU":"E","MT":"E",
}


def extract_duration_from_text(text):
    if pd.isna(text):
        return None
    times = re.findall(r"(\d{1,3}:\d{2})", str(text))
    if len(times) < 2:
        return None
    def to_minutes(value):
        h, m = map(int, value.split(":"))
        if m > 59 or h > 72:
            raise ValueError
        return h * 60 + m
    try:
        start, end = to_minutes(times[0]), to_minutes(times[-1])
        while end <= start:
            end += 1440
        return end - start
    except ValueError:
        return None


def estimate_duration_from_distance(distance_km, speed_kmh=70):
    """Compatibilite legacy : estime une duree simple en minutes."""
    distance = pd.to_numeric(distance_km, errors="coerce")
    speed = pd.to_numeric(speed_kmh, errors="coerce")
    if pd.isna(distance) or pd.isna(speed) or distance <= 0 or speed <= 0:
        return 0
    return round(float(distance) / float(speed) * 60)


def commercial_speed(row):
    country = str(row.get("country_code", "")).upper()
    group = COUNTRY_GROUPS.get(country, "C")
    text = " ".join(str(row.get(c, "")) for c in ["train", "route_long_name", "itinerary"]).lower()
    if any(t in text for t in ["tgv", "ice", "frecciarossa", "ave", "high speed"]):
        return 220
    if bool(row.get("is_night", False)):
        return {"A":95,"B":85,"C":75,"D":65,"E":55}.get(group, 75)
    if any(t in text for t in ["intercity", "eurocity", " ic ", " ec "]):
        return {"A":125,"B":115,"C":100,"D":85,"E":70}.get(group, 100)
    return {"A":100,"B":90,"C":75,"D":60,"E":45}.get(group, 75)


def minimum_duration(row):
    if bool(row.get("is_night", False)):
        return 90.0
    return 20.0 if COUNTRY_GROUPS.get(str(row.get("country_code", "")).upper()) == "E" else 30.0


def compute_night_train_durations(trains_df):
    if trains_df.empty:
        return trains_df
    out = trains_df.copy()
    durations = []
    for _, row in out.iterrows():
        existing = pd.to_numeric(row.get("duration_min"), errors="coerce")
        if pd.notna(existing) and existing > 0:
            durations.append(float(existing)); continue
        duration = extract_duration_from_text(row.get("itinerary_long", ""))
        if duration is None:
            distance = pd.to_numeric(row.get("distance_km"), errors="coerce")
            if pd.notna(distance) and distance > 0:
                duration = float(distance) / commercial_speed(row) * 60
        if duration is None or duration <= 0:
            duration = minimum_duration(row)
        durations.append(float(max(duration, minimum_duration(row))))
    out["duration_min"] = durations
    return out
