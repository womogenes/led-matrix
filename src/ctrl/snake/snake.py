#!/usr/bin/env python3
import argparse
import curses
from collections import deque
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
    score_frame,
)


WIDTH = 8
HEIGHT = 8
DIRECTIONS = {
    "left": (-1, 0),
    "right": (1, 0),
    "up": (0, -1),
    "down": (0, 1),
}


class SnakeGame:
    def __init__(self):
        self.reset()

    def reset(self):
        self.snake = deque([(3, 4), (2, 4), (1, 4)])
        self.direction = "right"
        self.pending_direction = "right"
        self.score = 0
        self.game_over = False
        self.food = self.spawn_food()

    def spawn_food(self):
        open_cells = [
            (x, y)
            for y in range(HEIGHT)
            for x in range(WIDTH)
            if (x, y) not in self.snake
        ]
        return random.choice(open_cells) if open_cells else None

    def set_direction(self, direction):
        if self.game_over:
            return
        dx, dy = DIRECTIONS[direction]
        current_dx, current_dy = DIRECTIONS[self.direction]
        if (dx, dy) == (-current_dx, -current_dy):
            return
        self.pending_direction = direction

    def tick(self):
        if self.game_over:
            return
        self.direction = self.pending_direction
        dx, dy = DIRECTIONS[self.direction]
        head_x, head_y = self.snake[0]
        new_head = (head_x + dx, head_y + dy)

        if not (0 <= new_head[0] < WIDTH and 0 <= new_head[1] < HEIGHT):
            self.game_over = True
            return

        growing = new_head == self.food
        body = set(self.snake if growing else list(self.snake)[:-1])
        if new_head in body:
            self.game_over = True
            return

        self.snake.appendleft(new_head)
        if growing:
            self.score += 1
            self.food = self.spawn_food()
            if self.food is None:
                self.game_over = True
        else:
            self.snake.pop()

    def cells(self, food_on=True):
        cells = set(self.snake)
        if food_on and self.food is not None and not self.game_over:
            cells.add(self.food)
        return cells

    def frame(self, food_on=True):
        return cells_to_frame(self.cells(food_on), mirror_x=True)

    def tick_interval(self):
        return max(0.08, 0.28 - self.score * 0.01)


def setup_colors(stdscr):
    if not curses.has_colors():
        return 0, 0
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    stdscr.bkgd(" ", curses.color_pair(1))
    return curses.color_pair(1), curses.color_pair(2)


def draw(stdscr, game, tick, normal_attr=0, block_attr=0):
    stdscr.erase()
    stdscr.addstr(0, 0, "8x8 Snake", normal_attr)
    food_on = tick % 8 < 5
    cells = game.cells(food_on)
    for y in range(HEIGHT):
        stdscr.addstr(y + 2, 0, "|", normal_attr)
        for x in range(WIDTH):
            attr = block_attr if (x, y) in cells else normal_attr
            stdscr.addstr(y + 2, 1 + x * 2, "  ", attr)
        stdscr.addstr(y + 2, 1 + WIDTH * 2, "|", normal_attr)
    stdscr.addstr(HEIGHT + 2, 0, "+" + "--" * WIDTH + "+", normal_attr)
    stdscr.addstr(HEIGHT + 4, 0, f"score {game.score}", normal_attr)
    stdscr.addstr(HEIGHT + 5, 0, "arrows/hjkl/wasd move  p pause  r restart  q quit", normal_attr)
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
        if key in (curses.KEY_LEFT, ord("h"), ord("a")):
            game.set_direction("left")
        elif key in (curses.KEY_RIGHT, ord("l"), ord("d")):
            game.set_direction("right")
        elif key in (curses.KEY_UP, ord("k"), ord("w")):
            game.set_direction("up")
        elif key in (curses.KEY_DOWN, ord("j"), ord("s")):
            game.set_direction("down")
        elif key in (ord("p"), ord("P")):
            stdscr.nodelay(False)
            stdscr.addstr(HEIGHT + 7, 0, "PAUSED - press any key")
            stdscr.getch()
            stdscr.nodelay(True)


def send_led_frame(client, game, tick):
    if game.game_over:
        client.send_binary(score_frame(game.score, tick, mirror_x=True))
    else:
        food_on = tick % 8 < 5
        client.send_binary(game.frame(food_on))


def play(stdscr, args):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.timeout(0)
    stdscr.keypad(True)
    normal_attr, block_attr = setup_colors(stdscr)

    game = SnakeGame()
    client = WebSocketFrameClient(args.host, args.port, args.path)
    client.connect()

    frame_interval = 1.0 / args.fps
    next_frame = time.monotonic()
    next_tick = next_frame + game.tick_interval()
    tick = 0

    try:
        while True:
            if not read_input(stdscr, game):
                break

            now = time.monotonic()
            if not game.game_over and now >= next_tick:
                game.tick()
                next_tick = now + game.tick_interval()

            if now >= next_frame:
                send_led_frame(client, game, tick)
                draw(stdscr, game, tick, normal_attr, block_attr)
                tick += 1
                next_frame = now + frame_interval

            time.sleep(0.005)
    finally:
        client.send_binary(empty_frame())
        client.close()


def main():
    parser = argparse.ArgumentParser(description="Play local-keyboard Snake on the 8x8 LED matrix.")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--path", default=DEFAULT_PATH)
    parser.add_argument("--fps", type=float, default=30)
    args = parser.parse_args()
    curses.wrapper(play, args)


if __name__ == "__main__":
    main()
