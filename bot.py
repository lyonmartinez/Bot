import os
import discord
from discord.ext import commands
import json
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS
import html2text
import re
from urllib.parse import urljoin, urlparse

CONFIG_FILE = "config.json"
DEFAULT_CONFIG_FILE = "config.example.json"

# Load config
def load_config():
    """
    Thứ tự ưu tiên:
    1. config.example.json (default).
    2. Ghi đè bằng config.json nếu file này tồn tại (local).
    3. Ghi đè tiếp bằng biến môi trường nếu có (trên Railway).
    """
    config_data = {}

    # 1) Load config mặc định
    try:
        with open(DEFAULT_CONFIG_FILE, "r") as f:
            config_data.update(json.load(f))
    except FileNotFoundError:
        # Không có file example cũng không sao, sẽ fallback sang env
        pass

    # 2) Ghi đè bằng config.json nếu tồn tại
    try:
        with open(CONFIG_FILE, "r") as f:
            config_data.update(json.load(f))
    except FileNotFoundError:
        print("[WARN] Không tìm thấy config.json, đang dùng config.example.json / biến môi trường.")

    # 3) Ghi đè bằng biến môi trường (tuỳ chọn)
    model_env = os.getenv("OPENAI_MODEL")
    api_base_env = os.getenv("OPENAI_API_BASE")
    system_context_env = os.getenv("SYSTEM_CONTEXT")
    error_message_env = os.getenv("ERROR_MESSAGE")

    if model_env:
        config_data["model"] = model_env
    if api_base_env:
        config_data["api_base"] = api_base_env
    if system_context_env:
        config_data["system_context"] = system_context_env
    if error_message_env:
        config_data["error_message"] = error_message_env

    return config_data

def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)

# Web search and content extraction functions
async def search_web(query: str, max_results: int = 5):
    """
    Tìm kiếm trên web và trả về danh sách các URL và tiêu đề
    """
    try:
        with DDGS() as ddgs:
            results = []
            for result in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": result.get("title", ""),
                    "url": result.get("href", ""),
                    "snippet": result.get("body", "")
                })
            return results
    except Exception as e:
        print(f"[SEARCH ERROR] {e}")
        return []

async def fetch_web_content(url: str, max_length: int = 5000):
    """
    Lấy và sàng lọc nội dung từ một trang web
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return None
                html = await response.text()
                
        soup = BeautifulSoup(html, 'lxml')
        
        # Xóa các thẻ script, style, và các phần không cần thiết
        for script in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
            script.decompose()
        
        # Lấy nội dung chính từ các thẻ phổ biến
        main_content = ""
        
        # Ưu tiên các thẻ article, main
        article = soup.find("article") or soup.find("main")
        if article:
            main_content = article.get_text(separator=" ", strip=True)
        else:
            # Nếu không có article/main, lấy từ body
            body = soup.find("body")
            if body:
                main_content = body.get_text(separator=" ", strip=True)
        
        # Làm sạch text: loại bỏ khoảng trắng thừa
        main_content = re.sub(r'\s+', ' ', main_content)
        main_content = main_content.strip()
        
        # Giới hạn độ dài
        if len(main_content) > max_length:
            main_content = main_content[:max_length] + "..."
        
        return main_content if main_content else None
        
    except Exception as e:
        print(f"[FETCH ERROR] {url}: {e}")
        return None

async def get_web_info(query: str, max_sources: int = 3):
    """
    Tìm kiếm và lấy thông tin từ web để trả lời câu hỏi
    Trả về một đoạn text tổng hợp từ các nguồn
    """
    # Tìm kiếm trên web
    search_results = await search_web(query, max_results=max_sources)
    
    if not search_results:
        return None
    
    # Lấy nội dung từ các trang web
    web_contents = []
    for result in search_results[:max_sources]:
        url = result["url"]
        title = result["title"]
        snippet = result["snippet"]
        
        # Lấy nội dung chi tiết từ trang web
        content = await fetch_web_content(url, max_length=3000)
        
        if content:
            web_contents.append({
                "title": title,
                "url": url,
                "content": content
            })
        elif snippet:
            # Nếu không lấy được content, dùng snippet
            web_contents.append({
                "title": title,
                "url": url,
                "content": snippet
            })
    
    if not web_contents:
        return None
    
    # Tổng hợp thông tin từ các nguồn
    info_text = "Thông tin từ web:\n\n"
    for i, source in enumerate(web_contents, 1):
        info_text += f"[Nguồn {i}] {source['title']}\n"
        info_text += f"URL: {source['url']}\n"
        info_text += f"Nội dung: {source['content']}\n\n"
    
    return info_text

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
                "> **`-aisearch <từ khóa>`** - tìm kiếm thông tin trên web\n" \
                "> **`-aihelp`** - hiển thị tin nhắn trợ giúp này\n\n" \
                "🌐 **Tính năng Web Search:**\n" \
                "> Bot tự động tìm kiếm web khi bạn hỏi về thông tin mới nhất, tin tức, giá cả, địa chỉ, hoặc các chủ đề cần cập nhật từ internet."
    await ctx.send(help_text)

@bot.command(name="search")
async def manual_search(ctx, *, query: str = None):
    """
    Tìm kiếm thủ công trên web
    """
    if not query:
        await ctx.send("⚠️ | Vui lòng nhập từ khóa tìm kiếm. Ví dụ: `-aisearch giá iPhone 15`")
        return
    
    await ctx.channel.typing()
    
    try:
        web_info = await get_web_info(query, max_sources=5)
        
        if web_info:
            # Giới hạn độ dài để tránh vượt quá giới hạn Discord (2000 ký tự)
            if len(web_info) > 1900:
                web_info = web_info[:1900] + "..."
            
            await ctx.send(f"🔍 **Kết quả tìm kiếm cho: {query}**\n\n{web_info}")
        else:
            await ctx.send(f"❌ | Không tìm thấy thông tin về: {query}")
    except Exception as e:
        await ctx.send("⚠️ | Lỗi khi tìm kiếm web. Vui lòng thử lại sau.")
        print(f"[SEARCH ERROR] {e}")

@bot.command(name="clearmemory")
async def clear_memory(ctx):
    user_id = str(ctx.author.id)
    if user_id in user_memory:
        del user_memory[user_id]
    await ctx.send("🧠 |Bộ nhớ của bạn đã được xóa!")

def should_search_web(message_content: str) -> bool:
    """
    Phát hiện khi nào cần tìm kiếm web dựa trên nội dung tin nhắn
    """
    # Các từ khóa gợi ý cần tìm kiếm web
    search_keywords = [
        "mới nhất", "hiện tại", "hôm nay", "gần đây", "2024", "2025",
        "tin tức", "news", "thông tin về", "tìm hiểu về", "là gì",
        "giá", "giá cả", "giá trị", "price", "cost",
        "địa chỉ", "address", "ở đâu", "where",
        "cách", "how to", "hướng dẫn", "tutorial",
        "so sánh", "compare", "khác nhau", "difference",
        "review", "đánh giá", "ý kiến", "opinion"
    ]
    
    message_lower = message_content.lower()
    
    # Kiểm tra xem có chứa từ khóa tìm kiếm không
    for keyword in search_keywords:
        if keyword in message_lower:
            return True
    
    # Kiểm tra xem có chứa URL không (người dùng muốn bot đọc trang web)
    if "http://" in message_lower or "https://" in message_lower or "www." in message_lower:
        return True
    
    return False

def extract_urls(message_content: str) -> list:
    """
    Trích xuất URL từ nội dung tin nhắn
    """
    url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+|www\.[^\s<>"{}|\\^`\[\]]+'
    urls = re.findall(url_pattern, message_content)
    return urls

def extract_search_query(message_content: str) -> str:
    """
    Trích xuất query để tìm kiếm từ nội dung tin nhắn
    """
    # Loại bỏ các từ không cần thiết và lấy phần chính
    query = message_content.strip()
    
    # Nếu có URL, loại bỏ URL khỏi query
    urls = extract_urls(query)
    if urls:
        for url in urls:
            query = query.replace(url, "").strip()
        # Nếu chỉ có URL và không có gì khác, return None để fetch URL trực tiếp
        if not query:
            return None
    
    return query if query else None

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
    
    user_message = message.content
    web_info = None
    
    # Kiểm tra xem có URL trực tiếp không
    urls = extract_urls(user_message)
    if urls:
        # Nếu có URL, fetch nội dung trực tiếp từ URL
        await message.channel.typing()
        url_contents = []
        for url in urls[:2]:  # Giới hạn 2 URL để tránh quá tải
            content = await fetch_web_content(url, max_length=3000)
            if content:
                url_contents.append(f"[Nội dung từ {url}]\n{content}")
        
        if url_contents:
            web_info = "\n\n".join(url_contents)
            user_message = f"{user_message}\n\n{web_info}"
    
    # Kiểm tra xem có cần tìm kiếm web không (nếu chưa có web_info từ URL)
    elif should_search_web(user_message):
        search_query = extract_search_query(user_message)
        if search_query:
            # Thông báo đang tìm kiếm
            await message.channel.typing()
            web_info = await get_web_info(search_query, max_sources=3)
            
            # Nếu có thông tin từ web, thêm vào tin nhắn
            if web_info:
                user_message = f"{user_message}\n\n{web_info}"
    
    user_memory[user_id].append({"role": "user", "content": user_message})

    # Cải thiện system context với khả năng web search
    enhanced_system_context = config["system_context"] + (
        "\n\nBạn có khả năng truy cập và đọc thông tin từ web. "
        "Khi người dùng hỏi về thông tin mới nhất, tin tức, hoặc cần thông tin chi tiết từ web, "
        "bạn sẽ nhận được thông tin từ các nguồn web đã được sàng lọc. "
        "Hãy sử dụng thông tin này để trả lời chính xác và cập nhật nhất. "
        "Nếu có nhiều nguồn, hãy tổng hợp và so sánh thông tin từ các nguồn khác nhau. "
        "Luôn trích dẫn nguồn khi có thể."
    )
    
    messages = [{"role": "system", "content": enhanced_system_context}] + user_memory[user_id]

    try:
        async with aiohttp.ClientSession() as session:
            # Ưu tiên lấy API key từ biến môi trường nếu có, ngược lại dùng trong config.json
            api_key = os.getenv("OPENAI_API_KEY", config.get("api_key"))
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