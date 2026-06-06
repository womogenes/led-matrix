#!/usr/bin/env python3
import argparse
import curses
from dataclasses import dataclass
from pathlib import Path
import random
import sys
import time


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ledgrid import (
    DEFAULT_HOST,
    DEFAULT_PATH,
    DEFAULT_PORT,
    WebSocketFrameClient,
    cells_to_frame,
    empty_frame,
)


WIDTH = 8
HEIGHT = 8

PIECES = {
    "I": [
        [(0, 1), (1, 1), (2, 1), (3, 1)],
        [(2, 0), (2, 1), (2, 2), (2, 3)],
    ],
    "O": [
        [(1, 0), (2, 0), (1, 1), (2, 1)],
    ],
    "T": [
        [(1, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (2, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (1, 2)],
        [(1, 0), (0, 1), (1, 1), (1, 2)],
    ],
    "L": [
        [(0, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (2, 0), (1, 1), (1, 2)],
        [(0, 1), (1, 1), (2, 1), (2, 2)],
        [(1, 0), (1, 1), (0, 2), (1, 2)],
    ],
    "J": [
        [(2, 0), (0, 1), (1, 1), (2, 1)],
        [(1, 0), (1, 1), (1, 2), (2, 2)],
        [(0, 1), (1, 1), (2, 1), (0, 2)],
        [(0, 0), (1, 0), (1, 1), (1, 2)],
    ],
    "S": [
        [(1, 0), (2, 0), (0, 1), (1, 1)],
        [(1, 0), (1, 1), (2, 1), (2, 2)],
    ],
    "Z": [
        [(0, 0), (1, 0), (1, 1), (2, 1)],
        [(2, 0), (1, 1), (2, 1), (1, 2)],
    ],
}

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


@dataclass
class ActivePiece:
    name: str
    x: int
    y: int
    rotation: int = 0

    @property
    def shape(self):
        rotations = PIECES[self.name]
        return rotations[self.rotation % len(rotations)]

    def cells(self):
        return {(self.x + dx, self.y + dy) for dx, dy in self.shape}


class TetrisGame:
    def __init__(self):
        self.bag = []
        self.reset()

    def reset(self):
        self.board = set()
        self.score = 0
        self.lines = 0
        self.level = 1
        self.game_over = False
        self.clearing_rows = []
        self.clear_flash_ticks = 0
        self.bag.clear()
        self.active = self.new_piece()

    def new_piece(self):
        if not self.bag:
            self.bag = list(PIECES)
            random.shuffle(self.bag)
        name = self.bag.pop()
        piece = ActivePiece(name=name, x=2, y=-1)
        if self.collides(piece):
            self.game_over = True
        return piece

    def collides(self, piece):
        for x, y in piece.cells():
            if x < 0 or x >= WIDTH or y >= HEIGHT:
                return True
            if y >= 0 and (x, y) in self.board:
                return True
        return False

    def try_move(self, dx=0, dy=0, rotate=0):
        if self.game_over or self.clearing_rows:
            return False
        rotations = PIECES[self.active.name]
        moved = ActivePiece(
            name=self.active.name,
            x=self.active.x + dx,
            y=self.active.y + dy,
            rotation=(self.active.rotation + rotate) % len(rotations),
        )
        if not self.collides(moved):
            self.active = moved
            return True
        if rotate:
            return self.try_wall_kicks(moved)
        return False

    def try_wall_kicks(self, rotated):
        for kick in (-1, 1, -2, 2):
            kicked = ActivePiece(rotated.name, rotated.x + kick, rotated.y, rotated.rotation)
            if not self.collides(kicked):
                self.active = kicked
                return True
        return False

    def tick(self):
        if self.game_over:
            return
        if self.clearing_rows:
            self.clear_flash_ticks -= 1
            if self.clear_flash_ticks <= 0:
                self.finish_clear_lines()
            return
        if not self.try_move(dy=1):
            self.lock_piece()

    def drop(self):
        if self.game_over or self.clearing_rows:
            return
        while self.try_move(dy=1):
            self.score += 1
        self.lock_piece()

    def lock_piece(self):
        for cell in self.active.cells():
            x, y = cell
            if y < 0:
                self.game_over = True
                return
            self.board.add(cell)
        if self.start_clear_lines():
            return
        self.active = self.new_piece()

    def start_clear_lines(self):
        full_rows = [y for y in range(HEIGHT) if all((x, y) in self.board for x in range(WIDTH))]
        if not full_rows:
            return False
        self.clearing_rows = full_rows
        self.clear_flash_ticks = 6
        return True

    def finish_clear_lines(self):
        kept = []
        for x, y in self.board:
            if y not in self.clearing_rows:
                shift = sum(1 for row in self.clearing_rows if row > y)
                kept.append((x, y + shift))
        self.board = set(kept)
        cleared = len(self.clearing_rows)
        self.clearing_rows = []
        self.clear_flash_ticks = 0
        self.lines += cleared
        self.level = 1 + self.lines // 5
        self.score += [0, 100, 300, 500, 800][cleared] * self.level
        self.active = self.new_piece()

    def visible_cells(self, flash_on=True):
        cells = set(self.board)
        if self.clearing_rows and not flash_on:
            cells = {(x, y) for x, y in cells if y not in self.clearing_rows}
        if not self.game_over:
            cells |= {(x, y) for x, y in self.active.cells() if y >= 0}
        return cells

    def frame(self, flash_on=True):
        return cells_to_frame(self.visible_cells(flash_on), mirror_x=True)

    def gravity_interval(self):
        return max(0.12, 0.75 - (self.level - 1) * 0.08)


def score_frame(score, tick):
    text = str(score)
    cells = set()
    cursor = 0
    for digit in text:
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
    visible = {(x + offset, y) for x, y in cells if 0 <= x + offset < WIDTH}
    return cells_to_frame(visible, mirror_x=True)


def setup_colors(stdscr):
    if not curses.has_colors():
        return 0, 0
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    stdscr.bkgd(" ", curses.color_pair(1))
    return curses.color_pair(1), curses.color_pair(2)


def draw(stdscr, game, normal_attr=0, block_attr=0):
    stdscr.erase()
    stdscr.addstr(0, 0, "8x8 Tetris", normal_attr)
    flash_on = not game.clearing_rows or game.clear_flash_ticks % 2 == 1
    cells = game.visible_cells(flash_on)
    for y in range(HEIGHT):
        stdscr.addstr(y + 2, 0, "|", normal_attr)
        for x in range(WIDTH):
            attr = block_attr if (x, y) in cells else normal_attr
            stdscr.addstr(y + 2, 1 + x * 2, "  ", attr)
        stdscr.addstr(y + 2, 1 + WIDTH * 2, "|", normal_attr)
    stdscr.addstr(HEIGHT + 2, 0, "+" + "--" * WIDTH + "+", normal_attr)
    stdscr.addstr(HEIGHT + 4, 0, f"score {game.score}  lines {game.lines}  level {game.level}", normal_attr)
    stdscr.addstr(HEIGHT + 5, 0, "arrows/hjkl move  z/x/up rotate  space drop  r restart  q quit", normal_attr)
    if game.game_over:
        stdscr.addstr(HEIGHT + 7, 0, "GAME OVER - press r to restart or q to quit", normal_attr)
    stdscr.refresh()


def read_input(stdscr, game):
    while True:
        key = stdscr.getch()
        if key == -1:
            return True
        if key in (ord("q"), 27):
            return False
        if key in (ord("r"), ord("R")):
            game.reset()
            continue
        if game.game_over:
            continue
        if key in (curses.KEY_LEFT, ord("h"), ord("a")):
            game.try_move(dx=-1)
        elif key in (curses.KEY_RIGHT, ord("l"), ord("d")):
            game.try_move(dx=1)
        elif key in (curses.KEY_DOWN, ord("j"), ord("s")):
            if game.try_move(dy=1):
                game.score += 1
        elif key in (curses.KEY_UP, ord("x"), ord("k"), ord("w")):
            game.try_move(rotate=1)
        elif key == ord("z"):
            game.try_move(rotate=-1)
        elif key == ord(" "):
            game.drop()
        elif key in (ord("p"), ord("P")):
            stdscr.nodelay(False)
            stdscr.addstr(HEIGHT + 7, 0, "PAUSED - press any key")
            stdscr.getch()
            stdscr.nodelay(True)


def send_led_frame(client, game, blink_index):
    if game.game_over:
        client.send_binary(score_frame(game.score, blink_index))
    else:
        flash_on = not game.clearing_rows or game.clear_flash_ticks % 2 == 1
        client.send_binary(game.frame(flash_on))


def play(stdscr, args):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(0)
    stdscr.keypad(True)
    normal_attr, block_attr = setup_colors(stdscr)

    game = TetrisGame()
    client = WebSocketFrameClient(args.host, args.port, args.path)
    client.connect()

    frame_interval = 1.0 / args.fps
    next_frame = time.monotonic()
    next_gravity = next_frame + game.gravity_interval()
    blink_index = 0

    try:
        while True:
            if not read_input(stdscr, game):
                break

            now = time.monotonic()
            if not game.game_over and now >= next_gravity:
                was_clearing = bool(game.clearing_rows)
                game.tick()
                if game.clearing_rows:
                    next_gravity = now + args.clear_flash_interval
                elif was_clearing:
                    next_gravity = now + game.gravity_interval()
                else:
                    next_gravity = now + game.gravity_interval()

            if now >= next_frame:
                send_led_frame(client, game, blink_index)
                draw(stdscr, game, normal_attr, block_attr)
                if game.game_over:
                    blink_index += 1
                next_frame = now + frame_interval

            time.sleep(0.005)
    finally:
        client.send_binary(empty_frame())
        client.close()


def main():
    parser = argparse.ArgumentParser(description="Play local-keyboard Tetris on the 8x8 LED matrix.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--path", default=DEFAULT_PATH)
    parser.add_argument("--fps", type=float, default=30)
    parser.add_argument("--clear-flash-interval", type=float, default=0.08)
    args = parser.parse_args()
    curses.wrapper(play, args)


if __name__ == "__main__":
    main()
