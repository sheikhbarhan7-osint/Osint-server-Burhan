import os
import logging
import asyncio
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

# Voice chat libraries
from pyrogram import Client
from pytgcalls import PyTgCalls, StreamType
from pytgcalls.types import Stream
from pytgcalls.types.input_stream import InputAudioStream

import yt_dlp

# ============================================
# 🔒 CONFIGURATION - ENVIRONMENT VARIABLES
# ============================================

BOT_TOKEN = os.environ.get('BOT_TOKEN')
API_ID = int(os.environ.get('API_ID', 0))
API_HASH = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('SESSION_STRING')

# ============================================
# 🔒 AUTHORIZED USERS - HARDCODED (OWNER + ADMIN)
# ============================================
AUTHORIZED_USERS = [
    2062068620,  # 🔴 OWNER (Aap)
    5804726533,  # 🔴 ADMIN (Doosra user)
]

# ============================================
# 🔒 AUTHORIZED GROUPS - SIRF 2 GROUPS
# ============================================
AUTHORIZED_GROUPS = [
    -1001234567890,  # 🔴 GROUP 1 KA ID (CHANGE KAREIN)
    -1009876543210,  # 🔴 GROUP 2 KA ID (CHANGE KAREIN)
]

# ============================================
# LOGGING
# ============================================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================
# Pyrogram Client + PyTgCalls
# ============================================
app = Client(
    "music_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING
)

call = PyTgCalls(app)

# Active voice chats
active_chats = {}

# ============================================
# 🔒 AUTHORIZATION CHECK - USER + GROUP
# ============================================

def is_authorized_user(user_id: int) -> bool:
    """Check if user is authorized."""
    return user_id in AUTHORIZED_USERS

def is_authorized_group(chat_id: int) -> bool:
    """Check if group is authorized."""
    return chat_id in AUTHORIZED_GROUPS

def is_authorized(update: Update) -> tuple:
    """Full authorization check."""
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    # Check user
    if not is_authorized_user(user_id):
        return False, "user"
    
    # Check group
    if update.effective_chat.type in ['group', 'supergroup']:
        if not is_authorized_group(chat_id):
            return False, "group"
    
    return True, "ok"

# ============================================
# YOUTUBE FUNCTIONS
# ============================================

def get_audio_url(youtube_url: str) -> Optional[str]:
    """Get direct audio stream URL from YouTube."""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extractaudio': True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=False)
            if info and 'url' in info:
                return info['url']
            formats = info.get('formats', [])
            for fmt in formats:
                if fmt.get('acodec') != 'none' and fmt.get('vcodec') == 'none':
                    return fmt.get('url')
            return None
    except Exception as e:
        logger.error(f"Audio URL error: {e}")
        return None

def search_youtube(query: str) -> Optional[str]:
    """Search YouTube and return first result URL."""
    try:
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'default_search': 'ytsearch',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f"ytsearch:{query}", download=False)
            if search_results and 'entries' in search_results:
                first_video = search_results['entries'][0]
                return first_video.get('url') or f"https://youtube.com/watch?v={first_video.get('id')}"
            result = ydl.extract_info(query, download=False)
            if result and result.get('id'):
                return f"https://youtube.com/watch?v={result.get('id')}"
            return None
    except Exception as e:
        logger.error(f"Search error: {e}")
        return None

def get_song_info(url: str) -> dict:
    """Get song metadata."""
    try:
        ydl_opts = {'quiet': True, 'no_warnings': True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
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

# ============================================
# VOICE CHAT FUNCTIONS
# ============================================

async def play_in_voice_chat(chat_id: int, audio_url: str, title: str):
    """Play audio in voice chat."""
    try:
        try:
            await call.leave_call(chat_id)
        except:
            pass
        await call.join_call(
            chat_id,
            stream=Stream(
                InputAudioStream(audio_url),
                stream_type=StreamType.LOCAL_STREAM,
            ),
        )
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
    """Stop playing and leave voice chat."""
    try:
        await call.leave_call(chat_id)
        if chat_id in active_chats:
            active_chats[chat_id]['playing'] = False
            active_chats[chat_id]['current'] = None
            active_chats[chat_id]['queue'] = []
        logger.info(f"🛑 Stopped in chat {chat_id}")
        return True
    except Exception as e:
        logger.error(f"Stop error: {e}")
        return False

# ============================================
# BOT COMMANDS
# ============================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Welcome message."""
    user_id = update.effective_user.id
    
    if not is_authorized_user(user_id):
        await update.message.reply_text(
            "❌ **Unauthorized User!**\n\n"
            "This bot is for authorized users only.\n"
            "Contact the bot owner for access."
        )
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
    """Play a song."""
    auth, reason = is_authorized(update)
    if not auth:
        if reason == "user":
            await update.message.reply_text(
                "❌ **Unauthorized User!**\n\n"
                "You are not authorized to use this bot.\n"
                "Contact the bot owner for access."
            )
        elif reason == "group":
            await update.message.reply_text(
                "❌ **Unauthorized Group!**\n\n"
                "This bot is only allowed in authorized groups."
            )
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
        
        keyboard = [
            [InlineKeyboardButton("⏹️ Stop", callback_data="stop")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await msg.edit_text(
            f"▶️ **Now Playing:**\n"
            f"🎵 {title}\n"
            f"⏱️ {duration_str}\n"
            f"📺 {info.get('uploader', 'Unknown')}",
            reply_markup=reply_markup
        )
        
        success = await play_in_voice_chat(chat_id, audio_url, title)
        if not success:
            await msg.edit_text("❌ Failed to join voice chat! Make sure bot has permissions.")
    
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Stop playing."""
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
    """Show queue."""
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
    """Show current song."""
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
    """Handle button callbacks."""
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
    """Help message."""
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
• Only 2 authorized groups
• Only authorized users
"""
    await update.message.reply_text(text)

async def authcheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check authorization status."""
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

# ============================================
# MAIN FUNCTION
# ============================================

async def main():
    """Start the bot."""
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
    print(f"✅ Authorized Users: {AUTHORIZED_USERS}")
    print(f"✅ Authorized Groups: {AUTHORIZED_GROUPS}")
    print("=" * 50)
    
    await application.run_polling()

# ============================================
# 🌐 KEEP ALIVE SERVER FOR RAILWAY (ADD THIS AT THE BOTTOM)
# ============================================
from flask import Flask
from threading import Thread

railway_app = Flask('')

@railway_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    railway_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ============================================
# 🚀 MAIN FUNCTION
# ============================================
if __name__ == "__main__":
    keep_alive()  # 👈 Pehle Flask server start karo
    asyncio.run(main())  # 👈 Phir bot start karo
