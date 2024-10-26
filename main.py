import discord
from discord import app_commands
from discord.ext import tasks

import random
from math import floor, log

import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from alembic import command
from alembic.config import Config

from models.submissions import Submission
from models.user_gold import UserGold
from models.user_inventory import UserInventory
from models.casino_spent_earned import CasinoSpentEarned

import os
from dotenv import load_dotenv

from blackjack import BlackjackGame
from higherlower import HigherLower
from slots import SlotsGame

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
BOT_TOKEN = os.getenv("BOT_TOKEN")


# Set up the client
class MyClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

        # Initialize an empty dictionary to store items for each guild
        self.items = {}

        # Initialize the SQLite database
        self.init_db()

    def init_db(self):
        # Connect to the MySQL database
        self.engine = create_engine(DATABASE_URL, echo=True)
        Session = sessionmaker(bind=self.engine)
        self.session = Session()

        alembic_cfg = Config("alembic.ini")
        alembic_conn = self.engine.connect()
        alembic_cfg.attributes["connection"] = alembic_conn

        with alembic_conn.begin():
            command.upgrade(alembic_cfg, "head")

    pst = datetime.datetime.now().astimezone().tzinfo
    remind_times = [
        datetime.time(hour=22, tzinfo=pst),
    ]

    @tasks.loop(time=remind_times)
    async def check_time(self):
        channel = self.get_channel(1255671491387850823)  # omnom
        if channel:
            await channel.send(
                "<@342526382816886804> it's time to eat! <:ginaMald:1087267737950244925>"
            )

    async def on_guild_join(self, guild):
        # Define role names, their rarities, and corresponding colors
        role_definitions = {
            "Common": [
                ("Common Role 1", 0xA9A9A9),  # Dark Gray
                ("Common Role 2", 0xC0C0C0),  # Silver
                ("Common Role 3", 0xD3D3D3),  # Light Gray
            ],
            "Rare": [
                ("Rare Role 1", 0x0000FF),  # Blue
                ("Rare Role 2", 0x1E90FF),  # Dodger Blue
            ],
            "Epic": [
                ("Epic Role 1", 0x800080),  # Purple
                ("Epic Role 2", 0xDA70D6),  # Orchid
            ],
            "Legendary": [
                ("Legendary Role 1", 0xFFD700),  # Gold
                ("Legendary Role 2", 0xFFA500),  # Orange
            ],
        }

        for rarity, role_data in role_definitions.items():
            if rarity not in self.items:
                self.items[rarity] = []

            for role_name, color in role_data:
                # Check if the role already exists
                existing_role = discord.utils.get(guild.roles, name=role_name)
                if existing_role is None:
                    # Create the role with the specified color if it doesn't exist
                    new_role = await guild.create_role(
                        name=role_name, color=discord.Color(color)
                    )
                    print(
                        f"Created role: {new_role.name} with ID {new_role.id} and color {color:#06X}"
                    )
                    self.items[rarity].append(
                        (new_role.name, new_role.id)
                    )  # Store name and ID
                else:
                    print(
                        f"Role {existing_role.name} already exists with ID {existing_role.id}"
                    )
                    self.items[rarity].append((existing_role.name, existing_role.id))

    async def on_ready(self):
        await self.tree.sync()  # Sync slash commands
        print(f"Logged in as {self.user}")
        for guild in self.guilds:
            # Ensure roles are loaded for each guild the bot is already in
            await self.on_guild_join(guild)

        # start timer to ping gina
        self.check_time.start()

    def add_gold(self, user_id, amount=1):
        # Check if the user already exists in the database
        user_to_add = self.session.query(UserGold).filter_by(user_id=user_id).first()
        if user_to_add:
            user_to_add.gold += amount
        else:
            user_to_add = UserGold(user_id=user_id, gold=amount)
            self.session.add(user_to_add)
        self.session.commit()
        return user_to_add.gold

    def get_gold(self, user_id):
        # Get the user's gold count
        user_to_check = self.session.query(UserGold).filter_by(user_id=user_id).first()
        if user_to_check:
            return user_to_check.gold
        return 0

    def deduct_gold(self, user_id, amount):
        # Deduct gold from the user if they have enough
        user_to_deduct = self.session.query(UserGold).filter_by(user_id=user_id).first()
        if user_to_deduct and user_to_deduct.gold >= amount:
            user_to_deduct.gold -= amount
            self.session.commit()
            return True
        return False

    # assumes amount_lost is negative and amount_earned is positive
    def update_casino_leaderboard(self, user_id, amount_spent=0, amount_earned=0):
        """Update user for amount spent and amount lost from casino games"""
        user_to_update = (
            self.session.query(CasinoSpentEarned).filter_by(user_id=user_id).first()
        )
        if user_to_update:
            # Ensure total_spent and total_earned are initialized to 0 if None
            user_to_update.total_spent = (
                user_to_update.total_spent or 0
            ) + amount_spent
            user_to_update.total_earned = (
                user_to_update.total_earned or 0
            ) + amount_earned
        else:
            # Create a new record with initial values
            user_to_update = CasinoSpentEarned(
                user_id=user_id, total_spent=amount_spent, total_earned=amount_earned
            )
            self.session.add(user_to_update)

        self.session.commit()

    def has_submitted(self, message_id):
        # Check if the image has already been submitted for gold
        return (
            self.session.query(Submission).filter_by(message_id=message_id).first()
            is not None
        )

    def track_submission(self, message_id, author_id):
        # Track the submission with the author's ID
        new_submission = Submission(message_id=message_id, user_id=author_id)
        self.session.add(new_submission)
        self.session.commit()

    def fetch_submissions(self, user_id):
        # Fetch all submissions by the user
        return self.session.query(Submission).filter_by(user_id=user_id).all()

    def get_current_streak(self, user_id):
        submissions = self.fetch_submissions(user_id)
        if not submissions:
            return 0
        # most likely won't be needed bc message id, but with test cases might f something up
        sorted_submissions = sorted(submissions, key=lambda x: x.inserted_at)
        unique_days = set()
        for i in range(len(sorted_submissions) - 1, -1, -1):
            submission_date = sorted_submissions[i].inserted_at.date()
            # check if there is at least one submission per day
            if submission_date not in unique_days:
                unique_days.add(submission_date)
                # print(f"found submission for {submission_date}")
            # check if there is a gap between submissions
            if (
                i > 0
                and (
                    submission_date - sorted_submissions[i - 1].inserted_at.date()
                ).days
                > 1
            ):
                # print(f"found gap between {submission_date} and {sorted_submissions[i - 1].inserted_at.date()}")
                break
        streak = len(unique_days)
        return streak

    def roll_item(self):
        # Roll for an item based on probabilities
        roll = random.random()
        if roll < 0.50:
            role_list = self.items["Common"]
            if role_list:
                gained_role = random.choice(role_list)
        elif roll < 0.80:  # 50% + 30% = 80%
            role_list = self.items["Rare"]
            if role_list:
                gained_role = random.choice(role_list)
        elif roll < 0.99:  # 80% + 19% = 99%
            role_list = self.items["Epic"]
            if role_list:
                gained_role = random.choice(role_list)
        else:
            role_list = self.items["Legendary"]
            if role_list:
                gained_role = random.choice(role_list)

        return gained_role

    def add_item_to_inventory(self, user_id, role_id):
        # Add the item to the user's inventory
        user_inventory = (
            self.session.query(UserInventory)
            .filter_by(user_id=user_id, role_id=role_id)
            .first()
        )
        if user_inventory:
            user_inventory.quantity += 1
        else:
            user_inventory = UserInventory(user_id=user_id, role_id=role_id, quantity=1)
            self.session.add(user_inventory)
        self.session.commit()

    def get_inventory(self, user_id):
        # Get the user's inventory with role IDs instead of names
        return (
            self.session.query(UserInventory.role_id, UserInventory.quantity)
            .filter_by(user_id=user_id)
            .all()
        )


# Instantiate the client
client = MyClient()


# FOR TESTING - adds 10 gold to user
@client.tree.command(name="add10", description="Adds 10 gold to user.")
async def add10(interaction: discord.Interaction):
    await interaction.response.defer()

    user_id = interaction.user.id
    client.add_gold(user_id, 10)

    # Create an embed
    embed = discord.Embed(
        title="Gold Received!",
        description="You have now received +10 gold!",
        color=0xFFD700,  # Gold color
    )

    # Set the image for the embed (replace 'YOUR_IMAGE_URL' with the actual URL)
    embed.set_thumbnail(
        url="https://static.wikia.nocookie.net/b__/images/8/8c/CashDropUpgradeIcon.png/revision/latest?cb=20200601042402&path-prefix=bloons"
    )

    # Send the embed in the followup message
    await interaction.followup.send(embed=embed)


# Define the context menu command for image uploads
@client.tree.context_menu(name="Submit Dailies")
async def get_image_link(interaction: discord.Interaction, message: discord.Message):
    # Check if the message contains attachments
    if message.attachments:
        # Get the first attachment (assuming the message has only one image)
        attachment = message.attachments[0]

        # Check if the attachment is an image
        if attachment.content_type and attachment.content_type.startswith("image/"):
            message_id = message.id  # Get the message ID
            author_id = message.author.id  # Get the author's ID

            # Check if the submitting user is the author of the message
            if interaction.user.id != author_id:
                await interaction.response.send_message(
                    "You are not allowed to submit gold for this image as you are not the original author.",
                    ephemeral=True,
                    delete_after=5,
                )
                return

            # Check if the image has already been submitted for gold
            if client.has_submitted(message_id):
                await interaction.response.send_message(
                    "This image has already been submitted for gold. No further submissions allowed.",
                    ephemeral=True,
                    delete_after=5,
                )
                return

            user_id = interaction.user.id  # Get the user's ID

            response_text = "You have now received +1 gold!"

            streak = client.get_current_streak(user_id)
            bonus = 0
            if streak > 7:
                bonus = floor(log(streak, 7))
                response_text += f" (+{bonus} streak bonus)!"

            current_gold = client.add_gold(
                user_id, 1 + bonus
            )  # Add gold and get updated total
            client.track_submission(message_id, author_id)  # Track the submission

            # Create an embed for successful submission
            embed = discord.Embed(
                title="Food Confirmed!",
                description=response_text,
                color=0xFFD700,  # Gold color
            )
            embed.add_field(
                name="Total Gold", value=f"🪙 {current_gold} gold", inline=True
            )
            embed.add_field(
                name="Current Streak", value=f"🔥 {streak} days", inline=True
            )

            # Respond with the embed
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message(
                "The attachment is not an image.", ephemeral=True, delete_after=5
            )
    else:
        await interaction.response.send_message(
            "This message does not contain any attachments.",
            ephemeral=True,
            delete_after=5,
        )


# displays users current streak
@client.tree.command(name="streaks", description="list current streak")
async def get_streak(interaction: discord.Interaction):
    streak = client.get_current_streak(interaction.user.id)
    if streak == 0:
        await interaction.response.send_message(
            "You have not submitted any dailies yet."
        )
        return
    if streak == 1:
        await interaction.response.send_message("Your current streak is 1 day.")
        return
    await interaction.response.send_message(f"Your current streak is {streak} days.")


# Define the roll command
@client.tree.command(name="roll", description="Roll for items costing 1 gold each.")
async def roll(interaction: discord.Interaction, amount: int):
    await interaction.response.defer()

    user_id = interaction.user.id  # Get the user's ID

    # Deduct gold for the rolls
    if not client.deduct_gold(user_id, amount):
        await interaction.followup.send(
            "You do not have enough gold to roll.", ephemeral=True, delete_after=5
        )
        return

    # Create a loading embed
    embed = discord.Embed(
        title="Rolling...",
        description="Please wait while we process your request!",
        color=0xFFD700,  # Gold color
    )

    # Set the loading GIF as the thumbnail
    embed.set_thumbnail(
        url="https://media.tenor.com/a6HSobGpgGMAAAAM/%E3%83%91%E3%82%BA%E3%83%89%E3%83%A9-puzzle-and-dragons.gif"
    )

    # Send the loading embed as a temporary message
    loading_message = await interaction.followup.send(embed=embed, ephemeral=True)

    # Roll the items
    rolled_items = []
    for _ in range(amount):
        role = client.roll_item()
        client.add_item_to_inventory(
            user_id, role[1]
        )  # Add the role_id to the user's inventory
        rolled_items.append(role)

    # Prepare the response message with role colors
    if rolled_items:
        role_messages = []
        for roll_name, role_id in rolled_items:
            role = interaction.guild.get_role(
                role_id
            )  # Get the role object from the guild
            if role:
                # Format the role name in the color of the role
                role_messages.append(
                    f"{role.mention}"
                )  # Use mention to display in the role color

        # Set the embed description with rolled items
        embed.title = "Rolling Result"
        embed.description = f"You rolled and gained: {', '.join(role_messages)}.\nYou spent {amount} gold."
    else:
        embed.description = "You didn't gain any roles."  # should not occur

    # Send the final embed as a response
    await loading_message.edit(
        embed=embed
    )  # Edit the loading message to show the final embed


# Define a slash command to check user's inventory
@client.tree.command(
    name="inventory", description="Check your inventory of earned roles."
)
async def inventory(interaction: discord.Interaction):
    user_id = interaction.user.id  # Get the user's ID
    inventory_items = client.get_inventory(user_id)  # Get the user's inventory

    # Create an embed for the inventory response
    embed = discord.Embed(
        title="Inventory",
        color=0x8B4513,  # Brown color for inventory
    )

    # Set embed thumbnail for inventory
    embed.set_thumbnail(
        url="https://cdn2.iconfinder.com/data/icons/rpg-fantasy-game-basic-ui/512/game_ui_bag_item_pack_backpack_2-512.png"
    )

    if inventory_items:
        # Build the description from the inventory items
        description = ""

        for item in inventory_items:
            role_id = item[0]
            quantity = item[1]

            # Find the role in the guild
            role = interaction.guild.get_role(
                role_id
            )  # Assuming item[0] contains the role ID

            if role:
                # Append role mention and quantity to the description
                description += f"{role.mention} (x{quantity})\n"
            else:
                description += f"Role ID {role_id} (no longer exists) (x{quantity})\n"  # Fallback if role doesn't exist

        embed.description = description  # Set the constructed description
    else:
        embed.description = "Your inventory is empty."

    # Send the embed with the inventory
    await interaction.response.send_message(
        embed=embed, ephemeral=True, delete_after=60
    )


# Define a select menu for equipping roles
class RoleSelect(discord.ui.Select):
    def __init__(self, roles):
        options = [
            discord.SelectOption(label=role.name, value=str(role.id)) for role in roles
        ]
        super().__init__(placeholder="Select a role to equip...", options=options)

    async def callback(self, interaction: discord.Interaction):
        selected_role_id = int(self.values[0])  # Get the selected role ID
        role_to_equip = interaction.guild.get_role(
            selected_role_id
        )  # Get the role object

        if role_to_equip:
            # Get the role's name to determine its rarity
            role_name = role_to_equip.name

            # Remove previously equipped roles in the same category
            equipped_roles = []
            for rarity, roles in interaction.client.items.items():
                for role in roles:
                    if role[0] != role_name:  # Don't remove the newly selected role
                        equipped_role = discord.utils.get(
                            interaction.user.roles, id=role[1]
                        )
                        if equipped_role:
                            equipped_roles.append(equipped_role)

            # Remove equipped roles
            if equipped_roles:
                await interaction.user.remove_roles(*equipped_roles)

            # Assign the new role to the user
            await interaction.user.add_roles(role_to_equip)
            await interaction.response.send_message(
                f"You have equipped the role: {role_to_equip.mention}!",
                ephemeral=True,
                delete_after=5,
            )

            # Disable the select menu
            self.disabled = True
            await interaction.message.edit(
                view=self.view
            )  # Update the message to reflect the change
        else:
            await interaction.response.send_message(
                "The selected role no longer exists.", ephemeral=True, delete_after=5
            )


# Define a view to hold the select menu
class RoleSelectView(discord.ui.View):
    def __init__(self, roles):
        super().__init__(timeout=None)  # Set timeout to None for no automatic timeout
        self.add_item(RoleSelect(roles))  # Add the select menu to the view


# Define a slash command to equip a role from the user's inventory
@client.tree.command(name="equip", description="Equip a role from your inventory.")
async def equip(interaction: discord.Interaction):
    user_id = interaction.user.id  # Get the user's ID
    inventory_items = client.get_inventory(user_id)  # Get the user's inventory

    if not inventory_items:
        await interaction.response.send_message(
            "Your inventory is empty. You have no roles to equip.",
            ephemeral=True,
            delete_after=5,
        )
        return

    # Create a list of roles from the user's inventory
    roles = [interaction.guild.get_role(item[0]) for item in inventory_items]

    # Filter out any None roles
    roles = [role for role in roles if role is not None]

    # If there are valid roles to equip
    if roles:
        view = RoleSelectView(
            roles, interaction.user
        )  # Pass the user who initiated the command
        await interaction.response.send_message(
            "Please select a role to equip:", view=view, ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "You have no valid roles to equip.", ephemeral=True, delete_after=5
        )


# Define a slash command to check user's gold balance
@client.tree.command(name="check_gold", description="Check your current gold balance.")
async def check_gold(interaction: discord.Interaction):
    user_id = interaction.user.id  # Get the user's ID
    gold = client.get_gold(user_id)  # Get the user's gold count
    await interaction.response.send_message(
        f"You currently have {gold} gold.", ephemeral=True, delete_after=30
    )


# Define a select menu for combining roles
class RoleCombineSelect(discord.ui.Select):
    def __init__(self, roles, session):
        options = [
            discord.SelectOption(label=role.name, value=str(role.id)) for role in roles
        ]
        super().__init__(placeholder="Select a role to combine...", options=options)
        self.session = session  # Store the session for later use

    async def callback(self, interaction: discord.Interaction):
        selected_role_id = int(self.values[0])  # Get the selected role ID
        role_to_combine = interaction.guild.get_role(
            selected_role_id
        )  # Get the role object

        if role_to_combine:
            user_id = interaction.user.id

            # Query the quantity for the user
            try:
                user_inventory = (
                    self.session.query(UserInventory)
                    .filter_by(user_id=user_id, role_id=role_to_combine.id)
                    .first()
                )
            except Exception as e:
                print(f"Error occurred: {e}")

            if user_inventory:
                # Deduct 10 from the user's inventory
                self.session.query(UserInventory).filter_by(
                    user_id=user_id, role_id=role_to_combine.id
                ).update({UserInventory.quantity: UserInventory.quantity - 10})

                # Commit the transaction
                self.session.commit()

            # Determine the new rarity
            new_rarity = self.get_higher_rarity(role_to_combine.name, interaction)
            if new_rarity:
                # 10% chance to gain the higher rarity role
                if random.random() < 0.1:
                    new_role = discord.utils.get(
                        interaction.guild.roles, name=new_rarity[0]
                    )
                    if new_role:
                        client.add_item_to_inventory(
                            user_id, new_role.id
                        )  # Add the new role to inventory
                        follow_up_msg = (
                            f"You combined and gained a new role: {new_role.mention}!"
                        )
                    else:
                        follow_up_msg = "Failed to gain a higher rarity role."
                else:
                    follow_up_msg = "You combined but did not gain a new role."
            else:
                follow_up_msg = f"There is no higher rarity for {role_to_combine.name}."

            # Disable the select menu
            self.disabled = True
            await interaction.response.edit_message(
                content=follow_up_msg, view=self.view
            )  # Update the message to show the result and disabled select
        else:
            await interaction.response.send_message(
                "The selected role no longer exists.", ephemeral=True, delete_after=5
            )

    def get_higher_rarity(self, role_name, interaction: discord.Interaction):
        """Return the name and rarity of the higher role if exists."""
        for rarity, roles in interaction.client.items.items():
            for role in roles:
                if role[0] == role_name:
                    next_rarity = list(interaction.client.items.keys())
                    next_index = next_rarity.index(rarity) + 1
                    if next_index < len(next_rarity):
                        next_rarity_name = next_rarity[next_index]
                        return interaction.client.items[next_rarity_name][
                            0
                        ]  # Return the first role of next rarity
        return None


# Define a view to hold the select menu for combining roles
class RoleCombineSelectView(discord.ui.View):
    def __init__(self, roles, session):
        super().__init__(timeout=None)  # Set timeout to None for no automatic timeout
        self.add_item(
            RoleCombineSelect(roles, session)
        )  # Pass the session to the select menu


# Define a slash command to combine a role from the user's inventory
@client.tree.command(
    name="combine",
    description="Combine 10 of a role to potentially gain a higher rarity.",
)
async def combine(interaction: discord.Interaction):
    user_id = interaction.user.id  # Get the user's ID
    inventory_items = client.get_inventory(user_id)  # Get the user's inventory

    if not inventory_items:
        await interaction.response.send_message(
            "Your inventory is empty. You have no roles to combine.",
            ephemeral=True,
            delete_after=5,
        )
        return

    # Create a list of roles from the user's inventory that have at least 10
    roles = []
    for item in inventory_items:
        role_id = item[0]
        quantity = item[1]
        # Find the role in the guild
        role = interaction.guild.get_role(role_id)
        if role and quantity >= 10:  # Only include roles with 10 or more
            roles.append(role)

    # If there are valid roles to combine
    if roles:
        view = RoleCombineSelectView(
            roles, client.session
        )  # Pass the session to the view
        await interaction.response.send_message(
            "Please select a role to combine:",
            view=view,
            ephemeral=True,
            delete_after=60,
        )
    else:
        await interaction.response.send_message(
            "You have no roles with sufficient quantity to combine.",
            ephemeral=True,
            delete_after=5,
        )


# Define the symbols for the slot machine
symbols = ["🍒", "🍋", "🍉", "🍇", "🍎"]


# Define the /slots command
@client.tree.command(name="slots", description="Play a slot machine game!")
@app_commands.describe(bet="Amount to bet")
async def slots(interaction: discord.Interaction, bet: int):
    if bet < 0:
        await interaction.response.send_message(
            "You need to bet a positive amount!", ephemeral=True
        )
        return
    elif bet > client.get_gold(interaction.user.id):
        await interaction.response.send_message(
            "You don't have enough gold to bet that amount!", ephemeral=True
        )
        return
    game = SlotsGame()
    result = await game.start_game(interaction, bet)
    client.deduct_gold(interaction.user.id, bet)
    user_id = interaction.user.id  # Get the user's ID
    client.update_casino_leaderboard(user_id, bet * -1, 0)  # add amount spent to play

    if result > 0:
        client.update_casino_leaderboard(user_id, 0, result)  # add amount earned
        client.add_gold(user_id, result)


@client.tree.command(
    name="blackjack", description="Start a game of Blackjack"
)  # Double down wont be allowed after a split
@app_commands.describe(bet="Amount to bet")
async def blackjack(interaction: discord.Interaction, bet: int):
    if bet < 0:
        await interaction.response.send_message(
            "You need to bet a positive amount!", ephemeral=True
        )
        return
    elif bet > client.get_gold(interaction.user.id):
        await interaction.response.send_message(
            "You don't have enough gold to bet that amount!", ephemeral=True
        )
        return

    can_double = True  # if double down or split is allowed
    if bet * 2 > client.get_gold(interaction.user.id):
        can_double = False

    game = BlackjackGame(can_double)
    result, did_double = await game.start_game(
        interaction, bet
    )  # amount of money gained

    user_id = interaction.user.id

    #  deduct money for cost of playing
    if did_double:
        client.deduct_gold(user_id, bet * 2)
    else:
        client.deduct_gold(user_id, bet)

    if result < 0:  # player lost
        client.update_casino_leaderboard(user_id, result, 0)
    elif result > 0:  # player won
        client.add_gold(user_id, result)
        if did_double:
            client.update_casino_leaderboard(user_id, 2 * bet * -1, result)
        else:
            client.update_casino_leaderboard(user_id, bet * -1, result)
    else:  # result is push, refund the bet
        if did_double:
            client.add_gold(user_id, bet * 2)
            client.update_casino_leaderboard(user_id, bet * -2, bet * 2)
        else:
            client.add_gold(user_id, bet)
            client.update_casino_leaderboard(user_id, bet * -1, bet)


@client.tree.command(name="high-low", description="Start a game of High-Low")
@app_commands.describe(bet="Amount to bet")
async def higherlower(interaction: discord.Interaction, bet: int):
    if bet < 0:
        await interaction.response.send_message(
            "You need to bet a positive amount!", ephemeral=True, delete_after=5
        )
        return
    elif bet > client.get_gold(interaction.user.id):
        await interaction.response.send_message(
            "You don't have enough gold to bet that amount!",
            ephemeral=True,
            delete_after=5,
        )
        return

    user_id = interaction.user.id
    client.deduct_gold(user_id, bet)
    client.update_casino_leaderboard(user_id, bet * -1, 0)  # add amount spent to play

    game = HigherLower()
    result = await game.start_game(interaction, bet)

    if result > 0:
        client.update_casino_leaderboard(user_id, 0, result)  # add amount earned
        client.add_gold(user_id, result)


# Define a slash command to check casino leaderboard
@client.tree.command(
    name="casino_leaderboard", description="Check the casino leaderboard."
)
async def casino_leaderboard(interaction: discord.Interaction):
    # Query the database to get the leaderboard data
    leaderboard_data = (
        client.session.query(CasinoSpentEarned)
        .order_by(CasinoSpentEarned.total_earned.desc())
        .limit(10)
        .all()
    )  # Get top 10 users by total_earned

    # Initialize the embed
    embed = discord.Embed(
        title="Casino Leaderboard",
        description="Top 10 users by earnings",
        color=discord.Color.gold(),
    )

    embed.set_thumbnail(
        url="https://support-leagueoflegends.riotgames.com/hc/article_attachments/4415894930323"
    )

    # Add leaderboard data to the embed
    if leaderboard_data:
        for rank, entry in enumerate(leaderboard_data, start=1):
            user = await client.fetch_user(entry.user_id)  # Get user object
            embed.add_field(
                name=f"{rank}. {user.display_name}",
                value=f"Spent: {entry.total_spent}\nEarned: {entry.total_earned}",
                inline=False,
            )
    else:
        embed.description = "No data available yet."

    # Send the embed as a response to the command
    await interaction.response.send_message(embed=embed)


@client.tree.command(name="remind_gina", description="Remind Gina to eat")
async def remind_gina(interaction: discord.Interaction):
    channel = client.get_channel(1255671491387850823)  # omnom
    if channel:
        await channel.send(
            "<@342526382816886804> it's time to eat! <:ginaMald:1087267737950244925>"
        )
    await interaction.response.send_message("Gina has been reminded to eat!")


# Run the bot with your token
client.run(BOT_TOKEN)
