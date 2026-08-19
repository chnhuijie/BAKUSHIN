import discord
from discord import app_commands
from discord.ext import commands
import random
import config
from utils import build_embed
from quotes import get_quote

class BakushinCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Setup the channel and server-specific roles for Bakushin to ping")
    @app_commands.describe(
        channel="The channel to send reminders in", 
        global_role="The role to ping for UMA Global reminders", 
        jp_role="The role to ping for UMA JP reminders"
    )
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel, global_role: discord.Role, jp_role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Only the Class President (Admins) can use this!", ephemeral=True)
            return

        conf = config.load_config()
        
        # We grab the unique ID of the server the command is run in
        guild_id = str(interaction.guild.id)
        
        # Save the settings specifically under this server's ID
        conf[guild_id] = {
            "channel_id": channel.id,
            "global_role_id": global_role.id,
            "jp_role_id": jp_role.id
        }
            
        config.save_config(conf)
        
        await interaction.response.send_message(
            f"Setup complete! I will BAKUSHIN into {channel.mention}!\n"
            f"**Global Pings:** {global_role.mention}\n"
            f"**JP Pings:** {jp_role.mention}", 
            ephemeral=True
        )

    @app_commands.command(name="dailies", description="Check the time left for Dailies and Team Trials")
    async def dailies(self, interaction: discord.Interaction):
        quote_type = random.choice(["dailies", "tt"])
        bakushin_line = get_quote(quote_type)

        await interaction.response.send_message(
            content=bakushin_line,
            embed=build_embed(), 
            allowed_mentions=discord.AllowedMentions.none()
        )

async def setup(bot):
    await bot.add_cog(BakushinCommands(bot))
    
