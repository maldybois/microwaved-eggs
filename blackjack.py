import discord
from asyncio import Event

from game import CardGame, GameView


class BlackjackGame(CardGame):
    def __init__(self, can_double):
        super().__init__()
        self.player_hand = []
        self.dealer_hand = []
        self.player_stand = False
        self.game_over = False
        self.can_double = can_double  # if user has enough money to double down or split
        self.doubled = False  # if user has doubled their wager

    def deal_initial_cards(self):
        """Deals the initial two cards to the player and dealer."""
        self.player_hand = [self.deal_card(), self.deal_card()]
        self.dealer_hand = [self.deal_card(), self.deal_card()]

    def hit(self, hand):
        """Deals one card to the specified hand."""
        hand.append(self.deal_card())

    def calculate_score(self, hand):
        """Calculates the score of a given hand."""
        score = 0
        ace_count = 0

        for card in hand:
            rank = card.split(" ")[0]
            if rank in ["J", "Q", "K"]:
                score += 10
            elif rank == "A":
                score += 11
                ace_count += 1
            else:
                score += int(rank)

        while score > 21 and ace_count:
            score -= 10
            ace_count -= 1

        return score

    def dealer_should_hit(self):
        """Determines if the dealer should hit based on their score."""
        return self.calculate_score(self.dealer_hand) < 17

    def check_winner(self):
        """Checks for the winner of the game."""
        player_score = self.calculate_score(self.player_hand)
        dealer_score = self.calculate_score(self.dealer_hand)

        if player_score == 21 and len(self.player_hand) == 2:
            return "Player hits Blackjack! Player wins!", 3  # Player wins (Blackjack)
        elif player_score > 21:
            return "Player busts! Dealer wins.", 1  # Dealer wins
        elif dealer_score > 21:
            return "Dealer busts! Player wins!", 0  # Player wins
        elif dealer_score == 21 and len(self.dealer_hand) == 2:
            return "Dealer hits Blackjack! Dealer wins!", 1  # Dealer wins (Blackjack)
        elif self.player_stand:
            if player_score > dealer_score:
                return "Player wins!", 0  # Player wins
            elif dealer_score > player_score:
                return "Dealer wins!", 1  # Dealer wins
            else:
                return "It's a push! Your bet is refunded.", 2  # Push (tie)

        return "Game still in progress.", -1  # Game is still ongoing

    async def start_game(self, interaction: discord.Interaction, bet: int):
        self.deal_initial_cards()

        embed = discord.Embed(
            title="Blackjack", description="Your move: Hit or Stand?", color=0x005B33
        )
        player_score = self.calculate_score(self.player_hand)
        dealer_card = self.dealer_hand[0]

        embed.add_field(name="Bet: ", value=str(bet) + " Gold", inline=False)
        embed.add_field(
            name="Your Hand",
            value=f"{', '.join(self.player_hand)} (Score: {player_score})",
            inline=False,
        )
        embed.add_field(name="Dealer's Hand", value=f"{dealer_card}, ?", inline=False)
        embed.set_thumbnail(
            url="https://png.pngtree.com/png-vector/20220812/ourmid/pngtree-blackjack-png-image_6107450.png"
        )

        view = BlackjackView(self, interaction.user, bet)
        await interaction.response.send_message(embed=embed, view=view)

        # Await the game result after the game is finished
        res, did_double = await view.wait_for_game_result()
        return (
            res,
            did_double,
        )  # Return the amount of money gained to main.py (negative value for money lost)


class BlackjackView(GameView):
    def __init__(self, game, player, bet):
        super().__init__(game, player, bet)
        self.event = Event()
        self.result_value = None
        self.did_double = False

    async def update_game_state(self, interaction: discord.Interaction):
        player_score = self.game.calculate_score(self.game.player_hand)
        dealer_card = self.game.dealer_hand[0]

        embed = discord.Embed(
            title="Blackjack", description="Your move: Hit or Stand?", color=0x005B33
        )
        embed.add_field(name="Bet: ", value=str(self.bet) + " Gold", inline=False)
        embed.add_field(
            name="Your Hand",
            value=f"{', '.join(self.game.player_hand)} (Score: {player_score})",
            inline=False,
        )
        embed.add_field(name="Dealer's Hand", value=f"{dealer_card}, ?", inline=False)
        embed.set_thumbnail(
            url="https://png.pngtree.com/png-vector/20220812/ourmid/pngtree-blackjack-png-image_6107450.png"
        )

        if self.game.game_over:
            dealer_score = self.game.calculate_score(self.game.dealer_hand)
            embed.set_field_at(
                2,
                name="Dealer's Hand",
                value=f"{', '.join(self.game.dealer_hand)} (Score: {dealer_score})",
                inline=False,
            )

            game_result_text = await self.finalize_game(interaction)
            embed.add_field(name="Result", value=game_result_text, inline=False)
            self.clear_items()  # Disable buttons if game is over

            # Set the result value once the game is over
            self.result_value = self.check_winner()[1]  # Get the result value

            self.event.set()  # Signal that the game is over

        await interaction.response.edit_message(embed=embed, view=self, delete_after=60)

    async def wait_for_game_result(self):
        """Wait until the game is over and return the amount gained."""
        await self.event.wait()  # Wait for the event to be set when the game ends

        if self.result_value == 3:
            return self.bet * 2.5, self.did_double
        elif self.result_value == 0:
            return self.bet * 2, self.did_double
        elif self.result_value == 1:
            return self.bet * -1, self.did_double
        return 0, self.did_double

    def check_winner(self):
        return self.game.check_winner()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit_button(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        if interaction.user != self.player:
            await interaction.response.send_message(
                "This is not your game!", ephemeral=True
            )
            return

        self.game.hit(self.game.player_hand)
        player_score = self.game.calculate_score(self.game.player_hand)

        if player_score >= 21:
            self.game.player_stand = True
            self.game.game_over = True

        await self.update_game_state(interaction)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand_button(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        if interaction.user != self.player:
            await interaction.response.send_message(
                "This is not your game!", ephemeral=True
            )
            return

        self.game.player_stand = True

        while self.game.dealer_should_hit():
            self.game.hit(self.game.dealer_hand)

        self.game.game_over = True
        await self.update_game_state(interaction)

    @discord.ui.button(label="Double Down", style=discord.ButtonStyle.secondary)
    async def double_down_button(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        if interaction.user != self.player:
            await interaction.response.send_message(
                "This is not your game!", ephemeral=True
            )
            return
        if not self.game.can_double:
            await interaction.response.send_message(
                "You don't have enough money to double down!", ephemeral=True
            )
            return

        self.bet *= 2
        self.did_double = True

        self.game.hit(self.game.player_hand)
        self.game.player_stand = True

        while self.game.dealer_should_hit():
            self.game.hit(self.game.dealer_hand)

        self.game.game_over = True
        await self.update_game_state(interaction)

    async def finalize_game(self, interaction: discord.Interaction):
        """Finalizes the game and updates the player's gold based on the outcome."""
        game_result_text, game_result_value = self.check_winner()

        if game_result_value == 0:  # Player wins
            game_result_text += (
                f"\nYou win {self.bet * 2} gold! <:POGGERS:596542804608679955>"
            )
        elif game_result_value == 1:  # Dealer wins
            game_result_text += (
                f"\nYou lost {self.bet} gold... <:Sadge:730242135332356157>"
            )
        elif game_result_value == 3:  # Blackjack win
            game_result_text += (
                f"\nYou win {self.bet * 3} gold! <:POGGERS:596542804608679955>"
            )

        self.result_value = game_result_value  # Set the result value here
        self.event.set()  # Signal that the game has finished
        return game_result_text
