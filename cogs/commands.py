import discord
import traceback
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

# --- NEW: CUSTOM EMBED EDITOR MODAL ---
class EmbedEditModal(discord.ui.Modal, title='Edit Bakushin Embed'):
    def __init__(self, message: discord.Message):
        super().__init__()
        self.message = message
        # Grab the first embed from the message to pre-fill our text boxes
        embed = message.embeds[0] if message.embeds else None
        
        self.embed_title = discord.ui.TextInput(
            label='Embed Title',
            style=discord.TextStyle.short,
            default=embed.title if embed and embed.title else '',
            required=True
        )
        self.add_item(self.embed_title)

        self.embed_desc = discord.ui.TextInput(
            label='Description',
            style=discord.TextStyle.paragraph,
            default=embed.description if embed and embed.description else '',
            required=True,
            max_length=4000
        )
        self.add_item(self.embed_desc)

        self.image_url = discord.ui.TextInput(
            label='Image URL (Optional)',
            style=discord.TextStyle.short,
            default=embed.image.url if embed and embed.image else '',
            required=False
        )
        self.add_item(self.image_url)

        # Convert the bot's internal color code back to a standard Hex code
        hex_color = hex(embed.color.value).replace('0x', '').upper() if embed and embed.color else 'FF77AA'
        self.embed_color = discord.ui.TextInput(
            label='Hex Color (Optional)',
            style=discord.TextStyle.short,
            default=hex_color,
            required=False
        )
        self.add_item(self.embed_color)

    async def on_submit(self, interaction: discord.Interaction):
        color_str = self.embed_color.value.replace("#", "") if self.embed_color.value else "FF77AA"
        try:
            color_val = int(color_str, 16)
        except ValueError:
            color_val = 0xFF77AA

        new_embed = discord.Embed(
            title=self.embed_title.value,
            description=self.embed_desc.value,
            color=color_val
        )

        if self.image_url.value:
            new_embed.set_image(url=self.image_url.value)

        # Edit the existing message instead of sending a new one!
        await self.message.edit(embed=new_embed)
        await interaction.response.send_message("BAKUSHIN! The embed has been successfully updated!", ephemeral=True)
        
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
        
    # --- NEW SLASH COMMAND FOR EDITING ---
    @app_commands.command(name="edit-embed", description="Edit an existing Bakushin custom embed")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(message_id="The ID of the message you want to edit")
    async def edit_embed(self, interaction: discord.Interaction, message_id: str):
        if not interaction.permissions.administrator:
            await interaction.response.send_message("Only the Class President can edit official announcements!", ephemeral=True)
            return
            
        try:
            # Try to find the message in the channel where you typed the command
            message = await interaction.channel.fetch_message(int(message_id))
        except discord.NotFound:
            await interaction.response.send_message("I couldn't find a message with that ID in this channel!", ephemeral=True)
            return
        except ValueError:
            await interaction.response.send_message("That doesn't look like a valid message ID! Please use the long number.", ephemeral=True)
            return

        # Safety checks so you don't accidentally try to edit a player's message
        if message.author != self.bot.user:
            await interaction.response.send_message("I can only edit my own messages!", ephemeral=True)
            return
            
        if not message.embeds:
            await interaction.response.send_message("That message doesn't have an embed to edit!", ephemeral=True)
            return

        # Pop open the new editor modal!
        await interaction.response.send_modal(EmbedEditModal(message))

    @app_commands.command(name="set-error-logs", description="Set the private channel where Bakushin will report code errors")
    @app_commands.default_permissions(administrator=True)
    async def set_error_logs(self, interaction: discord.Interaction, channel: discord.TextChannel):
        if not interaction.permissions.administrator:
            return
            
        conf = config.load_config()
        # We save this globally so it applies everywhere
        conf["global_log_channel"] = channel.id
        config.save_config(conf)
        
        await interaction.response.send_message(f"BAKUSHIN! System errors will now be logged in {channel.mention}!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(BakushinCommands(bot))
    
    # --- GLOBAL ERROR HANDLER ---
    async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        # Unwrap the error to get to the real cause
        original_error = getattr(error, 'original', error)
        
        # 1. Extract the file and exact line number
        line_num = "Unknown"
        file_name = "Unknown"
        if original_error.__traceback__:
            tb = traceback.extract_tb(original_error.__traceback__)
            if tb:
                last_call = tb[-1] # Grabs the final line before the crash
                line_num = last_call.lineno
                file_name = last_call.filename.split('/')[-1] # Hides your server folder path

        # 2. Format specific reasons (like 403 or 404)
        if isinstance(original_error, discord.errors.Forbidden):
            reason = "403 / No Perms (Missing Permissions)"
        elif isinstance(original_error, discord.errors.NotFound):
            reason = "404 / Not Found (Message Deleted or Interaction Timed Out)"
        else:
            reason = str(original_error) # Fallback for syntax errors, missing variables, etc.

        # 3. Build the error text
        cmd_name = interaction.command.name if interaction.command else 'Unknown'
        log_text = (
            f"**Command:** `/{cmd_name}`\n"
            f"**File:** `{file_name}`\n"
            f"**Error Line:** `{line_num}`\n"
            f"**Reason:** `{reason}`"
        )

        # 4. Politely tell the user something went wrong
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message("❌ Oops! A system error occurred. The Class President is looking into it!", ephemeral=True)
            except:
                pass

        # 5. Send the detailed log to your secret developer channel
        conf = config.load_config()
        log_channel_id = conf.get("global_log_channel")
        if log_channel_id:
            channel = bot.get_channel(log_channel_id)
            if channel:
                embed = discord.Embed(title="⚠️ Bakushin System Error", description=log_text, color=0xFF0000)
                await channel.send(embed=embed)
                
        # Always print to the SSH console as a backup!
        print(f"Error in /{cmd_name}: {original_error}")

    # Attach our custom handler to the bot's command tree
    bot.tree.on_error = on_tree_error
