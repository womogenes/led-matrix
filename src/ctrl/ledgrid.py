import base64
import hashlib
import os
import random
import socket


DEFAULT_HOST = "192.168.86.223"
DEFAULT_PORT = 80
DEFAULT_PATH = "/frame"

DIGITS = {
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "010", "100", "100"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
}


class WebSocketFrameClient:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, path=DEFAULT_PATH):
        self.host = host
        self.port = port
        self.path = path
        self.sock = None

    def connect(self):
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ).encode("ascii")

        sock = socket.create_connection((self.host, self.port), timeout=5)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.sendall(request)
        response = sock.recv(4096)
        status = response.split(b"\r\n", 1)[0]
        if b" 101 " not in status:
            sock.close()
            raise RuntimeError(response.decode("latin1", "replace"))

        accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        )
        if accept not in response:
            sock.close()
            raise RuntimeError("websocket accept header did not match")

        self.sock = sock

    def send_binary(self, payload):
        if self.sock is None:
            raise RuntimeError("websocket is not connected")
        if len(payload) > 125:
            raise ValueError("only small payloads are supported")
        mask = random.randbytes(4) if hasattr(random, "randbytes") else os.urandom(4)
        masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        packet = bytes([0x82, 0x80 | len(payload)]) + mask + masked
        self.sock.sendall(packet)

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None


def cells_to_frame(cells, mirror_x=False, invert=False):
    rows = []
    for y in range(8):
        byte = 0
        for x in range(8):
            cell_x = 7 - x if mirror_x else x
            if (cell_x, y) in cells:
                byte |= 1 << x
        if invert:
            byte ^= 0xff
        rows.append(byte)
    return bytes(rows)


def empty_frame():
    return b"\x00" * 8


def invert_frame(frame):
    return bytes(byte ^ 0xff for byte in frame)


def score_frame(score, tick=0, mirror_x=True):
    cells = set()
    cursor = 0
    for digit in str(score):
        glyph = DIGITS[digit]
        for y, row in enumerate(glyph):
            for x, value in enumerate(row):
                if value == "1":
                    cells.add((cursor + x, y + 1))
        cursor += 4

    width = max(0, cursor - 1)
    if width <= 8:
        offset = (8 - width) // 2
    else:
        offset = 8 - ((tick // 6) % (width + 9))
    visible = {(x + offset, y) for x, y in cells if 0 <= x + offset < 8}
    return cells_to_frame(visible, mirror_x=mirror_x)
