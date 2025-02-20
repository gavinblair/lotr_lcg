from core import *
from quests import *
from gavs_deck import *
from rich.console import Console
console = Console()

if __name__ == "__main__":
  gav = Player("gav")
  ai = Player("ai")
  boromir = Boromir()
  galadriel = Galadriel()
  gav.play_area['heroes'].extend([boromir, galadriel])
  gav.calculate_threat()

  ai.play_area['heroes'].extend([galadriel])
  ai.calculate_threat()
  
  # Create game with player
  game = Game([gav, ai], FleeingFromMirkwood())
  
  # Add some test cards to deck
  test_ally = Ally("Gondor Soldier", 2, "Leadership", 1, 2, 1, 3)
  gav.deck = [test_ally] * 20  # Fill deck with dummy cards
  ai.deck = [test_ally] * 20  # Fill deck with dummy cards
  
  game.run()