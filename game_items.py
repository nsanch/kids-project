#!/Users/nsanch/kids-project/.venv/bin/python

import curses
import math
import threading
import time
import random
import sys
import os
import json
from buffered_window import BufferedCenterableWindow

def sign(x: int) -> int:
  if x < 0:
    return -1
  elif x > 0:
    return 1
  return 0

class InventoryItem(object):
  def __init__(self):
    pass

  def fire(self, game, shooter):
    pass

  def should_be_removed(self) -> bool:
    return False

class GameObject(object):
  def __init__(self):
    self.should_be_removed: bool = False

  def addch(self, stdscr: BufferedCenterableWindow, pos: tuple[int, int], ch: str) -> None:
    stdscr.addch(pos[0], pos[1], ch)

  def addstr(self, stdscr: BufferedCenterableWindow, pos: tuple[int, int], s: str) -> None:
    for ch, i in zip(s, range(len(s))):
      self.addch(stdscr, (pos[0], pos[1] + i), ch)

  def addstr_vert(self, stdscr: BufferedCenterableWindow, pos: tuple[int, int], s: str) -> None:
    for ch, i in zip(s, range(len(s))):
      self.addch(stdscr, (pos[0] + (len(s) - 1) - i, pos[1]), ch)

  def tick(self, game) -> None:
    pass

  def render(self, stdscr: BufferedCenterableWindow) -> None:
    pass

  def collide(self, other_object) -> None:
    pass

  def kills_on_collision(self, other_object) -> bool:
    return False
  
  def signal_removal_from_game(self):
    self.should_be_removed = True
  
  def should_be_removed_from_game(self) -> bool:
    return self.should_be_removed
  
  def grants_item(self) -> bool:
    return False

  def grant_item(self) -> InventoryItem|None:
    return None
  
  def accept_item(self, item: InventoryItem) -> None:
    pass


class MovableObject(GameObject):
  def __init__(self, position: tuple[int, int], velocity: tuple[int, int]):
    super().__init__()
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
    elif self.velocity[0] < 0 and not any(map(lambda item: item.kills_on_collision(self), below_us)):
      # there's something below us, we can't fall.
      self.adjust_velocity(new_abs_y=0)

  def positions(self, start_pos=None) -> list[tuple[int, int]]:
    ret = []
    pos = start_pos if start_pos is not None else self.position
    for h in range(len(self.chars())):
      ret.append((pos[0] + h, pos[1]))
    return ret

  def render(self, stdscr: BufferedCenterableWindow):
    for pos, ch in zip(self.positions(), self.chars()):
      self.addch(stdscr, (pos[0], pos[1]), ch)
  
  def collide(self, other_object):
    if other_object.kills_on_collision(self):
      self.signal_removal_from_game()
    if other_object.grants_item():
      self.accept_item(other_object.grant_item())
    # literally ran into a wall, stop
    stop_in_y = False
    stop_in_x = False
    for self_p in self.positions():
      for other_p in other_object.positions():
        y_delta = other_p[0] - self_p[0]
        x_delta = other_p[1] - self_p[1]
        if (((0 < y_delta <= self.velocity[0]) or
              (0 > y_delta >= self.velocity[0]))):
          stop_in_y = True
        if (((0 < x_delta <= self.velocity[1]) or
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
      if self.velocity == (0,0):
        self.velocity = (0, random.choice([-1, 1]))
      else:
        self.velocity = (self.velocity[0], -1 * self.velocity[1])

  def chars(self):
    return "bb"
  
  def kills_on_collision(self, other_object):
    return isinstance(other_object, Player)

class ShootsFireballs(InventoryItem):
  def __init__(self):
    self.tick_counter = 0

  def fire(self, game, shooter):
    offset = sign(shooter.velocity[1])
    if offset == 0:
      offset = 1
    v = shooter.velocity[0] * 2, shooter.velocity[1] * 2
    if v[1] == 0:
      v = v[0], 1
    for i in range(len(shooter.chars())):
      game.add_item(Fireball((shooter.position[0]+i, shooter.position[1] + offset), v, 20, immune=shooter))

class BigBadGuy(MovableObject):
  def __init__(self, initial_pos):
    super().__init__(initial_pos, (0, 1))
    self.fireball_shooter = ShootsFireballs()

  def experiences_gravity(self):
    return True

  def tick(self, game):
    super().tick(game)

  def chars(self):
    return "BBBB"
  
  def kills_on_collision(self, other_object):
    return isinstance(other_object, Player)


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

  def kills_on_collision(self, other_object):
    return isinstance(other_object, Player)

class Player(MovableObject):
  CHARS = "MM"

  def __init__(self, pos):
    super().__init__(pos, (0, 0))

    self.is_dead = False
    self.items = []

  def experiences_gravity(self):
    return True
  
  def chars(self):
    if self.has_speed_boost():
      return "L" * len(Player.CHARS)
    else:
      return Player.CHARS
    
  def tick(self, game):
    super().tick(game)

  def fire(self, game):
    for item in self.items:
      item.fire(game, self)

  def jump(self):
    if self.has_speed_boost():
      self.adjust_velocity(relative_y=6)
    else: 
      self.adjust_velocity(relative_y=3)

  def has_speed_boost(self) -> bool:
    return any(map(lambda item: isinstance(item, SpeedBoost), self.items))

  def right(self):
    if self.has_speed_boost():
      self.adjust_velocity(relative_x=2)
    else: 
      self.adjust_velocity(relative_x=1)

  def left(self):
    if self.has_speed_boost():
      self.adjust_velocity(relative_x=-2)
    else: 
      self.adjust_velocity(relative_x=-1)

  def down(self):
    if self.has_speed_boost():
      self.adjust_velocity(relative_y=-4)
    else: 
      self.adjust_velocity(relative_y=-2)

  def accept_item(self, item: InventoryItem) -> None:
    self.items.append(item)
 
  def collide(self, other_object):
    super().collide(other_object)
    if isinstance(other_object, Edamame):
      self.is_little = False

class SpeedBoost(InventoryItem):
  def __init__(self):
    self.start_time = time.time()
    self.duration = 30

  def should_be_removed(self):
    if time.time() - self.start_time > self.duration:
      return True
    return False

class Edamame(GameObject):
  def __init__(self, pos):
    super().__init__()
    self.position = pos

  def positions(self):
    return [self.position]

  def render(self, stdscr: BufferedCenterableWindow):
    self.addch(stdscr, (self.position[0], self.position[1]), "E")

  def grants_item(self) -> bool:
    return True

  def grant_item(self) -> InventoryItem:
    self.signal_removal_from_game()
    return SpeedBoost()

class ItemHolder(GameObject):
  def __init__(self, pos, item):
    super().__init__()
    self.position = pos
    self.item = item

  def positions(self):
    return [self.position]

  def render(self, stdscr: BufferedCenterableWindow):
    self.addch(stdscr, (self.position[0], self.position[1]), "W")

  def grants_item(self) -> bool:
    return True

  def grant_item(self) -> InventoryItem:
    self.signal_removal_from_game()
    return self.item



class Brick(GameObject):
  def __init__(self, pos):
    super().__init__()
    self.position = pos

  def positions(self):
    return [self.position]

  def render(self, stdscr: BufferedCenterableWindow):
    self.addch(stdscr, self.position, "=")

class BreakableBrick(GameObject):
  def __init__(self, pos):
    super().__init__()
    self.position = pos
    self.chars = "+"
    self.brokenness = 0
    self.disappear = 0

  def positions(self):
    return [self.position]
  
  def collide(self, other_object):
    if isinstance(other_object, Player):
      self.brokenness += 1
      if self.brokenness >= 2:
        self.signal_removal_from_game()

  def render(self, stdscr: BufferedCenterableWindow):
    if len(self.positions()) == 0:
      return
    if self.brokenness == 0:
      self.addch(stdscr, self.position, "+")
    else:
      self.addch(stdscr, self.position, "-")

class Fire(GameObject):# there should be a special fire
  def __init__(self, pos):
    super().__init__()
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

  def render(self, stdscr: BufferedCenterableWindow):
    self.addstr_vert(stdscr, self.position, "🔥" * self.num_fire)

  def kills_on_collision(self, other_object):
    return isinstance(other_object, Player) or isinstance(other_object, LittleBadGuy) or isinstance(other_object, BigBadGuy)

class Tree(GameObject):
  def __init__(self, pos):
    super().__init__()
    self.position = pos
    self.chars = "TTT"

  def positions(self):
    ret = []
    for i in range(len(self.chars)):
      ret.append((self.position[0] + i, self.position[1]))
    return ret

  def render(self, stdscr: BufferedCenterableWindow):
    self.addstr_vert(stdscr, self.position, self.chars)

  def kills_on_collision(self, other_object):
    return isinstance(other_object, Player)

class EndingFlag(GameObject):
  def __init__(self, pos):
    super().__init__()
    self.position = pos
    self.had_collision = False
    self.chars = "WINHERE"

  def positions(self):
    ret = []
    for i in range(len(self.chars)):
      ret.append((self.position[0] + i, self.position[1]))
    return ret

  def render(self, stdscr: BufferedCenterableWindow):
    self.addstr_vert(stdscr, self.position, self.chars)

  def collide(self, other_object):
    if isinstance(other_object, Player):
      self.had_collision = True

class Fireball(MovableObject):
  def __init__(self, pos, velocity, lifetime: int, immune=None):
    super().__init__(pos, velocity)
    self.lifetime = lifetime
    self.immune = immune

  def chars(self) -> str:
    return "🔥"
  
  def tick(self, game):
    super().tick(game)
    self.lifetime -= 1
    if self.lifetime <= 0:
      self.signal_removal_from_game()

  def collide(self, other_object):
    super().collide(other_object)
    if self.kills_on_collision(other_object):
      # leave it on-screen for a tick, then remove it.
      self.lifetime = 2

  def experiences_gravity(self):
    return False

  def kills_on_collision(self, other_object):
    return (isinstance(other_object, Player) or
            isinstance(other_object, LittleBadGuy) or
            isinstance(other_object, BigBadGuy)) and (
              other_object != self.immune
            )

class Cannonball(MovableObject):
  def __init__(self, pos, velocity):
    super().__init__(pos, velocity)

  def chars(self) -> str:
    return "O"
  
  def tick(self, game):
    super().tick(game)

  def experiences_gravity(self):
    return True

  def kills_on_collision(self, other_object):
    return isinstance(other_object, Player)

class Cannon(GameObject):
  def __init__(self, pos, ch, direction):
    super().__init__()
    self.position = pos
    self.chars = ch
    self.tick_counter = 0
    self.direction = direction

  def positions(self):
    ret = []
    for i in range(len(self.chars)):
      ret.append((self.position[0] + i, self.position[1]))
    return ret

  def tick(self, game):
    super().tick(game)
    self.tick_counter += 1
    if self.tick_counter % 10 == 0:
      game.add_item(Cannonball((self.position[0] + self.direction[0], self.position[1] + self.direction[1]), (self.direction[0]*2, self.direction[1]*2)))

  def render(self, stdscr: BufferedCenterableWindow):
    self.addch(stdscr, self.position, self.chars)

class Fireline(GameObject):
  def __init__(self, pos):
    super().__init__()
    self.position = pos
    self.fireball_placement = None
    self.fireball_v = None
    self.tick_counter = 0

  def positions(self):
    if 0 <= self.tick_counter < 5:
      self.fireball_placement = None
      self.fireball_v = None
      return [(self.position[0] + ydelta, self.position[1]) for ydelta in range(-5, 5, 1)]
    elif 5 <= self.tick_counter < 10:
      self.fireball_placement = (self.position[0] + 5, self.position[1] + 5)
      self.fireball_v = (1, 2)
      return [(self.position[0] + ydelta, self.position[1] + ydelta) for ydelta in range(-5, 5, 1)]
    elif 10 < self.tick_counter < 15:
      self.fireball_placement = None
      self.fireball_v = None
      return [(self.position[0] + ydelta, self.position[1]) for ydelta in range(-5, 5, 1)]
    else: # if 15 <= self.tick_counter < 20:
      self.fireball_v = (1, -2)
      self.fireball_placement = (self.position[0] + 5, self.position[1] - 5)
      return [(self.position[0] + ydelta, self.position[1] - ydelta) for ydelta in range(-5, 5, 1)]

  def tick(self, game):
    super().tick(game)
    self.tick_counter += 1
    if self.tick_counter % 10 == 7 and self.fireball_placement is not None:
      game.add_item(Fireball(self.fireball_placement, self.fireball_v, 10))
    if self.tick_counter == 20:
      self.tick_counter = 0

  def render(self, stdscr: BufferedCenterableWindow):
    for position in self.positions():
      self.addch(stdscr, position, "O")

  def kills_on_collision(self, other_object) -> bool:
    return isinstance(other_object, Player) or isinstance(other_object, LittleBadGuy) or isinstance(other_object, BigBadGuy)

def get_game_object_for_name(ch: str, game_pos: tuple[int, int]) -> GameObject|None:
  if ch == " ":
    return None
  elif ch == "=":
    return Brick(game_pos)
  elif ch == "+":
    return BreakableBrick(game_pos)
  elif ch == "P":
    return Player(game_pos)
  elif ch == "E":
    return Edamame(game_pos)
  elif ch == "b":
    return LittleBadGuy(game_pos)
  elif ch == "B":
    return BigBadGuy(game_pos)
  elif ch == "F":
    return EndingFlag(game_pos)
  elif ch == "T":
    return Tree(game_pos)
  elif ch == "W":
    return Bird(game_pos)
  elif ch == "🔥":
    return Fire(game_pos)
  elif ch == "L":
    return Fireline(game_pos)
  elif ch == "H":
    return ItemHolder(game_pos, ShootsFireballs())
  elif ch == "/":
    return Cannon(game_pos, ch, direction=(1,1))
  elif ch == "\\":
    return Cannon(game_pos, ch, direction=(1,-1))
  
  return None