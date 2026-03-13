#!/usr/bin/env python3
# mcp_client.py — Mac-side MCP client + Ollama orchestration
# PROMETO GmbH — Embedded World 2026 Demo
#
# Connects to the Pico W MCP server over TCP.
# Sends tool calls driven by an Ollama LLM (llama3.2 or similar).
# Usage:  python3 mcp_client.py <pico_ip>
#         python3 mcp_client.py <pico_ip> --prompt "What is the temperature?"

import socket
import json
import sys
import time
import argparse
import urllib.request

# ── Config ────────────────────────────────────────────────────────────────────

TCP_PORT     = 3141
OLLAMA_URL   = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2"

SYSTEM_PROMPT = """You are an AI assistant controlling an embedded sensor demo board
(Raspberry Pi Pico W) via the Model Context Protocol (MCP).

The board has three tools:
- read_sensor: returns temperature (°C) and humidity (%)
- set_leds: sets 8 RGB LEDs to a colour (off/red/green/blue/orange/white)
- show_message: displays up to 3 lines of text on the LCD

When asked about the environment, always call read_sensor first.
When you set LEDs, confirm the colour chosen and why.
Keep your spoken responses short and factual — one or two sentences."""

# ── MCP transport ─────────────────────────────────────────────────────────────

class MCPClient:
    def __init__(self, host, port=TCP_PORT):
        self.host = host
        self.port = port
        self.sock = None
        self._id  = 0

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(10.0)
        self.sock.connect((self.host, self.port))
        self._buf = b""
        print(f"Connected to {self.host}:{self.port}")

    def close(self):
        if self.sock:
            self.sock.close()

    def _next_id(self):
        self._id += 1
        return self._id

    def _send(self, obj):
        self.sock.sendall(json.dumps(obj).encode() + b"\n")

    def _recv(self):
        while b"\n" not in self._buf:
            chunk = self.sock.recv(1024)
            if not chunk:
                raise ConnectionError("Server closed connection")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\n", 1)
        return json.loads(line.decode())

    def initialize(self):
        self._send({
            "jsonrpc": "2.0", "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcp-demo-client", "version": "1.0"}
            }
        })
        resp = self._recv()
        info = resp.get("result", {}).get("serverInfo", {})
        print(f"Server: {info.get('name')} v{info.get('version')}")
        # send initialized notification
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def list_tools(self):
        self._send({"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/list"})
        resp = self._recv()
        return resp.get("result", {}).get("tools", [])

    def call_tool(self, name, arguments=None):
        self._send({
            "jsonrpc": "2.0", "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}}
        })
        resp = self._recv()
        content = resp.get("result", {}).get("content", [])
        return content[0].get("text", "") if content else ""

# ── Ollama integration ────────────────────────────────────────────────────────

def ollama_chat(messages):
    payload = json.dumps({
        "model":    OLLAMA_MODEL,
        "messages": messages,
        "stream":   False,
        "tools":    _mcp_tools_to_ollama_format()
    }).encode()
    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())

def _mcp_tools_to_ollama_format():
    """Convert MCP tool descriptors to Ollama/OpenAI function-call format.

    MCP uses 'inputSchema'; Ollama expects the OpenAI-compatible 'function'
    wrapper with a 'parameters' key. This adapter bridges the two schemas so
    the LLM can declare tool calls that the MCP client then forwards verbatim.
    """
    return [
        {
            "type": "function",
            "function": {
                "name":        t["name"],
                "description": t["description"],
                "parameters":  t["inputSchema"]
            }
        }
        for t in _cached_tools
    ]

_cached_tools = []

# ── Agentic loop ──────────────────────────────────────────────────────────────

def run_agent(mcp, user_prompt):
    messages = [
        {"role": "system",  "content": SYSTEM_PROMPT},
        {"role": "user",    "content": user_prompt},
    ]

    print(f"\nUser: {user_prompt}")

    # Agentic loop: the LLM may call several tools before giving a final answer.
    # Each iteration is one LLM turn. If the response contains tool_calls we
    # execute them via MCP, append the results, and loop. When the LLM returns
    # plain text (no tool calls) it has finished reasoning — we return that text.
    # The cap of 6 turns prevents runaway loops on unexpected model behaviour.
    for step in range(6):
        response = ollama_chat(messages)
        msg = response.get("message", {})
        tool_calls = msg.get("tool_calls", [])

        if tool_calls:
            messages.append(msg)
            for tc in tool_calls:
                fn   = tc.get("function", {})
                name = fn.get("name", "")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    # Some models serialise arguments as a JSON string rather than an object.
                    args = json.loads(args)

                print(f"  → tool call: {name}({args})")
                result = mcp.call_tool(name, args)
                print(f"  ← result:    {result}")

                messages.append({
                    "role":    "tool",
                    "content": result
                })
        else:
            # No tool calls — the LLM produced its final text response.
            answer = msg.get("content", "").strip()
            print(f"\nAssistant: {answer}\n")
            return answer

    return "(max steps reached)"

# ── Interactive REPL ──────────────────────────────────────────────────────────

def repl(mcp):
    print("\nMCP Demo REPL — type a question, or 'quit' to exit.")
    print("Examples:")
    print("  What is the current temperature?")
    print("  Set the LEDs to blue and show a welcome message.")
    print("  Is the humidity comfortable?\n")
    while True:
        try:
            prompt = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not prompt:
            continue
        if prompt.lower() in ("quit", "exit", "q"):
            break
        run_agent(mcp, prompt)

# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Pico W MCP demo client")
    parser.add_argument("host",   help="Pico W IP address (shown on its display)")
    parser.add_argument("--prompt", "-p", help="Single prompt (non-interactive)", default=None)
    args = parser.parse_args()

    mcp = MCPClient(args.host)
    mcp.connect()
    mcp.initialize()

    global _cached_tools
    _cached_tools = mcp.list_tools()
    print(f"Tools available: {[t['name'] for t in _cached_tools]}")

    if args.prompt:
        run_agent(mcp, args.prompt)
    else:
        repl(mcp)

    mcp.close()

if __name__ == "__main__":
    main()
