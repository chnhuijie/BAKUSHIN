import discord
import datetime
from zoneinfo import ZoneInfo

UTC = datetime.timezone.utc
JST = ZoneInfo("Asia/Tokyo")

def get_next_timestamp(hour, minute, tz, weekday=None):
    """Calculates the next occurrence of a specific time in a given timezone."""
    now = datetime.datetime.now(tz)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    if target <= now:
        target += datetime.timedelta(days=1)
        
    if weekday is not None:
        while target.weekday() != weekday:
            target += datetime.timedelta(days=1)
            
    return int(target.timestamp())

def build_embed():
    """Builds the URA embed with split UTC/JST logic"""
    # Global (UTC): Reset 15:00 UTC | TT Mon 10:00 UTC
    global_reset = get_next_timestamp(15, 0, UTC)
    global_tt = get_next_timestamp(10, 0, UTC, weekday=0) 
    
    # JP (JST): Reset 05:00 JST | TT Mon 00:00 JST (Midnight Monday)
    jp_reset = get_next_timestamp(5, 0, JST)
    jp_tt = get_next_timestamp(0, 0, JST, weekday=0) 

    embed = discord.Embed(
        title="Official URA Starting Gate!",
        description="BAKUSHIN!",
        color=0xFF77AA # Bakushin Sakura Pink
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
    
    embed.set_footer(text="Class President • BAKUSHIN with all your might!")
    return embed
