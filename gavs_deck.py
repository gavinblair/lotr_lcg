from core import *

class Boromir(Hero):
    def __init__(self):
        super().__init__("Boromir", "Leadership", 11, 1, 3, 2, 5)
        self.description = "While Boromir has at least 1 resource in his resource pool, Gondor allies get +1 attack."
        self.add_keyword("Gondor")
        self.add_keyword("Warrior")
        self.add_keyword("Noble")

    def play(self, game_state, controller):
        super().play(game_state, controller)
        game_state.event_system.register_hook("CombatPhase", "CalculateAttack", self.modify_gondor_attack)

    def modify_gondor_attack(self, context):
        attacker = context.get('attacker')
        if (isinstance(attacker, Ally) and 'Gondor' in attacker.keywords):
            if self.resources[self.sphere] >= 1:
                context['modified_attack'] += 1


class Galadriel(Hero):
    def __init__(self):
        super().__init__("Galadriel", "Spirit", 9, 4, 0, 0, 4)
        self.description = "Galadriel cannot quest, attack or defend. Allies you control do not exhaust to commit to the quest during the round they enter play. Action: Exhaust Galadriel to choose a player. That player reduces their threat by 1 and draws 1 card (limit once per round)."
        self.add_keyword("Noldor")
        self.add_keyword("Noble")
        self.used_this_round = False
        self.can_attack = False  # Prevent attacking

    def can_quest(self):
        return False  # Cannot quest

    def can_defend(self):
        return False  # Cannot defend

    def play(self, game_state, controller):
        super().play(game_state, controller)
        game_state.event_system.register_hook("QuestPhase", "BeforeQuestExhaustion", self.prevent_ally_exhaustion)
        game_state.event_system.register_hook("PlanningPhase", "PlayerActions", self.offer_action)
        game_state.event_system.register_hook("RefreshPhase", "PhaseEnd", self.reset_used)

    def prevent_ally_exhaustion(self, context):
        character = context['character']
        player = context['player']
        if (isinstance(character, Ally) and 
            character in player.new_allies_this_round and 
            any(isinstance(h, Galadriel) for h in player.play_area['heroes'])):
            context['prevent_exhaustion'] = True

    def offer_action(self, context):
        player = context['player']
        game_state = context['game_state']
        controller = context['controller']
        if (self in player.play_area['heroes'] and 
            not self.exhausted and 
            not self.used_this_round):
            choice_indices = controller.get_choice(
                f"Use {self.title}'s action? (Exhaust to reduce threat by 1 and draw a card)",
                ["Yes", "No"]
            )
            if choice_indices and choice_indices[0] == 0:  # First option ("Yes")
                self.exhausted = True
                self.used_this_round = True
                target_player = controller.choose_player(game_state.players)
                target_player.threat = max(0, target_player.threat - 1)
                target_player.draw_card(game_state)
    
    def reset_used(self, context):
        self.used_this_round = False