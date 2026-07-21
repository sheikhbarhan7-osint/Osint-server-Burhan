import os
import logging
import asyncio
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

from pyrogram import Client
from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream

import yt_dlp

BOT_TOKEN = os.environ.get('BOT_TOKEN')
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('SESSION_STRING')

AUTHORIZED_USERS = [
    5804726533,
    2062068620,
]

AUTHORIZED_GROUPS = [
    -1001954191240,
]

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app: Client = None
call: PyTgCalls = None
active_chats = {}

COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')

def is_authorized_user(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS

def is_authorized_group(chat_id: int) -> bool:
    return chat_id in AUTHORIZED_GROUPS

def is_authorized(update: Update) -> tuple:
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not is_authorized_user(user_id):
        return False, "user"
    if update.effective_chat.type in ['group', 'supergroup']:
        if not is_authorized_group(chat_id):
            return False, "group"
    return True, "ok"

def get_ydl_base_opts() -> dict:
    """Base yt-dlp options with cookies and network fixes."""
    opts = {
        'quiet': True,
        'no_warnings': True,
        'nocheckcertificate': True,
        'source_address': '0.0.0.0',
        'geo_bypass': True,
    }
    if os.path.exists(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE
    return opts

def search_youtube(query: str) -> Optional[str]:
    """Search YouTube and return first result URL."""
    try:
        opts = get_ydl_base_opts()
        opts.update({
            'extract_flat': True,
            'default_search': 'ytsearch',
        })
        with yt_dlp.YoutubeDL(opts) as ydl:
            results = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if results and 'entries' in results and results['entries']:
                entry = results['entries'][0]
                video_id = entry.get('id')
                if video_id:
                    return f"https://www.youtube.com/watch?v={video_id}"
        return None
    except Exception as e:
        logger.error(f"Search error: {e}")
        return None

def get_audio_url(youtube_url: str) -> Optional[str]:
    """Get best audio stream URL from YouTube."""
    try:
        opts = get_ydl_base_opts()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            if not info:
                return None

            formats = info.get('formats', [])

            # 1. Pure audio formats (no video)
            audio_only = [
                f for f in formats
                if f.get('acodec') not in ('none', None)
                and f.get('vcodec') in ('none', None)
                and f.get('url')
            ]
            if audio_only:
                best = sorted(audio_only, key=lambda x: x.get('abr') or 0, reverse=True)
                return best[0]['url']

            # 2. Any format with audio
            with_audio = [
                f for f in formats
                if f.get('acodec') not in ('none', None)
                and f.get('url')
            ]
            if with_audio:
                return with_audio[-1]['url']

            # 3. Last resort — any URL
            for f in reversed(formats):
                if f.get('url'):
                    return f['url']

            return None
    except Exception as e:
        logger.error(f"Audio URL error: {e}")
        return None

def get_song_info(url: str) -> dict:
    """Get song metadata."""
    try:
        opts = get_ydl_base_opts()
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title': info.get('title', 'Unknown'),
                'duration': info.get('duration', 0),
                'url': url,
                'thumbnail': info.get('thumbnail', ''),
                'uploader': info.get('uploader', 'Unknown'),
            }
    except Exception as e:
        logger.error(f"Info error: {e}")
        return {'title': 'Unknown', 'duration': 0, 'url': url}

async def play_in_voice_chat(chat_id: int, audio_url: str, title: str):
    try:
        try:
            await call.leave_group_call(chat_id)
        except Exception:
            pass
        await call.play(chat_id, MediaStream(audio_url))
        if chat_id not in active_chats:
            active_chats[chat_id] = {'queue': [], 'current': None, 'playing': False}
        active_chats[chat_id]['current'] = {'title': title, 'url': audio_url}
        active_chats[chat_id]['playing'] = True
        logger.info(f"✅ Playing in chat {chat_id}: {title}")
        return True
    except Exception as e:
        logger.error(f"Play error: {e}")
        return False

async def stop_voice_chat(chat_id: int):
    try:
        await call.leave_group_call(chat_id)
        if chat_id in active_chats:
            active_chats[chat_id]['playing'] = False
            active_chats[chat_id]['current'] = None
            active_chats[chat_id]['queue'] = []
        logger.info(f"🛑 Stopped in chat {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Stop error: {e}")
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_authorized_user(user_id):
        await update.message.reply_text("❌ **Unauthorized User!**\n\nThis bot is for authorized users only.")
        return
    text = """
🎵 **Private Music Bot**

**Commands:**
/play <song> - Play a song
/stop - Stop and leave
/queue - Show queue
/current - Show current song
/help - Show this message
/authcheck - Check authorization status

🔒 **Private Bot**
- Only authorized users can use
- Only authorized groups
"""
    await update.message.reply_text(text)

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = is_authorized(update)
    if not auth:
        if reason == "user":
            await update.message.reply_text("❌ **Unauthorized User!**\n\nContact the bot owner for access.")
        elif reason == "group":
            await update.message.reply_text("❌ **Unauthorized Group!**\n\nThis bot is only allowed in authorized groups.")
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /play <song_name>")
        return
    query = ' '.join(context.args)
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text(f"🔍 Searching: `{query}`...")
    try:
        song_url = search_youtube(query)
        if not song_url:
            await msg.edit_text("❌ No results found!")
            return
        info = get_song_info(song_url)
        title = info.get('title', 'Unknown')
        duration = info.get('duration', 0)
        duration_str = f"{duration//60}:{duration%60:02d}" if duration else "Live"
        audio_url = get_audio_url(song_url)
        if not audio_url:
            await msg.edit_text("❌ Could not get audio stream!")
            return
        keyboard = [[InlineKeyboardButton("⏹️ Stop", callback_data="stop")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await msg.edit_text(
            f"▶️ **Now Playing:**\n🎵 {title}\n⏱️ {duration_str}\n📺 {info.get('uploader', 'Unknown')}",
            reply_markup=reply_markup
        )
        success = await play_in_voice_chat(chat_id, audio_url, title)
        if not success:
            await msg.edit_text("❌ Failed to join voice chat! Make sure bot has permissions.")
    except Exception as e:
        logger.error(f"play_command error: {e}")
        await msg.edit_text(f"❌ Error: {str(e)}")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = is_authorized(update)
    if not auth:
        await update.message.reply_text("❌ Unauthorized!")
        return
    chat_id = update.effective_chat.id
    success = await stop_voice_chat(chat_id)
    if success:
        await update.message.reply_text("⏹️ Stopped playing and left voice chat!")
    else:
        await update.message.reply_text("❌ Failed to stop!")

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = is_authorized(update)
    if not auth:
        await update.message.reply_text("❌ Unauthorized!")
        return
    chat_id = update.effective_chat.id
    if chat_id not in active_chats or not active_chats[chat_id]['queue']:
        await update.message.reply_text("📭 Queue is empty!")
        return
    queue = active_chats[chat_id]['queue']
    text = "📋 **Current Queue:**\n\n"
    for i, song in enumerate(queue, 1):
        text += f"{i}. {song.get('title', 'Unknown')}\n"
    await update.message.reply_text(text)

async def current_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = is_authorized(update)
    if not auth:
        await update.message.reply_text("❌ Unauthorized!")
        return
    chat_id = update.effective_chat.id
    if chat_id not in active_chats or not active_chats[chat_id]['current']:
        await update.message.reply_text("❌ Nothing is playing right now!")
        return
    current = active_chats[chat_id]['current']
    await update.message.reply_text(f"▶️ **Now Playing:**\n🎵 {current.get('title', 'Unknown')}")

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    auth, reason = is_authorized(update)
    if not auth:
        await query.edit_message_text("❌ Unauthorized!")
        return
    chat_id = update.effective_chat.id
    if query.data == "stop":
        await stop_voice_chat(chat_id)
        await query.edit_message_text("⏹️ Stopped!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = is_authorized(update)
    if not auth:
        await update.message.reply_text("❌ Unauthorized!")
        return
    text = """
🎵 **Private Music Bot Commands:**

/play <song> - Play a song
/stop - Stop and leave
/queue - Show queue
/current - Show current song
/authcheck - Check authorization status
/help - Show this message

🔒 **Private Bot**
• Only authorized groups
• Only authorized users
"""
    await update.message.reply_text(text)

async def authcheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_status = "✅ Authorized" if is_authorized_user(user_id) else "❌ Unauthorized"
    group_status = "✅ Authorized" if is_authorized_group(chat_id) else "❌ Unauthorized"
    text = f"""
🔒 **Authorization Status:**

👤 **User:** {user_status}
💬 **Group:** {group_status}

**Authorized Users:** {len(AUTHORIZED_USERS)} users
**Authorized Groups:** {len(AUTHORIZED_GROUPS)} groups
"""
    await update.message.reply_text(text)

async def main():
    global app, call
    app = Client(
        "music_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        session_string=SESSION_STRING
    )
    call = PyTgCalls(app)
    await app.start()
    await call.start()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("play", play_command))
    application.add_handler(CommandHandler("stop", stop_command))
    application.add_handler(CommandHandler("queue", queue_command))
    application.add_handler(CommandHandler("current", current_command))
    application.add_handler(CommandHandler("authcheck", authcheck_command))
    application.add_handler(CallbackQueryHandler(callback_handler))
    print("=" * 50)
    print("🎵 PRIVATE MUSIC BOT STARTED")
    print("=" * 50)
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await call.stop()
        await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
