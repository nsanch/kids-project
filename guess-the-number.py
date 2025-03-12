#!/Users/nsanch/kids-project/.venv/bin/python

import random
import sys

def guess_the_number(maximum):
  answer = random.randint(1, maximum)
  num_guesses = 0
  known_bounds = [1, maximum]
  while True:
    num_guesses += 1
    print(f"Guess #{num_guesses}: Enter a number between 1 and {maximum}:")
    try:
      input = int(sys.stdin.readline().strip())
    except ValueError:
      print(f"That's not a number. Try again!")
      continue

    if input > maximum or input < 1:
      print(f"That's not a number between 1 and {maximum}!")
      continue

    if input < known_bounds[0] or input > known_bounds[1]:
      print(f"Uh oh, you already knew it couldn't be {input}!")

    if input == answer:
      print("You guessed it!")
      break
    elif input < answer:
      print("Womp womp. Too low.")
      known_bounds[0] = max(known_bounds[0], input)
    else:
      print("Blergh! Too high.")
      known_bounds[1] = min(known_bounds[1], input)


maximum = None
while maximum is None:
  print("What is the maximum number you want to use for guessing? Hit \"Return\" for 100:")
  try:
    input_str = sys.stdin.readline().strip()
    if input_str == "":
      maximum = 100
    else:
      maximum = int(input_str)
  except ValueError:
    print("That's not a number. Try again!")
guess_the_number(maximum)