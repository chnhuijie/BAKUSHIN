import discord
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
    # Replace with your actual token or use environment variables
    bot.run("YOUR_DISCORD_BOT_TOKEN_HERE")
