import io
import requests
import datetime
from flask import Flask, send_file
from PIL import Image, ImageDraw, ImageFont
from google.transit import gtfs_realtime_pb2
import pytz

app = Flask(__name__)

# Updated feed URL for A/C/E lines, no API key required
FEED_URL = "https://api-endpoint.mta.info/Dataservice/mtagtfsfeeds/nyct%2Fgtfs-ace"
STATION_ID = "A46"  # Utica Av (A/C)
LINES = {"A", "C"}
DIRECTIONS = {"N": "Manhattan-bound", "S": "Brooklyn-bound"}
# Update image size for Paperwhite 3 landscape
IMG_SIZE = (1072, 758)  # width x height for Paperwhite 3 landscape
FONT_PATH = None  # Use default PIL font
NY_TZ = pytz.timezone("America/New_York")


def fetch_departures():
    resp = requests.get(FEED_URL)
    feed = gtfs_realtime_pb2.FeedMessage()
    feed.ParseFromString(resp.content)
    now = datetime.datetime.now(NY_TZ)
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
            dep_dt = datetime.datetime.fromtimestamp(dep_time, NY_TZ)
            if dep_dt < now:
                continue
            departures[direction].append((dep_dt, route_id))
    # Sort and keep next 4 for each direction
    for dir in departures:
        departures[dir] = sorted(departures[dir])[:4]
    return departures


def draw_train_logo(draw, x, y, letter, size=64):
    # Draw a black circle with a white letter inside
    radius = size // 2
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
    # Use larger font for title and time
    font_title = ImageFont.load_default()
    font_time = ImageFont.load_default()
    font_header = ImageFont.load_default()
    font_dep = ImageFont.load_default()

    # Centered title
    title = "Utica Av (A/C)"
    bbox = draw.textbbox((0, 0), title, font=font_title)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((IMG_SIZE[0] - w) // 2, 40), title, font=font_title, fill=0)

    # Centered current time
    now_str = datetime.datetime.now(NY_TZ).strftime("%Y-%m-%d %I:%M %p")
    bbox = draw.textbbox((0, 0), now_str, font=font_time)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((IMG_SIZE[0] - w) // 2, 120), now_str, font=font_time, fill=0)

    # Column headers
    col_margin = 100
    col_width = (IMG_SIZE[0] - 2 * col_margin) // 2
    col1_x = col_margin
    col2_x = col_margin + col_width
    y_start = 220
    y = y_start
    draw.text((col1_x, y), "Manhattan-bound", font=font_header, fill=0)
    draw.text((col2_x, y), "Brooklyn-bound", font=font_header, fill=0)
    y += 60

    max_rows = max(len(departures["N"]), len(departures["S"]))
    max_rows = max(max_rows, 4)
    row_height = 100
    logo_size = 64
    for i in range(max_rows):
        # Manhattan-bound (N)
        if i < len(departures["N"]):
            dep_dt, route_id = departures["N"][i]
            time_str = dep_dt.strftime("%I:%M %p")
            draw_train_logo(draw, col1_x, y, route_id, size=logo_size)
            draw.text((col1_x + logo_size + 30, y + 18), time_str, font=font_dep, fill=0)
        else:
            draw.text((col1_x, y + 18), "-", font=font_dep, fill=128)
        # Brooklyn-bound (S)
        if i < len(departures["S"]):
            dep_dt, route_id = departures["S"][i]
            time_str = dep_dt.strftime("%I:%M %p")
            draw_train_logo(draw, col2_x, y, route_id, size=logo_size)
            draw.text((col2_x + logo_size + 30, y + 18), time_str, font=font_dep, fill=0)
        else:
            draw.text((col2_x, y + 18), "-", font=font_dep, fill=128)
        y += row_height
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