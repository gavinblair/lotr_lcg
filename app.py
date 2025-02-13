from core import *
from quests import *
from gavs_deck import *

if __name__ == "__main__":
  gav = Player("gav")
  boromir = Boromir()
  galadriel = Galadriel()
  gav.play_area['heroes'].extend([boromir, galadriel])
  gav.calculate_threat()
  
  # Create game with player
  game = Game([gav], FleeingFromMirkwood())
  
  # Add some test cards to deck
  test_ally = Ally("Gondor Soldier", 2, "Leadership", 1, 2, 1, 3)
  gav.deck = [test_ally] * 20  # Fill deck with dummy cards

  print(gav.toString(game.game_state))
  
  print("\nStarting game!")
  print(f"Active Quest: {game.game_state.active_quest.title}")
  print(f"Required Progress: {game.game_state.active_quest.required_progress}")
  
  game.run()