#!/Users/nsanch/kids-project/.venv/bin/python

import curses
import math
import threading
import time
import random
import sys
import os
import json

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

def sign(x: int) -> int:
  if x < 0:
    return -1
  elif x > 0:
    return 1
  return 0

class GameArea(object):
  def __init__(self, win: curses.window):
    self.__win = win
    self.__buffer = {}

  def clear(self):
    self.__buffer = {}
    self.__win.clear()
  
  def refresh(self, player_location: list[tuple[int, int]]):
    max_y = max([k[0] for k in self.__buffer.keys()])
    max_x = max([k[1] for k in self.__buffer.keys()])
    if max_y < self.__win.getmaxyx()[0] and max_x < self.__win.getmaxyx()[1]:
      for (y,x), ch in self.__buffer.items():
        game_y = y
        game_x = x
        screen_y = self.__win.getmaxyx()[0] - game_y - 1
        self.__win.addch(screen_y, x, ch)
    else:
      bottom_left, top_right = self.center_around(player_location)
      for (y,x), ch in self.__buffer.items():
        if y < bottom_left[0] or y >= top_right[0]:
          continue
        if x < bottom_left[1] or x >= top_right[1]:
          continue
        game_y = y - bottom_left[0]
        game_x = x - bottom_left[1]
        screen_y = self.__win.getmaxyx()[0] - game_y - 1
        screen_x = game_x
        maxyx = self.__win.getmaxyx()
        # cannot write to bottom-right corner for some reason.
        if screen_y == maxyx[0]-1 and screen_x == maxyx[1]-1:
          continue
        self.__win.addch(screen_y, screen_x, ch)
    self.__win.refresh()

  def center_around(self, player_location: list[tuple[int, int]]):
    game_window_height, game_window_width = self.__win.getmaxyx()
    player_min_x = min([l[1] for l in player_location])
    player_min_y = min([l[0] for l in player_location])
    # center the player horizontally, but vertically keep them near the bottom.
    bottom = player_min_y - 10
    if bottom < 0:
      bottom = 0
    left = player_min_x - (game_window_width // 2)
    if left < 0:
      left = 0
    bottom_left = (bottom, left)
    top_right = bottom_left[0] + game_window_height, bottom_left[1] + game_window_width
    return bottom_left, top_right

  def addch(self, y: int, x: int, ch: str) -> None:
    self.__buffer[(y, x)] = ch

class GameWindow(object):
  def __init__(self, stdscr):
    self.__stdscr = stdscr
    self.__status_area = stdscr.subwin(5, curses.COLS, 0, 0)
    self.__game_area = GameArea(stdscr.subwin(curses.LINES - 5, curses.COLS, 5, 0))

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

class Collidable(object):
  def __init__(self):
    pass

  def addch(self, stdscr: GameArea, pos: tuple[int, int], ch: str) -> None:
    stdscr.addch(pos[0], pos[1], ch)

  def addstr(self, stdscr: GameArea, pos: tuple[int, int], s: str) -> None:
    for ch, i in zip(s, range(len(s))):
      self.addch(stdscr, (pos[0], pos[1] + i), ch)

  def addstr_vert(self, stdscr: GameArea, pos: tuple[int, int], s: str) -> None:
    for ch, i in zip(s, range(len(s))):
      self.addch(stdscr, (pos[0] + (len(s) - 1) - i, pos[1]), ch)

  def tick(self, game) -> None:
    pass

  def render(self, stdscr: GameArea) -> None:
    pass

  def collide(self, other_object) -> None:
    pass

  def kills_player_on_collision(self) -> bool:
    return False


class MovableObject(Collidable):
  def __init__(self, position: tuple[int, int], velocity: tuple[int, int]):
    self.position = position
    self.velocity = velocity

  def adjust_velocity(self, new_abs_x: int|None=None, new_abs_y: int|None=None, relative_x: int|None=None, relative_y: int|None=None):
    if new_abs_y is not None:
      self.velocity = (new_abs_y, self.velocity[1])
    if new_abs_x is not None:
      self.velocity = (self.velocity[0], new_abs_x)
    if relative_y is not None:
      self.velocity = (self.velocity[0] + relative_y, self.velocity[1])
    if relative_x is not None:
      self.velocity = (self.velocity[0], self.velocity[1] + relative_x)

    max_y_velocity: int = 4
    max_x_velocity: int = 2
    if abs(self.velocity[0]) > max_y_velocity:
      self.velocity = (sign(self.velocity[0]) * max_y_velocity, self.velocity[1])
    if abs(self.velocity[1]) > max_x_velocity:
      self.velocity = (self.velocity[0], sign(self.velocity[1]) * max_y_velocity)

  def chars(self) -> str:
    return ""

  def experiences_gravity(self) -> bool:
    return False

  def tick(self, game) -> None:
    remaining_velocity: tuple[int, int] = self.velocity
    while abs(remaining_velocity[0]) > 0 or abs(remaining_velocity[1]) > 0:
      # not quite perfect because if we need to do (3,1) then we'll do (1,1) then (1,0) and (1,0) which
      # may be a little wrong sometimes.
      y_movement: int = sign(remaining_velocity[0])
      x_movement: int = sign(remaining_velocity[1])
      remaining_velocity: tuple[int, int] = (remaining_velocity[0] - y_movement, remaining_velocity[1] - x_movement)

      next_position = self.position[0] + y_movement, self.position[1] + x_movement
      other_items = game.items_at(self.positions(start_pos=next_position))
      if len(other_items) == 0 or other_items == [self]:
        self.position = next_position
      else:
        for other_item in other_items:
          if self == other_item:
            continue
          self.collide(other_item)
          other_item.collide(self)
        remaining_velocity = (0, 0)
  
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

  def positions(self, start_pos=None) -> list[tuple[int, int]]:
    ret = []
    pos = start_pos if start_pos is not None else self.position
    for h in range(len(self.chars())):
      ret.append((pos[0] + h, pos[1]))
    return ret

  def render(self, stdscr: GameArea):
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
              ((0 < y_delta <= self.velocity[0]) or
               (0 > y_delta >= self.velocity[0]))):
            stop_in_y = True
          if (y_delta == 0 and 
              ((0 < x_delta <= self.velocity[1]) or
               (0 > x_delta >= self.velocity[1]))):
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
    return "bb"
  
  def kills_player_on_collision(self):
    return True

class Bird(MovableObject):
  def __init__(self, initial_pos):
    super().__init__(initial_pos, (0, -1))
    self.last_reversal = 0
    self.flap_indicator = 0

  def experiences_gravity(self):
    return False

  def tick(self, game):
    super().tick(game)
    self.last_reversal += 1
    if self.last_reversal > 10:
      self.last_reversal = 0
      self.velocity = (self.velocity[0], -1 * self.velocity[1])

  def chars(self):
    self.flap_indicator = (self.flap_indicator + 1) % 10
    if self.flap_indicator < 5:
      return "W"
    else:
      return "w"

  def kills_player_on_collision(self):
    return True

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
    if self.is_little:
      self.adjust_velocity(new_abs_y=3)
    else:
      self.adjust_velocity(new_abs_y=5)

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
    elif other_object.kills_player_on_collision():
      self.is_dead = True

class Edamame(Collidable):
  def __init__(self, pos):
    self.position = pos

  def positions(self):
    return [self.position]

  def render(self, stdscr: GameArea):
    self.addch(stdscr, (self.position[0], self.position[1]), "E")

class Brick(Collidable):
  def __init__(self, pos):
    self.position = pos

  def positions(self):
    return [self.position]

  def render(self, stdscr: GameArea):
    self.addch(stdscr, self.position, "=")

class Fire(Collidable):# there should be a special fire
  def __init__(self, pos):
    self.position = pos
    self.size_indicator = random.randint(0, 10)
    self.num_fire = 1

  def tick(self, game):
    super().tick(game)
    self.size_indicator = (self.size_indicator + 1) % 20
    if self.size_indicator > 15:
      self.num_fire = 2
    elif self.size_indicator > 7:
      self.num_fire = 1
    else:
      self.num_fire = 0  

  def positions(self):
    ret = []
    for i in range(self.num_fire):
      ret.append((self.position[0] + i, self.position[1]))
    return ret

  def render(self, stdscr: GameArea):
    self.addstr_vert(stdscr, self.position, "🔥" * self.num_fire)

  def kills_player_on_collision(self):
    return True

class Tree(Collidable):
  def __init__(self, pos):
    self.position = pos
    self.chars = "TTT"

  def positions(self):
    ret = []
    for i in range(len(self.chars)):
      ret.append((self.position[0] + i, self.position[1]))
    return ret

  def render(self, stdscr: GameArea):
    self.addstr_vert(stdscr, self.position, self.chars)

  def kills_player_on_collision(self):
    return True

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

  def render(self, stdscr: GameArea):
    self.addstr_vert(stdscr, self.position, self.chars)

  def collide(self, other_object):
    if isinstance(other_object, Player):
      self.had_collision = True

class Fireball(MovableObject):
  def __init__(self, pos, velocity):
    super().__init__(pos, velocity)

  def chars(self) -> str:
    return "O"

  def experiences_gravity(self):
    return True

  def kills_player_on_collision(self):
    return True

class Canon(Collidable):
  def __init__(self, pos):
    self.position = pos
    self.chars = "/"
    self.tick_counter = 0

  def positions(self):
    ret = []
    for i in range(len(self.chars)):
      ret.append((self.position[0] + i, self.position[1]))
    return ret

  def tick(self, game):
    super().tick(game)
    self.tick_counter += 1
    if self.tick_counter % 10 == 0:
      game.add_item(Fireball((self.position[0] + 1, self.position[1]), (2, 2)))

  def render(self, stdscr: GameArea):
    self.addch(stdscr, self.position, self.chars)

class Game(object):
  FINAL_LEVEL = 9

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
    return ""
    #x = []
    #for item in self.items:
    #  if isinstance(item, MovableObject):
    #    x.append(f"Pos: {item.position}, Vel: {item.velocity}")
    #return "|".join(x) + debugger.get_log_str()

  def tick(self):
    if self.game_over():
      # this shouldn't really get called if the game's over.
      return None
    
    for item in self.items:
      item.tick(self)
    
    if self.ending_flag.had_collision:
      return Game.TICK_WIN
    
    if self.player.is_dead:
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
          if self.level == Game.FINAL_LEVEL:
            self.status_msg = "You win the game! Woohoo! Hit 'e' to exit or 'r' to restart."
          else:
            self.status_msg = "You've completed the level! Hit 'p' to play the next level, 'r' to restart or 'e' to exit."
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
      elif ch == "W":
        stuff.append(Bird(game_pos))
      elif ch == "🔥":
        stuff.append(Fire(game_pos))
      elif ch == "C":
        stuff.append(Canon(game_pos))


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
      elif k in ['1','2','3','4','5','6','7','8','9']:
        play_game(stdscr, level=int(k))
        break
      elif k == 'r':
        play_game(stdscr, level=level)
        break
      else:
        pass
    else:
      game.accept_keypress(k, stdscr)
 
#curses.initscr()
#curses.resizeterm(40, 100)
curses.wrapper(play_game, int(sys.argv[1]) if len(sys.argv) > 1 else 1)