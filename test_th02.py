# test_th02.py — TH02 / HTU21D sensor test for Pico W (MicroPython)
# Wiring: SDA=GP4, SCL=GP5, VCC=3V3, GND=GND
# I2C address: 0x40 (both TH02 and HTU21D use same address)
#
# Seeed Grove TH02 modules after ~2018 use HTU21D silicon internally.
# HTU21D uses bare command bytes — no register addresses.

from machine import I2C, Pin
import time

ADDR = 0x40

CMD_TRIG_TEMP_NOHOLD = 0xF3
CMD_TRIG_RH_NOHOLD   = 0xF5
CMD_SOFT_RESET       = 0xFE

i2c = I2C(0, sda=Pin(4), scl=Pin(5), freq=400_000)

def scan():
    devices = i2c.scan()
    if ADDR in devices:
        print(f"Sensor found at 0x{ADDR:02X} ✓")
    else:
        print(f"Sensor NOT found. Devices: {[hex(d) for d in devices]}")
        raise SystemExit

def soft_reset():
    i2c.writeto(ADDR, bytes([CMD_SOFT_RESET]))
    time.sleep_ms(15)   # datasheet: max 15ms after reset

def _read_measurement(cmd, conversion_ms):
    i2c.writeto(ADDR, bytes([cmd]))
    time.sleep_ms(conversion_ms)
    # Poll until ACK (sensor holds NAK while converting in no-hold mode)
    for _ in range(20):
        try:
            data = i2c.readfrom(ADDR, 3)   # 2 data bytes + 1 CRC byte
            return (data[0] << 8) | (data[1] & 0xFC)  # mask status bits
        except OSError:
            time.sleep_ms(5)
    raise RuntimeError("Sensor did not respond after conversion")

def read_temperature():
    raw = _read_measurement(CMD_TRIG_TEMP_NOHOLD, conversion_ms=85)
    return -46.85 + 175.72 * raw / 65536.0

def read_humidity():
    raw = _read_measurement(CMD_TRIG_RH_NOHOLD, conversion_ms=30)
    rh = -6.0 + 125.0 * raw / 65536.0
    return max(0.0, min(100.0, rh))   # clamp to valid range

# --- Run test ---
print("=== TH02 / HTU21D Sensor Test ===")
scan()
soft_reset()
print("Soft reset OK")
print()

for i in range(5):
    temp = read_temperature()
    rh   = read_humidity()
    print(f"[{i+1}] Temp: {temp:.1f} °C   Humidity: {rh:.1f} %RH")
    time.sleep(2)

print()
print("Test complete.")
