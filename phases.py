class Phase(ABC):
    def end(self, game_state):
        game_state.event_system.trigger_event("EndOfPhase", {"game_state": game_state})

class ResourcePhase(Phase):
    def execute(self, game_state, controller):
        
        game_state.event_system.trigger_event("ResourcePhaseStart", game_state)
        controller.display_game_state()
        console.rule("Resource Phase")
        
        for player in game_state.players:
            console.print(f"Refreshing [yellow]{player.name}...")
            player.refresh_resources()
                
        game_state.event_system.trigger_event("ResourcePhaseEnd", game_state)
        self.end(game_state)

    def render(self, game_state):
        pass

class QuestPhase(Phase):
    def execute(self, game_state, controller):
        
        
        game_state.event_system.trigger_event("QuestPhaseStart", game_state)
        controller.display_game_state()
        console.rule("Quest Phase")
        if not game_state.active_quest:
            console.log("No active quest!")
            return
        
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
        self.end(game_state)

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

class PlanningPhase(Phase):
    def execute(self, game_state, controller):
        
        game_state.event_system.trigger_event("PlanningPhaseStart", game_state)
        controller.display_game_state()
        console.rule("Planning Phase")
        for player in game_state.players:
            while True:
                player.render(game_state)
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
        self.end(game_state)
    
    def render(self, game_state):
        pass

class TravelPhase(Phase):
    def execute(self, game_state, controller):
        

        game_state.event_system.trigger_event("TravelPhaseStart", game_state)
        controller.display_game_state()
        console.rule("Travel Phase")
        
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
        self.end(game_state)
    
    def render(self, game_state):
        pass

class EncounterPhase(Phase):
    def execute(self, game_state, controller):
        

        game_state.event_system.trigger_event("EncounterPhaseStart", game_state)
        controller.display_game_state()
        console.rule("Encounter Phase")
        
        # Reveal encounter cards
        revealed_cards = self.reveal_encounter_cards(game_state)
        game_state.staging_area.extend(revealed_cards)
        
        # Handle enemy engagements
        for player in game_state.players:
            self.handle_engagement(player, game_state)
        
        game_state.event_system.trigger_event("EncounterPhaseEnd", game_state)
        self.end(game_state)
        
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
class CombatPhase(Phase):
    def execute(self, game_state, controller):
        

        game_state.event_system.trigger_event("CombatPhaseStart", game_state)
        controller.display_game_state()
        console.rule("Combat Phase")
        
        # First resolve enemy attacks
        for player in game_state.players:
            for enemy in list(player.engaged_enemies):
                self.resolve_enemy_attack(enemy, player, game_state, controller)
        
        # Then player attacks
        for player in game_state.players:
            if player.engaged_enemies:
                self.resolve_player_attacks(player, game_state, controller)
        
        game_state.event_system.trigger_event("CombatPhaseEnd", game_state)
        self.end(game_state)
        
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

class RefreshPhase(Phase):
    def execute(self, game_state, controller):
        

        game_state.event_system.trigger_event("RefreshPhaseStart", game_state)
        controller.display_game_state()
        console.rule("Refresh Phase")
        
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
        self.end(game_state)
        
        
    def ready_characters(self, player):
        for char in player.play_area['heroes'] + player.play_area['allies']:
            char.exhausted = False

    def render(self, game_state):
        pass