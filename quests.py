from core import *

class FleeingFromMirkwood(QuestCard):
  def __init__(self):
    super().__init__("Fleeing from Mirkwood", 12, 0)  

  def play(game_state, controller):
    print("Fleeing from Mirkwood Quest Description.")
    
class DolGuldurOrcs(Enemy):
    def __init__(self):
        super().__init__("Dol Guldur Orcs", 2, 2, 2, 4, 10)
        self.description = "When Revealed: The first player chooses 1 character currently committed to a quest. Deal 2 damage to that character."
        self.add_keyword("Orc")

    def play(self, game_state, controller):
        super().play(game_state, controller)
        game_state.event_system.register_hook("WhenRevealed", self.deal_damage)
        game_state.event_system.register_hook("ShadowEffect", self.shadow_effect)

    def deal_damage(self, context):
        if 'questing_characters' in context:
            controller = context['controller']
            choice_indices = controller.get_choice(
                "Choose 1 character currently committed to a quest to deal 2 damage to",
                [character.title for character in context['questing_characters']]
            )
            if choice_indices:
                target_character = context['questing_characters'][choice_indices[0]]
                target_character.hit_points -= 2

    def shadow_effect(self, context):
        target_character = context['defender']
        if target_character:
            target_character.hit_points -= 1