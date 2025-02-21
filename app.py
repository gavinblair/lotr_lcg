from core import *
from quests import *
from gavs_deck import *
from rich.console import Console
import random
console = Console()

if __name__ == "__main__":
  gav = Player("Gavin")  
  gav.play_area['heroes'] = [
    Boromir(),
    Galadriel(),
    Aragorn()
  ]
  gav.calculate_threat()
  gav.deck = [
    Faramir(),Faramir(),Faramir(),
    Gandalf(),Gandalf(),Gandalf(),
    StewardOfGondor(),StewardOfGondor(),StewardOfGondor(),
    UnexpectedCourage(),UnexpectedCourage(),UnexpectedCourage()
  ]
  random.shuffle(gav.deck)

  p2 = Player("Player 2")
  p2.play_area['heroes'] = [
    Aragorn()
  ]
  p2.calculate_threat()
  p2.deck = [
    Faramir(),Faramir(),Faramir(),
    Gandalf(),Gandalf(),Gandalf(),
    StewardOfGondor(),StewardOfGondor(),StewardOfGondor(),
    UnexpectedCourage(),UnexpectedCourage(),UnexpectedCourage()
  ]
  random.shuffle(p2.deck)

  # Create game with player
  game = Game([gav, p2], FleeingFromMirkwood())
  game.run()