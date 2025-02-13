from core import *

class FleeingFromMirkwood(QuestCard):
  def __init__(self):
    super().__init__("Fleeing from Mirkwood", 12, 0)  

  def play(game_state, controller):
    print("Fleeing from Mirkwood Quest Description.")