#!/Users/nsanch/kids-project/.venv/bin/python

import curses
import threading
import time
import random
import sys
import os
import json

class DebugLogger(object):
  def __init__(self):
    self.log = []

  def add(self, msg):
    self.log.append(msg)
    if len(self.log) > 3:
      self.log = self.log[-3:]

  def get_log_str(self):
    return '|'.join(self.log)

debugger = DebugLogger()

class Collidable(object):
  def __init__(self):
    pass

  def addch(self, stdscr, pos, ch):
    # 0,0 in the game is y_max,0 in the rendering.
    game_y = pos[0]
    screen_y = curses.LINES - game_y - 1
    stdscr.addch(screen_y, pos[1], ch)

  def addstr(self, stdscr, pos, s):
    for ch, i in zip(s, range(len(s))):
      self.addch(stdscr, (pos[0], pos[1] + i), ch)

  def addstr_vert(self, stdscr, pos, s):
    for ch, i in zip(s, range(len(s))):
      self.addch(stdscr, (pos[0] + (len(s) - 1) - i, pos[1]), ch)

  def tick(self, game):
    pass

  def render(self, stdscr):
    pass

  def collide(self, other_object):
    pass


class MovableObject(Collidable):
  def __init__(self, position, velocity):
    self.position = position
    self.velocity = velocity

  def adjust_velocity(self, new_abs_x=None, new_abs_y=None, relative_x=None, relative_y=None):
    if new_abs_y is not None:
      self.velocity = (new_abs_y, self.velocity[1])
    if new_abs_x is not None:
      self.velocity = (self.velocity[0], new_abs_x)
    if relative_y is not None:
      self.velocity = (self.velocity[0] + relative_y, self.velocity[1])
    if relative_x is not None:
      self.velocity = (self.velocity[0], self.velocity[1] + relative_x)

    # clunky but simple to read -- just keep velocity wthin the bounds of (-1, 1) in both directions.
    if self.velocity[0] < -1:
      self.velocity = (-1, self.velocity[1])
    if self.velocity[0] > 1:
      self.velocity = (1, self.velocity[1])
    if self.velocity[1] < -1:
      self.velocity = (self.velocity[0], -1)
    if self.velocity[1] > 1:
      self.velocity = (self.velocity[0], 1)

  def chars(self):
    pass

  def experiences_gravity(self):
    return False

  def tick(self, game):
    next_position = self.position[0] + self.velocity[0], self.position[1] + self.velocity[1]
    other_items = game.items_at(self.positions(start_pos=next_position))
    if len(other_items) == 0 or other_items == [self]:
      self.position = next_position
    else:
      for other_item in other_items:
        if self == other_item:
          continue
        self.collide(other_item)
        other_item.collide(self)
  
    if self.experiences_gravity():
      self.apply_gravity(game)

  def apply_gravity(self, game):
    # if nothing is below our lowest point, then we should fall.
    lowest_pos = min(self.positions(), key=lambda x: x[0])
    below_us = game.items_at([(lowest_pos[0] - 1, lowest_pos[1])])
    if len(below_us) == 0:
      self.adjust_velocity(relative_y=-1)
    elif self.velocity[0] < 0:
      # there's something below us, we can't fall.
      self.adjust_velocity(new_abs_y=0)

  def positions(self, start_pos=None):
    ret = []
    pos = start_pos if start_pos is not None else self.position
    for h in range(len(self.chars())):
      ret.append((pos[0] + h, pos[1]))
    return ret

  def render(self, stdscr):
    for pos, ch in zip(self.positions(), self.chars()):
      self.addch(stdscr, (pos[0], pos[1]), ch)
  
  def collide(self, other_object):
    if isinstance(other_object, Brick):
      # literally ran into a wall, stop
      stop_in_y = False
      stop_in_x = False
      for self_p in self.positions():
        for other_p in other_object.positions():
          y_delta = other_p[0] - self_p[0]
          x_delta = other_p[1] - self_p[1]
          if (x_delta == 0 and
              ((y_delta == 1 and self.velocity[0] == 1) or
               (y_delta == -1 and self.velocity[0] == -1))):
            stop_in_y = True
          if (y_delta == 0 and 
              ((x_delta == 1 and self.velocity[1] == 1) or
               (x_delta == -1 and self.velocity[1] == -1))):
            stop_in_x = True
      if stop_in_y:
        self.adjust_velocity(new_abs_y=0)
      if stop_in_x:
        self.adjust_velocity(new_abs_x=0)

class LittleBadGuy(MovableObject):
  def __init__(self, initial_pos):
    super().__init__(initial_pos, (0, -1))
    self.last_reversal = 0

  def experiences_gravity(self):
    return True

  def tick(self, game):
    super().tick(game)
    self.last_reversal += 1
    if self.last_reversal > 10:
      self.last_reversal = 0
      self.velocity = (self.velocity[0], -1 * self.velocity[1])

  def chars(self):
    return "BB"

class Player(MovableObject):
  CHARS = "MM"
  MEGA_CHARS = "MMM"

  def __init__(self, pos):
    super().__init__(pos, (0, 0))

    self.is_little = True
    self.is_dead = False

  def experiences_gravity(self):
    return True
  
  def toggle_mega(self):
    self.is_little = not self.is_little

  def chars(self):
    if self.is_little:
      return Player.CHARS
    else:
      return Player.MEGA_CHARS

  def jump(self):
    self.adjust_velocity(new_abs_y=3)

  def right(self):
    self.adjust_velocity(relative_x=1)

  def left(self):
    self.adjust_velocity(relative_x=-1)

  def down(self):
    self.adjust_velocity(relative_y=-2)

  def collide(self, other_object):
    super().collide(other_object)
    if isinstance(other_object, Edamame):
      self.is_little = False
    elif isinstance(other_object, LittleBadGuy) or isinstance(other_object, Tree):
      self.is_dead = True

class Edamame(Collidable):
  def __init__(self, pos):
    self.position = pos

  def positions(self):
    return [self.position]

  def render(self, stdscr):
    self.addch(stdscr, (self.position[0], self.position[1]), "E")

class Brick(Collidable):
  def __init__(self, pos):
    self.position = pos

  def positions(self):
    return [self.position]

  def render(self, stdscr):
    self.addch(stdscr, (self.position[0], self.position[1]), "=")


class Tree(Collidable):
  def __init__(self, pos):
    self.position = pos
    self.chars = "TTT"

  def positions(self):
    ret = []
    for i in range(len(self.chars)):
      ret.append((self.position[0] + i, self.position[1]))
    return ret

  def render(self, stdscr):
    self.addstr_vert(stdscr, self.position, self.chars)

class EndingFlag(Collidable):
  def __init__(self, pos):
    self.position = pos
    self.had_collision = False
    self.chars = "WINHERE"

  def positions(self):
    ret = []
    for i in range(len(self.chars)):
      ret.append((self.position[0] + i, self.position[1]))
    return ret

  def render(self, stdscr):
    self.addstr_vert(stdscr, self.position, self.chars)

  def collide(self, other_object):
    self.had_collision = True

class Game(object):
  FINAL_LEVEL = 4

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
  
  def debug_msg(self):
    return ""
    #x = []
    #for item in self.items:
    #  if isinstance(item, MovableObject):
    #    x.append(f"Pos: {item.position}, Vel: {item.velocity}")
    #return "|".join(x) + debugger.get_log_str()

  def tick(self):
    if self.game_over():
      return False
    
    for item in self.items:
      item.tick(self)
    
    if self.ending_flag.had_collision:
      return Game.TICK_WIN
    
    if self.player.is_dead:
      return Game.TICK_LOSS

    return Game.TICK_CONTINUING
  
  def render(self, stdscr):
    stdscr.clear()
    for item in self.items:
      item.render(stdscr)
    if self.status_msg is not None:
      stdscr.addstr(curses.LINES // 2, (curses.COLS - len(self.status_msg)) // 2, self.status_msg)      
    stdscr.addstr(1, 0, "Type 'e' to exit. 'r' to restart. 'p' to pause. Up/left/right/down to move.")
    stdscr.addstr(4, 0, self.debug_msg())
    stdscr.refresh()

  def refresh_window(self, stdscr):
    try:
      self.acquire_lock()

      if self.game_over():
        return
      
      if self.game_state == Game.RUNNING:
        tick_result = self.tick()
        if tick_result == Game.TICK_WIN:
          if self.level == Game.FINAL_LEVEL:
            self.status_msg = "You win the game! Woohoo! Hit 'e' to exit or 'r' to restart."
          else:
            self.status_msg = "You've completed the level! Hit 'p' to play the next level, 'r' to restart or 'e' to exit."
          self.game_state = Game.WON
        elif tick_result == Game.TICK_LOSS:
          self.status_msg = "Oh no! You died. :( :( Hit 'r' to restart or 'e' to exit."
          self.game_state = Game.LOST
        
      self.render(stdscr)

      def task():
        self.refresh_window(stdscr)

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

    return max(base_speed, (base_speed - adjustment_by_score) * boost_multiplier) / boost_denominator
    return max(0.1 - (total_score * 0.005), 0.02) / (1 + self.speed_boost)
  
  def accept_keypress(self, k, stdscr):
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
        self.speed_boost = max(0, self.speed_boost - 1)
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
      if ch == " ":
        pass
      elif ch == "=":
        stuff.append(Brick(game_pos))
      elif ch == "P":
        stuff.append(Player(game_pos))
      elif ch == "E":
        stuff.append(Edamame(game_pos))
      elif ch == "b":
        stuff.append(LittleBadGuy(game_pos))
      elif ch == "F":
        stuff.append(EndingFlag(game_pos))
      elif ch == "T":
        stuff.append(Tree(game_pos))
  
  return stuff

def play_game(stdscr, level):
  stdscr.clear()

  game = Game(load_initial_state(f"/Users/nsanch/kids-project/side-scroller-levels/level{level}.txt"), level)
  game.refresh_window(stdscr)

  while game.game_state != Game.QUIT:
    k = stdscr.getkey()
    if game.game_over():
      if k == 'p':
        play_game(stdscr, level=level + 1)
      elif k in ['1','2','3','4','5','6','7','8','9']:
        play_game(stdscr, level=int(k))
      elif k == 'r':
        play_game(stdscr, level=level)
      elif k == 'e':
        break
    else:
      game.accept_keypress(k, stdscr)
 
curses.initscr()
curses.resizeterm(40, 100)
curses.wrapper(play_game, sys.argv[1] if len(sys.argv) > 1 else 1)