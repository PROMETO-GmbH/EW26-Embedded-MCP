# test_ws2812.py — CJMCU-2812 WS2812B 8-LED ring test for Pico W (MicroPython)
# Wiring: DI=GP22, VCC=VBUS(5V) via 1N4148 diode, GND=GND
# Pimoroni firmware includes the 'neopixel' module.

import neopixel
from machine import Pin
import time

NUM_LEDS = 8
PIN      = 22

np = neopixel.NeoPixel(Pin(PIN), NUM_LEDS)

def fill(r, g, b):
    for i in range(NUM_LEDS):
        np[i] = (r, g, b)
    np.write()

def dim(r, g, b, brightness=0.4):
    return (int(r * brightness), int(g * brightness), int(b * brightness))

def off():
    fill(0, 0, 0)

# --- Test 1: single colour fills ---
def test_fills():
    print("Test 1: colour fills")
    for name, rgb in [
        ("Red",    (255,   0,   0)),
        ("Green",  (  0, 255,   0)),
        ("Blue",   (  0,   0, 255)),
        ("White",  (255, 255, 255)),
        ("Off",    (  0,   0,   0)),
    ]:
        fill(*dim(*rgb))
        print(f"  {name}")
        time.sleep_ms(700)

# --- Test 2: chase animation ---
def test_chase():
    print("Test 2: chase")
    for colour in [(255, 0, 0), (0, 255, 0), (0, 0, 255)]:
        for _ in range(2):
            for i in range(NUM_LEDS):
                off()
                np[i] = dim(*colour)
                np.write()
                time.sleep_ms(80)
    off()

# --- Test 3: demo colour mapping (matches MCP firmware logic) ---
def test_demo_colours():
    print("Test 3: demo temperature colour mapping")
    scenarios = [
        ("< 22°C  → Blue",   dim(  0,   0, 255, 0.4)),
        ("22-26°C → Green",  dim(  0, 255,   0, 0.4)),
        ("26-30°C → Orange", dim(255, 165,   0, 0.6)),
        ("> 30°C  → Red",    dim(255,   0,   0, 0.8)),
    ]
    for label, colour in scenarios:
        fill(*colour)
        print(f"  {label}")
        time.sleep(1)
    off()

# --- Run all tests ---
print("=== WS2812B Ring Test ===")
test_fills()
test_chase()
test_demo_colours()

print()
print("Test complete.")
print("If any LEDs stayed off or showed wrong colours,")
print("check: diode orientation (stripe→ring VCC), VBUS not 3V3.")
