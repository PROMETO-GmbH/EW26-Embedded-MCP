# Lightweight MCP for Embedded AI — Embedded World 2026 Demo

**PROMETO GmbH** | Talk: *"Lightweight and Secure MCP for Embedded AI: Bringing Agent Protocols to the Edge"*

This repository contains the firmware and host client from the live demo. A Raspberry Pi Pico W acts as an MCP server; a Mac runs a local LLM (Ollama) that talks to it over TCP via the Model Context Protocol.

> **Want the full setup guide?** Download the complete step-by-step PDF (hardware sourcing, soldering, flashing, troubleshooting) at **[prometo.de/embedded-mcp](https://prometo.de/embedded-mcp)** — free with email opt-in.

---

## Architecture

```
┌─────────────────────────────────┐        TCP :3141 (WiFi)        ┌────────────────────────────┐
│         Mac / Linux Host        │ ◄─────────────────────────────► │     Raspberry Pi Pico W    │
│                                 │                                  │                            │
│  Ollama (llama3.2 or similar)   │   JSON-RPC 2.0 over newline-    │  MCP server  (MicroPython) │
│  └─ mcp_client.py               │   delimited TCP stream          │  └─ main.py                │
│      └─ agentic loop            │                                  │      ├─ read_sensor        │
│          └─ tool calls via MCP  │                                  │      ├─ set_leds           │
└─────────────────────────────────┘                                  │      └─ show_message       │
                                                                      └────────────────────────────┘
```

The LLM never touches the hardware directly. It issues MCP `tools/call` requests; the Pico W executes them and returns JSON results. Footprint on the Pico W: **<100 KB flash, <50 KB RAM**, no heap allocation after boot.

---

## Hardware

| Part | Purpose |
|------|---------|
| Raspberry Pi Pico W | MCP server, WiFi transport |
| Pimoroni Pico Omnibus | Expander breakout (passive pass-through) |
| Pimoroni Pico Display Pack PIM543 | 1.14" IPS LCD + RGB status LED |
| Seeed Studio TH02 Grove sensor | Temperature + humidity (I2C, addr 0x40) |
| AZ-Delivery CJMCU-2812 8-LED ring | WS2812B RGB indicator ring |
| 1N4148 diode | Level-shift trick for WS2812B data line |

### Wiring summary

**TH02 sensor → Pico W**

| TH02 pin | Pico W pin |
|----------|-----------|
| SDA | GP4 (I2C0) |
| SCL | GP5 (I2C0) |
| VCC | 3V3 ⚠️ not VBUS |
| GND | GND |

**WS2812B ring → Pico W**

| Ring pin | Pico W / note |
|----------|--------------|
| DI | GP22 |
| VCC | VBUS (5V) **via 1N4148 diode** — anode to VBUS, cathode to ring |
| GND | GND |

> The 1N4148 drops VCC from 5V to ~4.3V, which lowers the WS2812B data threshold below the Pico W's 3.3V output. Without the diode, signal levels are unreliable.

The **Display Pack** plugs directly into the Omnibus — no additional wiring required.

---

## Installation

### 1 — Flash Pimoroni MicroPython to the Pico W

The Display Pack requires Pimoroni's firmware (not the standard RPi build).

1. Download `pimoroni-picow-vX.X.X-micropython.uf2` from [github.com/pimoroni/pimoroni-pico/releases](https://github.com/pimoroni/pimoroni-pico/releases)
2. Hold **BOOTSEL** while plugging in USB — the Pico W mounts as `RPI-RP2`
3. Drag the `.uf2` onto the drive

### 2 — Copy firmware files to the Pico W

Use [Thonny](https://thonny.org) (`brew install --cask thonny` on Mac) or `mpremote`.

Files to upload:
- `main.py`
- `secrets.py` (create from `secrets.py.example` — **never commit this file**)

```bash
# secrets.py.example → secrets.py
cp secrets.py.example secrets.py
# edit WIFI_SSID and WIFI_PASS, then upload via Thonny or:
mpremote connect auto cp secrets.py :secrets.py
mpremote connect auto cp main.py :main.py
```

After upload the Pico W reboots, connects to WiFi, and shows its IP address on the display.

### 3 — Install Ollama on the Mac

```bash
brew install ollama
ollama pull llama3.2
ollama serve          # starts API on localhost:11434
```

---

## Running the Demo

```bash
# Interactive REPL — replace 192.168.x.x with the IP shown on the Pico W display
python3 mcp_client.py 192.168.x.x

# Single prompt
python3 mcp_client.py 192.168.x.x --prompt "What is the temperature? Set the LEDs accordingly."
```

**Available MCP tools exposed by the Pico W:**

| Tool | What it does |
|------|-------------|
| `read_sensor` | Returns temperature (°C) and humidity (%) from the HTU21D |
| `set_leds` | Sets all 8 ring LEDs to a named colour (off / red / green / blue / orange / white) |
| `show_message` | Displays up to 3 lines of text on the LCD |

---

## Repository Contents

```
main.py              # MicroPython MCP server — runs on the Pico W
mcp_client.py        # Python 3 MCP client + Ollama agentic loop — runs on the Mac
secrets.py.example   # WiFi credentials template
test_th02.py         # Standalone I2C sensor test
test_ws2812.py       # Standalone LED ring test
test_display.py      # Standalone display test
ws2812b_ring_mount.scad  # Optional 3D-printable ring mount (OpenSCAD)
```

---

## Full Guide

The README covers the essentials. The **complete guide** includes hardware sourcing links, soldering photos, Thonny walkthrough, troubleshooting for common failures, and notes on extending the demo with additional MCP tools.

**Download free at [prometo.ai/mcp-for-embedded](https://www.prometo.ai/mcp-for-embedded/)**
---

## License

Apache 2.0 — see `LICENSE`.

© 2026 PROMETO GmbH# EW26-Embedded-MCP
Demo MCP based on Ollama and Rasberry Pi Pico W for Embedded World 2026 Conference
