import discord
from discord.ext import tasks, commands
import datetime
import config
from quotes import get_quote
from utils import build_embed, get_next_timestamp, UTC, JST

class BakushinTasks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.global_dailies_task.start()
        self.jp_dailies_task.start()
        self.global_tt_task.start()
        self.jp_tt_task.start()

    def cog_unload(self):
        self.global_dailies_task.cancel()
        self.jp_dailies_task.cancel()
        self.global_tt_task.cancel()
        self.jp_tt_task.cancel()

    async def send_reminder(self, region, quote_type, target_timestamp, title_context):
        conf = config.load_config()
        
        # Ensures reminders only send to the designated setup channel
        if not conf.get("channel_id"): return
        channel = self.bot.get_channel(conf["channel_id"])
        if not channel: return

        # Dynamically fetch the correct role based on the region
        role_id = conf.get(f"{region}_role_id")
        mentions = f"<@&{role_id}>" if role_id else ""
        
        quote = get_quote(quote_type)
        
        message_content = f"{mentions}\n\n{quote}\n**Time left until {title_context}:** <t:{target_timestamp}:R>"
        
        # Strictly permits ONLY the exact designated role to be pinged
        await channel.send(
            content=message_content, 
            embed=build_embed(),
            allowed_mentions=discord.AllowedMentions(roles=True, users=False, everyone=False)
        )

    # --- GLOBAL TASKS (UTC) ---
    @tasks.loop(time=datetime.time(hour=13, minute=0, tzinfo=UTC))
    async def global_dailies_task(self):
        await self.send_reminder("global", "dailies", get_next_timestamp(15, 0, UTC), "Global Dailies Reset")

    @tasks.loop(time=datetime.time(hour=9, minute=0, tzinfo=UTC))
    async def global_tt_task(self):
        if datetime.datetime.now(UTC).weekday() == 0: # 0 = Monday
            await self.send_reminder("global", "tt", get_next_timestamp(10, 0, UTC, weekday=0), "Global TT Tallying")

    # --- JP TASKS (JST) ---
    @tasks.loop(time=datetime.time(hour=3, minute=0, tzinfo=JST))
    async def jp_dailies_task(self):
        await self.send_reminder("jp", "dailies", get_next_timestamp(5, 0, JST), "JP Dailies Reset")

    @tasks.loop(time=datetime.time(hour=23, minute=0, tzinfo=JST))
    async def jp_tt_task(self):
        if datetime.datetime.now(JST).weekday() == 6: # 6 = Sunday in JST
            await self.send_reminder("jp", "tt", get_next_timestamp(0, 0, JST, weekday=0), "JP TT Tallying")

    @global_dailies_task.before_loop
    @jp_dailies_task.before_loop
    @global_tt_task.before_loop
    @jp_tt_task.before_loop
    async def before_tasks(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(BakushinTasks(bot))
