from abc import ABC, abstractmethod
from collections import defaultdict
import random

class Player:
    def __init__(self, name):
        self.name = name
        self.threat = 0  # Will be updated when heroes are added
        self.deck = []
        self.hand = []
        self.discard_pile = []
        self.play_area = {
            'heroes': [],
            'allies': [],
            #todo: attachments go on cards, not the play area and not the player.
            # 'attachments': []
        }
        self.engaged_enemies = []
        self.new_allies_this_round = []
        
    def toString(self, game_state):
        return (
            f"Player: {self.name}\n"
            f"Threat: {self.threat}\n"
            f"Hand: {[c.title for c in self.hand]}\n"
            f"Deck: {len(self.deck)} cards\n"
            f"Discard: {len(self.discard_pile)} cards\n"
            f"Heroes: {[h.title for h in self.play_area['heroes']]}\n"
            f"Allies: {[a.title for a in self.play_area['allies']]}\n"
            #todo: attachments are on cards, not players
            # f"Attachments: {[at.title for at in self.play_area['attachments']]}\n"
        )
    
    def draw_card(self, game_state, num=1):
        for _ in range(num):
            game_state.event_system.trigger_event("BeforeDrawCard", {"player": self})
            print("Drawing a card.")
            if len(self.deck) == 0:
                print("The deck is empty. Reshuffling the discard into the deck.")
                self.reshuffle_discard(game_state)
                if len(self.deck) == 0:  # Still empty after reshuffle
                    print("Still no cards in the deck, this means you lose!")
                    self.threat = 50  # Immediate loss condition
                    return
            if len(self.deck) > 0:
                drawn_card = self.deck.pop()
                print(f"Drawn card: {drawn_card.title}")
                self.hand.append(drawn_card)
                game_state.event_system.trigger_event("AfterDrawCard", {"player": self, "card": drawn_card})
                
                
    def reshuffle_discard(self, game_state):
        game_state.event_system.trigger_event("BeforeReshuffleDiscard", {"player": self})
        self.deck.extend(self.discard_pile)
        self.discard_pile = []
        random.shuffle(self.deck)
        game_state.event_system.trigger_event("AfterReshuffleDiscard", {"player": self})
    
    def calculate_threat(self):
        """Update threat based on heroes' threat costs"""
        self.threat = sum(hero.threat_cost for hero in self.play_area['heroes'])
        
    def play_card(self, card, game_state):
        if self.can_afford(card.cost, card.sphere):
            game_state.event_system.trigger_event("BeforeAnyCardPlayed", {"card": card, "player": self})
            self.deduct_resources(card.cost, card.sphere, game_state)
            self.hand.remove(card)  # Remove from hand
            
            # Handle different card types
            card_type = "card"
            if isinstance(card, Hero):
                self.play_area['heroes'].append(card)
                
            elif isinstance(card, Ally):
                self.play_area['allies'].append(card)
                card.parent = self
                self.new_allies_this_round.append(card)  # Track new allies
            elif isinstance(card, Attachment):
                pass  # Handled in Attachment.play()
            elif isinstance(card, Event):
                self.discard_pile.append(card)  # Events go to discard after play
            
            card.play(game_state, self.controller)
            game_state.event_system.trigger_event(f"AfterCardPlayed", {"card": card, "player": self})

            
    def can_afford(self, cost, sphere):
        # Calculate total available resources from all eligible cards
        return self.get_available_resources(sphere) >= cost
        
    def get_available_resources(self, sphere):
        """Correctly iterate through all resource-providing cards"""
        total = 0
        # Heroes
        for hero in self.play_area['heroes']:
            total += hero.resources.get(sphere, 0)
        return total
        
    def deduct_resources(self, amount, sphere, game_state):
        game_state.event_system.trigger_event(
            "BeforeDeductingResources",
            {"player": self, "sphere": sphere, "amount": amount}
        )
        remaining = amount
        
        for hero in self.play_area['heroes']:
            if remaining <= 0: break
            if hero.sphere == sphere:
                available = hero.resources.get(sphere, 0)
                use = min(available, remaining)
                hero.resources[sphere] -= use
                remaining -= use
                hero.exhausted = True
                hero.on_exhaust()
                game_state.event_system.trigger_event(
                    "AfterExhausted",
                    {"card": hero, "player": self}
                )
        game_state.event_system.trigger_event(
            "AfterDeductingResources",
            {"player": self, "sphere": sphere, "amount": amount}
        )

    def refresh_resources(self):
        """Reset card resources and ready exhausted cards"""
        for hero in self.play_area['heroes']:
            hero.refresh_resources()

    def select_card_to_play(self, controller):
        return controller.choose_card_to_play(self)
        
    def select_defender(self, enemy, controller):
        #todo: hook for "before selecting a defender"
        valid_defenders = [
            c for c in self.play_area['heroes'] + self.play_area['allies']
            if not c.exhausted and c.can_defend()
        ]
        if not valid_defenders:
            return None
            
        output = controller.choose_defender(self, enemy, valid_defenders)
        #todo: hook for "after selecting a defender"
        return output
    
    def select_location_to_travel(self, locations, controller):
        #todo: hook for "before selecting a location to travel"
        output = controller.choose_location_to_travel(locations)
        #todo: hook for "after selecting a location to travel"
        return output

    def play(self, game_state, controller):
        """Activate this quest card"""
        if game_state.active_quest:
            game_state.active_quest.is_active = False
        self.is_active = True
        game_state.active_quest = self

class Game:
    def __init__(self, players, quest):
        self.players = players
        self.controller = GameController(self)
        self.phases = [
            ResourcePhase(),
            PlanningPhase(),
            QuestPhase(),
            TravelPhase(),
            EncounterPhase(),
            CombatPhase(),
            RefreshPhase()
        ]
        self.game_state = GameState(players, EventSystem())
        
        self.game_state.active_quest = quest

        for player in self.players:
            for hero in player.play_area['heroes']:
                hero.play(self.game_state, self.controller)
            player.calculate_threat()  # Set initial threat
        
    def run(self):
        #first every player draw 5 cards
        for player in self.players:
            player.draw_card(self.game_state, 5)

        while not self.check_game_over():
            for phase in self.phases:
                print(phase.toString(self.game_state))
                self.game_state.current_phase = type(phase).__name__
                phase.execute(self.game_state, self.controller)
            print(f"Completed round {self.game_state.round_number}")
                
    def check_game_over(self):
        # Check loss conditions first
        for player in self.game_state.players:
            if player.threat >= 50:
                print(f"Game Over! {player.name} reached 50 threat!")
                return True
            if not any(isinstance(card, Hero) for card in player.play_area.get('heroes', [])):
                print(f"Game Over! {player.name} has no surviving heroes!")
                return True

        # Check victory condition
        if (self.game_state.active_quest and 
            self.game_state.active_quest.progress >= self.game_state.active_quest.required_progress):
            print(f"Victory! Completed quest: {self.game_state.active_quest.title}")
            return True
            
        return False

class GameState:
    def __init__(self, players, event_system):
        self.players = players
        self.active_player = players[0]
        self.victory_display = []
        self.encounter_deck = []
        self.encounter_discard = []
        self.staging_area = []
        self.active_location = None
        self.round_number = 0
        self.current_phase = None
        self.new_allies_this_round = [] # Track allies played this round
        self.event_system = event_system
        self.active_quest = None
        
    def toString(self):
        return (
            f"Game State (Round {self.round_number})\n"
            f"Phase: {self.current_phase}\n"
            f"Quest Progress: {self.quest_progress}\n"
            f"Active Location: {self.active_location.title if self.active_location else 'None'}\n"
            f"Staging Area: {[c.title for c in self.staging_area]}\n"
            f"Encounter Deck: {len(self.encounter_deck)} cards\n"
            f"Victory Display: {[c.title for c in self.victory_display]}"
        )
        
    def select_character(self, player):
        # Simple implementation - could be expanded with UI
        return next((c for c in player.play_area['allies'] + player.play_area['heroes']), None)
    def draw_encounter_card(self):
        if not self.encounter_deck:
            #todo: hook for "before reshuffling the encounter deck"
            self.encounter_deck = self.encounter_discard
            self.encounter_discard = []
            random.shuffle(self.encounter_deck)
            #todo: hook for "after reshuffling the encounter deck"
        #todo: hook for "before drawing a card from the encounter deck"
        output = self.encounter_deck.pop() if self.encounter_deck else None
        #todo: hook for "after drawing a card from the encounter deck"
        return output

class GameController:
    def __init__(self, game):
        self.game = game
        self.current_choices = []
        
    def display_game_state(self, player):
        """Show current game state to player"""
        print(f"\n--- {player.name}'s Turn ---")
        print(f"Threat: {player.threat}")
        print("Hand:", [c.title for c in player.hand])
        print("Heroes:", [f"{h.title} (WP:{h.willpower})" for h in player.play_area['heroes']])
        print("Allies:", [a.title for a in player.play_area['allies']])
        print("Staging Area:", [c.title for c in self.game.game_state.staging_area])
    
    def choose_player(self, players):
        """Let player choose from available players"""
        options = [p.name for p in players]
        choice = self.get_choice("Choose a player:", options)
        return players[options.index(choice)]

    def get_choice(self, prompt, options, multi_select=False):
        print("\n" + prompt)
        for i, option in enumerate(options, 1):
            print(f"{i}. {option}")
            
        while True:
            choice = input("Enter choice(s), comma-separated: " if multi_select else "Enter choice: ")
            if multi_select:
                indices = [int(c.strip())-1 for c in choice.split(",") if c.strip().isdigit()]
                if all(0 <= i < len(options) for i in indices):
                    return indices
            else:
                if choice.isdigit() and 1 <= int(choice) <= len(options):
                    return [int(choice)-1]
            print("Invalid choice, try again")

    def choose_card_to_play(self, player):
        """Let player select a card to play or pass"""
        playable = [c for c in player.hand if player.can_afford(c.cost, c.sphere)]
        if not playable:
            return None
            
        self.display_game_state(player)
        options = [f"{c.title} ({c.cost} {c.sphere})" for c in playable] + ["Pass"]
        choice = self.get_choice("Choose a card to play:", options)
        
        if choice == "Pass":
            return None
        return playable[options.index(choice)]

    def choose_defender(self, player, enemy, valid_defenders):
        """Let player choose defender for an attack"""
        
        self.display_game_state(player)
        options = [f"{c.title} (Defense: {c.defense})" for c in valid_defenders] + ["No defender"]
        choice = self.get_choice(f"Choose defender against {enemy.title}:", options)
        
        if choice == "No defender":
            return None
        return valid_defenders[options.index(choice)]

    def choose_enemy_to_attack(self, player, enemies):
        options = [f"{e.title} (HP: {e.hit_points})" for e in enemies] + ["Pass"]
        choice = self.get_choice("Choose enemy to attack:", options)
        return enemies[choice] if choice != "Pass" else None

    def choose_attackers(self, valid_attackers):
        choices = self.get_choice(
            "Select attackers:",
            [f"{a.title} (Attack {a.attack})" for a in valid_attackers],
            multi_select=True
        )
        return [valid_attackers[i] for i in choices]

    def choose_location_to_travel(self, locations):
        if not locations:
            return None
        options = [f"{loc.title} (Threat: {loc.threat})" for loc in locations]
        choice = self.get_choice("Choose location to travel to:", options)
        return locations[options.index(choice)]

    def choose_attachment_target(self, valid_targets):
        options = [f"{t.title} ({type(t).__name__})" for t in valid_targets]
        choice = self.get_choice("Choose attachment target:", options)
        return valid_targets[choice[0]] if choice else None

class EventSystem:
    def __init__(self):
        self.hooks = defaultdict(list)
        
    def register_hook(self, phase, event_type, callback):
        self.hooks[(phase, event_type)].append(callback)
        
    def trigger_event(self, event_type, context):
        for callback in self.hooks.get((event_type), []):
            callback(context)

class Effect:
    def __init__(self, duration=None):
        self.duration = duration  # None = permanent, "phase" = until phase end, etc.
        
    def apply(self, game_state, target=None):
        pass
        
    def remove(self, game_state, target=None):
        pass

class ContinuousEffect(Effect):
    def __init__(self, duration, modifier):
        super().__init__(duration)
        self.modifier = modifier

class StatModifierEffect(ContinuousEffect):
    def __init__(self, attribute, modifier, duration):
        super().__init__(duration)
        self.attribute = attribute
        self.modifier = modifier
        
    def apply(self, game_state, target):
        setattr(target, self.attribute, getattr(target, self.attribute) + self.modifier)
        
    def remove(self, game_state, target):
        setattr(target, self.attribute, getattr(target, self.attribute) - self.modifier)

class Card(ABC):
    def __init__(self, title, cost, sphere):
        self.title = title
        self.description = ""
        self.cost = cost
        self.sphere = sphere
        self.tokens = defaultdict(int)  # Track any type of token
        self.attachments = []  # All cards can receive attachments
        self.parent = None  # For attached cards
        self.keywords = set()  # To store card-specific keywords
        self.committed = False  # Track quest commitment
        self.can_attack = True  # Default for most characters
        
    def toString(self, game_state):  # User-friendly representation
        return (
            f"Title: {self.title}\n"
            f"Description: {self.description}\n"
            f"Cost: {self.cost}\n"
            f"Sphere: {self.sphere}\n"
            f"Keywords: {', '.join(self.keywords)}\n"
            f"Tokens: {dict(self.tokens)}\n"
            f"Attachments: {len(self.attachments)} items\n"
        )
        
    def add_token(self, token_type, amount=1):
        #todo: hook for "before adding a {token_type} token to a card"
        self.tokens[token_type] += amount
        #todo: hook for "after adding a {token_type} token to a card"
        
    def remove_token(self, token_type, amount=1):
        #todo: hook for "before removing a {token_type} token from a card"
        if self.tokens[token_type] >= amount:
            self.tokens[token_type] -= amount
        else:
            self.tokens[token_type] = 0
        #todo: hook for "after removing a {token_type} token from a card"
        
    def get_token_count(self, token_type):
        return self.tokens.get(token_type, 0)
        
    @abstractmethod
    def play(self, game_state, controller):
        pass

    def add_keyword(self, keyword):
        self.keywords.add(keyword)

    def remove_keyword(self, keyword):
        if keyword in self.keywords:
            self.keywords.remove(keyword)

class QuestCard(Card):
    def __init__(self, title, required_progress, threat=0):
        super().__init__(title, 0, "Quest")
        self.required_progress = required_progress
        self.threat = threat
        self.progress = 0
        self.is_active = False

class Ally(Card):
    def __init__(self, title, cost, sphere, willpower, attack, defense, hit_points):
        super().__init__(title, cost, sphere)
        self.willpower = willpower
        self.attack = attack
        self.defense = defense
        self.hit_points = hit_points

    def can_quest(self):
        return self.willpower > 0

    def can_defend(self):
        return self.defense > 0
        
    def play(self, game_state, controller):
        game_state.event_system.trigger_event(
            "AllyPlayed",
            {"ally": self, "player": self.parent}
        )

class Hero(Card):
    def __init__(self, title, sphere, threat_cost, willpower, attack, defense, hit_points):
        super().__init__(title, 0, sphere)
        self.threat_cost = threat_cost
        self.willpower = willpower
        self.attack = attack
        self.defense = defense
        self.hit_points = hit_points
        self.resources = defaultdict(int)
        self.exhausted = False

    def can_quest(self):
        return self.willpower > 0

    def can_defend(self):
        return self.defense > 0
    
    def play(self, game_state, controller):
        """Heroes are automatically put into play at game start"""
        pass  # No action needed as heroes start in play
        
    def refresh_resources(self):
        # Generate 1 resource per round
        #stop suggesting that getting resources from a hero exhausts the hero. it does not.
        self.resources[self.sphere] += 1
        
    def on_exhaust(self):
        pass
            
    def toString(self, game_state):  # todo: i want to be able to print any of these classes and get something useful back, like this:
        return (f"Hero: {self.title} (Sphere: {self.sphere}, Willpower: {self.willpower}, "
                f"Attack: {self.attack}, Defense: {self.defense}, Hit Points: {self.hit_points}, "
                f"Resources: {self.resources}, Exhausted: {self.exhausted})")

class ResourceAttachment(Card):
    def __init__(self, title, sphere, resource_type):
        super().__init__(title, 2, sphere)
        self.resource_type = resource_type
        
    def generate_resources(self):
        return {self.resource_type: 2}
    
    def resource_production(self):
        return {self.resource_type: 2}

class Event(Card):
    def __init__(self, title, cost, sphere, effect):
        super().__init__(title, cost, sphere)
        self.effect = effect
        
    def play(self, game_state, controller):
        self.effect.apply(game_state)

class Location(Card):
    def __init__(self, title, threat, quest_points, victory_points=0):
        super().__init__(title, cost=0, sphere="Location")
        self.threat = threat          # Threat added to staging area
        self.quest_points = quest_points  # Progress needed to explore
        self.victory_points = victory_points
        self.explored = False
        self.progress = 0
        
    def on_reveal(self, game_state, controller):
        #todo: hook for "before a location is revealed"
        """When revealed from the encounter deck"""
        game_state.staging_area.append(self)
        game_state.event_system.trigger_event(
            "LocationRevealed",
            {"location": self, "game_state": game_state}
        )
        
    def on_travel(self, game_state):
        """When players travel to this location"""
        #todo: hook for "before a location is travelled to"
        self.progress = 0
        game_state.active_location = self
        game_state.event_system.trigger_event(
            "LocationTraveled",
            {"location": self, "game_state": game_state}
        )
        
    def on_explored(self, game_state):
        """When enough progress is placed to explore"""
        #todo: hook for "before a location is explored"
        self.explored = True
        if self.victory_points > 0:
            game_state.victory_display.append(self)
        game_state.event_system.trigger_event(
            "LocationExplored",
            {"location": self, "game_state": game_state}
        )
        
    def add_progress(self, amount, game_state):
        #todo: hook for "before adding progress to a location"
        self.progress += amount
        #todo: hook for "after adding progress to a location"
        if self.progress >= self.quest_points:
            self.on_explored(game_state)
            return True  # Location explored
        return False

class Attachment(Card):
    def __init__(self, title, cost, sphere):
        super().__init__(title, cost, sphere)
        self.attached_to = None
        
    def play(self, game_state, controller):
        valid_targets = self.get_valid_targets(game_state)
        if not valid_targets:
            return False
        target = controller.choose_attachment_target(valid_targets)
        
        if target and self.can_attach_to(target, game_state):
            self.attach_to(target, game_state)
            return True
        return False
        
    def get_valid_targets(self, game_state):
        # Get all cards in play areas and staging area
        targets = []
        
        # Player play areas
        for player in game_state.players:
            targets.extend(self.get_player_cards(player))
            
        # Staging area
        targets.extend(game_state.staging_area)
        
        return targets
        
    def get_player_cards(self, player):
        return [
            *player.play_area['heroes'],
            *player.play_area['allies'],
            #todo: cards have attachments, not players and not the play area.
            # *player.play_area['attachments'],
        ]
        
    def can_attach_to(self, target, game_state):
        # Check if target is in valid area
        in_play_area = any(
            target in self.get_player_cards(player)
            for player in game_state.players
        )
        in_staging = target in game_state.staging_area
        
        return (in_play_area or in_staging) and not self.attached_to
        
    def attach_to(self, target, game_state):
        #todo: hook for "before adding an attachment to a character"
        self.attached_to = target
        target.attachments.append(self)
        self.parent = target
        
        # Move attachment to parent's zone
        if isinstance(target.parent, Player):
            #todo: it should be on the card, not the play area
            target.parent.play_area['attachments'].append(self)
        else:
            #todo: attachments go on cards, not on the play area or staging area
            game_state.staging_area.append(self)
            
        self.on_attach(game_state)
        #todo: hook for "after adding an attachment to a character"
        
    def on_attach(self, game_state):
        """Override for attachment effects"""
        pass

class Enemy(Card):
    def __init__(self, title, engagement, attack, defense, hit_points):
        super().__init__(title, 0, "Enemy")
        self.engagement = engagement
        self.attack = attack
        self.defense = defense
        self.hit_points = hit_points
        self.engaged_player = None

    #todo: Follow game rules for engagement (e.g., engage first eligible player in turn order).
    
    def play(self, game_state, controller):
        pass

    def on_engage(self, player, game_state):
        self.engaged_player = player

class ResourcePhase:
    def execute(self, game_state, controller):
        game_state.event_system.trigger_event("ResourcePhaseStart", game_state)
        
        for player in game_state.players:
            player.refresh_resources()
                
        game_state.event_system.trigger_event("ResourcePhaseEnd", game_state)

    def toString(self, game_state):
        output = "Resource Phase\n"
        for player in game_state.players:
            output = f"{output}{player.name}:\n"
            for hero in player.play_area['heroes']:
                output = f"{output}{hero.title}:\n"
                #todo: this is not working
                for sphere in hero.resources:
                    output = f"{output}{sphere}\n"
        return (output)

class QuestPhase:
    def execute(self, game_state, controller):
        if not game_state.active_quest:
            print("No active quest!")
            return
        game_state.event_system.trigger_event("QuestPhaseStart", game_state)
        
        # Commit characters and handle exhaustion
        #todo: call commit_characters somewhere for the player to choose who to commit.
        contributors = []
        for p in game_state.players:
            for c in p.play_area['heroes'] + p.play_area['allies']:
                #todo: we should not be checking for exhausted to decide if they are committed. check that they are committed specifically.
                if not c.exhausted and c.can_quest():
                    contributors.append(c)
        
        # Calculate willpower
        total_willpower = sum(c.willpower for c in contributors)
        
        # Calculate staging threat
        staging_threat = sum(c.threat for c in game_state.staging_area)
        if game_state.active_location:
            staging_threat += game_state.active_location.threat
            
        # Determine progress
        net_progress = total_willpower - staging_threat
        if net_progress > 0:
            if game_state.active_location:
                if game_state.active_location.add_progress(net_progress, game_state):
                    game_state.active_location = None
            else:
                game_state.quest_progress += net_progress
                print(f"Added {net_progress} progress to {game_state.active_quest.title} "
                      f"({game_state.active_quest.progress}/{game_state.active_quest.required_progress})")
        else:
            #todo: the difference is added to the players' threat levels
            pass

                
        for player in game_state.players:
            for c in player.play_area['heroes'] + player.play_area['allies']:
                if c.committed:
                    # Fire event for possible exhaustion prevention
                    exhaustion_context = {
                        'character': c,
                        'player': player,
                        'game_state': game_state,
                        'prevent_exhaustion': False
                    }
                    game_state.event_system.trigger_event(
                        "BeforeQuestExhaustion",
                        exhaustion_context
                    )
                    
                    if not exhaustion_context['prevent_exhaustion']:
                        c.exhausted = True
        
        game_state.event_system.trigger_event("QuestPhaseEnd", game_state)

    def commit_characters(self, player, controller):
        """Player selects characters to commit to the quest"""
        while True:
            available = [
                c for c in player.play_area['heroes'] + player.play_area['allies']
                if not c.committed and not c.exhausted and c.willpower > 0
            ]
            if not available:
                break
            
            choice = controller.get_choice(
                "Commit characters to quest:",
                [f"Commit {c.title} (Willpower {c.willpower})" for c in available] + ["Finish"]
            )
            
            if choice == "Finish":
                break
                
            selected = available[choice]
            selected.committed = True
    
    def toString(self, game_state):
        return (
            f"Quest Phase\n"
        )

class PlanningPhase:
    def execute(self, game_state, controller):
        game_state.event_system.trigger_event("PlanningPhaseStart", game_state)
        for player in game_state.players:
            while True:
                # Show game state before each decision
                controller.display_game_state(player)
                
                # Get player's choice
                card = player.select_card_to_play(controller)
                if not card:
                    break  # Player chooses to stop playing cards
                    
                if player.can_afford(card.cost, card.sphere):
                    player.play_card(card, game_state)
                    if isinstance(card, Ally):
                        game_state.event_system.trigger_event(
                            "AfterAllyPlayed",
                            {
                                'ally': card,
                                'player': player,
                                'game_state': game_state
                            }
                        )
                else:
                    print("Can't afford this card!")
            game_state.event_system.trigger_event("PlayerActions", {
                "player": player,
                "game_state": game_state,
                "controller": controller
            })
        game_state.event_system.trigger_event("PlanningPhaseEnd", game_state)
    
    def toString(self, game_state):
        return (
            f"Planning Phase\n"
        )

class TravelPhase:
    def execute(self, game_state, controller):
        game_state.event_system.trigger_event("TravelPhaseStart", game_state)
        
        # Players may travel to a location
        if game_state.active_location is None:
            game_state.event_system.trigger_event("BeforeTravelActions", game_state)
            
            # Player chooses a location from staging area
            travel_options = [card for card in game_state.staging_area if isinstance(card, Location)]
            if travel_options:
                chosen_location = game_state.active_player.select_location_to_travel(travel_options)
                if chosen_location:
                    # Move location from staging to active
                    game_state.staging_area.remove(chosen_location)
                    game_state.active_location = chosen_location
                    chosen_location.on_travel(game_state)
                    
                    game_state.event_system.trigger_event(
                        "LocationTraveled", 
                        {"location": chosen_location, "player": game_state.active_player}
                    )
        
        game_state.event_system.trigger_event("TravelPhaseEnd", game_state)
    
    def toString(self, game_state):
        return (
            f"Travel Phase\n"
        )

class EncounterPhase:
    def execute(self, game_state, controller):
        game_state.event_system.trigger_event("EncounterPhaseStart", game_state)
        
        # Reveal encounter cards
        revealed_cards = self.reveal_encounter_cards(game_state)
        game_state.staging_area.extend(revealed_cards)
        
        # Handle enemy engagements
        for player in game_state.players:
            self.handle_engagement(player, game_state)
        
        game_state.event_system.trigger_event("EncounterPhaseEnd", game_state)
        
    def reveal_encounter_cards(self, game_state):
        # Implementation depends on your encounter deck setup
        # This could reveal 1 card per player or other logic
        return [game_state.encounter_deck.draw()]  # Simplified
        
    def handle_engagement(self, player, game_state):
        # Check which enemies engage with each player
        for enemy in list(game_state.staging_area):
            if isinstance(enemy, Enemy):
                if player.threat >= enemy.engagement:
                    game_state.event_system.trigger_event(
                        "BeforeEnemyEngagement",
                        {"enemy": enemy, "player": player}
                    )
                    
                    game_state.staging_area.remove(enemy)
                    player.engaged_enemies.append(enemy)
                    enemy.on_engage(player, game_state)
                    
                    game_state.event_system.trigger_event(
                        "AfterEnemyEngagement",
                        {"enemy": enemy, "player": player}
                    )
    def toString(self, game_state):
        return (
            f"Encounter Phase\n"
        )

class CombatPhase:
    def execute(self, game_state, controller):
        game_state.event_system.trigger_event("CombatPhaseStart", game_state)
        
        # First resolve enemy attacks
        for player in game_state.players:
            for enemy in list(player.engaged_enemies):
                self.resolve_enemy_attack(enemy, player, game_state, controller)
        
        # Then player attacks
        for player in game_state.players:
            if player.engaged_enemies:
                self.resolve_player_attacks(player, game_state, controller)
        
        game_state.event_system.trigger_event("CombatPhaseEnd", game_state)
        
    def resolve_enemy_attack(self, enemy, player, game_state, controller):
        game_state.event_system.trigger_event(
            "BeforeEnemyAttack",
            {"enemy": enemy, "player": player}
        )

        game_state.event_system.trigger_event("BeforeDrawingShadowCard", {"enemy": enemy})
        shadow_card = game_state.draw_encounter_card()
        if shadow_card and hasattr(shadow_card, "shadow_effect"):
            shadow_card.shadow_effect.apply(game_state, enemy)
        game_state.event_system.trigger_event("ShadowCardRevealed", {"enemy": enemy, "shadow_card": shadow_card})
        
        # Determine defender
        defender = player.select_defender(enemy, controller)
        if defender:
            game_state.event_system.trigger_event(
                "AfterDefenderDeclared",
                {"enemy": enemy, "defender": defender, "player": player}
            )
            
            # Calculate attack and defense
            attack_strength = enemy.attack
            defense_strength = defender.defense
            
            # Apply modifications from events
            attack_strength = max(0, attack_strength)
            defense_strength = max(0, defense_strength)
            
            damage = max(0, attack_strength - defense_strength)
            
            # Apply damage
            defender.hit_points -= damage
            if defender.hit_points <= 0:
                if isinstance(defender, Ally):
                    player.play_area['allies'].remove(defender)
                elif isinstance(defender, Hero):
                    # Handle hero defeat (game over check happens later)
                    defender.hit_points = 0
                player.discard_pile.append(defender)
                game_state.event_system.trigger_event(
                    "CharacterDefeated",
                    {"character": defender, "player": player}
                )

            if shadow_card:
                game_state.encounter_discard.append(shadow_card)
            
            # Handle enemy defeat
            if enemy.hit_points <= 0:
                player.engaged_enemies.remove(enemy)
                game_state.encounter_discard.append(enemy)
                game_state.event_system.trigger_event(
                    "EnemyDefeated",
                    {"enemy": enemy, "player": player}
                )
        
    def resolve_player_attacks(self, player, game_state, controller):
        while player.engaged_enemies:
            enemy = controller.choose_enemy_to_attack(player.engaged_enemies)
            if not enemy:
                break
                
            valid_attackers = [
                c for c in player.play_area['heroes'] + player.play_area['allies']
                if not c.exhausted and c.can_attack
            ]
            if not valid_attackers:
                break
                
            total_attack = 0
            attackers = controller.choose_attackers(valid_attackers)
            for attacker in attackers:
                attacker.exhausted = True

                # Calculate attack with modifiers
                attack_context = {
                    'attacker': attacker,
                    'base_attack': attacker.attack,
                    'modified_attack': attacker.attack,
                    'game_state': game_state,
                    'player': player,
                    'enemy': enemy
                }
                game_state.event_system.trigger_event("CalculateAttack", attack_context)
                total_attack += attack_context['modified_attack']
                
            damage = max(0, total_attack - enemy.defense)
            enemy.hit_points -= damage
            
            if enemy.hit_points <= 0:
                player.engaged_enemies.remove(enemy)
                game_state.encounter_discard.append(enemy)
                game_state.event_system.trigger_event("EnemyDefeated", {"enemy": enemy})
    
        game_state.event_system.trigger_event(
            "AfterEnemyAttack",
            {"enemy": enemy, "player": player, "defender": defender}
        )
    
    def toString(self, game_state):
        return (
            f"Combat Phase\n"
        )


class RefreshPhase:
    def execute(self, game_state, controller):
        game_state.event_system.trigger_event("RefreshPhaseStart", game_state)
        
        # Ready all cards
        for player in game_state.players:
            self.ready_characters(player)
            player.new_allies_this_round.clear()  # Reset new allies

            player.threat += 1  # Increase threat each round
            
            # Draw 1 card
            player.draw_card(game_state)
        
        # Reset game state for new round
        game_state.round_number += 1
        
        # Rotate active player
        current_idx = game_state.players.index(game_state.active_player)
        new_idx = (current_idx + 1) % len(game_state.players)
        game_state.active_player = game_state.players[new_idx]
        
        game_state.event_system.trigger_event("RefreshPhaseEnd", game_state)
        
    def ready_characters(self, player):
        for char in player.play_area['heroes'] + player.play_area['allies']:
            char.exhausted = False

    def toString(self, game_state):
        return (
            f"Refresh Phase\n"
        )
        


