
import streamlit as st
import paho.mqtt.client as mqtt
import gspread
import threading
import time
from datetime import datetime
from collections import deque

# -----------------------------
# MQTT SETTINGS
# -----------------------------
BROKER = "172.29.44.168"
PORT = 1883
MQTT_USER = "me_iot038"
MQTT_PASSWORD = "LoudCouchFriend531#"
TOPIC = "me_iot038/lab8/temperature"

# -----------------------------
# GOOGLE SHEETS SETTINGS
# -----------------------------
SHEET_NAME = "ME4145 Lab 8 Temperature Data"

@st.cache_resource
def start_system():
    gc = gspread.service_account(
        filename="service_account.json"
    )

    sheet = gc.open(SHEET_NAME).sheet1

    if sheet.acell("A1").value != "Date":
        sheet.update(
            range_name="A1:C1",
            values=[["Date", "Time", "Temperature (F)"]]
        )

    data = {
        "latest": None,
        "samples": deque(maxlen=10),
        "connected": False,
        "lock": threading.Lock()
    }

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            client.subscribe(TOPIC)
            with data["lock"]:
                data["connected"] = True

    def on_message(client, userdata, msg):
        try:
            temperature = float(msg.payload.decode())
            with data["lock"]:
                data["latest"] = temperature
                data["samples"].append(temperature)
        except ValueError:
            pass

    client = mqtt.Client(
        client_id="lab8_google_sheets"
    )

    client.username_pw_set(
        MQTT_USER, MQTT_PASSWORD
    )

    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(BROKER, PORT, 60)
    client.loop_start()

    data["sheet"] = sheet
    data["client"] = client

    return data

st.title("Lab 8 Thermistor Monitor")

try:
    data = start_system()
except Exception as e:
    st.error(f"Connection error: {e}")
    st.stop()

interval = st.slider(
    "Google Sheets update interval (seconds)",
    min_value=15,
    max_value=300,
    value=60,
    step=5
)

if "last_log" not in st.session_state:
    st.session_state.last_log = time.monotonic()

@st.fragment(run_every="1s")
def monitor():
    now = datetime.now()

    st.write(
        "Date and Time:",
        now.strftime("%Y-%m-%d %H:%M:%S")
    )

    with data["lock"]:
        latest = data["latest"]
        samples = list(data["samples"])
        connected = data["connected"]

    if latest is not None:
        st.metric(
            "Current Temperature",
            f"{latest:.3f} °F"
        )

    if connected:
        st.success("Connected to MQTT")
    else:
        st.warning("Connecting to MQTT...")

    elapsed = time.monotonic() - st.session_state.last_log

    if elapsed >= interval and len(samples) == 10:
        average = round(sum(samples) / 10, 3)

        try:
            data["sheet"].append_row([
                now.strftime("%Y-%m-%d"),
                now.strftime("%H:%M:%S"),
                average
            ])

            st.session_state.last_log = time.monotonic()

            st.success(
                f"Uploaded {average:.3f} °F to Google Sheets"
            )

        except Exception as e:
            st.error(f"Upload failed: {e}")

monitor()
