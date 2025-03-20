#!/Users/nsanch/kids-project/.venv/bin/python

import curses
import threading
import random
import os
import json

class SavedState(object):
  VERSION = 1

  def __init__(self):
    self.fname: str = os.path.join(os.getenv("HOME"), ".dino") # type: ignore
    self.load()
    self.save()

  def load(self):
    default_new_state = { "high_score": 0, "version": 1 }
    if os.path.exists(self.fname):
      with open(self.fname, "r") as f:
        input = f.read()
        try:
          self.state = json.loads(input)

          if self.state is None or len(self.state) == 0:
            self.state = default_new_state

          if self.state.get("version", 0) != SavedState.VERSION:
            self.state = self.upgrade(self.state)
        except json.JSONDecodeError:
          self.state = default_new_state
    else:
      self.state = default_new_state

  def upgrade(self, old_state):
    if old_state.get("version", 0) < SavedState.VERSION:
      new_state = {}
      new_state["version"] = SavedState.VERSION
      new_state["high_score"] = old_state["high_score"] // 10
      return new_state
    return old_state

  def save(self):
    with open(self.fname, "w") as f:
      json.dump(self.state, f)

  def maybe_update_high_score(self, newscore):
    if newscore > self.high_score():
      self.state["high_score"] = newscore
      self.save()
      return True
    return False

  def high_score(self):
    return self.state.get("high_score", 0)
  
class Renderable(object):
  def __init__(self):
    pass

  def render(self, stdscr: curses.window, i: int) -> None:
    pass

  def tick(self) -> None:
    pass

class Empty(Renderable):
  def __init__(self):
    pass

  def tick(self):
    pass

  def render(self, stdscr, i):
    stdscr.addch(curses.LINES - 1, i, ".")
  
class Dino(Renderable):
  CHARS = "DDDDD"
  MEGA_CHARS = CHARS * 3

  def __init__(self):
    self.height = 0
    self.upcoming_heights = None
    self.chars = Dino.CHARS

  def tick(self) -> None:
    if self.upcoming_heights is not None:
      self.height = self.upcoming_heights.pop(0)
      if len(self.upcoming_heights) == 0:
        self.upcoming_heights = None

  def render(self, stdscr, i) -> None:
    for h in range(len(self.chars)):
      stdscr.addch(curses.LINES - 1 - (self.height + h), i, self.chars[h])

  def jump(self) -> None: 
    # 1 to N-1, N, N, N, N-1 to 1
    if self.upcoming_heights is None:
      self.upcoming_heights = list(range(1, len(self.chars))) + (3*[len(self.chars)]) + list(range(len(self.chars), -1, -1))

  def mega(self) -> None:
    if self.chars == Dino.CHARS:
      self.chars = Dino.MEGA_CHARS
    else:
      self.chars = Dino.CHARS

  def y_positions(self) -> list[int]:
    return list(range(self.height, self.height + len(self.chars), 1))

class Obstacle(Renderable):
  def __init__(self):
    pass

  def render(self, stdscr, i) -> None:
    pass

  def tick(self) -> None:
    pass

  def y_positions(self) -> list[int]: # type: ignore
    pass

  def difficulty(self) -> int:
    return 1

class Tree(Obstacle):
  CHARS = "TTT"
  MEGA_CHARS = "MT" * 5
  
  def __init__(self, is_mega: bool):
    if is_mega:
      self.chars = Tree.MEGA_CHARS
    else:
      self.chars = Tree.CHARS

  def render(self, stdscr: curses.window, i: int) -> None:
    for h in range(len(self.chars)):
      stdscr.addch(curses.LINES - 1 - h, i, self.chars[h])

  def y_positions(self) -> list[int]:
    return list(range(len(self.chars)))
  
  def difficulty(self) -> int:
    return 3 * len(self.chars)
  
class Bird(Obstacle):
  FLAPS: list[str] = ["W", "w"]

  def __init__(self, is_tall: bool):
    if is_tall:
      self.y = 8
    else:
      self.y = 3
    self.flappy_index: int = 0

  def tick(self) -> None:
    self.flappy_index = (self.flappy_index + 1) % len(self.FLAPS)

  def chars(self) -> str:
    return Bird.FLAPS[self.flappy_index]
  
  def render(self, stdscr: curses.window, i: int) -> None:
    stdscr.addch(curses.LINES - 1 - self.y, i, self.chars()) 
    stdscr.addch(curses.LINES - 1, i, ".")
  
  def y_positions(self) -> list[int]:
    return [self.y]
  
  def difficulty(self) -> int:
    return self.y * 5

class Game(object):
  MIN_DIST_BETWEEEN_TREES = 30
  DINO_POS = 2

  RUNNING = 0
  PAUSED = 1
  LOST = 2
  QUIT = 3

  def __init__(self):
    self.dino: Dino = Dino()
    self.next_n_columns: list[Renderable] = [Empty() for i in range(Game.DINO_POS)]
    self.last_obstacle: int = 0
    self.game_state: int = Game.RUNNING
    self.points: int = 0
    self.lock: threading.Lock = threading.Lock()
    self.saved_state: SavedState = SavedState()
    for i in range(curses.COLS-1 - Game.DINO_POS - 1):
      self.next_n_columns.append(self.next_up())

  def acquire_lock(self) -> None:
    self.lock.acquire()
  
  def release_lock(self) -> None:
    self.lock.release()

  def game_over(self) -> bool:
    return self.game_state in [Game.LOST, Game.QUIT]

  def next_up(self) -> Renderable:
    if self.last_obstacle >= Game.MIN_DIST_BETWEEEN_TREES:
      if random.randint(0, 100) < 10:
        self.last_obstacle = 0
        dice_roll = random.randint(0, 100)
        if dice_roll < 10:
          return Tree(is_mega=True)
        elif dice_roll < 20:
          return Bird(is_tall=True)
        elif dice_roll < 30:
          return Bird(is_tall=False)
        else:
          return Tree(is_mega=False)
    self.last_obstacle += 1
    return Empty()
  
  def tick(self) -> bool:
    if self.game_over(): 
      return False
    
    self.next_n_columns.pop(0)
    closest: Renderable = self.next_n_columns[Game.DINO_POS + 1]
    if isinstance(closest, Obstacle):
      dino_pos = self.dino.y_positions()
      obstacle_pos = closest.y_positions()
      if any([y in dino_pos for y in obstacle_pos]):
        self.game_state = Game.LOST
        return False
      else:
        self.points += closest.difficulty()
    else:
      self.points += 1
    
    self.next_n_columns.append(self.next_up())

    for item in self.next_n_columns:
      item.tick()
    self.dino.tick()

    return True

  def refresh_window(self, stdscr):
    try:
      self.acquire_lock()

      if self.game_over():
        return
      
      if self.game_state == Game.PAUSED:
        stdscr.addstr(5, 0, "Game paused. Press 'p' to continue.")
        stdscr.refresh()
      elif not self.tick():
        if self.saved_state.maybe_update_high_score(self.points):
          stdscr.addstr(5, 0, "NEW HIGH SCORE! Press 'e' to exit or press r to restart.")
        else:
          stdscr.addstr(5, 0, "Game over! Press 'e' to exit or press r to restart.")

        stdscr.refresh()
        return
      
      stdscr.clear()
      
      for i in range(len(self.next_n_columns)):
        self.next_n_columns[i].render(stdscr, i)
      self.dino.render(stdscr, Game.DINO_POS)

      stdscr.addstr(0, 0, f"Score: {self.points}")
      stdscr.addstr(1, 0, f"High Score: {self.saved_state.high_score()}")
      stdscr.addstr(2, 0, "Type 'e' to exit, Space to jump, 'm' to mega. 'p' to pause.")
      stdscr.refresh()

      def task():
        self.refresh_window(stdscr)

      if not self.game_over():
        threading.Timer(self.speed(), task).start()
    finally:
      self.release_lock()

  def speed(self):
    return 0.1
  
  def accept_keypress(self, k):
    try:
      self.acquire_lock()
      if k == "p":
        if self.game_state == Game.PAUSED:
          self.game_state = Game.RUNNING
        else:
          self.game_state = Game.PAUSED
      elif k == " ":
        self.dino.jump()
      elif k == "m":
        self.dino.mega()
      elif k == "e":
        self.game_state = Game.QUIT
        self.saved_state.maybe_update_high_score(self.points)
    finally:
      self.release_lock()

def play_game(stdscr):
  stdscr.clear()

  game = Game()
  game.refresh_window(stdscr)

  while game.game_state != Game.QUIT:
    k = stdscr.getkey()
    if game.game_over():
      if k == 'r':
        play_game(stdscr)
        break
      elif k == 'e':
        break
    else:
      game.accept_keypress(k)

curses.wrapper(play_game)