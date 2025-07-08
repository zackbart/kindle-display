import io
import requests
import datetime
from flask import Flask, send_file
from PIL import Image, ImageDraw, ImageFont
from google.transit import gtfs_realtime_pb2

app = Flask(__name__)

# Constants
FEED_URL = "http://gtfsrt.prod.mta.info/feed/nyct%2Fgtfs"  # Public feed, update if needed
STATION_ID = "A46"  # Utica Av (A/C)
LINES = {"A", "C"}
DIRECTIONS = {"N": "Manhattan-bound", "S": "Brooklyn-bound"}
IMG_SIZE = (800, 600)
FONT_PATH = None  # Use default PIL font


def fetch_departures():
    resp = requests.get(FEED_URL)
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(resp.content)
    now = datetime.datetime.now()
    departures = {"N": [], "S": []}
    for entity in feed.entity:
        if not entity.HasField("trip_update"):
            continue
        trip = entity.trip_update.trip
        route_id = trip.route_id
        if route_id not in LINES:
            continue
        for stop_time_update in entity.trip_update.stop_time_update:
            stop_id = stop_time_update.stop_id
            # Stop IDs are like 'A46N' or 'A46S'
            if not stop_id.startswith(STATION_ID):
                continue
            direction = stop_id[-1]
            if direction not in DIRECTIONS:
                continue
            dep_time = stop_time_update.departure.time if stop_time_update.HasField("departure") else stop_time_update.arrival.time
            dep_dt = datetime.datetime.fromtimestamp(dep_time)
            if dep_dt < now:
                continue
            departures[direction].append((dep_dt, route_id))
    # Sort and keep next 3 for each direction
    for dir in departures:
        departures[dir] = sorted(departures[dir])[:3]
    return departures


def make_image(departures):
    img = Image.new("L", IMG_SIZE, color=255)
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default() if FONT_PATH is None else ImageFont.truetype(FONT_PATH, 28)
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    y = 10
    draw.text((10, y), f"Utica Av (A/C)", font=font, fill=0)
    y += 30
    draw.text((10, y), f"Current Time: {now}", font=font, fill=0)
    y += 40
    for dir, label in DIRECTIONS.items():
        draw.text((10, y), f"{label} ({dir}):", font=font, fill=0)
        y += 25
        if departures[dir]:
            for dep_dt, route_id in departures[dir]:
                time_str = dep_dt.strftime("%H:%M")
                draw.text((30, y), f"{route_id} train: {time_str}", font=font, fill=0)
                y += 22
        else:
            draw.text((30, y), "No upcoming trains", font=font, fill=0)
            y += 22
        y += 10
    return img


@app.route("/kindle.png")
def kindle_image():
    try:
        departures = fetch_departures()
    except Exception as e:
        # On error, show message
        img = Image.new("L", IMG_SIZE, color=255)
        draw = ImageDraw.Draw(img)
        font = ImageFont.load_default()
        draw.text((10, 10), f"Error fetching data: {e}", font=font, fill=0)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return send_file(buf, mimetype="image/png")
    img = make_image(departures)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000) 