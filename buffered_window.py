import curses

class BufferedCenterableWindow(object):
  def __init__(self, win: curses.window):
    self.__win = win
    self.__buffer = {}
    self.__last_player_location: list[tuple[int, int]] = [(0,0)]

  def clear(self):
    self.__buffer = {}
    self.__win.clear()

  def repaint(self):
    self.__win.clear()
    self.refresh(self.__last_player_location)
  
  def refresh(self, player_location: list[tuple[int, int]]):
    self.__last_player_location = player_location
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
    if len(self.__buffer) == 0:
      return (0, 0), self.__win.getmaxyx()

    max_y_to_paint = max([k[0] for k in self.__buffer.keys()])
    max_x_to_paint = max([k[1] for k in self.__buffer.keys()])
    game_window_height, game_window_width = self.__win.getmaxyx()

    if max_y_to_paint < game_window_height:
      bottom = 0
    else:
      # keep the player near the bottom of the screen.
      player_min_y = min([l[0] for l in player_location])
      bottom = player_min_y - 10
      if bottom < 0:
        bottom = 0

    if max_x_to_paint < game_window_width:
      left = 0
    else:
      player_min_x = min([l[1] for l in player_location])
      # center the player horizontally except don't show past the edge.
      left = player_min_x - (game_window_width // 2)
      if left < 0:
        left = 0
      if left + game_window_width > max_x_to_paint:
        left = max_x_to_paint - game_window_width

    bottom_left = (bottom, left)
    top_right = bottom_left[0] + game_window_height, bottom_left[1] + game_window_width
    return bottom_left, top_right

  def addch(self, y: int, x: int, ch: str) -> None:
    self.__buffer[(y, x)] = ch

  def addstr(self, y: int, x: int, str: str) -> None:
    for i, ch in enumerate(str):
      self.addch(y, x + i, ch)

  def move_cursor(self, y: int, x: int) -> None:
    self.__win.move(y, x)