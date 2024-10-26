import discord
import asyncio
from asyncio import Event

from game import CardGame, GameView


class HigherLower(CardGame):
    def __init__(self):
        super().__init__()
        self.player_hand = ""  # face down card
        self.dealer_hand = ""  # face up card
        self.game_over = False

    def deal_initial_cards(self):
        """Deals the initial card to the player and dealer."""
        self.player_hand = self.deal_card()
        self.dealer_hand = self.deal_card()

    def check_win(self, higher):
        player_rank = self.get_value(self.player_hand)
        dealer_rank = self.get_value(self.dealer_hand)

        if player_rank == dealer_rank: # tie
            return 2
        
        if higher:
            if player_rank > dealer_rank:
                return 1  # win
            else:
                return 0  # loss
        else:
            if dealer_rank > player_rank:
                return 1  # win
            else:
                return 0  # loss

    def get_value(self, card):
        rank = card.split(' ')[0]
        value = 0

        if rank == 'J':
            value += 11
        elif rank == 'Q':
            value += 12
        elif rank == 'K':
            value += 13
        elif rank == 'A':
            value += 14
        else:
            value += int(rank)
        return value

    async def start_game(self, interaction: discord.Interaction, bet: int):
        self.deal_initial_cards()

        embed = discord.Embed(title="High-Low", description="Your card: Higher or Lower?", color=0x005B33)
        embed.add_field(name="Pot (25% per win): ", value=str(bet) + " gold", inline=False)
        embed.add_field(name="Dealer's card: ", value=self.dealer_hand, inline=False)
        embed.add_field(name="Your card: ", value="?", inline=False)
        embed.add_field(name="Current Streak: ", value="0", inline=False)

        view = HigherLowerView(self, interaction.user, bet)
        await interaction.response.send_message(embed=embed, view=view)

        # Await the game result after the game is finished
        await view.wait_for_game_result()
        return view.pot # Return the amount earned for main.py


class HigherLowerView(GameView):
    def __init__(self, game, player, bet):
        super().__init__(game, player, bet)
        self.event = Event() 
        self.result_value = None  # 0 - Lose, 1 - Win, 2 - Tie, 3 - Cash out
        self.pot = bet  # amount earned
        self.streak = 0  # number of wins in a row

        # Initialize with only the higher and lower buttons
        self.add_higher_lower_buttons()
    
    def end_game(self):  # assumes pot is valid number
        self.clear_items()
        self.event.set()

    async def update_game_state(self, interaction: discord.Interaction):
        if self.result_value == 3:  # Cashing out
            self.pot = int(self.pot)
            embed = discord.Embed(
                title="HigherLower",
                description=f"You cashed out **{self.pot} gold** with a streak of {self.streak}!",
                color=0x005B33
            )
            await interaction.response.edit_message(embed=embed, view=None)  # Remove buttons on cash out
            self.end_game()  # Call to end the game
            return  # Exit the function after cashing out

        embed = discord.Embed(title="High-Low", description="Your card: Higher or Lower?", color=0x005B33)
        embed.add_field(name="Pot (25% per win): ", value=str(int(self.pot)) + " Gold", inline=False)
        embed.add_field(name="Dealer's card: ", value=self.game.dealer_hand, inline=False)
        embed.add_field(name="Your card: ", value="?", inline=False)
        embed.add_field(name="Current Streak: ", value=self.streak, inline=False)

        # print(self.game.player_hand)  # TESTING

        if self.result_value is not None:
            embed.set_field_at(2, name="Your card: ", value=self.game.player_hand, inline=False)

            if self.result_value == 1:
                game_result_text = "You Win!"
                self.pot = self.pot * 1.25  # keep as float until cash out
                self.streak += 1
                embed.set_field_at(0, name="Pot (25% per win): ", value=str(int(self.pot)) + " Gold", inline=False)
                embed.set_field_at(3, name="Current Streak: ", value=self.streak, inline=False)
                self.add_cashout_continue_buttons()  # Add buttons only if the player wins
            elif self.result_value == 0:
                game_result_text = "You Lose!"
                self.pot = 0
                self.end_game()
            elif self.result_value == 2:
                game_result_text = "It's a tie!"
                self.add_cashout_continue_buttons()
            
            embed.add_field(name="Result", value=game_result_text, inline=False)

        await interaction.response.edit_message(embed=embed, view=self, delete_after=60)


    def add_higher_lower_buttons(self):
        self.clear_items()  # Clear existing buttons before adding new ones
        higher_button = discord.ui.Button(label="Higher", style=discord.ButtonStyle.primary)
        lower_button = discord.ui.Button(label="Lower", style=discord.ButtonStyle.secondary)

        higher_button.callback = self.handle_higher
        lower_button.callback = self.handle_lower

        self.add_item(higher_button)
        self.add_item(lower_button)

    def add_cashout_continue_buttons(self):
        """Add buttons for cash out and continue after a win."""
        self.clear_items()  # Clear existing buttons before adding new ones
        cash_out_button = discord.ui.Button(label="Cash Out", style=discord.ButtonStyle.success)
        continue_button = discord.ui.Button(label="Continue", style=discord.ButtonStyle.primary)

        cash_out_button.callback = self.handle_cash_out
        continue_button.callback = self.handle_continue

        self.add_item(cash_out_button)
        self.add_item(continue_button)


    async def handle_higher(self, interaction: discord.Interaction):
        if interaction.user != self.player:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        
        self.result_value = self.game.check_win(higher=True)
        await self.update_game_state(interaction)

    async def handle_lower(self, interaction: discord.Interaction):
        if interaction.user != self.player:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        
        self.result_value = self.game.check_win(higher=False)
        await self.update_game_state(interaction)

    async def handle_cash_out(self, interaction: discord.Interaction):
        if interaction.user != self.player:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        
        self.result_value = 3
        await self.update_game_state(interaction)

    async def handle_continue(self, interaction: discord.Interaction):
        if interaction.user != self.player:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return
        
        self.game.dealer_hand = self.game.player_hand  # move current player card to become next round dealers
        self.game.player_hand = self.game.deal_card()  # draw new card for player
        self.result_value = None  # Reset result for the new round

        self.add_higher_lower_buttons()
        await self.update_game_state(interaction)  # Update game state to reflect the new round

    async def wait_for_game_result(self):
        await self.event.wait()  # Wait for the game to finish
        return self.result_value
    
    
