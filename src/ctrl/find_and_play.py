#!/usr/bin/env python3

import argparse
import fcntl
import ipaddress
import socket
import struct
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ledgrid import WebSocketFrameClient


MATRIX_MAC = "70:4b:ca:4d:86:74"


def interface_address(interface, request):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        result = fcntl.ioctl(
            sock.fileno(),
            request,
            struct.pack("256s", interface.encode("ascii")[:15]),
        )
        return socket.inet_ntoa(result[20:24])
    finally:
        sock.close()


def local_network():
    with open("/proc/net/route", encoding="ascii") as routes:
        next(routes)
        for line in routes:
            fields = line.split()
            if len(fields) >= 4 and fields[1] == "00000000":
                interface = fields[0]
                address = interface_address(interface, 0x8915)
                netmask = interface_address(interface, 0x891B)
                return ipaddress.ip_network(f"{address}/{netmask}", strict=False)
    raise SystemExit("no default IPv4 network found")


def has_http(host):
    try:
        with socket.create_connection((host, 80), timeout=0.25):
            return host
    except OSError:
        return None


def arp_table():
    entries = {}
    with open("/proc/net/arp", encoding="ascii") as table:
        next(table)
        for line in table:
            fields = line.split()
            if len(fields) >= 6 and fields[2] == "0x2":
                entries[fields[0]] = fields[3].lower()
    return entries


def find_matrix(mac):
    network = local_network()
    hosts = (str(host) for host in network.hosts())

    with ThreadPoolExecutor(max_workers=64) as pool:
        candidates = [host for host in pool.map(has_http, hosts) if host]

    neighbors = arp_table()
    for host in candidates:
        if neighbors.get(host) != mac.lower():
            continue
        client = WebSocketFrameClient(host)
        try:
            client.connect()
            return host
        except (OSError, RuntimeError):
            pass
        finally:
            client.close()

    raise SystemExit(
        f"LED matrix {mac} is not online on {network}"
    )


def main():
    parser = argparse.ArgumentParser(description="Find the LED matrix and play Bad Apple")
    parser.add_argument("--find-only", action="store_true")
    parser.add_argument("--mac", default=MATRIX_MAC)
    args = parser.parse_args()

    host = find_matrix(args.mac)
    print(f"found LED matrix {args.mac} at {host}", flush=True)
    if args.find_only:
        return

    badapple = Path(__file__).with_name("badapple.py")
    subprocess.run(
        [sys.executable, str(badapple), "stream", "--host", host],
        check=True,
    )


if __name__ == "__main__":
    main()
