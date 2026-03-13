# test_display.py — Pimoroni Display Pack PIM543 test for Pico W (MicroPython)
# Requires Pimoroni MicroPython firmware (pimoroni-picow-*.uf2)
# Display: 1.14" IPS 240x135, ST7789 driver, SPI0
# Buttons: A=GP12, B=GP13, X=GP14, Y=GP15 (active-low)
# RGB LED: R=GP6, G=GP7, B=GP8 (active-low)

import picographics
from picographics import PicoGraphics, DISPLAY_PICO_DISPLAY
from pimoroni import RGBLED, Button
import time

# --- Init display ---
display = PicoGraphics(display=DISPLAY_PICO_DISPLAY, rotate=0)
W, H = display.get_bounds()

# --- Init RGB LED (active-low: 0=full brightness, 65535=off) ---
led = RGBLED(6, 7, 8)

# --- Init buttons (active-low) ---
btn_a = Button(12)
btn_b = Button(13)
btn_x = Button(14)
btn_y = Button(15)

# --- Colours ---
BLACK  = display.create_pen(0,   0,   0)
WHITE  = display.create_pen(255, 255, 255)
RED    = display.create_pen(255,  40,  40)
GREEN  = display.create_pen( 40, 200,  40)
BLUE   = display.create_pen( 40, 120, 255)
YELLOW = display.create_pen(255, 220,   0)
CYAN   = display.create_pen(  0, 220, 220)
ORANGE = display.create_pen(255, 140,   0)

def cls(colour=BLACK):
    display.set_pen(colour)
    display.clear()

def text(s, x, y, colour=WHITE, scale=2):
    display.set_pen(colour)
    display.text(s, x, y, W, scale)

def show():
    display.update()

# --- Test 1: colour fill sequence ---
def test_colours():
    print("Test 1: colour fills")
    for name, pen in [("RED", RED), ("GREEN", GREEN), ("BLUE", BLUE),
                      ("WHITE", WHITE), ("BLACK", BLACK)]:
        cls(pen)
        show()
        print(f"  {name}")
        time.sleep_ms(600)

# --- Test 2: text rendering ---
def test_text():
    print("Test 2: text rendering")
    cls()
    text("PROMETO", 10, 10, CYAN,   scale=3)
    text("Embedded",10, 50, WHITE,  scale=2)
    text("World 26", 10, 75, YELLOW, scale=2)
    text("MCP Demo", 10,105, GREEN,  scale=2)
    show()
    time.sleep(2)

# --- Test 3: RGB LED ---
def test_led():
    print("Test 3: RGB LED")
    for colour, r, g, b in [
        ("Red",    255,   0,   0),
        ("Green",    0, 255,   0),
        ("Blue",     0,   0, 255),
        ("White",  255, 255, 255),
        ("Off",      0,   0,   0),
    ]:
        led.set_rgb(r, g, b)
        print(f"  LED {colour}")
        time.sleep_ms(500)

# --- Test 4: button detection ---
def test_buttons():
    print("Test 4: buttons (press each one, or wait 8s to skip)")
    cls()
    text("Press A B X Y", 5, 50, WHITE, scale=2)
    show()
    pressed = set()
    deadline = time.ticks_add(time.ticks_ms(), 8000)
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        for label, btn in [("A", btn_a), ("B", btn_b),
                            ("X", btn_x), ("Y", btn_y)]:
            if btn.read() and label not in pressed:
                pressed.add(label)
                print(f"  Button {label} ✓")
                cls()
                text(f"Button {label}", 30, 50, GREEN, scale=3)
                show()
                time.sleep_ms(400)
    if len(pressed) == 4:
        print("  All buttons OK ✓")
    else:
        missing = set("ABXY") - pressed
        print(f"  Not pressed: {missing}")

# --- Run all tests ---
print("=== Display Pack Test ===")
print(f"Display: {W}x{H}")
test_colours()
test_text()
test_led()
test_buttons()

cls()
text("Display OK", 20, 45, GREEN, scale=3)
show()
led.set_rgb(0, 60, 0)
print()
print("Test complete.")
