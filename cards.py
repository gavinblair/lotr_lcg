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
    
    def render_panel(self, in_hand=False, show_description=True):
        color = self.getColour()
        title = f"{self.title}"
        
        # Always show cost/sphere when in hand
        if in_hand:
            title += f" (Cost: {self.cost} {self.sphere})"
        
        # Create main panel components
        panel_elements = [Text(title)]
        
        # Show full description when viewing
        if show_description and self.description:
            panel_elements.append(Panel.fit(self.description, border_style=color))
        
        # Add type-specific stats
        stats_text = Text()
        if isinstance(self, (Hero, Ally, Enemy)):
            stats = []
            if hasattr(self, 'willpower'):
                stats.append(f"😤 {self.willpower}")
            if hasattr(self, 'attack'):
                stats.append(f"💪 {self.attack}")
            if hasattr(self, 'defense'):
                stats.append(f"✋ {self.defense}")
            if hasattr(self, 'hit_points'):
                stats.append(f"💖 {self.hit_points}")
            
            # Join stats into a single line
            stats_line = " ".join(stats)
            stats_text.append(stats_line)
            
            if hasattr(self, 'keywords') and self.keywords:
                keywords_str = ", ".join(self.keywords)
                stats_text.append(f"\n{keywords_str}") #keywords on a new line.
        
        panel_elements.append(stats_text)
        
        return Panel(
            Group(*panel_elements),
            border_style=color,
            expand=False
        )
        
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

    def render_panel(self, in_hand=False, show_description=True):
        base_panel = super().render_panel(in_hand, show_description)
        # Add hero-specific status
        status = []
        if self.exhausted:
            status.append("[orange]Exhausted[/orange]")
        if self.committed:
            status.append("[green]Committed[/green]")

        for sphere in self.resources:
            status.append(f"\t{sphere} Resources: {self.resources[sphere]}")
        for attachment in self.attachments:
            status.append(f"\t{attachment.title}")

        if status:
            return Panel(
                Group(base_panel, Text(" ".join(status))),
                border_style=self.getColour()
            )
        return base_panel
            
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

    def render_panel(self, in_hand=False, show_description=True):
        panel = super().render_panel(in_hand, show_description)
        progress_bar = Text(
            f"Progress: {'■' * self.progress}{'□' * (self.quest_points - self.progress)}"
        )
        return Panel(Group(panel, progress_bar), border_style=self.getColour())

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


