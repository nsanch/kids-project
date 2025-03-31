#!/Users/nsanch/kids-project/.venv/bin/python

import curses
import math
import threading
import time
import random
import sys
import os
import json
from level_selector import LevelSelector
from buffered_window import BufferedCenterableWindow
from game_items import *

class DebugLogger(object):
  def __init__(self):
    self.log: list[str] = []

  def add(self, msg: str) -> None:
    self.log.append(msg)
    if len(self.log) > 3:
      self.log = self.log[-3:]

  def get_log_str(self) -> str:
    return '|'.join(self.log)

debugger: DebugLogger = DebugLogger()

class GameWindow(object):
  def __init__(self, stdscr):
    self.__stdscr = stdscr
    self.__status_area = stdscr.subwin(5, curses.COLS, 0, 0)
    self.__game_area = BufferedCenterableWindow(stdscr.subwin(curses.LINES - 5, curses.COLS, 5, 0))

  def status_area(self):
    return self.__status_area
  
  def game_area(self):
    return self.__game_area
  
  def clear(self):
    self.game_area().clear()
    self.status_area().clear()
    self.__stdscr.clear()

  def refresh(self, player_location):
    self.game_area().refresh(player_location)
    self.status_area().refresh()
    self.__stdscr.refresh()

class Game(object):
  # game states
  RUNNING = 0
  PAUSED = 1
  LOST = 2
  QUIT = 3
  WON = 4
  WAITING_FOR_NEXT_LEVEL = 5

  # results of tick()
  TICK_CONTINUING = 0
  TICK_LOSS = 1
  TICK_WIN = 2
  TICK_CPU_POINT = 3
  TICK_PLAYER_POINT = 4

  def __init__(self, initial_state, level):
    self.items = initial_state
    self.game_state = Game.RUNNING
    for i in self.items:
      if isinstance(i, Player):
        self.player = i
      elif isinstance(i, EndingFlag):
        self.ending_flag = i
    self.lock = threading.Lock()
    self.score = (0, 0)
    self.status_msg = None
    self.speed_boost = 0
    self.level = level

  def acquire_lock(self):
    self.lock.acquire()
  
  def release_lock(self):
    self.lock.release()

  def game_over(self):
    return self.game_state in [Game.LOST, Game.QUIT, Game.WON]
  
  def items_at(self, positions_to_check):
    ret = []
    for item in self.items:
      for position in positions_to_check:
        if position in item.positions():
          ret.append(item)
          break
    return ret
  
  def add_item(self, item):
    self.items.append(item)
  
  def debug_msg(self):
    #return ""
    x = []
    item = self.player
    if isinstance(item, MovableObject):
      x.append(f"Pos: {item.position}, Vel: {item.velocity}")
    return "|".join(x) + debugger.get_log_str()

  def tick(self):
    if self.game_over():
      # this shouldn't really get called if the game's over.
      return None
    
    for item in self.items:
      item.tick(self)
    self.items = [i for i in self.items if not i.should_be_removed_from_game() or i == self.player]

    
    if self.ending_flag.had_collision:
      return Game.TICK_WIN
    
    if self.player.should_be_removed_from_game():
      return Game.TICK_LOSS

    return Game.TICK_CONTINUING
  
  def render(self, game_window: GameWindow):
    game_window.clear()
    for item in self.items:
      item.render(game_window.game_area())
    if self.status_msg is not None:
      height, width = game_window.status_area().getmaxyx()
      game_window.status_area().addstr(2, (width - len(self.status_msg)) // 2, self.status_msg)
    game_window.status_area().addstr(1, 0, "Type 'e' to exit. 'r' to restart. 'p' to pause. Up/left/right/down to move.")
    game_window.status_area().addstr(3, 0, self.debug_msg())
    game_window.status_area().hline(4, 0, '-', curses.COLS)
    game_window.refresh(self.player.positions())

  def refresh_window(self, game_window: GameWindow):
    try:
      self.acquire_lock()
      
      if self.game_state == Game.RUNNING:
        tick_result = self.tick()

        if tick_result == Game.TICK_WIN:
          self.status_msg = "You've completed the level! 's' to pick a level, 'p' for next, 'e' to exit, 'r' to restart."
          self.game_state = Game.WON
        elif tick_result == Game.TICK_LOSS:
          self.status_msg = "Oh no! You died. :( :( Hit 'r' to restart or 'e' to exit."
          self.game_state = Game.LOST
    
      player_location = self.player.positions()
      game_window.game_area().center_around(player_location)
      self.render(game_window)

      def task():
        self.refresh_window(game_window)

      if not self.game_over():
        threading.Timer(self.speed(), task).start()
    finally:
      self.release_lock()

  def speed(self):
    total_score = self.score[0] + self.score[1]
    base_speed = 0.1
    adjustment_by_score = 0.005*total_score
    boost_multiplier = 1
    boost_denominator = 1
    if self.speed_boost < 0:
      boost_multiplier = -1 * self.speed_boost
    else:
      boost_denominator = 1 + self.speed_boost
    max_speed = 0.02
    min_speed = 0.5

    return min(min_speed, max(max_speed, ((base_speed - adjustment_by_score) * boost_multiplier) / boost_denominator))
  
  def accept_keypress(self, k, stdscr: curses.window):
    try:
      self.acquire_lock()
      if k == "p":
        if self.game_state in [Game.PAUSED, Game.WAITING_FOR_NEXT_LEVEL]:
          self.game_state = Game.RUNNING
          self.status_msg = None
        else:
          self.game_state = Game.PAUSED
          self.status_msg = "Game paused. Press 'p' to continue."
      elif k == " " or k == "KEY_UP":
        self.player.jump()
      elif k == "f":
        self.player.fire(self)
      elif k == "KEY_RIGHT":
        self.player.right()
      elif k == "KEY_LEFT":
        self.player.left()
      elif k == "KEY_DOWN":
        self.player.down()
      elif k == "e":
        self.game_state = Game.QUIT
      elif k == "f":
        self.speed_boost = min(5, 1 + self.speed_boost)
      elif k == "s":
        self.speed_boost = max(-5, self.speed_boost - 1)
    finally:
      self.release_lock()

def load_initial_state(fname):
  with open(fname, "r") as f:
    input = f.readlines()

  stuff = []
  for y in range(len(input)):
    row = input[y]
    # 0,0 in the input is y_max,0 in the game. y_max = len(input) - 1
    game_y = len(input) - y - 1
    for x in range(len(row)):
      ch = row[x]
      game_pos = (game_y, x)
      item = get_game_object_for_name(ch, game_pos)
      if item is not None:
        stuff.append(item)

  return stuff

def play_game(stdscr, level):
  stdscr.clear()

  game = Game(load_initial_state(f"/Users/nsanch/kids-project/side-scroller-levels/level{level}.txt"), level)
  game.refresh_window(GameWindow(stdscr))

  while game.game_state != Game.QUIT:
    k = stdscr.getkey()
    if game.game_over():
      if k == 'p':
        if game.game_state == Game.WON:
          play_game(stdscr, level=level + 1)
        else:
          play_game(stdscr, level=level)
        break
      elif k == 's':
        select_level(stdscr)
        break
      elif k == 'r':
        play_game(stdscr, level=level)
        break
      elif k == 'e':
        break
      else:
        pass
    else:
      game.accept_keypress(k, stdscr)

def select_level(stdscr):
  level_selector = LevelSelector(stdscr, "/Users/nsanch/kids-project/side-scroller-levels")
  selected_level = level_selector.render_and_get_selected_level()
  play_game(stdscr, selected_level)
 
curses.wrapper(select_level)