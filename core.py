from abc import ABC, abstractmethod
from collections import defaultdict
import random
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
console = Console()

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
        }
        self.engaged_enemies = []
        self.new_allies_this_round = []
        
    def render(self, game_state):
        panel = Panel(
            f"[b]Player:[/b] {self.name}\n"
            f"[b]Deck:[/b] {len(self.deck)} cards\n"
            f"[b]Discard:[/b] {len(self.discard_pile)} cards\n  ",
            title=f":bust_in_silhouette: {self.name}",
            subtitle=f"Threat: [red]{self.threat}",
            expand=False
        )
        console.print("Hand:")
        for i, card in enumerate(self.hand, start=1):
            colour = card.getColour()
            # Show stats for Allies in hand
            if isinstance(card, Ally):
                details = f"{card.title} (Cost: {card.cost}, WP: {card.willpower}, A: {card.attack}, D: {card.defense}, HP: {card.hit_points})"
            else:
                details = f"{card.title} (Cost: {card.cost})"
            console.print(f"\t{i}: [{colour}]{details}[/{colour}]")
        console.print("Heroes:")
        # Show detailed stats for Heroes
        for idx, hero in enumerate(self.play_area['heroes'], start=1):
            hero.render(game_state)
            # colour = hero.getColour()
            # console.print(f"\t{idx}: [{colour}]{hero.title}[/{colour}] (WP:{hero.willpower}, A:{hero.attack}, D:{hero.defense}, HP:{hero.hit_points})")
        
        console.print("Allies:")
        # Show detailed stats for Allies in play
        for idx, ally in enumerate(self.play_area['allies'], start=1):
            colour = ally.getColour()
            console.print(f"\t{idx}: [{colour}]{ally.title}[/{colour}] (WP:{ally.willpower}, A:{ally.attack}, D:{ally.defense}, HP:{ally.hit_points})")
    
        console.print(panel)
    
    def draw_card(self, game_state, num=1):
        for _ in range(num):
            game_state.event_system.trigger_event("BeforeDrawCard", {"player": self})
            console.print(f"[yellow]{self.name}[/yellow] is drawing a card...")
            if len(self.deck) == 0:
                console.print("\tThe deck is empty. Reshuffling the discard into the deck.")
                self.reshuffle_discard(game_state)
                if len(self.deck) == 0:  # Still empty after reshuffle
                    console.print("[red]Still no cards in the deck, this means you lose![/red]")
                    self.threat = 50  # Immediate loss condition
                    return
            if len(self.deck) > 0:
                drawn_card = self.deck.pop()
                colour = drawn_card.getColour()
                console.print(f"\tDrawn card: [{colour}]{drawn_card.title}[/{colour}]")
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
        
    def play_card(self, card, game_state, controller):
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
            
            card.play(game_state, controller)
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
        game_state = controller.game.game_state
        game_state.event_system.trigger_event("BeforeSelectDefender", 
            {"player": self, "enemy": enemy})
        
        valid_defenders = [c for c in self.play_area['heroes'] + self.play_area['allies']
                        if not c.exhausted and c.can_defend()]
        
        defender = controller.choose_defender(self, enemy, valid_defenders)
        
        game_state.event_system.trigger_event("AfterSelectDefender",
            {"player": self, "enemy": enemy, "defender": defender})
        return defender
    
    def select_location_to_travel(self, locations, controller):
        game_state = controller.game.game_state
        game_state.event_system.trigger_event("BeforeSelectTravelLocation",
            {"player": self, "locations": locations})
        
        choice = controller.choose_location_to_travel(locations)
        
        game_state.event_system.trigger_event("AfterSelectTravelLocation",
            {"player": self, "location": choice})
        return choice

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
        console.rule("Starting game!")
        console.print(f"Active Quest: {self.game_state.active_quest.title}")
        console.print(f"Required Progress: {self.game_state.active_quest.required_progress}")
        #first every player draw 5 cards
        
        console.rule("Setup")
        for player in self.players:
            player.draw_card(self.game_state, 5)

        while not self.check_game_over():
            for phase in self.phases:
                self.game_state.current_phase = type(phase).__name__
                phase.execute(self.game_state, self.controller)
                phase.render(self.game_state)
            console.print(f"[green]Completed round {self.game_state.round_number}[/green]")
                
    def check_game_over(self):
        # Check loss conditions first
        for player in self.game_state.players:
            if player.threat >= 50:
                console.print(f"[red]Game Over![/red] [yellow]{player.name}[/yellow] reached 50 threat!")
                return True
            if not any(isinstance(card, Hero) for card in player.play_area.get('heroes', [])):
                console.print(f"[red]Game Over![/red] [yellow]{player.name}[/yellow] has no surviving heroes!")
                return True

        # Check victory condition
        if (self.game_state.active_quest and 
            self.game_state.active_quest.progress >= self.game_state.active_quest.required_progress):
            console.print(f"[green]Victory![/green] Completed quest: [yellow]{self.game_state.active_quest.title}[/yellow]")
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
        
    def render(self):
        console.print(f"Game State (Round {self.round_number})")
        console.print(f"Phase: {self.current_phase}")
        console.print(f"Quest Progress: {self.active_quest.progress}")
        console.print(f"Active Location: {self.active_location.title if self.active_location else 'None'}")
        console.print(f"Staging Area: {[c.title for c in self.staging_area]}")
        console.print(f"Encounter Deck: {len(self.encounter_deck)} cards")
        # console.print(f"Victory Display: {[c.title for c in self.victory_display]}")
        
    def select_character(self, player):
        # Simple implementation - could be expanded with UI
        return next((c for c in player.play_area['allies'] + player.play_area['heroes']), None)
    
    def draw_encounter_card(game_state):
        if not game_state.encounter_deck:
            game_state.event_system.trigger_event("BeforeEncounterReshuffle",
                {"game_state": game_state})
            game_state.encounter_deck = game_state.encounter_discard
            game_state.encounter_discard = []
            random.shuffle(game_state.encounter_deck)
            game_state.event_system.trigger_event("AfterEncounterReshuffle",
                {"game_state": game_state})
        
        game_state.event_system.trigger_event("BeforeEncounterDraw",
            {"game_state": game_state})
        card = game_state.encounter_deck.pop() if game_state.encounter_deck else None
        game_state.event_system.trigger_event("AfterEncounterDraw",
            {"game_state": game_state, "card": card})
        return card

class GameController:
    def __init__(self, game):
        self.game = game
        self.current_choices = []
        
    def display_game_state(self, player):
        """Show current game state to player"""
        player.render(self.game.game_state)
        
    def choose_player(self, players):
        """Let player choose from available players"""
        options = [p.name for p in players]
        choice = self.get_choice("Choose a player:", options)
        return players[options.index(choice)]

    def get_choice(self, prompt, options, multi_select=False):
        console.log("\n" + prompt)
        for i, option in enumerate(options, 1):
            console.log(f"{i}. {option}")
            
        while True:
            choice = input("Enter choice(s), comma-separated: " if multi_select else "Enter choice: ")
            if multi_select:
                indices = [int(c.strip())-1 for c in choice.split(",") if c.strip().isdigit()]
                if all(0 <= i < len(options) for i in indices):
                    return indices
            else:
                if choice.isdigit() and 1 <= int(choice) <= len(options):
                    return int(choice)-1
            console.log("Invalid choice, try again")

    def choose_card_to_play(self, player):
        playable = [c for c in player.hand if player.can_afford(c.cost, c.sphere)]
        if not playable:
            return None
            
        self.display_game_state(player)
        options = []
        for c in playable:
            # Include stats for Allies in the playable options
            if isinstance(c, Ally):
                option = f"{c.title} (Cost: {c.cost} {c.sphere}, WP: {c.willpower}, A: {c.attack}, D: {c.defense}, HP: {c.hit_points})"
            else:
                option = f"{c.title} ({c.cost} {c.sphere})"
            options.append(option)
        options.append("Pass")
        choice_idx = self.get_choice("Choose a card to play:", options)
        
        if choice_idx == len(options) - 1:  # "Pass" selected
            return None
        return playable[choice_idx]

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
        
    def register_hook(self, event_type, callback):
        self.hooks[(event_type)].append(callback)
        
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

    def getColour(self):
        if self.sphere == 'Leadership':
            return 'purple'
        elif self.sphere == 'Tactics':
            return 'red'
        elif self.sphere == 'Spirit':
            return 'blue'
        elif self.sphere == 'Lore':
            return 'green'
        elif self.sphere == 'Neutral':
            return 'white'
        return 'yellow'
        
    def render(self, game_state):  # User-friendly representation
        console.print(f"Title: {self.title}")
        console.print(f"Description: {self.description}")
        console.print(f"Cost: {self.cost}")
        console.print(f"Sphere: [{self.getColour()}]{self.sphere}")
        console.print(f"Keywords: {', '.join(self.keywords)}")
        console.print(f"Tokens: {dict(self.tokens)}")
        console.print(f"Attachments: {len(self.attachments)} items")
        
    def add_token(self, token_type, amount=1):
        game_state.event_system.trigger_event(f"BeforeAddToken:{token_type}",
            {"card": self, "amount": amount})
        self.tokens[token_type] += amount
        game_state.event_system.trigger_event(f"AfterAddToken:{token_type}",
            {"card": self, "amount": amount})
        
    def remove_token(self, token_type, amount=1):
        game_state.event_system.trigger_event(f"BeforeRemoveToken:{token_type}",
            {"card": self, "amount": amount})
        if self.tokens[token_type] >= amount:
            self.tokens[token_type] -= amount
        else:
            self.tokens[token_type] = 0
        game_state.event_system.trigger_event(f"AfterRemoveToken:{token_type}",
            {"card": self, "amount": amount})
        
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

# todo: Character Keywords:
# Unique: As discussed, only one copy of a Unique card with the same title can be in play at a time.
# Restricted: Limits the number of powerful attachments a character can have.

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

#todo: heroes are characters too, so the character keywords apply to heroes as well
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
        console.print(f"Adding 1 [{self.getColour()}]{self.sphere}[/{self.getColour()}] resource to {self.title}")
        self.resources[self.sphere] += 1
        
    def on_exhaust(self):
        pass
            
    def render(self, game_state):  # todo: i want to be able to print any of these classes and get something useful back, like this:
        exhausted = ""
        if({self.exhausted}):
            exhausted = "[orange](Exhausted)"
        console.print(f"[{self.getColour()}]{self.title} ({self.sphere})[/{self.getColour()}] {exhausted}")
        console.print(f"WP: {self.willpower}, A: {self.attack}, D: {self.defense}, HP: {self.hit_points}")
        for sphere in self.resources:
            console.print(f"\t[{self.getColour()}]{sphere} Resources[/{self.getColour()}]: {self.resources[sphere]}")
        for attachment in self.attachments:
            console.print(f"\t{attachment.title}")

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
        game_state.event_system.trigger_event("BeforeAddProgress",
            {"location": self, "amount": amount})
        self.progress += amount
        game_state.event_system.trigger_event("AfterAddProgress",
            {"location": self, "amount": amount})
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
        targets = []
        # Player cards
        for player in game_state.players:
            #todo: the attachment card itself should determine what valid targets are. some cards are for heroes only, etc.
            targets += player.play_area['heroes']
            targets += player.play_area['allies']
            for card in player.play_area['heroes'] + player.play_area['allies']:
                targets += card.attachments  # Attach to other attachments?
        # Encounter cards
        targets += game_state.staging_area
        return [t for t in targets if self.can_attach_to(t,game_state)]

        
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

    def engage(self, player, game_state):
        self.engaged_player = player
        game_state.staging_area.remove(self)
        player.engaged_enemies.append(self)

class ResourcePhase:
    def execute(self, game_state, controller):
        console.rule("Resource Phase")
        game_state.event_system.trigger_event("ResourcePhaseStart", game_state)
        
        for player in game_state.players:
            player.refresh_resources()
                
        game_state.event_system.trigger_event("ResourcePhaseEnd", game_state)

    def render(self, game_state):
        for player in game_state.players:
            console.print(f"Player: [yellow]{player.name}")
            for hero in player.play_area['heroes']:
                console.print(f"[{hero.getColour()}]{hero.title}[/{hero.getColour()}]")
                for sphere in hero.resources:
                    console.print(f"\t[{hero.getColour()}]{sphere}[/{hero.getColour()}]: {hero.resources[sphere]}")

class QuestPhase:
    def execute(self, game_state, controller):
        console.rule("Quest Phase")
        if not game_state.active_quest:
            console.log("No active quest!")
            return
        game_state.event_system.trigger_event("QuestPhaseStart", game_state)
        
        # Commit characters and handle exhaustion
        contributors = []
        for p in game_state.players:
            self.commit_characters(player, controller)
        
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
                console.log(f"Added {net_progress} progress to {game_state.active_quest.title} "
                      f"({game_state.active_quest.progress}/{game_state.active_quest.required_progress})")
        else:
            threat_increase = -net_progress
            for player in game_state.players:
                player.threat += threat_increase

                
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

    def commit_characters(controller, player):
        # Controller method
        available = [c for c in player.play_area['heroes'] + player.play_area['allies']
                    if not c.exhausted and c.can_quest()]
        
        choices = controller.get_choice(
            "Select characters to commit to quest:",
            [f"{c.title} (Willpower {c.willpower})" for c in available],
            multi_select=True
        )
        
        for idx in choices:
            available[idx].committed = True
    
    def render(self, game_state):
        pass

class PlanningPhase:
    def execute(self, game_state, controller):
        console.rule("Planning Phase")
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
                    player.play_card(card, game_state, controller)
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
                    console.log("Can't afford this card!")
            game_state.event_system.trigger_event("PlayerActions", {
                "player": player,
                "game_state": game_state,
                "controller": controller
            })
        game_state.event_system.trigger_event("PlanningPhaseEnd", game_state)
    
    def render(self, game_state):
        pass

class TravelPhase:
    def execute(self, game_state, controller):
        console.rule("Travel Phase")

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
    
    def render(self, game_state):
        pass

class EncounterPhase:
    def execute(self, game_state, controller):
        console.rule("Encounter Phase")

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
        
    def handle_engagement(self, game_state):
        players_in_order = game_state.players[game_state.active_player_idx:] + \
                      game_state.players[:game_state.active_player_idx]
        game_state.event_system.trigger_event(
            "BeforeEnemyEngagement",
            {"enemy": enemy, "player": player}
        )
        for enemy in list(game_state.staging_area):
            if isinstance(enemy, Enemy):
                for player in players_in_order:
                    if player.threat >= enemy.engagement:
                        enemy.engage(player,game_state)
                        break
                    
                game_state.event_system.trigger_event(
                    "AfterEnemyEngagement",
                    {"enemy": enemy, "player": player}
                )
    def render(self, game_state):
        pass

# todo: Combat Keywords:
# Ranged: Allows a character to attack enemies engaged with other players.
# Sentinel: Allows a character to defend an attack against another player's hero.
# Guard: Forces enemies to attack the character with Guard first.
# Stealth: Makes a character untargetable by enemies until revealed.
# Ambush: Allows an enemy to make an immediate attack when revealed.
# Doomed: Forces all players to raise their threat level.
# Surge: Draw an extra encounter card.
# Time X: Puts time counters on a card, which are removed each round.
# Victory: Awards victory points when a card is defeated.
class CombatPhase:
    def execute(self, game_state, controller):
        console.rule("Combat Phase")

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
        
        game_state.encounter_discard.append(shadow_card)
        #todo: does that ^ remove it from the enemy card?

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
    
    def render(self, game_state):
        pass

class RefreshPhase:
    def execute(self, game_state, controller):
        console.rule("Refresh Phase")

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

    def render(self, game_state):
        pass        


