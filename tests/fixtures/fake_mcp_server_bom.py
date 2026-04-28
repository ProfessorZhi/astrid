import json
import sys


_BOM = b"\xef\xbb\xbf"


def send(message):
    payload = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(_BOM + payload + b"\n")
    sys.stdout.buffer.flush()


for line in sys.stdin:
    line = line.strip()
    if not line:
        continue
    message = json.loads(line)
    method = message.get("method")
    message_id = message.get("id")

    if method == "initialize":
        send({"jsonrpc": "2.0", "id": message_id, "result": {"serverInfo": {"name": "fake-bom"}}})
    elif method == "notifications/initialized":
        continue
    elif method == "tools/list":
        send(
            {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {
                    "tools": [
                        {
                            "name": "echo",
                            "description": "Echo text",
                            "inputSchema": {"type": "object"},
                        }
                    ]
                },
            }
        )
    elif method == "tools/call":
        arguments = message.get("params", {}).get("arguments", {})
        send(
            {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"content": [{"type": "text", "text": f"echo:{arguments.get('text', '')}"}]},
            }
        )
