#!/usr/bin/env python3

import argparse
import ctypes
import time

from ledgrid import WebSocketFrameClient, cells_to_frame


GLYPHS = {
    "H": ("101", "101", "111", "101"),
    "M": ("10001", "11011", "10101", "10001"),
}


class Timespec(ctypes.Structure):
    _fields_ = [("tv_sec", ctypes.c_long), ("tv_nsec", ctypes.c_long)]


libc = ctypes.CDLL(None)
clock_nanosleep = libc.clock_nanosleep
clock_nanosleep.argtypes = [
    ctypes.c_int,
    ctypes.c_int,
    ctypes.POINTER(Timespec),
    ctypes.c_void_p,
]


def sleep_until(deadline_ns):
    target = Timespec(
        deadline_ns // 1_000_000_000,
        deadline_ns % 1_000_000_000,
    )
    clock_nanosleep(1, 1, ctypes.byref(target), None)


def make_frames(text):
    columns = []
    for char in text.upper():
        if char == " ":
            columns.extend([0, 0])
            continue

        glyph = GLYPHS.get(char)
        if glyph is None:
            raise ValueError(f"unsupported character: {char!r}")

        for x in range(len(glyph[0])):
            columns.append(
                sum((row[x] == "1") << y for y, row in enumerate(glyph))
            )
        columns.append(0)

    columns.extend([0] * 8)
    return tuple(
        cells_to_frame(
            {
                (x, y + 2)
                for x in range(8)
                for y in range(4)
                if columns[(offset + x) % len(columns)] & (1 << y)
            },
            mirror_x=True,
        )
        for offset in range(len(columns))
    )


def main():
    parser = argparse.ArgumentParser(description="Scroll 4-pixel text on the LED matrix")
    parser.add_argument("text", nargs="?", default="H M")
    parser.add_argument("--host", default="192.168.86.23")
    parser.add_argument("--period-ms", type=float, default=64.0)
    args = parser.parse_args()

    frames = make_frames(args.text)
    period_ns = round(args.period_ms * 1_000_000)
    client = WebSocketFrameClient(args.host)
    client.connect()
    print(
        f"Scrolling {args.text!r} on {args.host} every {args.period_ms:g} ms; "
        "press Ctrl-C to stop"
    )

    try:
        deadline = time.monotonic_ns()
        while True:
            for frame in frames:
                client.send_binary(frame)
                deadline += period_ns
                sleep_until(deadline)
    finally:
        client.close()


if __name__ == "__main__":
    main()
