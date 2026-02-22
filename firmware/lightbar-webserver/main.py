import network
import socket
import time
from machine import Pin
from neopixel import NeoPixel
import credentials

# ========= WIFI SETTINGS =========
ssid = credentials.wifi_ssid
password = credentials.wifi_pwd

# ========= NEOPIXEL =========
NUM_LEDS = 59
np_pin = Pin(2, Pin.OUT)
np = NeoPixel(np_pin, NUM_LEDS)

# ========= STATE =========
mode = "off"          # off / on
speed = 10            # ms
cycle_limit = 0       # 0 = unlimited

index = 0
direction = 1
cycle_count = 0

last_update = time.ticks_ms()
last_net = time.ticks_ms()

NET_INTERVAL = 20     # Check network only every 20 ms to avoid blocking animation

# ========= HELPER: BLINK LED =========
def blink_led(delay=0.5):
    np[0] = (255, 165, 0)  # orange
    np.write()
    time.sleep(delay)
    np[0] = (0, 0, 0)
    np.write()
    time.sleep(delay)

# ========= CONNECT WIFI WITH BLINK =========
wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)

print("Connecting...")
while not wlan.isconnected():
    blink_led()  # blink orange until connected

ip = wlan.ifconfig()[0]
print("Connected! IP:", ip)

# ========= START SERVER =========
addr = socket.getaddrinfo("0.0.0.0", 80)[0][-1]
server = socket.socket()
server.bind(addr)
server.listen(5)
server.settimeout(0)   # NOT blocking

print("Web server running...")

# ========= READY STATUS LIGHT =========
np[0] = (0, 255, 0)  # green
np[-1] = (0, 255, 0)
np.write()

# ========= WEB PAGE =========
def web_page():
    return f"""<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>EMDR Lightbar</title>
</head>
<body style="font-family:Arial;text-align:center;">
<h2>EMDR Lightbar</h2>

<p><b>Mode:</b> {mode.upper()}</p>
<p><b>Speed:</b> {speed} ms</p>
<p><b>Cycle limit:</b> {cycle_limit if cycle_limit>0 else "Unlimited"}</p>

<p>
<a href="/?mode=on"><button>START</button></a>
<a href="/?mode=off"><button>STOP</button></a>
</p>

<form>
<input type="hidden" name="mode" value="on">
<p>Speed (ms): <input type="number" name="speed" value="{speed}"></p>
<p>Cycles (0 = unlimited): <input type="number" name="limit" value="{cycle_limit}"></p>
<input type="submit" value="Set & Start">
</form>
</body>
</html>
"""

# ========= MAIN LOOP =========
while True:
    
    now = time.ticks_ms()

    # =========================
    # Animation
    # =========================
    if mode == "on":
        if time.ticks_diff(now, last_update) >= speed:
            last_update = now

            np.fill((0, 0, 0))
            np[index] = (255, 255, 255)
            np.write()

            index += direction

            if index >= NUM_LEDS - 1:
                index = NUM_LEDS - 1
                direction = -1

            elif index <= 0:
                index = 0
                direction = 1
                cycle_count += 1

                if cycle_limit > 0 and cycle_count >= cycle_limit:
                    mode = "off"
                    np.fill((0, 0, 0))
                    # ========= READY STATUS LIGHT =========
                    np[0] = (0, 255, 0)  # green
                    np[-1] = (0, 255, 0)
                    np.write()
                    cycle_count = 0

    # =========================
    # Check Network periodically to avoid blocking animation
    # =========================
    if time.ticks_diff(now, last_net) >= NET_INTERVAL:
        last_net = now

        try:
            conn, addr = server.accept()
        except OSError:
            conn = None

        if conn:
            try:
                conn.settimeout(0.1)
                request = conn.recv(1024).decode()
            except:
                conn.close()
                continue

            request_line = request.split("\r\n")[0]

            if "GET /" in request_line:
                try:
                    path = request_line.split(" ")[1]
                except:
                    path = "/"

                if "?" in path:
                    query = path.split("?")[1]
                    params = query.split("&")

                    for p in params:

                        if p.startswith("mode="):
                            value = p.split("=")[1]

                            if value == "on":
                                mode = "on"
                                cycle_count = 0
                                index = 0
                                direction = 1
                                last_update = time.ticks_ms()

                            elif value == "off":
                                mode = "off"
                                np.fill((0, 0, 0))
                                # ========= READY STATUS LIGHT =========
                                np[0] = (0, 255, 0) # green
                                np[-1] = (0, 255, 0)
                                np.write()

                        if p.startswith("speed="):
                            try:
                                speed = int(p.split("=")[1])
                            except:
                                pass

                        if p.startswith("limit="):
                            try:
                                cycle_limit = int(p.split("=")[1])
                                cycle_count = 0
                            except:
                                pass

            response = web_page()

            try:
                conn.send("HTTP/1.1 200 OK\r\n")
                conn.send("Content-Type: text/html\r\n")
                conn.send("Connection: close\r\n\r\n")
                conn.sendall(response)
            except:
                pass

            conn.close()