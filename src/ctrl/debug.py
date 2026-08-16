#!/usr/bin/env python3

import argparse
import glob
import os
import select
import sys
import termios
import tty


KEY_HELP = {
    "j": "toggle anode SER (green, GPIO 27)",
    "k": "toggle anode CLK (GPIO 25)",
    "a": "toggle cathode SER (green, GPIO 33)",
    "s": "toggle cathode SRCLK (yellow, GPIO 32)",
    "d": "toggle cathode RCLK (blue, GPIO 26)",
    "r": "reset every output LOW",
    "?": "print firmware help",
}


def find_serial_port():
    candidates = (
        glob.glob("/dev/serial/by-id/*")
        + glob.glob("/dev/ttyUSB*")
        + glob.glob("/dev/ttyACM*")
    )
    if not candidates:
        raise SystemExit("no serial bridge found; pass its path with --port")
    return candidates[0]


def configure_serial(fd, baud):
    baud_constant = getattr(termios, f"B{baud}", None)
    if baud_constant is None:
        raise SystemExit(f"unsupported baud rate: {baud}")

    attrs = termios.tcgetattr(fd)
    attrs[0] = 0
    attrs[1] = 0
    attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
    attrs[3] = 0
    attrs[4] = baud_constant
    attrs[5] = baud_constant
    attrs[6][termios.VMIN] = 0
    attrs[6][termios.VTIME] = 0
    termios.tcsetattr(fd, termios.TCSANOW, attrs)


def print_help(port, baud):
    print(f"Connected to {port} at {baud} baud")
    for key, description in KEY_HELP.items():
        print(f"  {key}  {description}")
    print("  :  enter a runtime configuration command")
    print("  q  reset outputs and quit")
    print("\nConfiguration commands:")
    print("  map <key> <gpio> <name>")
    print("  unmap <key>")
    print("  list")
    print("  reset")


def run(port, baud):
    serial_fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
    stdin_fd = sys.stdin.fileno()
    saved_terminal = termios.tcgetattr(stdin_fd)

    try:
        configure_serial(serial_fd, baud)
        tty.setcbreak(stdin_fd)
        print_help(port, baud)
        command = None

        while True:
            readable, _, _ = select.select([stdin_fd, serial_fd], [], [])

            if serial_fd in readable:
                output = os.read(serial_fd, 4096)
                if output:
                    sys.stdout.write(output.decode("utf-8", "replace"))
                    sys.stdout.flush()

            if stdin_fd in readable:
                key = os.read(stdin_fd, 1)
                if command is not None:
                    if key in (b"\r", b"\n"):
                        os.write(serial_fd, b":" + command + b"\n")
                        command = None
                        print()
                    elif key == b"\x1b":
                        command = None
                        print("\nconfiguration cancelled")
                    elif key in (b"\x7f", b"\b") and command:
                        command = command[:-1]
                        sys.stdout.write("\b \b")
                        sys.stdout.flush()
                    elif 32 <= key[0] <= 126:
                        command += key
                        sys.stdout.write(key.decode("ascii"))
                        sys.stdout.flush()
                    continue

                if key == b"q":
                    break
                if key == b":":
                    command = bytearray()
                    sys.stdout.write("\nconfig> ")
                    sys.stdout.flush()
                    continue

                action = key.decode("ascii", "ignore").lower()
                if action in KEY_HELP:
                    os.write(serial_fd, action.encode("ascii"))
    finally:
        try:
            os.write(serial_fd, b"r")
            termios.tcdrain(serial_fd)
        except OSError:
            pass
        termios.tcsetattr(stdin_fd, termios.TCSADRAIN, saved_terminal)
        os.close(serial_fd)
        print("\nDisconnected; sent the reset-LOW command")


def main():
    parser = argparse.ArgumentParser(description="Control the LED matrix GPIO debug firmware")
    parser.add_argument("--port", help="serial bridge, for example /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=115200)
    args = parser.parse_args()
    run(args.port or find_serial_port(), args.baud)


if __name__ == "__main__":
    main()
