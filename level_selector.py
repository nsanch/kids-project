import curses
import json
import os
from buffered_window import BufferedCenterableWindow

class Level(object):
  def __init__(self, id, description, path):
    self.id = id
    self.description = description
    self.path = path

class LevelSelector(object):
  def __init__(self, stdscr, rootdir):
    self.__stdscr = stdscr
    self.__rootdir = rootdir
    self.__win = BufferedCenterableWindow(stdscr.subwin(curses.LINES, curses.COLS, 0, 0))
    self.__levels = self.read_levels()

  def read_levels(self):
    with open(os.path.join(self.__rootdir, "levels.json")) as f:
      levels_json: list[dict] = json.load(f)

    levels = []
    for level in levels_json:
      path = os.path.join(self.__rootdir, "side-scroller-levels", level["path"])
      levels.append(Level(level["id"], level["description"], path))
    return levels
  
  def get_input(self):
    return self.__stdscr.getstr().decode("utf-8")


  def render_and_get_selected_level(self):
    self.__win.clear()
    prompt = "Type a level number and hit enter to play: "
    self.__win.addstr(curses.LINES-2, 0, prompt)
    self.__win.move_cursor(curses.LINES-2, len(prompt) + 2)
    
    for i, level in enumerate(self.__levels):
      self.__win.addstr(curses.LINES - (i + 4), 3, f"{level.id}: {level.description}")
    self.__win.refresh([(len(self.__levels) // 2, 0)])

    selected_level = None
    while selected_level is None:
      level_id = self.get_input()
      for level in self.__levels:
        if str(level.id) == level_id:
          selected_level = level
    return selected_level.id
