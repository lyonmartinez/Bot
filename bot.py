import os
import discord
from discord.ext import commands
import json
import asyncio
import aiohttp

CONFIG_FILE = "config.json"

# Load config
def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

config = load_config()

# Bot setup
intents = discord.Intents.default()
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix="-ai", intents=intents, help_command=None)
user_memory = {}
active_channel_id = config.get("channel_id")  # Load saved channel

@bot.event
async def on_ready():
    print(f"Liên hệ 1 Đời Liêm Khiết nhá!!")
    print(f"Đăng nhập thành công với {bot.user}!!")

    await bot.change_presence(
        activity=discord.Activity(type=discord.ActivityType.watching, name="BOT Patrick"),
        status=discord.Status.idle
    )

@bot.command()
@commands.has_permissions(administrator=True)
async def setup(ctx):
    global active_channel_id
    active_channel_id = ctx.channel.id
    config["channel_id"] = active_channel_id
    save_config(config)
    await ctx.send(f"✅ |Đây hiện là kênh hoạt động để trò chuyện với bot: <#{active_channel_id}>")

@bot.command(name="unsetup")
@commands.has_permissions(administrator=True)
async def unsetup(ctx):
    global active_channel_id
    if "channel_id" in config:
        removed_channel = config.pop("channel_id", None)
        save_config(config)
        active_channel_id = None
        await ctx.send(f"✅ |Đã xóa thiết lập kênh: <#{removed_channel}>")
    else:
        await ctx.send("⚠️ |Không tìm thấy kênh thiết lập nào để xóa.")

@bot.command(name="help")
async def custom_help(ctx):
    help_text = "🤖 __**BOT PATRICK SET UP:**__\n" \
                "> **`-aisetup`** - thiết lập bot trong kênh\n" \
                "> **`-aiunsetup`** - xóa kênh thiết lập\n" \
                "> **`-aiclearmemory`** - xoá bộ nhớ của BOT PATRICK\n" \
                "> **`-aihelp`** - hiển thị tin nhắn trợ giúp này"
    await ctx.send(help_text)

@bot.command(name="clearmemory")
async def clear_memory(ctx):
    user_id = str(ctx.author.id)
    if user_id in user_memory:
        del user_memory[user_id]
    await ctx.send("🧠 |Bộ nhớ của bạn đã được xóa!")

@bot.event
async def on_message(message):
    global active_channel_id

    if message.author.bot:
        return

    await bot.process_commands(message)

    # Only respond in the designated channel
    if active_channel_id is None or message.channel.id != active_channel_id:
        return

    if message.content.startswith("-ai"):
        return

    await message.channel.typing()

    user_id = str(message.author.id)
    user_memory.setdefault(user_id, [])
    user_memory[user_id].append({"role": "user", "content": message.content})

    messages = [{"role": "system", "content": config["system_context"]}] + user_memory[user_id]

    try:
        async with aiohttp.ClientSession() as session:
            # Ưu tiên lấy API key từ biến môi trường nếu có, ngược lại dùng trong config.json
            api_key = os.getenv("OPENROUTER_API_KEY", config.get("api_key"))
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": config["model"],
                "messages": messages
            }
            async with session.post(f"{config['api_base']}/chat/completions", headers=headers, json=payload) as resp:
                if resp.status != 200:
                    error_detail = await resp.text()
                    print(f"[API ERROR] {resp.status}: {error_detail}")
                    await message.reply(config.get("error_message", "❌ | Lỗi API, vui lòng thử lại sau."))
                    return
                response = await resp.json()
                reply = response["choices"][0]["message"]["content"]
                user_memory[user_id].append({"role": "assistant", "content": reply})
                await message.reply(reply)
    except Exception as e:
        await message.reply(config.get("error_message", "⚠️ | Lỗi nội bộ đã xảy ra."))
        print(f"[ERROR] {e}")

# Lấy Discord bot token từ biến môi trường, KHÔNG hard-code trong code
discord_token = os.getenv("DISCORD_TOKEN")
if not discord_token:
    raise ValueError("DISCORD_TOKEN không được tìm thấy trong biến môi trường.")

bot.run(discord_token)