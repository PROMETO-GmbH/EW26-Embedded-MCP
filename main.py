# main.py — Pico W MCP Server
# PROMETO GmbH — Embedded World 2026 Demo
#
# Implements a minimal Model Context Protocol (MCP) server over WiFi (TCP).
# Exposes three tools to an MCP host (Claude / Ollama on the Mac):
#   - read_sensor   → temperature + humidity from HTU21D
#   - set_leds      → set WS2812B ring to a named colour
#   - show_message  → display text on the Display Pack
#
# Protocol: newline-delimited JSON (one JSON object per line).
# MCP subset: initialize / tools/list / tools/call only.
# Static buffers, no dynamic allocation beyond initial setup.
# Footprint target: <100 KB flash, <50 KB RAM.

import network
import socket
import json
import time
from machine import I2C, Pin
import neopixel
import picographics
from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY
from pimoroni import RGBLED

# ── WiFi credentials ──────────────────────────────────────────────────────────
# Create a secrets.py file on the Pico (see secrets.py.example in the repo)
from secrets import WIFI_SSID, WIFI_PASS  # noqa: E402
TCP_PORT = 3141

# ── Hardware init ─────────────────────────────────────────────────────────────

# HTU21D sensor (was labelled TH02 on Grove board)
i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400_000)
_CMD_TEMP = 0xF3
_CMD_RH   = 0xF5
_CMD_RST  = 0xFE
SENSOR_ADDR = 0x40

def _sensor_reset():
    i2c.writeto(SENSOR_ADDR, bytes([_CMD_RST]))
    time.sleep_ms(15)

def _sensor_read(cmd, conv_ms):
    i2c.writeto(SENSOR_ADDR, bytes([cmd]))
    time.sleep_ms(conv_ms)
    # HTU21D no-hold mode: sensor NAKs while converting; poll until ACK.
    for _ in range(20):
        try:
            d = i2c.readfrom(SENSOR_ADDR, 3)   # 2 data bytes + 1 CRC byte
            # Lower 2 bits of byte 1 are status flags — mask them out before use.
            return (d[0] << 8) | (d[1] & 0xFC)
        except OSError:
            time.sleep_ms(5)
    return 0

def read_sensor():
    raw_t = _sensor_read(_CMD_TEMP, 85)
    raw_h = _sensor_read(_CMD_RH,   30)
    # Conversion formulas from HTU21D datasheet (SHT21 compatible), section 6:
    #   T [°C] = -46.85 + 175.72 * S_T / 2^16
    #   RH [%] =  -6.00 + 125.00 * S_RH / 2^16
    temp  = round(-46.85 + 175.72 * raw_t / 65536.0, 1)
    hum   = round(max(0.0, min(100.0, -6.0 + 125.0 * raw_h / 65536.0)), 1)  # clamp 0–100 %
    return temp, hum

# WS2812B ring
_np = neopixel.NeoPixel(Pin(22), 8)

_COLOURS = {
    "off":    (  0,   0,   0),
    "red":    (204,   0,   0),   # 80% of 255
    "green":  (  0, 102,   0),   # 40%
    "blue":   (  0,   0, 102),   # 40%
    "orange": (153,  99,   0),   # 60%
    "white":  (102, 102, 102),   # 40%
}

def set_leds(colour_name):
    rgb = _COLOURS.get(colour_name.lower(), (0, 0, 0))
    for i in range(8):
        _np[i] = rgb
    _np.write()
    return colour_name.lower() in _COLOURS

# Display
_display = PicoGraphics(display=DISPLAY_PICO_DISPLAY, rotate=0)
_W, _H   = _display.get_bounds()
_led     = RGBLED(6, 7, 8)

_PEN_BLACK  = _display.create_pen(  0,   0,   0)
_PEN_WHITE  = _display.create_pen(255, 255, 255)
_PEN_CYAN   = _display.create_pen(  0, 220, 220)
_PEN_GREEN  = _display.create_pen( 40, 200,  40)
_PEN_YELLOW = _display.create_pen(255, 220,   0)
_PEN_RED    = _display.create_pen(255,  60,  60)

def show_message(line1, line2="", line3=""):
    _display.set_pen(_PEN_BLACK)
    _display.clear()
    _display.set_pen(_PEN_CYAN)
    _display.text(line1[:20], 4,  8, _W, scale=2)
    _display.set_pen(_PEN_WHITE)
    _display.text(line2[:20], 4, 45, _W, scale=2)
    _display.set_pen(_PEN_YELLOW)
    _display.text(line3[:20], 4, 82, _W, scale=2)
    _display.update()

def _temp_to_led_colour(temp):
    if temp < 22:   return "blue"
    if temp < 26:   return "green"
    if temp < 30:   return "orange"
    return "red"

# ── MCP protocol ──────────────────────────────────────────────────────────────

_TOOLS = [
    {
        "name": "read_sensor",
        "description": (
            "Read the current temperature (°C) and relative humidity (%) "
            "from the embedded HTU21D sensor on the Pico W demo board."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "set_leds",
        "description": (
            "Set all 8 WS2812B LEDs on the ring to a named colour. "
            "Valid colours: off, red, green, blue, orange, white."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "colour": {
                    "type": "string",
                    "description": "Colour name: off | red | green | blue | orange | white"
                }
            },
            "required": ["colour"]
        }
    },
    {
        "name": "show_message",
        "description": (
            "Display up to three lines of text on the 1.14-inch LCD. "
            "Each line is truncated to 20 characters."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "line1": {"type": "string", "description": "Top line (cyan)"},
                "line2": {"type": "string", "description": "Middle line (white)"},
                "line3": {"type": "string", "description": "Bottom line (yellow)"}
            },
            "required": ["line1"]
        }
    }
]

def _handle_request(req):
    method = req.get("method", "")
    rid    = req.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0", "id": rid,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "pico-mcp", "version": "1.0.0"}
            }
        }

    if method == "notifications/initialized":
        return None   # no response needed for notifications

    if method == "tools/list":
        return {
            "jsonrpc": "2.0", "id": rid,
            "result": {"tools": _TOOLS}
        }

    if method == "tools/call":
        name   = req.get("params", {}).get("name", "")
        args   = req.get("params", {}).get("arguments", {})
        result = _dispatch_tool(name, args)
        return {
            "jsonrpc": "2.0", "id": rid,
            "result": {
                "content": [{"type": "text", "text": result}],
                "isError": False
            }
        }

    return {
        "jsonrpc": "2.0", "id": rid,
        "error": {"code": -32601, "message": f"Method not found: {method}"}
    }

def _dispatch_tool(name, args):
    if name == "read_sensor":
        temp, hum = read_sensor()
        set_leds(_temp_to_led_colour(temp))
        show_message("Sensor reading", f"Temp: {temp} C", f"Hum:  {hum} %")
        return json.dumps({"temperature_c": temp, "humidity_pct": hum})

    if name == "set_leds":
        colour = args.get("colour", "off")
        ok = set_leds(colour)
        return json.dumps({"colour": colour, "ok": ok})

    if name == "show_message":
        l1 = args.get("line1", "")
        l2 = args.get("line2", "")
        l3 = args.get("line3", "")
        show_message(l1, l2, l3)
        return json.dumps({"displayed": True})

    return json.dumps({"error": f"Unknown tool: {name}"})

# ── WiFi connection ───────────────────────────────────────────────────────────

def connect_wifi():
    show_message("Connecting...", WIFI_SSID, "")
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(WIFI_SSID, WIFI_PASS)
    _led.set_rgb(60, 40, 0)   # amber while connecting
    for _ in range(20):
        if wlan.isconnected():
            break
        time.sleep(1)
    if not wlan.isconnected():
        show_message("WiFi FAILED", "Check credentials", "Reboot to retry")
        _led.set_rgb(60, 0, 0)
        raise RuntimeError("WiFi connection failed")
    ip = wlan.ifconfig()[0]
    show_message("MCP Ready", ip, f"Port {TCP_PORT}")
    _led.set_rgb(0, 40, 0)   # green = ready
    print(f"WiFi OK — {ip}:{TCP_PORT}")
    return ip

# ── TCP server ────────────────────────────────────────────────────────────────

def serve():
    addr = socket.getaddrinfo("0.0.0.0", TCP_PORT)[0][-1]
    srv  = socket.socket()
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(addr)
    srv.listen(1)
    print("Listening…")

    while True:
        conn, client = srv.accept()
        print(f"Client: {client}")
        _led.set_rgb(0, 0, 60)   # blue = active connection
        buf = b""
        try:
            while True:
                chunk = conn.recv(256)
                if not chunk:
                    break
                buf += chunk
                # MCP transport: newline-delimited JSON — one complete JSON object per line.
                # Accumulate chunks until a newline is found, then parse the full message.
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        req  = json.loads(line)
                        resp = _handle_request(req)
                        if resp is not None:   # notifications return None — no response sent
                            conn.sendall(json.dumps(resp).encode() + b"\n")
                    except Exception as e:
                        err = json.dumps({
                            "jsonrpc": "2.0", "id": None,
                            "error": {"code": -32700, "message": str(e)}
                        })
                        conn.sendall(err.encode() + b"\n")
        except OSError:
            pass
        finally:
            conn.close()
            _led.set_rgb(0, 40, 0)   # back to green = ready
            print("Client disconnected")

# ── Entry point ───────────────────────────────────────────────────────────────

_sensor_reset()
set_leds("off")
show_message("PROMETO GmbH", "Embedded World", "2026")
time.sleep(1)

connect_wifi()
serve()
