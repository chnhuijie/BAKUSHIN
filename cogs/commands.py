import discord
import traceback
from discord import app_commands
from discord.ext import commands
import random
import uuid
import config
import datetime
from utils import (
    build_embed, 
    parse_time_input, 
    get_available_emoji,
    build_event_embed,
    build_game_embed, 
    update_boards
)
from quotes import get_quote

# --- SECURITY HELPERS ---
def is_safe_role(role: discord.Role, default_role: discord.Role) -> bool:
    if role.permissions.value == default_role.permissions.value:
        return True
    
    p = role.permissions
    if p.administrator or p.manage_guild or p.manage_roles or p.manage_channels or \
       p.manage_messages or p.manage_webhooks or p.manage_events or \
       p.kick_members or p.ban_members or p.moderate_members or \
       p.view_audit_log or p.mention_everyone:
        return False
        
    return True

def validate_emoji_input(emoji_str: str):
    """Prevents users from typing text shortcodes like :microphone: instead of 🎤"""
    if not emoji_str:
        return
    val = emoji_str.strip()
    if val.startswith(":") and val.endswith(":") and not val.startswith("<"):
        raise ValueError("Please paste the actual visual emoji (e.g. 🎤), not the text shortcode (e.g. :microphone:).")


# ==========================================
# 1. EVENT MODALS (TEMPORARY & PERMANENT)
# ==========================================
class CreateEventModal(discord.ui.Modal, title="Create New Event"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    event_name = discord.ui.TextInput(label="Event Name", placeholder="e.g., Summer Sprint Tournament", required=True)
    role_name = discord.ui.TextInput(label="Role Name", placeholder="e.g., Sprint Contender", required=True)
    emoji_input = discord.ui.TextInput(label="Reaction Emoji (Optional)", placeholder="e.g., paste 🎤. Blank = auto", required=False)
    role_color = discord.ui.TextInput(label="Role Hex Color", placeholder="FF77AA", default="FF77AA", required=False)
    end_time_input = discord.ui.TextInput(label="End Time (UTC) or Duration", placeholder="e.g., 2h, 1d (Blank = Permanent)", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            validate_emoji_input(self.emoji_input.value)
            end_ts = parse_time_input(self.end_time_input.value)
        except ValueError as err:
            await interaction.response.send_message(f"[Error] {err}", ephemeral=True)
            return

        color_str = self.role_color.value.replace("#", "") if self.role_color.value else "FF77AA"
        try:
            color_val = int(color_str, 16)
        except ValueError:
            color_val = 0xFF77AA

        try:
            new_role = await interaction.guild.create_role(
                name=self.role_name.value,
                colour=discord.Colour(color_val),
                permissions=interaction.guild.default_role.permissions,
                reason=f"Event role for {self.event_name.value}"
            )
        except discord.Forbidden:
            await interaction.response.send_message("[Error] Missing Manage Roles permission.", ephemeral=True)
            return

        events_data = config.load_events()
        chosen_emoji = get_available_emoji(interaction.guild.id, events_data, self.emoji_input.value)

        event_id = str(uuid.uuid4())[:8]
        events_data.setdefault("events", {})[event_id] = {
            "name": self.event_name.value,
            "role_name": self.role_name.value,
            "role_id": new_role.id,
            "guild_id": interaction.guild.id,
            "end_time": end_ts,
            "emoji": chosen_emoji
        }
        config.save_events(events_data)
        
        time_msg = f"<t:{end_ts}:F> (<t:{end_ts}:R>)" if end_ts else "Permanent Event (No Expiration)"
        
        await interaction.response.send_message(
            f"[BAKUSHIN] Event created!\n"
            f"- Event: **{self.event_name.value}**\n"
            f"- Role: {new_role.mention}\n"
            f"- Reaction: {chosen_emoji}\n"
            f"- Ends: {time_msg}",
            ephemeral=True
        )
        await update_boards(self.bot, interaction.guild.id)

class EditEventModal(discord.ui.Modal):
    def __init__(self, bot: commands.Bot, event_id: str, current_data: dict):
        super().__init__(title="Edit Active Event")
        self.bot = bot
        self.event_id = event_id
        self.current_data = current_data

        self.event_name = discord.ui.TextInput(label="Event Name", default=current_data.get("name", ""), required=True)
        self.add_item(self.event_name)
        self.role_name = discord.ui.TextInput(label="Role Name", default=current_data.get("role_name", ""), required=True)
        self.add_item(self.role_name)
        self.emoji_input = discord.ui.TextInput(label="Reaction Emoji", default=current_data.get("emoji", ""), required=False)
        self.add_item(self.emoji_input)

        dt_str = ""
        if current_data.get("end_time"):
            dt = datetime.datetime.fromtimestamp(current_data.get("end_time"), tz=datetime.timezone.utc)
            dt_str = dt.strftime("%Y-%m-%d %H:%M")

        self.end_time_input = discord.ui.TextInput(label="End Time (UTC) or Duration", default=dt_str, placeholder="Blank = Permanent", required=False)
        self.add_item(self.end_time_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            validate_emoji_input(self.emoji_input.value)
            new_end_ts = parse_time_input(self.end_time_input.value)
        except ValueError as err:
            await interaction.response.send_message(f"[Error] {err}", ephemeral=True)
            return

        events_data = config.load_events()
        if self.event_id not in events_data.get("events", {}):
            await interaction.response.send_message("[Error] Event not found or already ended.", ephemeral=True)
            return

        chosen_emoji = get_available_emoji(interaction.guild.id, events_data, self.emoji_input.value)
        role = interaction.guild.get_role(self.current_data["role_id"])
        if role:
            try:
                await role.edit(name=self.role_name.value, reason=f"Event updated to {self.event_name.value}")
            except discord.Forbidden:
                pass 

        events_data["events"][self.event_id].update({
            "name": self.event_name.value,
            "role_name": self.role_name.value,
            "end_time": new_end_ts,
            "emoji": chosen_emoji
        })
        
        config.save_events(events_data)
        await interaction.response.send_message(f"[BAKUSHIN] Event '{self.event_name.value}' has been successfully updated!", ephemeral=True)
        await update_boards(self.bot, interaction.guild.id)


# ==========================================
# 2. GAME ROLE MODALS (PERMANENT)
# ==========================================
class CreatePermanentRoleModal(discord.ui.Modal, title="Create Permanent Game Role"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    role_name = discord.ui.TextInput(label="Role Name", placeholder="e.g., Maple Bossing", required=True)
    emoji_input = discord.ui.TextInput(label="Reaction Emoji (Optional)", placeholder="e.g., paste 🎮. Blank = auto", required=False)
    role_color = discord.ui.TextInput(label="Role Hex Color", placeholder="FF77AA", default="FF77AA", required=False)
    description = discord.ui.TextInput(label="Role Description", placeholder="e.g., Ping to coordinate multiplayer lobbies", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            validate_emoji_input(self.emoji_input.value)
        except ValueError as err:
            await interaction.response.send_message(f"[Error] {err}", ephemeral=True)
            return

        color_str = self.role_color.value.replace("#", "") if self.role_color.value else "FF77AA"
        try:
            color_val = int(color_str, 16)
        except ValueError:
            color_val = 0xFF77AA

        try:
            new_role = await interaction.guild.create_role(
                name=self.role_name.value,
                colour=discord.Colour(color_val),
                permissions=interaction.guild.default_role.permissions,
                reason="Permanent game notification role"
            )
        except discord.Forbidden:
            await interaction.response.send_message("[Error] Missing Manage Roles permission.", ephemeral=True)
            return

        events_data = config.load_events()
        chosen_emoji = get_available_emoji(interaction.guild.id, events_data, self.emoji_input.value)

        perm_id = str(uuid.uuid4())[:8]
        events_data.setdefault("permanent_roles", {})[perm_id] = {
            "name": self.role_name.value,
            "role_id": new_role.id,
            "guild_id": interaction.guild.id,
            "description": self.description.value or "Game notification role",
            "emoji": chosen_emoji
        }
        config.save_events(events_data)
        
        await interaction.response.send_message(
            f"[BAKUSHIN] Permanent role created!\n"
            f"- Role: {new_role.mention}\n"
            f"- Reaction: {chosen_emoji}",
            ephemeral=True
        )
        await update_boards(self.bot, interaction.guild.id)

class EditGameRoleModal(discord.ui.Modal):
    def __init__(self, bot: commands.Bot, perm_id: str, current_data: dict):
        super().__init__(title="Edit Game Role")
        self.bot = bot
        self.perm_id = perm_id
        self.current_data = current_data

        self.role_name = discord.ui.TextInput(label="Role Name", default=current_data.get("name", ""), required=True)
        self.add_item(self.role_name)
        self.emoji_input = discord.ui.TextInput(label="Reaction Emoji", default=current_data.get("emoji", ""), required=False)
        self.add_item(self.emoji_input)
        self.description = discord.ui.TextInput(label="Role Description", default=current_data.get("description", ""), required=False)
        self.add_item(self.description)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            validate_emoji_input(self.emoji_input.value)
        except ValueError as err:
            await interaction.response.send_message(f"[Error] {err}", ephemeral=True)
            return

        events_data = config.load_events()
        if self.perm_id not in events_data.get("permanent_roles", {}):
            await interaction.response.send_message("[Error] Game role not found.", ephemeral=True)
            return

        chosen_emoji = get_available_emoji(interaction.guild.id, events_data, self.emoji_input.value)
        role = interaction.guild.get_role(self.current_data["role_id"])
        if role:
            try:
                await role.edit(name=self.role_name.value, reason=f"Game role updated")
            except discord.Forbidden:
                pass 

        events_data["permanent_roles"][self.perm_id].update({
            "name": self.role_name.value,
            "description": self.description.value,
            "emoji": chosen_emoji
        })
        
        config.save_events(events_data)
        await interaction.response.send_message(f"[BAKUSHIN] Game role '{self.role_name.value}' successfully updated!", ephemeral=True)
        await update_boards(self.bot, interaction.guild.id)


# ==========================================
# 3. INTERACTIVE DROPDOWNS & VIEWS
# ==========================================
class AssignUserSelectView(discord.ui.View):
    def __init__(self, role: discord.Role):
        super().__init__(timeout=120)
        self.role = role

    @discord.ui.select(cls=discord.ui.UserSelect, placeholder="Select members to grant this event role", max_values=10)
    async def select_users(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        added = []
        for member in select.values:
            if isinstance(member, discord.Member):
                await member.add_roles(self.role)
                added.append(member.display_name)
        names = ", ".join(added) if added else "None"
        await interaction.response.send_message(f"Assigned {self.role.mention} to: {names}", ephemeral=True)

class AssignRoleSelect(discord.ui.Select):
    def __init__(self, guild_events: dict, guild_game_roles: dict):
        options = []
        for ev_id, ev in guild_events.items():
            options.append(discord.SelectOption(
                label=f"Event: {ev['name']}"[:100], 
                value=str(ev["role_id"])
            ))
        for pr_id, pr in guild_game_roles.items():
            options.append(discord.SelectOption(
                label=f"Game: {pr['name']}"[:100], 
                value=str(pr["role_id"])
            ))
        super().__init__(placeholder="Select the role you want to assign", options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        role_id = int(self.values[0])
        target_role = interaction.guild.get_role(role_id)
        if not target_role:
            await interaction.response.send_message("Role not found on server.", ephemeral=True)
            return
        
        await interaction.response.send_message(
            f"Select members to assign to {target_role.mention}:",
            view=AssignUserSelectView(target_role),
            ephemeral=True
        )

class AssignRoleSelectView(discord.ui.View):
    def __init__(self, guild_events: dict, guild_game_roles: dict):
        super().__init__(timeout=120)
        self.add_item(AssignRoleSelect(guild_events, guild_game_roles))

class EventManageSelect(discord.ui.Select):
    def __init__(self, guild_events: dict, row: int = 0):
        options = []
        for ev_id, ev in guild_events.items():
            options.append(discord.SelectOption(
                label=f"Cancel: {ev['name']}"[:100],
                value=ev_id,
                description=f"Deletes event & removes Discord role"[:100]
            ))
        super().__init__(placeholder="Select an active event to cancel & delete", options=options[:25], row=row)

    async def callback(self, interaction: discord.Interaction):
        event_id = self.values[0]
        events_data = config.load_events()
        ev = events_data.get("events", {}).get(event_id)
        if not ev:
            await interaction.response.send_message("Event not found or already deleted.", ephemeral=True)
            return

        del events_data["events"][event_id]
        config.save_events(events_data)

        role = interaction.guild.get_role(ev["role_id"])
        if role:
            try:
                await role.delete(reason="Event canceled by administrator")
            except discord.Forbidden:
                pass

        await interaction.response.send_message(f"[BAKUSHIN] Event '{ev['name']}' canceled and the role was removed.", ephemeral=True)
        await update_boards(interaction.client, interaction.guild.id)

class GameRoleManageSelect(discord.ui.Select):
    def __init__(self, guild_game_roles: dict, row: int = 1):
        options = []
        for pr_id, pr in guild_game_roles.items():
            desc = pr.get("description", "No description")
            options.append(discord.SelectOption(
                label=f"Remove: {pr['name']}"[:100],
                value=pr_id,
                description=f"{desc}"[:100]
            ))
        super().__init__(placeholder="Select a game role to remove from the board", options=options[:25], row=row)

    async def callback(self, interaction: discord.Interaction):
        perm_id = self.values[0]
        events_data = config.load_events()
        pr = events_data.get("permanent_roles", {}).get(perm_id)
        if not pr:
            await interaction.response.send_message("Game role not found or already removed.", ephemeral=True)
            return

        del events_data["permanent_roles"][perm_id]
        config.save_events(events_data)
        
        await interaction.response.send_message(
            f"[BAKUSHIN] Game role '{pr['name']}' removed from the board. (The Discord role still exists in your server settings!)",
            ephemeral=True
        )
        await update_boards(interaction.client, interaction.guild.id)

class EventEditSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, guild_events: dict):
        self.bot = bot
        options = []
        for ev_id, ev in guild_events.items():
            if ev.get("end_time"):
                dt_str = datetime.datetime.fromtimestamp(ev["end_time"], tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')
                desc = f"Ends: {dt_str} UTC"[:100]
            else:
                desc = "Permanent Event"
            options.append(discord.SelectOption(label=ev["name"][:100], value=ev_id, description=desc))
        super().__init__(placeholder="Select an active event to edit", options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        event_id = self.values[0]
        events_data = config.load_events()
        ev = events_data.get("events", {}).get(event_id)
        if not ev:
            await interaction.response.send_message("Event not found or already ended.", ephemeral=True)
            return
        await interaction.response.send_modal(EditEventModal(self.bot, event_id, ev))

class GameRoleEditSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, guild_game_roles: dict):
        self.bot = bot
        options = []
        for pr_id, pr in guild_game_roles.items():
            desc = pr.get("description", "No description")
            options.append(discord.SelectOption(
                label=f"Edit: {pr['name']}"[:100], 
                value=pr_id,
                description=f"{desc}"[:100]
            ))
        super().__init__(placeholder="Select a game role to edit", options=options[:25])

    async def callback(self, interaction: discord.Interaction):
        perm_id = self.values[0]
        events_data = config.load_events()
        pr = events_data.get("permanent_roles", {}).get(perm_id)
        if not pr:
            await interaction.response.send_message("Role not found.", ephemeral=True)
            return
        await interaction.response.send_modal(EditGameRoleModal(self.bot, perm_id, pr))

class EventEditSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_events: dict):
        super().__init__(timeout=120)
        self.add_item(EventEditSelect(bot, guild_events))

class GameRoleEditSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_game_roles: dict):
        super().__init__(timeout=120)
        self.add_item(GameRoleEditSelect(bot, guild_game_roles))

class EventHubView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild: discord.Guild, guild_events: dict, guild_game_roles: dict):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild = guild
        
        if guild_events:
            self.add_item(EventManageSelect(guild_events, row=0))
            
        if guild_game_roles:
            self.add_item(GameRoleManageSelect(guild_game_roles, row=1))

    @discord.ui.button(label="Create Event", style=discord.ButtonStyle.primary, row=2)
    async def create_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CreateEventModal(self.bot))

    @discord.ui.button(label="Edit Event", style=discord.ButtonStyle.secondary, row=2)
    async def edit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        events_data = config.load_events()
        guild_id = str(self.guild.id)
        guild_events = {k: v for k, v in events_data.get("events", {}).items() if str(v.get("guild_id")) == guild_id}
        if not guild_events:
            await interaction.response.send_message("There are no active events to edit.", ephemeral=True)
            return
        await interaction.response.send_message("Select the event you wish to edit:", view=EventEditSelectView(self.bot, guild_events), ephemeral=True)

    @discord.ui.button(label="Add Game Role", style=discord.ButtonStyle.success, row=3)
    async def perm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CreatePermanentRoleModal(self.bot))

    @discord.ui.button(label="Edit Game Role", style=discord.ButtonStyle.secondary, row=3)
    async def edit_perm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        events_data = config.load_events()
        guild_id = str(self.guild.id)
        guild_game_roles = {k: v for k, v in events_data.get("permanent_roles", {}).items() if str(v.get("guild_id")) == guild_id}
        if not guild_game_roles:
            await interaction.response.send_message("There are no active game roles to edit.", ephemeral=True)
            return
        await interaction.response.send_message("Select the game role you wish to edit:", view=GameRoleEditSelectView(self.bot, guild_game_roles), ephemeral=True)

    @discord.ui.button(label="Assign Members", style=discord.ButtonStyle.secondary, row=4)
    async def assign_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        events_data = config.load_events()
        guild_id = str(self.guild.id)
        guild_events = {k: v for k, v in events_data.get("events", {}).items() if str(v.get("guild_id")) == guild_id}
        guild_game_roles = {k: v for k, v in events_data.get("permanent_roles", {}).items() if str(v.get("guild_id")) == guild_id}
        
        if not guild_events and not guild_game_roles:
            await interaction.response.send_message("There are no active roles to assign.", ephemeral=True)
            return
            
        await interaction.response.send_message(
            "Select which role you want to assign to members:",
            view=AssignRoleSelectView(guild_events, guild_game_roles),
            ephemeral=True
        )

    @discord.ui.button(label="Close Menu", style=discord.ButtonStyle.danger, row=4)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Class President Event Menu closed.", embed=None, view=None)


# ==========================================
# 4. CUSTOM EMBED MODALS
# ==========================================
class EmbedBuilderModal(discord.ui.Modal, title='Bakushin Custom Embed Builder'):
    embed_title = discord.ui.TextInput(label='Embed Title', style=discord.TextStyle.short, required=False)
    embed_desc = discord.ui.TextInput(label='Description', style=discord.TextStyle.paragraph, required=False, max_length=4000)
    image_url = discord.ui.TextInput(label='Image URL (Optional)', style=discord.TextStyle.short, required=False)
    embed_color = discord.ui.TextInput(label='Hex Color (Optional)', style=discord.TextStyle.short, default='FF77AA', required=False)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.embed_title.value and not self.embed_desc.value and not self.image_url.value:
            await interaction.response.send_message("You must provide at least a Title, Description, or Image!", ephemeral=True)
            return
        color_str = self.embed_color.value.replace("#", "") if self.embed_color.value else "FF77AA"
        try: color_val = int(color_str, 16)
        except ValueError: color_val = 0xFF77AA 

        embed = discord.Embed(
            title=self.embed_title.value if self.embed_title.value else None,
            description=self.embed_desc.value if self.embed_desc.value else None,
            color=color_val
        )
        if self.image_url.value:
            embed.set_image(url=self.image_url.value)

        await interaction.channel.send(embed=embed)
        await interaction.response.send_message("[BAKUSHIN] Custom embed successfully posted!", ephemeral=True)

class EmbedEditModal(discord.ui.Modal, title='Edit Bakushin Embed'):
    def __init__(self, message: discord.Message):
        super().__init__()
        self.message = message
        embed = message.embeds[0] if message.embeds else None
        
        self.embed_title = discord.ui.TextInput(label='Embed Title', style=discord.TextStyle.short, default=embed.title if embed and embed.title else '', required=False)
        self.add_item(self.embed_title)
        self.embed_desc = discord.ui.TextInput(label='Description', style=discord.TextStyle.paragraph, default=embed.description if embed and embed.description else '', required=False, max_length=4000)
        self.add_item(self.embed_desc)
        self.image_url = discord.ui.TextInput(label='Image URL (Optional)', style=discord.TextStyle.short, default=embed.image.url if embed and embed.image else '', required=False)
        self.add_item(self.image_url)
        hex_color = hex(embed.color.value).replace('0x', '').upper() if embed and embed.color else 'FF77AA'
        self.embed_color = discord.ui.TextInput(label='Hex Color (Optional)', style=discord.TextStyle.short, default=hex_color, required=False)
        self.add_item(self.embed_color)

    async def on_submit(self, interaction: discord.Interaction):
        if not self.embed_title.value and not self.embed_desc.value and not self.image_url.value:
            await interaction.response.send_message("You must provide at least a Title, Description, or Image!", ephemeral=True)
            return
        color_str = self.embed_color.value.replace("#", "") if self.embed_color.value else "FF77AA"
        try: color_val = int(color_str, 16)
        except ValueError: color_val = 0xFF77AA

        new_embed = discord.Embed(
            title=self.embed_title.value if self.embed_title.value else None,
            description=self.embed_desc.value if self.embed_desc.value else None,
            color=color_val
        )
        if self.image_url.value:
            new_embed.set_image(url=self.image_url.value)

        await self.message.edit(embed=new_embed)
        await interaction.response.send_message("[BAKUSHIN] The embed has been successfully updated!", ephemeral=True)


# ==========================================
# 5. MAIN COG IMPLEMENTATION
# ==========================================
class BakushinCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # --- REACTION ROLE LISTENERS ---
    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id or not payload.guild_id:
            return

        events_data = config.load_events()
        guild_boards = events_data.get("boards", {}).get(str(payload.guild_id), {})
        
        is_event_board = (guild_boards.get("event", {}).get("message_id") == payload.message_id)
        is_game_board = (guild_boards.get("game", {}).get("message_id") == payload.message_id)
        if not is_event_board and not is_game_board:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild: return
        member = payload.member
        if not member:
            try: member = await guild.fetch_member(payload.user_id)
            except Exception: return

        emoji_str = str(payload.emoji)
        role_id = None

        if is_event_board:
            for ev in events_data.get("events", {}).values():
                if str(ev.get("guild_id")) == str(payload.guild_id) and ev.get("emoji") == emoji_str:
                    role_id = ev.get("role_id")
                    break
        elif is_game_board:
            for pr in events_data.get("permanent_roles", {}).values():
                if str(pr.get("guild_id")) == str(payload.guild_id) and pr.get("emoji") == emoji_str:
                    role_id = pr.get("role_id")
                    break

        if role_id:
            role = guild.get_role(role_id)
            if role and role not in member.roles:
                try:
                    await member.add_roles(role, reason="Role board self-assign reaction")
                except discord.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.user_id == self.bot.user.id or not payload.guild_id:
            return

        events_data = config.load_events()
        guild_boards = events_data.get("boards", {}).get(str(payload.guild_id), {})
        
        is_event_board = (guild_boards.get("event", {}).get("message_id") == payload.message_id)
        is_game_board = (guild_boards.get("game", {}).get("message_id") == payload.message_id)
        if not is_event_board and not is_game_board:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if not guild: return
        try: member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
        except Exception: return

        emoji_str = str(payload.emoji)
        role_id = None

        if is_event_board:
            for ev in events_data.get("events", {}).values():
                if str(ev.get("guild_id")) == str(payload.guild_id) and ev.get("emoji") == emoji_str:
                    role_id = ev.get("role_id")
                    break
        elif is_game_board:
            for pr in events_data.get("permanent_roles", {}).values():
                if str(pr.get("guild_id")) == str(payload.guild_id) and pr.get("emoji") == emoji_str:
                    role_id = pr.get("role_id")
                    break

        if role_id:
            role = guild.get_role(role_id)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Role board self-remove reaction")
                except discord.Forbidden:
                    pass

    # --- EXISTING ROLES SLASH COMMANDS ---
    @app_commands.command(name="link-event-role", description="Link an EXISTING server role to the events board")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(role="The existing server role", event_name="Name of the event", end_time="Optional end time. Blank = Permanent", emoji="Optional reaction emoji")
    async def link_event_role(self, interaction: discord.Interaction, role: discord.Role, event_name: str, end_time: str = None, emoji: str = None):
        await interaction.response.defer(ephemeral=True)
        
        if not is_safe_role(role, interaction.guild.default_role):
            await interaction.followup.send("[Error] Cannot link a role with administrative or server-altering permissions! Please select a basic user role.", ephemeral=True)
            return

        try:
            validate_emoji_input(emoji)
            end_ts = parse_time_input(end_time) if end_time else None
        except ValueError as err:
            await interaction.followup.send(f"[Error] {err}", ephemeral=True)
            return

        events_data = config.load_events()
        for ev in events_data.get("events", {}).values():
            if str(ev.get("guild_id")) == str(interaction.guild.id) and ev.get("role_id") == role.id:
                await interaction.followup.send("[Error] That role is already linked to the event board! Use `/event` to edit it.", ephemeral=True)
                return

        chosen_emoji = get_available_emoji(interaction.guild.id, events_data, emoji)
        event_id = str(uuid.uuid4())[:8]
        events_data.setdefault("events", {})[event_id] = {
            "name": event_name, "role_name": role.name, "role_id": role.id,
            "guild_id": interaction.guild.id, "end_time": end_ts, "emoji": chosen_emoji
        }
        config.save_events(events_data)
        
        time_msg = f"<t:{end_ts}:F>" if end_ts else "Permanent"
        
        await interaction.followup.send(
            f"[BAKUSHIN] Existing role successfully linked to an event!\n"
            f"- Event: **{event_name}**\n- Role: {role.mention}\n- Reaction: {chosen_emoji}\n- Ends: {time_msg}",
            ephemeral=True
        )
        await update_boards(self.bot, interaction.guild.id)

    @app_commands.command(name="link-game-role", description="Link an EXISTING server role to the permanent gaming board")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(role="The existing server role", description="Short description of the game", emoji="Optional reaction emoji")
    async def link_game_role(self, interaction: discord.Interaction, role: discord.Role, description: str = None, emoji: str = None):
        await interaction.response.defer(ephemeral=True)
        
        if not is_safe_role(role, interaction.guild.default_role):
            await interaction.followup.send("[Error] Cannot link a role with administrative or server-altering permissions! Please select a basic user role.", ephemeral=True)
            return

        try:
            validate_emoji_input(emoji)
        except ValueError as err:
            await interaction.followup.send(f"[Error] {err}", ephemeral=True)
            return

        events_data = config.load_events()
        for pr in events_data.get("permanent_roles", {}).values():
            if str(pr.get("guild_id")) == str(interaction.guild.id) and pr.get("role_id") == role.id:
                await interaction.followup.send("[Error] That role is already linked to the game board! Use `/event` to edit it.", ephemeral=True)
                return

        chosen_emoji = get_available_emoji(interaction.guild.id, events_data, emoji)
        perm_id = str(uuid.uuid4())[:8]
        events_data.setdefault("permanent_roles", {})[perm_id] = {
            "name": role.name, "role_id": role.id, "guild_id": interaction.guild.id,
            "description": description or "Game notification role", "emoji": chosen_emoji
        }
        config.save_events(events_data)
        await interaction.followup.send(
            f"[BAKUSHIN] Existing role successfully linked to the game board!\n- Role: {role.mention}\n- Reaction: {chosen_emoji}",
            ephemeral=True
        )
        await update_boards(self.bot, interaction.guild.id)

    # --- GENERAL COMMANDS ---
    @app_commands.command(name="event", description="View, create, or manage community events and roles")
    @app_commands.default_permissions(manage_roles=True)
    async def event_command(self, interaction: discord.Interaction):
        events_data = config.load_events()
        guild_id = str(interaction.guild.id)
        
        guild_events = {k: v for k, v in events_data.get("events", {}).items() if str(v.get("guild_id")) == guild_id}
        guild_game_roles = {k: v for k, v in events_data.get("permanent_roles", {}).items() if str(v.get("guild_id")) == guild_id}

        embed = discord.Embed(
            title="Class President Hub",
            description="Manage your active Events and Gaming Roles below.",
            color=0xFF77AA
        )
        
        if not guild_events:
            embed.add_field(name="Active Events", value="No active events scheduled.", inline=False)
        else:
            lines = []
            for ev_id, ev in guild_events.items():
                role = interaction.guild.get_role(ev["role_id"])
                role_str = role.mention if role else f"@{ev['role_name']}"
                ends_str = f"Ends <t:{ev['end_time']}:R>" if ev.get("end_time") else "Permanent"
                lines.append(f"{ev.get('emoji', '🟠')} **{ev['name']}** ({role_str}) - {ends_str}")
            embed.add_field(name="Active Events", value="\n".join(lines), inline=False)

        if not guild_game_roles:
            embed.add_field(name="Gaming Roles", value="No permanent game roles added.", inline=False)
        else:
            lines = []
            for pr_id, pr in guild_game_roles.items():
                role = interaction.guild.get_role(pr["role_id"])
                role_str = role.mention if role else f"@{pr['name']}"
                lines.append(f"{pr.get('emoji', '⚪')} **{pr['name']}** ({role_str})")
            embed.add_field(name="Gaming Roles", value="\n".join(lines), inline=False)

        view = EventHubView(self.bot, interaction.guild, guild_events, guild_game_roles)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="setup-boards", description="Deploy the live role assignment boards")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(event_channel="Channel for the Active Events board", game_channel="Channel for the Gaming Roles board")
    async def setup_boards(self, interaction: discord.Interaction, event_channel: discord.TextChannel = None, game_channel: discord.TextChannel = None):
        if not event_channel and not game_channel:
            await interaction.response.send_message("You must select at least one channel to setup a board!", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)
        try:
            events_data = config.load_events()
            guild_id_str = str(interaction.guild.id)
            boards = events_data.setdefault("boards", {}).setdefault(guild_id_str, {})
            reply_text = "[BAKUSHIN] Boards deployed!\n"

            if event_channel:
                embed = build_event_embed(interaction.guild, events_data)
                msg = await event_channel.send(embed=embed)
                boards["event"] = {"channel_id": event_channel.id, "message_id": msg.id}
                reply_text += f"- Event Board placed in {event_channel.mention}\n"

            if game_channel:
                embed = build_game_embed(interaction.guild, events_data)
                msg = await game_channel.send(embed=embed)
                boards["game"] = {"channel_id": game_channel.id, "message_id": msg.id}
                reply_text += f"- Game Board placed in {game_channel.mention}\n"

            config.save_events(events_data)
            await interaction.followup.send(reply_text, ephemeral=True)
            await update_boards(self.bot, interaction.guild.id)
            
        except Exception as e:
            await interaction.followup.send(f"An error occurred while setting up the boards: {e}", ephemeral=True)
            raise e

    @app_commands.command(name="setup", description="Setup reminder channels and roles")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(channel="Reminder channel", global_role="Global reminder role", jp_role="JP reminder role")
    async def setup(self, interaction: discord.Interaction, channel: discord.TextChannel, global_role: discord.Role, jp_role: discord.Role):
        conf = config.load_config()
        conf[str(interaction.guild_id)] = {
            "channel_id": channel.id,
            "global_role_id": global_role.id,
            "jp_role_id": jp_role.id
        }
        config.save_config(conf)
        await interaction.response.send_message(
            f"[BAKUSHIN] Setup complete into {channel.mention}!\nGlobal: {global_role.mention}\nJP: {jp_role.mention}", 
            ephemeral=True
        )

    @app_commands.command(name="dailies", description="Check time left for Dailies and Team Trials")
    async def dailies(self, interaction: discord.Interaction):
        quote_type = random.choice(["dailies", "tt"])
        await interaction.response.send_message(
            content=get_quote(quote_type),
            embed=build_embed(), 
            allowed_mentions=discord.AllowedMentions.none()
        )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if not message.webhook_id: return
        if message.content:
            try:
                raw_parts = message.content.split(" ::: ", 1)
                routing_args = raw_parts[0].split()
                msg_text = raw_parts[1] if len(raw_parts) > 1 else None
                msg_embed = message.embeds[0] if message.embeds else None

                if not msg_text and not msg_embed: return

                if routing_args[0] == "EDIT" and len(routing_args) == 3:
                    channel_id = int(routing_args[1])
                    message_id = int(routing_args[2])
                    target_channel = self.bot.get_channel(channel_id)
                    if target_channel:
                        target_message = await target_channel.fetch_message(message_id)
                        await target_message.edit(content=msg_text, embed=msg_embed)
                        await message.delete() 
                        await message.channel.send(f"[BAKUSHIN] Message successfully edited in {target_channel.mention}!")
                    else:
                        raise ValueError(f"Could not find target channel <{channel_id}>.")

                elif routing_args[0].isdigit():
                    channel_id = int(routing_args[0])
                    target_channel = self.bot.get_channel(channel_id)
                    if target_channel:
                        await target_channel.send(content=msg_text, embed=msg_embed)
                        await message.delete() 
                        await message.channel.send(f"[BAKUSHIN] Message successfully sent to {target_channel.mention}!")
                    else:
                        raise ValueError(f"Could not find target channel <{channel_id}>.")
                        
            except Exception as e:
                if isinstance(e, discord.Forbidden): reason = "403 Forbidden: Missing permissions in Target Channel or Manage Messages in Relay Channel."
                elif isinstance(e, discord.NotFound): reason = "404 Not Found: Could not find Message ID to edit."
                else: reason = str(e)

                log_sent = False
                conf = config.load_config()
                log_channel_id = conf.get("global_log_channel")
                if log_channel_id:
                    log_channel = self.bot.get_channel(log_channel_id)
                    if log_channel:
                        log_text = f"**Action:** `Webhook Relay`\n**Reason:** `{reason}`\n[Jump to Webhook Message]({message.jump_url})"
                        error_embed = discord.Embed(title="Bakushin Relay Error", description=log_text, color=0xFF0000)
                        await log_channel.send(embed=error_embed)
                        log_sent = True

                if not log_sent:
                    await message.channel.send(f"[Error] {reason}")

    @app_commands.command(name="test-reminder", description="Force the bot to send a test reminder immediately")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(region="Which region to test (global or jp)", reminder_type="Which timer to test (dailies or tt)")
    @app_commands.choices(
        region=[app_commands.Choice(name="Global", value="global"), app_commands.Choice(name="JP", value="jp")],
        reminder_type=[app_commands.Choice(name="Dailies", value="dailies"), app_commands.Choice(name="Team Trials", value="tt")]
    )
    async def test_reminder(self, interaction: discord.Interaction, region: str, reminder_type: str):
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
            await interaction.followup.send("[Error] Could not find the background tasks!", ephemeral=True)

    @app_commands.command(name="create-embed", description="Design and send a custom embed into the current channel")
    @app_commands.default_permissions(administrator=True)
    async def create_embed(self, interaction: discord.Interaction):
        await interaction.response.send_modal(EmbedBuilderModal())

    @app_commands.command(name="edit-embed", description="Edit an existing Bakushin custom embed")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(message_id="The ID of the message you want to edit")
    async def edit_embed(self, interaction: discord.Interaction, message_id: str):
        try: message = await interaction.channel.fetch_message(int(message_id))
        except discord.NotFound:
            await interaction.response.send_message("I couldn't find a message with that ID in this channel!", ephemeral=True)
            return
        except ValueError:
            await interaction.response.send_message("Invalid ID format.", ephemeral=True)
            return

        if message.author != self.bot.user:
            await interaction.response.send_message("I can only edit my own messages!", ephemeral=True)
            return
            
        if not message.embeds:
            await interaction.response.send_message("That message has no embed to edit!", ephemeral=True)
            return

        await interaction.response.send_modal(EmbedEditModal(message))

    @app_commands.command(name="set-error-logs", description="Set the channel where Bakushin reports system errors")
    @app_commands.default_permissions(administrator=True)
    async def set_error_logs(self, interaction: discord.Interaction, channel: discord.TextChannel):
        conf = config.load_config()
        conf["global_log_channel"] = channel.id
        config.save_config(conf)
        await interaction.response.send_message(f"[BAKUSHIN] System errors will now be logged in {channel.mention}!", ephemeral=True)

async def setup(bot):
    await bot.add_cog(BakushinCommands(bot))

    async def on_tree_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
        original_error = getattr(error, 'original', error)
        line_num = "Unknown"
        file_name = "Unknown"
        if original_error.__traceback__:
            tb = traceback.extract_tb(original_error.__traceback__)
            if tb:
                last_call = tb[-1]
                line_num = last_call.lineno
                file_name = last_call.filename.split('/')[-1]

        if isinstance(original_error, discord.errors.Forbidden): reason = "403 / No Perms (Missing Permissions)"
        elif isinstance(original_error, discord.errors.NotFound): reason = "404 / Not Found"
        else: reason = str(original_error)

        cmd_name = interaction.command.name if interaction.command else 'Unknown'
        log_text = f"**Command:** `/{cmd_name}`\n**File:** `{file_name}`\n**Line:** `{line_num}`\n**Reason:** `{reason}`"

        if not interaction.response.is_done():
            try: await interaction.response.send_message("A system error occurred. The Class President is looking into it!", ephemeral=True)
            except Exception: pass

        conf = config.load_config()
        log_channel_id = conf.get("global_log_channel")
        if log_channel_id:
            channel = bot.get_channel(log_channel_id)
            if channel:
                err_embed = discord.Embed(title="Bakushin System Error", description=log_text, color=0xFF0000)
                await channel.send(embed=err_embed)
                
        print(f"Error in /{cmd_name}: {original_error}")

    bot.tree.on_error = on_tree_error
