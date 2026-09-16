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

# --- EVENT MANAGEMENT MODALS ---
class CreateEventModal(discord.ui.Modal, title="Create New Event"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    event_name = discord.ui.TextInput(
        label="Event Name",
        placeholder="e.g., Summer Sprint Tournament",
        required=True
    )
    role_name = discord.ui.TextInput(
        label="Role Name",
        placeholder="e.g., Sprint Contender",
        required=True
    )
    emoji_input = discord.ui.TextInput(
        label="Reaction Emoji (Optional)",
        placeholder="e.g., standard emoji or server emoji. Blank = auto",
        required=False
    )
    role_color = discord.ui.TextInput(
        label="Role Hex Color",
        placeholder="FF77AA",
        default="FF77AA",
        required=False
    )
    end_time_input = discord.ui.TextInput(
        label="Event Duration or End Time (UTC)",
        placeholder="e.g., 2h, 1d, or 2026-10-31 18:00",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        try:
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
            await interaction.response.send_message("[Error] Missing Manage Roles permission to create the event role.", ephemeral=True)
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
        
        await interaction.response.send_message(
            f"[BAKUSHIN] Event created!\n"
            f"- Event: **{self.event_name.value}**\n"
            f"- Role: {new_role.mention}\n"
            f"- Reaction: {chosen_emoji}\n"
            f"- Ends: <t:{end_ts}:F> (<t:{end_ts}:R>)\n"
            f"The role will be automatically deleted when the event concludes.",
            ephemeral=True
        )
        
        # Update boards in background
        await update_boards(self.bot, interaction.guild.id)


class EditEventModal(discord.ui.Modal):
    def __init__(self, bot: commands.Bot, event_id: str, current_data: dict):
        super().__init__(title="Edit Active Event")
        self.bot = bot
        self.event_id = event_id
        self.current_data = current_data

        self.event_name = discord.ui.TextInput(
            label="Event Name",
            default=current_data.get("name", ""),
            required=True
        )
        self.add_item(self.event_name)

        self.role_name = discord.ui.TextInput(
            label="Role Name",
            default=current_data.get("role_name", ""),
            required=True
        )
        self.add_item(self.role_name)

        self.emoji_input = discord.ui.TextInput(
            label="Reaction Emoji",
            default=current_data.get("emoji", ""),
            required=False
        )
        self.add_item(self.emoji_input)

        dt = datetime.datetime.fromtimestamp(current_data.get("end_time", 0), tz=datetime.timezone.utc)
        self.end_time_input = discord.ui.TextInput(
            label="End Time (UTC) or Duration",
            default=dt.strftime("%Y-%m-%d %H:%M"),
            required=True
        )
        self.add_item(self.end_time_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
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


class CreatePermanentRoleModal(discord.ui.Modal, title="Create Permanent Game Role"):
    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot

    role_name = discord.ui.TextInput(
        label="Role Name",
        placeholder="e.g., Maple Bossing or Uma Lobbies",
        required=True
    )
    emoji_input = discord.ui.TextInput(
        label="Reaction Emoji (Optional)",
        placeholder="e.g., standard emoji or server emoji. Blank = auto",
        required=False
    )
    role_color = discord.ui.TextInput(
        label="Role Hex Color",
        placeholder="FF77AA",
        default="FF77AA",
        required=False
    )
    description = discord.ui.TextInput(
        label="Role Description",
        placeholder="e.g., Ping to coordinate multiplayer lobbies",
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
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
            f"- Reaction: {chosen_emoji}\n"
            f"- Use: React on the role board to assign or remove this role.",
            ephemeral=True
        )
        
        await update_boards(self.bot, interaction.guild.id)


# --- USER ASSIGNMENT VIEW ---
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


# --- EVENT HUB VIEWS (/event) ---
class EventManageSelect(discord.ui.Select):
    def __init__(self, guild_events: dict):
        options = []
        for ev_id, ev in guild_events.items():
            options.append(discord.SelectOption(
                label=ev["name"][:100],
                value=ev_id,
                description=f"Role: @{ev['role_name']}"[:100]
            ))
        super().__init__(placeholder="Select an active event to cancel or delete", options=options)

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


class EventEditSelect(discord.ui.Select):
    def __init__(self, bot: commands.Bot, guild_events: dict):
        self.bot = bot
        options = []
        for ev_id, ev in guild_events.items():
            dt_str = datetime.datetime.fromtimestamp(ev["end_time"], tz=datetime.timezone.utc).strftime('%Y-%m-%d %H:%M')
            options.append(discord.SelectOption(
                label=ev["name"][:100],
                value=ev_id,
                description=f"Ends: {dt_str} UTC"[:100]
            ))
        super().__init__(placeholder="Select an active event to edit", options=options)

    async def callback(self, interaction: discord.Interaction):
        event_id = self.values[0]
        events_data = config.load_events()
        ev = events_data.get("events", {}).get(event_id)
        if not ev:
            await interaction.response.send_message("Event not found or already ended.", ephemeral=True)
            return

        await interaction.response.send_modal(EditEventModal(self.bot, event_id, ev))


class EventEditSelectView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild_events: dict):
        super().__init__(timeout=120)
        self.add_item(EventEditSelect(bot, guild_events))


class EventHubView(discord.ui.View):
    def __init__(self, bot: commands.Bot, guild: discord.Guild, guild_events: dict):
        super().__init__(timeout=180)
        self.bot = bot
        self.guild = guild
        if guild_events:
            self.add_item(EventManageSelect(guild_events))

    @discord.ui.button(label="Create Event", style=discord.ButtonStyle.primary)
    async def create_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CreateEventModal(self.bot))

    @discord.ui.button(label="Edit Event", style=discord.ButtonStyle.secondary)
    async def edit_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        events_data = config.load_events()
        guild_id = str(self.guild.id)
        guild_events = {k: v for k, v in events_data.get("events", {}).items() if str(v.get("guild_id")) == guild_id}
        
        if not guild_events:
            await interaction.response.send_message("There are no active temporary events to edit.", ephemeral=True)
            return
        
        await interaction.response.send_message(
            "Select the event you wish to edit:",
            view=EventEditSelectView(self.bot, guild_events),
            ephemeral=True
        )

    @discord.ui.button(label="Add Permanent Role", style=discord.ButtonStyle.secondary)
    async def perm_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(CreatePermanentRoleModal(self.bot))

    @discord.ui.button(label="Assign Members", style=discord.ButtonStyle.secondary)
    async def assign_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        events_data = config.load_events()
        guild_id = str(self.guild.id)
        events = [e for e in events_data.get("events", {}).values() if str(e.get("guild_id")) == guild_id]
        if not events:
            await interaction.response.send_message("There are no active temporary event roles to assign.", ephemeral=True)
            return
        
        target_role = self.guild.get_role(events[0]["role_id"])
        if not target_role:
            await interaction.response.send_message("Role not found on server.", ephemeral=True)
            return

        await interaction.response.send_message(
            f"Select members to assign to **{events[0]['name']}** ({target_role.mention}):",
            view=AssignUserSelectView(target_role),
            ephemeral=True
        )

    @discord.ui.button(label="Close Menu", style=discord.ButtonStyle.danger)
    async def close_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="Class President Event Menu closed.", embed=None, view=None)


# --- EMBED MODALS ---
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
        try:
            color_val = int(color_str, 16)
        except ValueError:
            color_val = 0xFF77AA 

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
        try:
            color_val = int(color_str, 16)
        except ValueError:
            color_val = 0xFF77AA

        new_embed = discord.Embed(
            title=self.embed_title.value if self.embed_title.value else None,
            description=self.embed_desc.value if self.embed_desc.value else None,
            color=color_val
        )
        if self.image_url.value:
            new_embed.set_image(url=self.image_url.value)

        await self.message.edit(embed=new_embed)
        await interaction.response.send_message("[BAKUSHIN] The embed has been successfully updated!", ephemeral=True)


# --- COG IMPLEMENTATION ---
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
        if not guild:
            return

        member = payload.member
        if not member:
            try:
                member = await guild.fetch_member(payload.user_id)
            except Exception:
                return

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
                    print(f"Forbidden: Cannot assign role {role_id} to {member.id}")

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
        if not guild:
            return

        try:
            member = guild.get_member(payload.user_id) or await guild.fetch_member(payload.user_id)
        except Exception:
            return

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
                    print(f"Forbidden: Cannot remove role {role_id} from {member.id}")

    # --- EXISTING ROLES SLASH COMMANDS ---
    @app_commands.command(name="link-event-role", description="Link an EXISTING server role to the temporary events board")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(role="The existing server role", event_name="Name of the event", end_time="UTC time or duration (e.g., 2h)", emoji="Optional reaction emoji")
    async def link_event_role(self, interaction: discord.Interaction, role: discord.Role, event_name: str, end_time: str, emoji: str = None):
        await interaction.response.defer(ephemeral=True)
        
        try:
            end_ts = parse_time_input(end_time)
        except ValueError as err:
            await interaction.followup.send(f"[Error] {err}", ephemeral=True)
            return

        events_data = config.load_events()
        chosen_emoji = get_available_emoji(interaction.guild.id, events_data, emoji)

        event_id = str(uuid.uuid4())[:8]
        events_data.setdefault("events", {})[event_id] = {
            "name": event_name,
            "role_name": role.name,
            "role_id": role.id,
            "guild_id": interaction.guild.id,
            "end_time": end_ts,
            "emoji": chosen_emoji
        }
        config.save_events(events_data)
        
        await interaction.followup.send(
            f"[BAKUSHIN] Existing role successfully linked to an event!\n"
            f"- Event: **{event_name}**\n"
            f"- Role: {role.mention}\n"
            f"- Reaction: {chosen_emoji}\n"
            f"- Ends: <t:{end_ts}:F> (<t:{end_ts}:R>)",
            ephemeral=True
        )
        await update_boards(self.bot, interaction.guild.id)


    @app_commands.command(name="link-game-role", description="Link an EXISTING server role to the permanent gaming board")
    @app_commands.default_permissions(manage_roles=True)
    @app_commands.describe(role="The existing server role", description="Short description of the game", emoji="Optional reaction emoji")
    async def link_game_role(self, interaction: discord.Interaction, role: discord.Role, description: str = None, emoji: str = None):
        await interaction.response.defer(ephemeral=True)
        
        events_data = config.load_events()
        chosen_emoji = get_available_emoji(interaction.guild.id, events_data, emoji)

        perm_id = str(uuid.uuid4())[:8]
        events_data.setdefault("permanent_roles", {})[perm_id] = {
            "name": role.name,
            "role_id": role.id,
            "guild_id": interaction.guild.id,
            "description": description or "Game notification role",
            "emoji": chosen_emoji
        }
        config.save_events(events_data)
        
        await interaction.followup.send(
            f"[BAKUSHIN] Existing role successfully linked to the game board!\n"
            f"- Role: {role.mention}\n"
            f"- Reaction: {chosen_emoji}",
            ephemeral=True
        )
        await update_boards(self.bot, interaction.guild.id)


    # --- GENERAL COMMANDS ---
    @app_commands.command(name="event", description="View, create, or manage community events and roles")
    @app_commands.default_permissions(manage_roles=True)
    async def event_command(self, interaction: discord.Interaction):
        events_data = config.load_events()
        guild_id = str(interaction.guild.id)
        
        guild_events = {
            k: v for k, v in events_data.get("events", {}).items() 
            if str(v.get("guild_id")) == guild_id
        }

        if not guild_events:
            embed = discord.Embed(
                title="Class President Event Operations",
                description="Class President Announcement: There are currently no active events scheduled! Forward, forward, forward! Keep your spirit sharp for the next starting gate!",
                color=0xFF77AA
            )
        else:
            embed = discord.Embed(
                title="Current Active Community Events",
                description="Review current running events, their target roles, and scheduled completion times below.",
                color=0xFF77AA
            )
            for ev_id, ev in guild_events.items():
                role = interaction.guild.get_role(ev["role_id"])
                role_str = role.mention if role else f"@{ev['role_name']}"
                emoji_str = ev.get("emoji", "🟠")
                embed.add_field(
                    name=ev["name"],
                    value=f"Reaction: {emoji_str}\nRole: {role_str}\nEnds: <t:{ev['end_time']}:F> (<t:{ev['end_time']}:R>)",
                    inline=False
                )

        view = EventHubView(self.bot, interaction.guild, guild_events)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="setup-boards", description="Deploy the live role assignment boards")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        event_channel="Channel for the Active Events board",
        game_channel="Channel for the Gaming Roles board"
    )
    async def setup_boards(self, interaction: discord.Interaction, event_channel: discord.TextChannel = None, game_channel: discord.TextChannel = None):
        if not event_channel and not game_channel:
            await interaction.response.send_message("You must select at least one channel to setup a board!", ephemeral=True)
            return

        # Defer the interaction immediately to prevent the 3-second 404 timeout
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
            
            # Send the success message FIRST so it doesn't get stuck on "Thinking..."
            await interaction.followup.send(reply_text, ephemeral=True)
            
            # THEN silently update the boards and process all the emojis in the background
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
        if not message.webhook_id:
            return
            
        if message.content:
            try:
                raw_parts = message.content.split(" ::: ", 1)
                routing_args = raw_parts[0].split()
                msg_text = raw_parts[1] if len(raw_parts) > 1 else None
                msg_embed = message.embeds[0] if message.embeds else None

                if not msg_text and not msg_embed:
                    return

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
                if isinstance(e, discord.Forbidden):
                    reason = "403 Forbidden: Missing permissions in Target Channel or Manage Messages in Relay Channel."
                elif isinstance(e, discord.NotFound):
                    reason = "404 Not Found: Could not find Message ID to edit."
                else:
                    reason = str(e)

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
        try:
            message = await interaction.channel.fetch_message(int(message_id))
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

        if isinstance(original_error, discord.errors.Forbidden):
            reason = "403 / No Perms (Missing Permissions)"
        elif isinstance(original_error, discord.errors.NotFound):
            reason = "404 / Not Found"
        else:
            reason = str(original_error)

        cmd_name = interaction.command.name if interaction.command else 'Unknown'
        log_text = f"**Command:** `/{cmd_name}`\n**File:** `{file_name}`\n**Line:** `{line_num}`\n**Reason:** `{reason}`"

        if not interaction.response.is_done():
            try:
                await interaction.response.send_message("A system error occurred. The Class President is looking into it!", ephemeral=True)
            except Exception:
                pass

        conf = config.load_config()
        log_channel_id = conf.get("global_log_channel")
        if log_channel_id:
            channel = bot.get_channel(log_channel_id)
            if channel:
                err_embed = discord.Embed(title="Bakushin System Error", description=log_text, color=0xFF0000)
                await channel.send(embed=err_embed)
                
        print(f"Error in /{cmd_name}: {original_error}")

    bot.tree.on_error = on_tree_error
