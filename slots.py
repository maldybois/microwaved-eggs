import discord

from game import GameView
import random
from asyncio import Event, sleep

class SlotsGame():
    def __init__(self):
        self.symbols = ["🍒", "🍋", "🍉", "🍇", "🍎"]

    def generate_spins(self, spin_count=1):
        # return a list of a set of 3 random symbols for the amount of spins
        spins = []
        for _ in range(spin_count):
            spin = [random.randint(0, len(self.symbols)-1) for _ in range(3)]
            spins.append(spin)
        return spins
    
    def check_win(self, slots):
        if slots[0] == slots[1] == slots[2]:
            return 3
        elif slots[0] == slots[1] or slots[1] == slots[2]:
            return 2
        else:
            return -1
    
    async def start_game(self, interaction: discord.Interaction, bet: int):
        view = SlotsView(self, interaction.user, bet)
        embed = discord.Embed(title="🎰  Slots  🎰", description=f"🪙 Bet: {bet} gold 🪙", color=discord.Color.yellow())
        embed.add_field(name="Slot Spin", value="🟦 🟦 🟦", inline=False)
        embed.add_field(name="Result", value="❓ Good Luck! ❓", inline=True)
        await interaction.response.send_message(embed=embed, view=view)

        result = await view.wait_for_result()
        return result * bet
        

class SlotsView(GameView):
    def __init__(self, game, player, bet):
        super().__init__(game, player, bet)
        self.event = Event()
        self.result = 0
        self.bet = bet

    async def wait_for_result(self):
        await self.event.wait()
        return self.result
        
    async def update_game_state(self, interaction: discord.Interaction):
        print("Updating game state")
        embed = discord.Embed(title="🎰  Slots  🎰", description=f"🪙 Bet: {self.bet} gold 🪙", color=discord.Color.yellow())
        embed.add_field(name="Slot Spin", value="🟦 🟦 🟦", inline=False)
        embed.add_field(name="Result", value="❓ Good Luck! ❓", inline=True)
        self.clear_items()
        await interaction.edit_original_response(embed=embed, view=self)

        spins = self.game.generate_spins(15)
        for spin in spins:
            await sleep(0.05)
            embed.set_field_at(0, name="Slot Spin", value=" ".join([self.game.symbols[s] for s in spin]), inline=False)
            await interaction.edit_original_response(embed=embed, view=self)
        # check win
        final_spin_result = self.game.check_win(spins[-1])    
        self.result = final_spin_result

        print("Final spin result:", final_spin_result)
        if final_spin_result == 3:
            embed.set_field_at(1, name="Result", value="Lucky you!\nYou win 3x your bet!", inline=True)
            embed.color = discord.Color.green()
            print("Win 3x")
        elif final_spin_result == 2:
            embed.set_field_at(1, name="Result", value="You won 2x your bet!", inline=True)
            embed.color = discord.Color.green()
            print("Win 2x")
        else:
            embed.set_field_at(1, name="Result", value="You lost!\nBetter luck next time!", inline=True)
            embed.color = discord.Color.red()
            print("Lost")

        await interaction.edit_original_response(embed=embed, view=self)
        await sleep(60)
        try:
            await interaction.delete_original_message()
        except discord.NotFound:
            pass
        
        self.event.set()

    @discord.ui.button(label="Spin", style=discord.ButtonStyle.primary)
    async def spin_slots(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await self.update_game_state(interaction)
        
