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

def build_event_board_embed(guild: discord.Guild, events_data: dict) -> discord.Embed:
    guild_id = str(guild.id)
    events = [e for e in events_data.get("events", {}).values() if str(e.get("guild_id")) == guild_id]
    perm_roles = [r for r in events_data.get("permanent_roles", {}).values() if str(r.get("guild_id")) == guild_id]

    embed = discord.Embed(
        title="Event Roles",
        description="Would you like to be pinged for specific server related events?\n\n**React to this message to assign yourself an event role.**",
        color=0x00A2FF
    )

    lines = []
    if events:
        lines.append("**Temporary Events**")
        for ev in events:
            role = guild.get_role(ev["role_id"])
            role_mention = role.mention if role else f"@{ev['role_name']}"
            emoji = ev.get("emoji", "🟠")
            lines.append(f"| {emoji} - {role_mention} (Ends <t:{ev['end_time']}:R>)")

    if perm_roles:
        if events:
            lines.append("")
        lines.append("**Permanent Roles**")
        for pr in perm_roles:
            role = guild.get_role(pr["role_id"])
            role_mention = role.mention if role else f"@{pr['role_name']}"
            emoji = pr.get("emoji", "🎮")
            desc = f" - {pr['description']}" if pr.get("description") else ""
            lines.append(f"| {emoji} - {role_mention}{desc}")

    if lines:
        embed.add_field(name="\u200b", value="\n".join(lines), inline=False)
    else:
        embed.add_field(
            name="\u200b",
            value="Class President Notice: There are currently no active events scheduled! Forward, forward, forward! Keep up your daily training until the next starting bell rings!",
            inline=False
        )

    embed.set_footer(text="Class President Bakushin - Event Roles")
    return embed

async def update_event_board(bot: discord.Client, guild_id: int):
    events_data = config.load_events()
    board_info = events_data.get("boards", {}).get(str(guild_id))
    if not board_info:
        return

    channel = bot.get_channel(board_info["channel_id"])
    if not channel:
        try:
            channel = await bot.fetch_channel(board_info["channel_id"])
        except Exception:
            return

    try:
        message = await channel.fetch_message(board_info["message_id"])
    except Exception:
        return

    guild = bot.get_guild(guild_id)
    if not guild:
        return

    embed = build_event_board_embed(guild, events_data)
    await message.edit(embed=embed, view=None)

    guild_id_str = str(guild_id)
    events = [e for e in events_data.get("events", {}).values() if str(e.get("guild_id")) == guild_id_str]
    perm_roles = [r for r in events_data.get("permanent_roles", {}).values() if str(r.get("guild_id")) == guild_id_str]
    
    active_emojis = []
    for item in events + perm_roles:
        emo = item.get("emoji")
        if emo and emo not in active_emojis:
            active_emojis.append(emo)

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
