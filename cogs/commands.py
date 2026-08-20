import discord
from discord import app_commands
from discord.ext import commands
import random
import config
import datetime
from utils import build_embed
from quotes import get_quote

# --- NEW: CUSTOM EMBED BUILDER MODAL ---
class EmbedBuilderModal(discord.ui.Modal, title='Bakushin Custom Embed Builder'):
    embed_title = discord.ui.TextInput(
        label='Embed Title',
        style=discord.TextStyle.short,
        placeholder='e.g., Uma Club Roles',
        required=True
    )

    embed_desc = discord.ui.TextInput(
        label='Description (Supports Emojis & Roles)',
        style=discord.TextStyle.paragraph,
        placeholder='Use <@&ROLE_ID> for roles and <:name:ID> for custom emojis!',
        required=True,
        max_length=4000
    )

    image_url = discord.ui.TextInput(
        label='Image URL (Optional)',
        style=discord.TextStyle.short,
        placeholder='https://example.com/image.png',
        required=False
    )

    embed_color = discord.ui.TextInput(
        label='Hex Color (Optional)',
        style=discord.TextStyle.short,
        default='FF77AA',
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Convert the hex color string into a format Discord understands
        color_str = self.embed_color.value.replace("#", "") if self.embed_color.value else "FF77AA"
        try:
            color_val = int(color_str, 16)
        except ValueError:
            color_val = 0xFF77AA # Fallback to Bakushin Pink if the user types an invalid color

        # Build the embed
        embed = discord.Embed(
            title=self.embed_title.value,
            description=self.embed_desc.value,
            color=color_val
        )

        # Attach the image if a URL was provided
        if self.image_url.value:
            embed.set_image(url=self.image_url.value)

        # Send the embed to the exact channel the command was used in
        await interaction.channel.send(embed=embed)
        
        # Silently confirm to the admin that it worked
        await interaction.response.send_message("BAKUSHIN! Custom embed successfully posted!", ephemeral=True)


# --- EXISTING COMMANDS ---
class BakushinCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="setup", description="Setup the channel and server-specific roles for Bakushin to ping")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        channel="The channel to send reminders in", 
        global_role="The role to ping for UMA Global reminders", 
        jp_role="The role to ping for UMA JP reminders"
    )
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel, global_role: discord.Role, jp_role: discord.Role):
        if not interaction.permissions.administrator:
            await interaction.response.send_message("Only the Class President (Admins) can use this!", ephemeral=True)
            return

        conf = config.load_config()
        guild_id = str(interaction.guild_id)
        
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

    @app_commands.command(name="test-reminder", description="Force the bot to send a test reminder immediately")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(region="Which region to test (global or jp)", reminder_type="Which timer to test (dailies or tt)")
    @app_commands.choices(
        region=[app_commands.Choice(name="Global", value="global"), app_commands.Choice(name="JP", value="jp")],
        reminder_type=[app_commands.Choice(name="Dailies", value="dailies"), app_commands.Choice(name="Team Trials", value="tt")]
    )
    async def test_reminder(self, interaction: discord.Interaction, region: str, reminder_type: str):
        if not interaction.permissions.administrator:
            await interaction.response.send_message("Only the Class President can trigger tests!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        
        tasks_cog = self.bot.get_cog("BakushinTasks")
        if tasks_cog:
            fake_future_time = int(datetime.datetime.now(datetime.timezone.utc).timestamp()) + 3600
            
            await tasks_cog.send_reminder(
                region, 
                reminder_type, 
                fake_future_time, 
                f"TESTING {region.upper()} {reminder_type.upper()}",
                target_guild_id=interaction.guild_id
            )
            
            await interaction.followup.send(f"Testing the **{region.upper()} {reminder_type.title()}** reminder now in this server only!", ephemeral=True)
        else:
            await interaction.followup.send("Error: Could not find the background tasks!", ephemeral=True)

    # --- NEW SLASH COMMAND FOR THE BUILDER ---
    @app_commands.command(name="create-embed", description="Design and send a custom embed into the current channel")
    @app_commands.default_permissions(administrator=True)
    async def create_embed(self, interaction: discord.Interaction):
        if not interaction.permissions.administrator:
            await interaction.response.send_message("Only the Class President can make official announcements!", ephemeral=True)
            return
            
        # This tells Discord to pop open our modal window!
        await interaction.response.send_modal(EmbedBuilderModal())

async def setup(bot):
    await bot.add_cog(BakushinCommands(bot))
