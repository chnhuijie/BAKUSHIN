import discord
import datetime
import re
from zoneinfo import ZoneInfo
import config

UTC = datetime.timezone.utc
JST = ZoneInfo("Asia/Tokyo")

DEFAULT_EMOJI_POOL = ["🟠", "🔵", "🟢", "🟡", "🟣", "🔴", "⚪", "⭐", "🏆", "🎯"]

def get_next_timestamp(hour, minute, tz, weekday=None):
    now = datetime.datetime.now(tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    if target <= now:
        target += datetime.timedelta(days=1)
        
    if weekday is not None:
        while target.weekday() != weekday:
            target += datetime.timedelta(days=1)
            
    return int(target.timestamp())

def build_embed():
    global_reset = get_next_timestamp(15, 0, UTC)
    global_tt = get_next_timestamp(10, 0, UTC, weekday=0) 
    
    jp_reset = get_next_timestamp(5, 0, JST)
    jp_tt = get_next_timestamp(0, 0, JST, weekday=0) 

    embed = discord.Embed(
        title="Official URA Starting Gate!",
        description="BAKUSHIN!",
        color=0xFF77AA
    )
    
    embed.add_field(
        name="UMA Global",
        value=f"**Daily Server Reset:** <t:{global_reset}:f> (<t:{global_reset}:R>)\n**Tally Phase Starts:** <t:{global_tt}:f> (<t:{global_tt}:R>)",
        inline=False
    )
    
    embed.add_field(
        name="UMA JP",
        value=f"**Daily Server Reset:** <t:{jp_reset}:f> (<t:{jp_reset}:R>)\n**Tally Phase Starts:** <t:{jp_tt}:f> (<t:{jp_tt}:R>)",
        inline=False
    )
    
    embed.set_footer(text="Class President - BAKUSHIN with all your might!")
    return embed

def parse_time_input(time_str: str) -> int:
    time_str = time_str.strip().lower()
    now = datetime.datetime.now(datetime.timezone.utc)

    pattern = r'^(?:(\d+)\s*d)?\s*(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?$'
    match = re.fullmatch(pattern, time_str)
    if match and any(match.groups()):
        days = int(match.group(1) or 0)
        hours = int(match.group(2) or 0)
        minutes = int(match.group(3) or 0)
        target = now + datetime.timedelta(days=days, hours=hours, minutes=minutes)
        return int(target.timestamp())

    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%m/%d/%Y %H:%M"):
        try:
            dt = datetime.datetime.strptime(time_str, fmt).replace(tzinfo=datetime.timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            continue

    raise ValueError("Invalid time format. Use relative time (e.g., 2h, 30m, 1d) or YYYY-MM-DD HH:MM (UTC).")

def get_available_emoji(guild_id: int, events_data: dict, preferred: str = None) -> str:
    if preferred and preferred.strip():
        return preferred.strip()

    guild_id_str = str(guild_id)
    used = set()
    for ev in events_data.get("events", {}).values():
        if str(ev.get("guild_id")) == guild_id_str and ev.get("emoji"):
            used.add(ev["emoji"])
    for pr in events_data.get("permanent_roles", {}).values():
        if str(pr.get("guild_id")) == guild_id_str and pr.get("emoji"):
            used.add(pr["emoji"])

    for candidate in DEFAULT_EMOJI_POOL:
        if candidate not in used:
            return candidate
    return "🟠"

def build_event_embed(guild: discord.Guild, events_data: dict) -> discord.Embed:
    guild_id = str(guild.id)
    events = [e for e in events_data.get("events", {}).values() if str(e.get("guild_id")) == guild_id]

    embed = discord.Embed(
        title="Event Roles",
        description="Would you like to be pinged for specific server related events?\n\n**React to this message to assign yourself an event role.**",
        color=0xFF77AA
    )

    if events:
        lines = []
        for ev in events:
            role = guild.get_role(ev["role_id"])
            role_mention = role.mention if role else f"@{ev['role_name']}"
            emoji = ev.get("emoji", "🟠")
            lines.append(f"| {emoji} - {role_mention} (Ends <t:{ev['end_time']}:R>)")
        embed.add_field(name="Active Events", value="\n".join(lines), inline=False)
    else:
        embed.add_field(
            name="Active Events",
            value="Class President Notice: There are currently no active events scheduled! Forward, forward, forward! Keep up your daily training until the next starting bell rings!",
            inline=False
        )

    embed.set_footer(text="Class President Bakushin - Event Roles")
    return embed

def build_game_embed(guild: discord.Guild, events_data: dict) -> discord.Embed:
    guild_id = str(guild.id)
    perm_roles = [r for r in events_data.get("permanent_roles", {}).values() if str(r.get("guild_id")) == guild_id]
    
    embed = discord.Embed(
        title="Gaming Roles",
        description="Would you like to be pinged for specific gaming related events?\n\n**React to this message to assign yourself game specific roles.**",
        color=0xFF77AA
    )
    
    if perm_roles:
        lines = []
        for pr in perm_roles:
            role = guild.get_role(pr["role_id"])
            role_mention = role.mention if role else f"@{pr['role_name']}"
            emoji = pr.get("emoji", "⚪")
            desc = f" - {pr['description']}" if pr.get("description") else ""
            lines.append(f"| {emoji} - {role_mention}{desc}")
        embed.add_field(name="Available Games", value="\n".join(lines), inline=False)
    else:
        embed.add_field(
            name="Available Games",
            value="No gaming roles are currently active.",
            inline=False
        )
    
    embed.set_footer(text="Class President Bakushin - Gaming Roles")
    return embed

async def sync_reactions(bot: discord.Client, message: discord.Message, active_emojis: list):
    """Helper function to clean up old reactions and add new ones."""
    for reaction in message.reactions:
        emoji_str = str(reaction.emoji)
        if emoji_str not in active_emojis and reaction.me:
            try:
                await message.clear_reaction(reaction.emoji)
            except Exception:
                try:
                    await reaction.remove(bot.user)
                except Exception:
                    pass

    existing_bot_emojis = [str(r.emoji) for r in message.reactions if r.me]
    for emo in active_emojis:
        if emo not in existing_bot_emojis:
            try:
                custom_match = re.match(r"^<a?:(\w+):(\d+)>$", emo)
                if custom_match:
                    emoji_obj = bot.get_emoji(int(custom_match.group(2)))
                    if emoji_obj:
                        await message.add_reaction(emoji_obj)
                    else:
                        await message.add_reaction(emo)
                else:
                    await message.add_reaction(emo)
            except Exception as err:
                print(f"Failed to add reaction {emo}: {err}")

async def update_boards(bot: discord.Client, guild_id: int):
    events_data = config.load_events()
    guild_boards = events_data.get("boards", {}).get(str(guild_id), {})
    guild = bot.get_guild(guild_id)
    if not guild:
        return

    guild_id_str = str(guild_id)

    # --- UPDATE EVENT BOARD ---
    event_board = guild_boards.get("event")
    if event_board:
        channel = bot.get_channel(event_board["channel_id"])
        if not channel:
            try: channel = await bot.fetch_channel(event_board["channel_id"])
            except Exception: channel = None
        
        if channel:
            try:
                message = await channel.fetch_message(event_board["message_id"])
                embed = build_event_embed(guild, events_data)
                await message.edit(embed=embed, view=None)

                events = [e for e in events_data.get("events", {}).values() if str(e.get("guild_id")) == guild_id_str]
                active_emojis = []
                for ev in events:
                    if ev.get("emoji") and ev["emoji"] not in active_emojis:
                        active_emojis.append(ev["emoji"])
                
                await sync_reactions(bot, message, active_emojis)
            except Exception as e:
                print(f"Failed to update Event board: {e}")

    # --- UPDATE GAME BOARD ---
    game_board = guild_boards.get("game")
    if game_board:
        channel = bot.get_channel(game_board["channel_id"])
        if not channel:
            try: channel = await bot.fetch_channel(game_board["channel_id"])
            except Exception: channel = None
        
        if channel:
            try:
                message = await channel.fetch_message(game_board["message_id"])
                embed = build_game_embed(guild, events_data)
                await message.edit(embed=embed, view=None)

                perm_roles = [r for r in events_data.get("permanent_roles", {}).values() if str(r.get("guild_id")) == guild_id_str]
                active_emojis = []
                for pr in perm_roles:
                    if pr.get("emoji") and pr["emoji"] not in active_emojis:
                        active_emojis.append(pr["emoji"])
                
                await sync_reactions(bot, message, active_emojis)
            except Exception as e:
                print(f"Failed to update Game board: {e}")
