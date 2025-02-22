from abc import ABC, abstractmethod
from collections import defaultdict
import random
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.console import Console, Group
from rich.text import Text
from rich.layout import Layout
from rich.columns import Columns


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
        # Build list of renderables for the hand
        hand_renderables = []
        for i, card in enumerate(self.hand, 1):
            hand_renderables.append(card.render_panel(in_hand=True, show_description=True))
        
        # Create Group with all renderables
        hand_group = Group(*hand_renderables)
        
        panel = Panel(
            hand_group,
            title=f":bust_in_silhouette: {self.name}'s Hand",
            subtitle=f"Threat: [red]{self.threat}",
            expand=False
        )
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
        console.print(f"Active Quest: [yellow]{self.game_state.active_quest.title}[/yellow]")
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
        console.print(f"Staging Are🗡️ {[c.title for c in self.staging_area]}")
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
        
    def display_game_state(self):
        # Render active quest and location
        active_quest_panel = Panel(
            f"[yellow]{self.game.game_state.active_quest.title}[/yellow]",
            title=":scroll: Active Quest",
            subtitle=f"[white]{self.game.game_state.active_quest.progress}[white]/[white]{self.game.game_state.active_quest.required_progress}",
            expand=False
        )
        console.print(active_quest_panel)

        # Render staging area
        staging_area_panel = Panel(
            "\n".join([f"{card.title} (Threat: {card.threat})" for card in self.game.game_state.staging_area]),
            title=":crossed_swords: Staging Area",
            expand=False
        )
        console.print(staging_area_panel, style="on #220000")
        
        # Render each player's play area and engaged enemies
        for p in self.game.game_state.players:

            play_area_panels = []

            engaged_enemies_panel = Panel(
                "\n".join([f"{enemy.title} (💪{enemy.attack}, ✋{enemy.defense}, ❤️{enemy.hit_points})" for enemy in p.engaged_enemies]),
                title=f":japanese_ogre: {p.name}'s Engaged Enemies",
                expand=False,
                style="on #220000"
            )
            play_area_panels.append(engaged_enemies_panel)
            for card in p.play_area['heroes'] + p.play_area['allies']:
                card_panel = card.render_panel()
                play_area_panels.append(card_panel)

            if play_area_panels:
                columns = Columns(play_area_panels, equal=True) # equal=True ensures they have equal width
                play_area_panel = Panel(
                    columns,
                    title=f":bust_in_silhouette: {p.name}'s Play Area",
                    expand=False
                )
                console.print(play_area_panel, style="on #222222")
            else:
                empty_panel = Panel("[italic]No cards in play area[/italic]", title=f":bust_in_silhouette: {p.name}'s Play Area", expand=False)
                console.print(empty_panel)

        
        if self.game.game_state.active_location:
            active_location_panel = Panel(
                f"{self.game.game_state.active_location.title}\nProgress: {self.game.game_state.active_location.progress}/{self.game.game_state.active_location.quest_points}",
                title=":round_pushpin: Active Location",
                expand=False
            )
            console.print(active_location_panel)
        
    def inspect_card(self):
        card_name = input("Enter card name to inspect: ")
        card = self.find_card(card_name)
        if card:
            console.print(card.render_panel(show_description=True))
        else:
            console.print(f"[red]Card '{card_name}' not found!")

    def find_card(self, name):
        # Search all game zones
        zones = [
            *self.game.game_state.encounter_deck,
            *self.game.game_state.encounter_discard,
            *self.game.game_state.staging_area,
            *self.game.game_state.victory_display
        ]
        
        for player in self.game.game_state.players:
            zones.extend([
                *player.hand,
                *player.deck,
                *player.discard_pile,
                *player.play_area['heroes'],
                *player.play_area['allies']
            ])
            
        return next((c for c in zones if c.title.lower() == name.lower()), None)

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
        while True:
            # Show all cards in hand with basic info
            options = []
            for i, card in enumerate(player.hand, 1):
                option = f"{card.title} ({card.cost} {card.sphere})"
                options.append(option)
            options.append("Pass")
            
            # Get initial card selection
            choice = self.get_choice("Choose a card to view or Pass:", options)
            if choice == len(options)-1:
                return None  # Player chose Pass
            
            selected_card = player.hand[choice]
            
            # Show detailed card view
            console.clear()
            console.print(selected_card.render_panel(in_hand=False, show_description=True))
            
            # Check if playable
            if player.can_afford(selected_card.cost, selected_card.sphere):
                play_choice = self.get_choice(
                    f"Play {selected_card.title}? (Cost: {selected_card.cost} {selected_card.sphere})", 
                    ["Play", "Back to hand"]
                )
                if play_choice == 0:
                    return selected_card
            else:
                console.print(f"[red]Can't afford {selected_card.title}![/red]")
                input("Press Enter to continue...")

    def choose_defender(self, player, enemy, valid_defenders):
        """Let player choose defender for an attack"""
        
        player.render(self.game.game_state)
        options = [f"{c.title} (✋{c.defense})" for c in valid_defenders] + ["No defender"]
        choice = self.get_choice(f"Choose defender against {enemy.title}:", options)
        
        if choice == "No defender":
            return None
        return valid_defenders[options.index(choice)]

    def choose_enemy_to_attack(self, player, enemies):
        options = [f"{e.title} (💖 {e.hit_points})" for e in enemies] + ["Pass"]
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
    def __init__(self, expiration_event=None):
        self.expiration_event = expiration_event

    def apply(self, game_state, target=None):
        if self.expiration_event:
            game_state.event_system.register_hook(self.expiration_event, self.remove)

    def remove(self, context):
        pass

class ContinuousEffect(Effect):
    def __init__(self, duration, modifier):
        super().__init__(duration)
        self.modifier = modifier

class StatModifierEffect(ContinuousEffect):
    def __init__(self, attribute, modifier, expiration_event=None):
        super().__init__(expiration_event)
        self.attribute = attribute
        self.modifier = modifier

    def apply(self, game_state, target):
        setattr(target, self.attribute, getattr(target, self.attribute) + self.modifier)
        super().apply(game_state, target)  # Register for event-based expiration

    def remove(self, context):
        target = context.get('target')
        if target:
            setattr(target, self.attribute, getattr(target, self.attribute) - self.modifier)
