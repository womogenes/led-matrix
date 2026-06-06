#!/usr/bin/env python3
import argparse
from pathlib import Path
import shutil
import subprocess
import time

from PIL import Image

from ledgrid import DEFAULT_HOST, DEFAULT_PATH, WebSocketFrameClient


ROOT = Path(__file__).resolve().parent
MEDIA_DIR = ROOT / "media"
FRAME_DIR = MEDIA_DIR / "badapple_frames"
DEFAULT_VIDEO = MEDIA_DIR / "badapple.mp4"
DEFAULT_PACKED = MEDIA_DIR / "badapple_8x8.bin"
DEFAULT_URL = "ytsearch1:Bad Apple!! PV 影絵"


def require_tool(name):
    if shutil.which(name) is None:
        raise SystemExit(f"missing required tool: {name}")


def run(cmd):
    print("+", " ".join(str(part) for part in cmd))
    subprocess.run(cmd, check=True)


def download(args):
    require_tool("yt-dlp")
    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    if args.video.exists() and not args.force:
        print(f"already exists: {args.video}")
        return
    run([
        "yt-dlp",
        "-f",
        "18/b[ext=mp4]/b",
        "--extractor-args",
        "youtube:player_client=default",
        "--merge-output-format",
        "mp4",
        "-o",
        str(args.video),
        args.url,
    ])


def extract(args):
    require_tool("ffmpeg")
    args.frames.mkdir(parents=True, exist_ok=True)
    if args.force:
        for old in args.frames.glob("*.png"):
            old.unlink()
    if any(args.frames.glob("*.png")):
        print(f"frames already exist: {args.frames}")
        return
    run([
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(args.video),
        "-r",
        str(args.source_fps),
        "-vf",
        f"scale={args.scale}",
        str(args.frames / "img_%06d.png"),
    ])


def image_to_row_bytes(path, threshold, invert):
    img = Image.open(path).convert("L").resize((8, 8), Image.Resampling.LANCZOS)
    rows = []
    for y in range(8):
        byte = 0
        for x in range(8):
            on = img.getpixel((x, y)) >= threshold
            if invert:
                on = not on
            if on:
                byte |= 1 << x
        rows.append(byte)
    return bytes(rows)


def build(args):
    frame_paths = sorted(args.frames.glob("*.png"))
    if not frame_paths:
        raise SystemExit(f"no frames found in {args.frames}; run extract first")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("wb") as out:
        for frame_path in frame_paths:
            out.write(image_to_row_bytes(frame_path, args.threshold, args.invert))
    print(f"wrote {len(frame_paths)} packed frames to {args.output}")


def packed_frames(path):
    data = path.read_bytes()
    if len(data) % 8:
        raise SystemExit(f"packed frame file length must be divisible by 8: {path}")
    for offset in range(0, len(data), 8):
        yield data[offset:offset + 8]


def stream(args):
    frames = list(packed_frames(args.input))
    if not frames:
        raise SystemExit(f"no frames in {args.input}")

    repeats = max(1, round(args.fps / args.source_fps))
    frame_interval = 1.0 / args.fps
    client = WebSocketFrameClient(args.host, args.port, args.path)
    client.connect()
    print(
        f"streaming {len(frames)} frames to ws://{args.host}:{args.port}{args.path} at {args.fps:g} fps",
        flush=True,
    )
    next_send = time.monotonic()
    stop_at = None if args.seconds is None else next_send + args.seconds
    sent = 0
    try:
        for frame in frames:
            for _ in range(repeats):
                if stop_at is not None and time.monotonic() >= stop_at:
                    return
                now = time.monotonic()
                if now < next_send:
                    time.sleep(next_send - now)
                elif now - next_send > frame_interval:
                    next_send = now
                client.send_binary(frame)
                next_send += frame_interval
                sent += 1
    finally:
        client.close()


def run_all(args):
    download(args)
    extract(args)
    build(args)
    stream(args)


def add_common(parser):
    parser.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--frames", type=Path, default=FRAME_DIR)
    parser.add_argument("--force", action="store_true")


def main():
    parser = argparse.ArgumentParser(description="Download, pack, and stream Bad Apple to the 8x8 LED matrix.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("download")
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--video", type=Path, default=DEFAULT_VIDEO)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=download)

    p = sub.add_parser("extract")
    add_common(p)
    p.add_argument("--source-fps", type=float, default=30)
    p.add_argument("--scale", default="48:32")
    p.set_defaults(func=extract)

    p = sub.add_parser("build")
    p.add_argument("--frames", type=Path, default=FRAME_DIR)
    p.add_argument("--output", type=Path, default=DEFAULT_PACKED)
    p.add_argument("--threshold", type=int, default=128)
    p.add_argument("--invert", action="store_true")
    p.set_defaults(func=build)

    p = sub.add_parser("stream")
    p.add_argument("--input", type=Path, default=DEFAULT_PACKED)
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=80)
    p.add_argument("--path", default=DEFAULT_PATH)
    p.add_argument("--fps", type=float, default=60)
    p.add_argument("--source-fps", type=float, default=30)
    p.add_argument("--seconds", type=float)
    p.set_defaults(func=stream)

    p = sub.add_parser("run")
    add_common(p)
    p.add_argument("--url", default=DEFAULT_URL)
    p.add_argument("--source-fps", type=float, default=30)
    p.add_argument("--scale", default="48:32")
    p.add_argument("--output", type=Path, default=DEFAULT_PACKED)
    p.add_argument("--threshold", type=int, default=128)
    p.add_argument("--invert", action="store_true")
    p.add_argument("--input", type=Path, default=DEFAULT_PACKED)
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=80)
    p.add_argument("--path", default=DEFAULT_PATH)
    p.add_argument("--fps", type=float, default=60)
    p.add_argument("--seconds", type=float)
    p.set_defaults(func=run_all)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
