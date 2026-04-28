import json
import sys


def _read_message():
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            return None
        if line in {b"\r\n", b"\n"}:
            break
        name, value = line.decode("utf-8").split(":", 1)
        headers[name.strip().lower()] = value.strip()

    content_length = int(headers.get("content-length", "0"))
    if content_length <= 0:
        return None
    body = sys.stdin.buffer.read(content_length)
    if not body:
        return None
    return json.loads(body.decode("utf-8"))


def _send(message):
    payload = json.dumps(message).encode("utf-8")
    sys.stdout.buffer.write(f"Content-Length: {len(payload)}\r\n\r\n".encode("utf-8"))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


while True:
    message = _read_message()
    if message is None:
        break

    method = message.get("method")
    message_id = message.get("id")

    if method == "initialize":
        _send({"jsonrpc": "2.0", "id": message_id, "result": {"serverInfo": {"name": "fake-cl"}}})
    elif method == "notifications/initialized":
        continue
    elif method == "tools/list":
        _send(
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
    elif method == "resources/list":
        _send(
            {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"resources": [{"uri": "fake://hello", "name": "Hello"}]},
            }
        )
    elif method == "resources/read":
        _send(
            {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"contents": [{"uri": "fake://hello", "text": "hello resource"}]},
            }
        )
    elif method == "prompts/list":
        _send(
            {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"prompts": [{"name": "hello", "arguments": [{"name": "name", "required": True}]}]},
            }
        )
    elif method == "prompts/get":
        arguments = message.get("params", {}).get("arguments", {})
        name = arguments.get("name", "world")
        _send(
            {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"messages": [{"role": "user", "content": f"hello {name}"}]},
            }
        )
    elif method == "tools/call":
        arguments = message.get("params", {}).get("arguments", {})
        _send(
            {
                "jsonrpc": "2.0",
                "id": message_id,
                "result": {"content": [{"type": "text", "text": f"echo:{arguments.get('text', '')}"}]},
            }
        )
