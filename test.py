import unittest
from core import Player, Ally, Game, GameState, GameController
from gavs_deck import *
from unittest.mock import Mock

class TestBoromir(unittest.TestCase):
    def setUp(self):
        self.boromir = Boromir()
        self.player = Player("Test")
        self.player.play_area['heroes'].append(self.boromir)
        self.boromir.resources['Leadership'] = 1  # Ensure resource available


    def test_gondor_ally_attack_bonus(self):
        """Test that Gondor allies get +1 attack when Boromir has resources."""
        gondor_ally = Ally("Gondor Soldier", 2, "Leadership", 1, 2, 1, 2)
        gondor_ally.add_keyword("Gondor")
        self.player.play_area['allies'].append(gondor_ally)

        # Simulate attack calculation
        attack_context = {
            'attacker': gondor_ally,
            'modified_attack': 2,
            'game_state': None,
            'player': self.player
        }
        self.boromir.modify_gondor_attack(attack_context)
        self.assertEqual(attack_context['modified_attack'], 3)  # +1 bonus

    def test_non_gondor_ally_no_bonus(self):
        """Test that non-Gondor allies do not get the attack bonus."""
        non_gondor_ally = Ally("Rohan Horseman", 2, "Leadership", 1, 2, 1, 2)
        self.player.play_area['allies'].append(non_gondor_ally)

        # Simulate attack calculation
        attack_context = {
            'attacker': non_gondor_ally,
            'modified_attack': 2,
            'game_state': None,
            'player': self.player
        }
        self.boromir.modify_gondor_attack(attack_context)
        self.assertEqual(attack_context['modified_attack'], 2)  # No bonus


class TestGaladriel(unittest.TestCase):
    def setUp(self):
        self.galadriel = Galadriel()
        self.player = Player("Test")
        self.player.play_area['heroes'].append(self.galadriel)
        self.game = Game([self.player])
        self.target_player = Player("Target")
        self.game.game_state.players.append(self.target_player)

    def test_new_ally_no_exhaust(self):
        """Test that new allies do not exhaust when questing in the same round."""
        ally = Ally("Lórien Guide", 2, "Spirit", 2, 1, 1, 2)
        self.player.play_area['allies'].append(ally)
        self.player.new_allies_this_round.append(ally)

        # Simulate quest exhaustion check
        context = {
            'character': ally,
            'player': self.player,
            'prevent_exhaustion': False
        }
        self.galadriel.prevent_ally_exhaustion(context)
        self.assertTrue(context['prevent_exhaustion'])

    def test_galadriel_action_ability(self):
        """Test Galadriel's action to reduce threat and draw a card."""
        # Setup initial state
        self.target_player.deck = [
            Ally("Test Ally 1", 1, "Spirit", 1, 1, 1, 2),
            Ally("Test Ally 2", 1, "Spirit", 1, 1, 1, 2),
            Ally("Test Ally 3", 1, "Spirit", 1, 1, 1, 2),
            Ally("Test Ally 4", 1, "Spirit", 1, 1, 1, 2)
        ]
        self.target_player.threat = 30
        initial_hand_size = len(self.target_player.hand)
        self.galadriel.exhausted = False
        self.galadriel.used_this_round = False

        # Mock controller choices
        def mock_choose_player(players):
            return self.target_player
        self.game.controller.choose_player = mock_choose_player
        
        # Mock the get_choice to auto-select "Yes"
        def mock_get_choice(prompt, options, multi_select=False):
            return [0]  # Select first option ("Yes")
        self.game.controller.get_choice = mock_get_choice

        # Trigger action
        self.galadriel.offer_action({
            'player': self.player,
            'game_state': self.game.game_state,
            'controller': self.game.controller
        })

        # Verify results
        self.assertEqual(self.target_player.threat, 29)
        self.assertEqual(len(self.target_player.hand), initial_hand_size + 1)
        self.assertTrue(self.galadriel.exhausted)
        self.assertTrue(self.galadriel.used_this_round)

    def test_galadriel_action_limit_once_per_round(self):
        """Test that Galadriel's action can only be used once per round."""
        # Setup initial state
        self.target_player.deck = [
            Ally("Test Ally 1", 1, "Spirit", 1, 1, 1, 2),
            Ally("Test Ally 2", 1, "Spirit", 1, 1, 1, 2),
            Ally("Test Ally 3", 1, "Spirit", 1, 1, 1, 2),
            Ally("Test Ally 4", 1, "Spirit", 1, 1, 1, 2)
        ]
        self.target_player.threat = 30
        self.galadriel.exhausted = False
        self.galadriel.used_this_round = False

        # Mock controller choices
        def mock_choose_player(players):
            return self.target_player
        
        # Mock get_choice to always select "Yes"
        def mock_get_choice(prompt, options, multi_select=False):
            return [0]
        
        self.game.controller.choose_player = mock_choose_player
        self.game.controller.get_choice = mock_get_choice

        # Trigger action twice
        self.galadriel.offer_action({
            'player': self.player,
            'game_state': self.game.game_state,
            'controller': self.game.controller
        })
        self.galadriel.offer_action({
            'player': self.player,
            'game_state': self.game.game_state,
            'controller': self.game.controller
        })

        # Verify results
        self.assertEqual(self.target_player.threat, 29)  # Only reduced once
        self.assertTrue(self.galadriel.used_this_round)


if __name__ == "__main__":
    unittest.main()