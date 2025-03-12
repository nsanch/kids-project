#!/Users/nsanch/kids-project/.venv/bin/python

import curses
import threading
import time
import random
import sys
import os
import json

class Collidable(object):
  def __init__(self):
    pass

  def tick(self, game):
    pass

  def render(self, stdscr):
    pass

  def collide(self, other_object):
    pass

  def is_wall(self):
    return False


class MovableObject(Collidable):
  def __init__(self, position, velocity):
    self.position = position
    self.velocity = velocity

  def chars(self):
    pass

  def tick(self, game):
    next_position = self.position[0] + self.velocity[0], self.position[1] + self.velocity[1]
    other_items = game.items_at(self.positions(start_pos=next_position))
    if self in other_items:
      other_items.remove(self)
    if len(other_items) == 0:
      self.position = next_position
    else:
      assert len(other_items) == 1
      other_item = other_items[0]
      self.collide(other_item)
      other_item.collide(self)

  def positions(self, start_pos=None):
    ret = []
    pos = start_pos if start_pos is not None else self.position
    for h in range(len(self.chars())):
      ret.append((pos[0] - h, pos[1]))
    return ret

  def render(self, stdscr):
    for pos, ch in zip(self.positions(), self.chars()):
      stdscr.addch(pos[0], pos[1], ch)

  def collide(self, other_object):
    pass

  def is_wall(self):
    return False

class Ball(MovableObject):
  def __init__(self, initial_pos):
    super().__init__(initial_pos, self.random_velocity())
    self.initial_position = initial_pos
  
  def reset(self):
    self.position = self.initial_position
    self.velocity = self.random_velocity()

  def random_velocity(self):
    return (random.choice([-1, 1]), random.choice([-1, 1]))

  def chars(self):
    return "O"

  def collide(self, other_object):
    if other_object.is_wall():
      self.velocity = (-self.velocity[0], self.velocity[1])
    else:
      # bouncing off paddle, we take on the velocity of the paddle in the Y dimension.
      self.velocity = (self.velocity[0], -self.velocity[1])

class Paddle(MovableObject):
  HEIGHT = 10

  def __init__(self, pos):
    super().__init__(pos, (0, 0))

  def chars(self):
    return "|" * Paddle.HEIGHT

  def up(self):
    # up is a negative y-velocity because 0,0 is the top-left.
    # we can move at most 1 pixel per tick.
    self.velocity = max(-1, self.velocity[0] - 1), 0

  def down(self):
    # down is a positive y-velocity because 0,0 is the top-left
    # we can move at most 1 pixel per tick.
    self.velocity = min(1, self.velocity[0] + 1), 0

  def collide(self, other_object):
    if other_object.is_wall():
      self.velocity = (0, 0)

class Wall(Collidable):
  def __init__(self, pos):
    self.position = pos

  def tick(self, game):
    pass

  def positions(self):
    return [(self.position[0], i) for i in range(curses.COLS)]

  def render(self, stdscr):
    stdscr.addstr(self.position[0], 0, "=" * (curses.COLS-1))

  def collide(self, other_object):
    pass

  def is_wall(self):
    return True

class Game(object):
  LEFT_PADDLE_POS = lambda: (curses.LINES - ((curses.LINES - Paddle.HEIGHT) // 2), 3)
  RIGHT_PADDLE_POS = lambda: (curses.LINES - ((curses.LINES - Paddle.HEIGHT) // 2), curses.COLS - 4)

  # game states
  RUNNING = 0
  PAUSED = 1
  LOST = 2
  QUIT = 3
  WON = 4
  WAITING_FOR_NEXT_POINT = 5

  # results of tick()
  CONTINUING = 0
  RIGHT_POINT = 1
  LEFT_POINT = 2

  def __init__(self):
    self.ball = Ball(((curses.LINES - 5) // 2, curses.COLS // 2))
    self.left_paddle = Paddle(Game.LEFT_PADDLE_POS())
    self.right_paddle = Paddle(Game.RIGHT_PADDLE_POS())
    self.top_wall = Wall((6, 0))
    self.bottom_wall = Wall((curses.LINES - 1, 0))
    self.items = [self.left_paddle, self.right_paddle, self.top_wall, self.bottom_wall, self.ball]
    self.game_state = Game.RUNNING
    self.lock = threading.Lock()
    self.score = (0, 0)
    self.status_msg = None

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
  

  def maybe_move_left_paddle(self):
    # we get a 1 in 6 chance of moving the paddle when the ball is moving towards us
    if random.randint(0, 5) == 0 and self.ball.velocity[1] < 0:
      # if the ball is above the paddle, move up.
      # if the ball is below the paddle, move down.
      ball_pos = self.ball.position
      paddle_pos = self.left_paddle.position
      if ball_pos[0] < paddle_pos[0]:
        self.left_paddle.up()
      elif ball_pos[0] > paddle_pos[0]:
        self.left_paddle.down()

  def debug_msg(self):
    return ""
    #return f"Ball: {self.ball.position}, Left Paddle: {self.left_paddle.velocity}, Right Paddle: {self.right_paddle.velocity}"

  def tick(self):
    if self.game_over():
      return False
    
    for item in self.items:
      item.tick(self)
    
    if self.ball.position[1] == 0:
      self.score = (self.score[0], self.score[1] + 1)
      self.ball.reset()
      return Game.RIGHT_POINT
    elif self.ball.position[1] == curses.COLS - 1:
      self.score = (self.score[0] + 1, self.score[1])
      self.ball.reset()
      return Game.LEFT_POINT
    
    self.maybe_move_left_paddle()
    return Game.CONTINUING

  def refresh_window(self, stdscr):
    try:
      self.acquire_lock()

      if self.game_over():
        return
      
      if self.game_state not in [Game.PAUSED, Game.WAITING_FOR_NEXT_POINT]:
        tick_result = self.tick()
        if tick_result == Game.RIGHT_POINT:
          if self.score[1] == 10:
            self.status_msg = "You win!"
            self.game_state = Game.WON
          else:
            self.status_msg = "Point to you!!  Hit 'p' to continue."
            self.game_state = Game.WAITING_FOR_NEXT_POINT
        elif tick_result == Game.LEFT_POINT:
          if self.score[0] == 10:
            self.status_msg = "Oh no, the computer wins. :( :("
            self.game_state = Game.LOST
          else:
            self.status_msg = "Point to the computer! Hit 'p' to continue."
            self.game_state = Game.WAITING_FOR_NEXT_POINT
        
      stdscr.clear()
      for item in self.items:
        item.render(stdscr)
      stdscr.addstr(0, 0, f"CPU: {self.score[0]}")
      stdscr.addstr(0, curses.COLS - 13, f"Player 1: {self.score[1]}")
      if self.status_msg is not None:
        stdscr.addstr(curses.LINES // 2, (curses.COLS - len(self.status_msg)) // 2, self.status_msg)      
      stdscr.addstr(2, 0, "Type 'e' to exit. 'r' to restart. 'p' to pause. Up to move paddle up, down to move down.")
      stdscr.addstr(4, 0, self.debug_msg())
      stdscr.refresh()

      def task():
        self.refresh_window(stdscr)

      if not self.game_over():
        threading.Timer(self.speed(), task).start()
    finally:
      self.release_lock()

  def speed(self):
    return 0.1
  
  def accept_keypress(self, k, stdscr):
    try:
      self.acquire_lock()
      if k == "p":
        if self.game_state in [Game.PAUSED, Game.WAITING_FOR_NEXT_POINT]:
          self.game_state = Game.RUNNING
          self.status_msg = None
        else:
          self.game_state = Game.PAUSED
          self.status_msg = "Game paused. Press 'p' to continue."
      elif k == "KEY_UP":
        self.right_paddle.up()
      elif k == "KEY_DOWN":
        self.right_paddle.down()
      elif k == "e":
        self.game_state = Game.QUIT
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
      elif k == 'e':
        break
    else:
      game.accept_keypress(k, stdscr)
 
curses.wrapper(play_game)