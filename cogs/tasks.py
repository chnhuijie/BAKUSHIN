import discord
from discord.ext import tasks, commands
import datetime
import config
from quotes import get_quote
from utils import build_embed, get_next_timestamp, update_boards, UTC, JST

class BakushinTasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.global_dailies_task.start()
        self.jp_dailies_task.start()
        self.global_tt_task.start()
        self.jp_tt_task.start()
        self.event_cleanup_task.start()

    def cog_unload(self):
        self.global_dailies_task.cancel()
        self.jp_dailies_task.cancel()
        self.global_tt_task.cancel()
        self.jp_tt_task.cancel()
        self.event_cleanup_task.cancel()

    async def send_reminder(self, region, quote_type, target_timestamp, title_context, target_guild_id=None):
        conf = config.load_config()
        quote = get_quote(quote_type)
        embed = build_embed()
        
        for guild_id, settings in conf.items():
            if target_guild_id and str(guild_id) != str(target_guild_id):
                continue

            if not isinstance(settings, dict):
                continue
                
            channel_id = settings.get("channel_id")
            if not channel_id: 
                continue
            
            channel = self.bot.get_channel(channel_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except Exception:
                    continue

            role_id = settings.get(f"{region}_role_id")
            if role_id and quote_type == "tt":
                mentions = f"<@&{role_id}>"
            else:
                mentions = ""
            
            if mentions:
                message_content = f"{mentions}\n\n{quote}\n**Time left until {title_context}:** <t:{target_timestamp}:R>"
            else:
                message_content = f"{quote}\n**Time left until {title_context}:** <t:{target_timestamp}:R>"
            
            try:
                await channel.send(
                    content=message_content, 
                    embed=embed,
                    allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False)
                )
            except discord.Forbidden:
                pass
            except Exception as e:
                print(f"Failed to send to guild {guild_id}: {e}")

    # --- EVENT EXPIRATION TASK ---
    @tasks.loop(seconds=60)
    async def event_cleanup_task(self):
        events_data = config.load_events()
        now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        
        dirty = False
        expired_events = []
        affected_guilds = set()

        for event_id, ev in events_data.get("events", {}).items():
            if ev.get("end_time") and now_ts >= ev["end_time"]:
                expired_events.append(event_id)
                affected_guilds.add(ev["guild_id"])

        for event_id in expired_events:
            ev = events_data["events"].pop(event_id)
            dirty = True
            guild = self.bot.get_guild(ev["guild_id"])
            if guild:
                role = guild.get_role(ev["role_id"])
                if role:
                    try:
                        await role.delete(reason=f"Event '{ev['name']}' has completed.")
                    except discord.Forbidden:
                        print(f"[Error] Missing permissions to delete event role {ev['role_id']} in guild {guild.id}.")
                    except Exception as e:
                        print(f"[Error] Failed to delete role {ev['role_id']}: {e}")

        if dirty:
            config.save_events(events_data)
            for guild_id in affected_guilds:
                await update_boards(self.bot, guild_id)

    # --- GLOBAL TASKS (UTC) ---
    @tasks.loop(time=datetime.time(hour=13, minute=0, tzinfo=UTC))
    async def global_dailies_task(self):
        await self.send_reminder("global", "dailies", get_next_timestamp(15, 0, UTC), "Global Dailies Reset")

    @tasks.loop(time=datetime.time(hour=9, minute=0, tzinfo=UTC))
    async def global_tt_task(self):
        if datetime.datetime.now(UTC).weekday() == 0: 
            await self.send_reminder("global", "tt", get_next_timestamp(10, 0, UTC, weekday=0), "Global TT Tallying")

    # --- JP TASKS (JST) ---
    @tasks.loop(time=datetime.time(hour=3, minute=0, tzinfo=JST))
    async def jp_dailies_task(self):
        await self.send_reminder("jp", "dailies", get_next_timestamp(5, 0, JST), "JP Dailies Reset")

    @tasks.loop(time=datetime.time(hour=23, minute=0, tzinfo=JST))
    async def jp_tt_task(self):
        if datetime.datetime.now(JST).weekday() == 6: 
            await self.send_reminder("jp", "tt", get_next_timestamp(0, 0, JST, weekday=0), "JP TT Tallying")

    @global_dailies_task.before_loop
    @jp_dailies_task.before_loop
    @global_tt_task.before_loop
    @jp_tt_task.before_loop
    @event_cleanup_task.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(BakushinTasks(bot))
