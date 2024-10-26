import random
import discord


class CardGame:
    def __init__(self):
        self.deck = self.create_deck()
        random.shuffle(self.deck)

    def create_deck(self):
        """Creates a standard deck of cards."""
        suits = ["♥", "♦", "♣", "♠"]
        ranks = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
        return [f"{rank} {suit}" for suit in suits for rank in ranks]

    def deal_card(self):
        """Deals a card from the deck."""
        return self.deck.pop() if self.deck else None


class GameView(discord.ui.View):
    def __init__(self, game, player, bet):
        super().__init__()
        self.game = game
        self.player = player
        self.bet = bet

    async def update_game_state(self, interaction: discord.Interaction):
        """Abstract method to update the game state; to be implemented in subclasses."""
        raise NotImplementedError("Subclasses must implement this method.")
