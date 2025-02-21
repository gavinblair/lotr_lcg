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
  # Create game with player
  game = Game([gav], FleeingFromMirkwood())
  game.run()