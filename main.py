import discord
import os
from dotenv import load_dotenv
from discord.ext import commands

class BakushinBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=discord.Intents.default())

    async def setup_hook(self):
        # Load our separated code modules (Cogs)
        await self.load_extension("cogs.commands")
        await self.load_extension("cogs.tasks")
        
        # Sync slash commands to Discord
        await self.tree.sync()
        print("BAKUSHIN! System online and synced.")

bot = BakushinBot()

if __name__ == "__main__":
    load_dotenv() # This loads the token from a hidden .env file
    bot.run(os.getenv("DISCORD_TOKEN"))
