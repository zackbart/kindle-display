#!/bin/sh

IMG_URL="http://10.1.1.12:5000/kindle.png"
SCREENSAVER_PATH="/mnt/us/linkss/screensaver/00-trains.png"

# Wait until 10 seconds after the minute
now_sec=$(date +%S)
if [ "$now_sec" -le 10 ]; then
    sleep $((10 - now_sec))
else
    sleep $((70 - now_sec))
fi

wget -O "$SCREENSAVER_PATH" "$IMG_URL"
/usr/bin/eips -c
/usr/bin/eips -g "$SCREENSAVER_PATH" 