import io
import requests
import datetime
from flask import Flask, send_file
from PIL import Image, ImageDraw, ImageFont
from google.transit import gtfs_realtime_pb2
import pytz

app = Flask(__name__)

# Paperwhite 3 portrait (vertical) orientation
IMG_SIZE = (758, 1024)  # width x height
FEED_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace"
STATION_ID = "A46"  # Utica Av (A/C)
LINES = {"A", "C"}
DIRECTIONS = {"N": "Manhattan-bound", "S": "Brooklyn-bound"}
FONT_PATH = None  # Use default PIL font
NY_TZ = pytz.timezone("America/New_York")


def fetch_departures():
    resp = requests.get(FEED_URL)
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(resp.content)
    now = datetime.datetime.now(NY_TZ)
    min_delta = datetime.timedelta(minutes=5)
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
            if not stop_id.startswith(STATION_ID):
                continue
            direction = stop_id[-1]
            if direction not in DIRECTIONS:
                continue
            dep_time = stop_time_update.departure.time if stop_time_update.HasField("departure") else stop_time_update.arrival.time
            dep_dt = datetime.datetime.fromtimestamp(dep_time, NY_TZ)
            # Only include trains 5 minutes or more away
            if dep_dt - now < min_delta:
                continue
            departures[direction].append((dep_dt, route_id))
    for dir in departures:
        departures[dir] = sorted(departures[dir])[:4]
    return departures


def draw_train_logo(draw, x, y, letter, size=56):
    # Draw a black circle with a white letter inside
    draw.ellipse((x, y, x + size, y + size), fill=0)
    font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), letter, font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    text_x = x + (size - w) // 2
    text_y = y + (size - h) // 2
    draw.text((text_x, text_y), letter, font=font, fill=255)


def make_image(departures):
    img = Image.new("L", IMG_SIZE, color=255)
    draw = ImageDraw.Draw(img)
    font_path = "DejaVuSans-Bold.ttf"
    font_title = ImageFont.truetype(font_path, 90)
    font_time = ImageFont.truetype(font_path, 60)
    font_dep = ImageFont.truetype(font_path, 80)
    font_logo = ImageFont.truetype(font_path, 120)

    # Centered title
    title = "Utica Av (A/C)"
    bbox = draw.textbbox((0, 0), title, font=font_title)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((IMG_SIZE[0] - w) // 2, 30), title, font=font_title, fill=0)

    # Centered current time (directly below title)
    now_dt = datetime.datetime.now(NY_TZ)
    now_str = now_dt.strftime("%I:%M %p")
    bbox = draw.textbbox((0, 0), now_str, font=font_time)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((IMG_SIZE[0] - w) // 2, 130), now_str, font=font_time, fill=0)

    # Only show Manhattan-bound departures, no header
    y = 230
    logo_size = 150
    row_height = 160
    for i in range(4):
        if i < len(departures["N"]):
            dep_dt, route_id = departures["N"][i]
            time_str = dep_dt.strftime("%I:%M %p")
            # Draw large train logo (centered vertically in row)
            logo_x = (IMG_SIZE[0] - (logo_size + 60 + 400)) // 2
            logo_y = y
            # Draw black circle
            draw.ellipse((logo_x, logo_y, logo_x + logo_size, logo_y + logo_size), fill=0)
            # Draw white train letter centered using anchor
            center_x = logo_x + logo_size // 2
            center_y = logo_y + logo_size // 2
            draw.text((center_x, center_y), route_id, font=font_logo, fill=255, anchor="mm")
            # Draw time, large, to the right of the logo, vertically centered
            bbox_time = draw.textbbox((0, 0), time_str, font=font_dep)
            time_h = bbox_time[3] - bbox_time[1]
            time_y = logo_y + (logo_size - time_h) // 2
            draw.text((logo_x + logo_size + 60, time_y), time_str, font=font_dep, fill=0)
        else:
            # Draw a dash centered
            dash = "-"
            bbox = draw.textbbox((0, 0), dash, font=font_dep)
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            draw.text(((IMG_SIZE[0] - w) // 2, y + (logo_size - h) // 2), dash, font=font_dep, fill=128)
        y += row_height
    return img


@app.route("/kindle.png")
def kindle_image():
    try:
        departures = fetch_departures()
    except Exception as e:
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


@app.route("/")
def kindle_html():
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
      <meta http-equiv="refresh" content="30">
      <style>
        body { background: #fff; margin: 0; padding: 0; }
        img { display: block; margin: 0 auto; max-width: 100vw; max-height: 100vh; }
      </style>
    </head>
    <body>
      <img src="/kindle.png" alt="Train Times" />
    </body>
    </html>
    '''
    return html


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000) 