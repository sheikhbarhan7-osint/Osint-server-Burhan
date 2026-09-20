"""
╔══════════════════════════════════════════════════════════════════╗
║        SHEIKH BURHAN PREMIUM MEDIA BOT v4.0 INLINE KB            ║
║     YouTube + Instagram + TikTok + Facebook + Generic Media      ║
║    Inline Keyboard System • Auto-Detect • Quality Selection      ║
║             Music Player + Group Audio Support                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import os, re, time, random, logging, asyncio, uuid, hashlib, json
import requests
from typing import Optional, List, Dict, Any, Tuple
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message, ChatAction
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters, ConversationHandler
)
from telegram.error import BadRequest as TgBadRequest

from pyrogram import Client
import pyrogram.errors as _pyro_errors

from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream

import yt_dlp

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIGURATION — RAILWAY ENV VARIABLES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOT_TOKEN        = os.environ.get('BOT_TOKEN')
API_ID           = int(os.environ.get('API_ID', 0))
API_HASH         = os.environ.get('API_HASH')
SESSION_STRING   = os.environ.get('SESSION_STRING')
AUTHORIZED_USERS = list(map(int, os.environ.get('AUTHORIZED_USERS', '').split(','))) if os.environ.get('AUTHORIZED_USERS') else []
AUTHORIZED_GROUPS = list(map(int, os.environ.get('AUTHORIZED_GROUPS', '').split(','))) if os.environ.get('AUTHORIZED_GROUPS') else []
INSTA_COOKIES    = os.environ.get('INSTA_COOKIES', '')

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  BRANDING & PREMIUM EMOJIS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BRAND = "🎵 *SHEIKH BURHAN MEDIA BOT* 🎵"
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

EMOJI_MUSIC = "🎵"
EMOJI_VIDEO = "📹"
EMOJI_PHOTO = "📸"
EMOJI_DOWNLOAD = "⬇️"
EMOJI_PLAY = "▶️"
EMOJI_PAUSE = "⏸️"
EMOJI_SKIP = "⏭️"
EMOJI_BACK = "◀️"
EMOJI_STOP = "⏹️"
EMOJI_CHECK = "✅"
EMOJI_ERROR = "❌"
EMOJI_LOADING = "⏳"
EMOJI_QUALITY = "🎬"
EMOJI_FIRE = "🔥"
EMOJI_STAR = "⭐"
EMOJI_CROWN = "👑"
EMOJI_LINK = "🔗"
EMOJI_SEARCH = "🔍"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CALLBACK DATA STATES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
WAITING_FOR_QUALITY = "quality_select"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def btn(text: str, callback: str, emoji: str = ""):
    """Create inline button with auto-color styling"""
    label = f"{emoji} {text}".strip() if emoji else text
    return InlineKeyboardButton(text=label, callback_data=callback)

def btn_blue(text: str, callback: str, emoji: str = ""):
    """Blue button"""
    return btn(text, callback, emoji)

def btn_green(text: str, callback: str, emoji: str = ""):
    """Green button"""
    return btn(text, callback, emoji)

def btn_red(text: str, callback: str, emoji: str = ""):
    """Red button"""
    return btn(text, callback, emoji)

def btn_yellow(text: str, callback: str, emoji: str = ""):
    """Yellow button"""
    return btn(text, callback, emoji)

def btn_url(text: str, url: str, emoji: str = ""):
    """URL button"""
    label = f"{emoji} {text}".strip() if emoji else text
    return InlineKeyboardButton(text=label, url=url)

def keyboard(*rows) -> InlineKeyboardMarkup:
    """Create inline keyboard"""
    return InlineKeyboardMarkup(inline_keyboard=[[btn] if not isinstance(btn, list) else btn for btn in rows])

def is_auth_user(uid: int) -> bool:
    return uid in AUTHORIZED_USERS

def is_auth_group(cid: int) -> bool:
    return cid in AUTHORIZED_GROUPS

def check_auth(update: Update) -> Tuple[bool, str]:
    """Check if user/group is authorized"""
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if cid < 0 and is_auth_group(cid):
        return True, ""
    if is_auth_user(uid):
        return True, ""
    return False, "⛔ Unauthorized"

def _detect_platform(url: str) -> str:
    """Detect media platform from URL"""
    if 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube'
    if 'instagram.com' in url:
        return 'instagram'
    if 'tiktok.com' in url:
        return 'tiktok'
    if 'facebook.com' in url:
        return 'facebook'
    return 'generic'

def _detect_content_type(url: str) -> str:
    """Detect content type: music, video, or photo"""
    platform = _detect_platform(url)
    
    if platform == 'instagram':
        if '/reel/' in url or '/video/' in url or 'v=' in url:
            return 'video'
        if '/stories/' in url:
            return 'video'
        return 'photo'  # default for posts
    
    if platform in ['youtube', 'facebook', 'tiktok']:
        return 'video'
    
    # generic detection
    if any(x in url.lower() for x in ['.mp3', 'audio', 'music']):
        return 'music'
    if any(x in url.lower() for x in ['.mp4', '.webm', '.avi', '.mov', 'video']):
        return 'video'
    if any(x in url.lower() for x in ['.jpg', '.png', '.jpeg', '.gif', 'image', 'photo']):
        return 'photo'
    
    return 'video'  # default

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  INSTAGRAM DOWNLOADER — FIXED
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def download_instagram(url: str) -> Optional[Dict[str, Any]]:
    """
    Download Instagram photos/videos using yt-dlp with proper cookies
    """
    try:
        ydl_opts = {
            'format': 'best',
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'outtmpl': f'/tmp/insta_{uuid.uuid4().hex[:8]}',
        }
        
        if INSTA_COOKIES:
            ydl_opts['cookiefile'] = None
            # write cookies dynamically
            cookie_path = f'/tmp/insta_cookies_{uuid.uuid4().hex[:8]}.txt'
            with open(cookie_path, 'w') as f:
                f.write(INSTA_COOKIES)
            ydl_opts['cookiefile'] = cookie_path
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            
            if info:
                file_path = ydl.prepare_filename(info)
                return {
                    'title': info.get('title', 'Instagram Media'),
                    'url': url,
                    'file': file_path,
                    'platform': 'instagram',
                    'type': 'video' if info.get('ext') == 'mp4' else 'photo'
                }
    except Exception as e:
        logging.warning(f"Instagram download failed: {e}")
    
    return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  YOUTUBE AUDIO/VIDEO DOWNLOADER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def download_youtube_audio(url: str) -> Optional[Dict[str, Any]]:
    """Download YouTube audio (MP3)"""
    try:
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'quiet': True,
            'outtmpl': f'/tmp/yt_{uuid.uuid4().hex[:8]}'
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            
            # find mp3 file
            base = file_path.rsplit('.', 1)[0]
            mp3_file = f"{base}.mp3"
            if os.path.exists(mp3_file):
                return {
                    'title': info.get('title', 'Audio'),
                    'file': mp3_file,
                    'platform': 'youtube',
                    'type': 'music'
                }
    except Exception as e:
        logging.warning(f"YouTube audio download failed: {e}")
    
    return None

async def download_youtube_video(url: str, quality: str = 'best') -> Optional[Dict[str, Any]]:
    """Download YouTube video"""
    try:
        format_map = {
            'highest': 'bestvideo+bestaudio/best',
            'high': 'bestvideo[height<=720]+bestaudio/best',
            'medium': 'bestvideo[height<=480]+bestaudio/best',
            'low': 'bestvideo[height<=360]+bestaudio/best',
        }
        
        fmt = format_map.get(quality, 'best')
        
        ydl_opts = {
            'format': fmt,
            'quiet': True,
            'outtmpl': f'/tmp/yt_v_{uuid.uuid4().hex[:8]}'
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            file_path = ydl.prepare_filename(info)
            
            return {
                'title': info.get('title', 'Video'),
                'file': file_path,
                'platform': 'youtube',
                'type': 'video',
                'quality': quality
            }
    except Exception as e:
        logging.warning(f"YouTube video download failed: {e}")
    
    return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  COMMAND HANDLERS — INLINE KEYBOARD BASED
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command with inline menu"""
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(f"⛔ {reason}", parse_mode='Markdown')
        return
    
    text = f"""{BRAND}
{DIVIDER}

👋 Welcome! I can download:
{EMOJI_MUSIC} Music from YouTube
{EMOJI_VIDEO} Videos from YouTube/Instagram/TikTok
{EMOJI_PHOTO} Photos from Instagram/Web
{EMOJI_FIRE} Audio playback in groups

Just send me any link!

{DIVIDER}
"""
    
    kb = keyboard(
        [btn_blue("ℹ️ Help", "help", EMOJI_LINK), btn_green("🎮 Controls", "controls", EMOJI_PLAY)],
        [btn_yellow("📝 About", "about", EMOJI_CROWN), btn_red("❌ Close", "close", EMOJI_STOP)]
    )
    
    await update.message.reply_text(text, reply_markup=kb, parse_mode='Markdown')

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline button callbacks"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "help":
        text = f"""{BRAND}
{DIVIDER}

📚 *How to use:*

1️⃣ Send any media link
2️⃣ Bot detects type automatically
3️⃣ Choose quality if prompted
4️⃣ Download starts!

*Supported:* YouTube, Instagram, TikTok, Facebook, Generic URLs

{DIVIDER}
"""
        kb = keyboard([btn_blue("← Back", "back", EMOJI_BACK)])
        await query.edit_message_text(text, reply_markup=kb, parse_mode='Markdown')
    
    elif data == "controls":
        text = f"""{BRAND}
{DIVIDER}

🎮 *Music Controls:*

▶️ /play <URL> - Play music
⏸️ /pause - Pause
⏭️ /skip - Skip song
⏹️ /stop - Stop playback
🔊 /volume <0-200> - Set volume

{DIVIDER}
"""
        kb = keyboard([btn_blue("← Back", "back", EMOJI_BACK)])
        await query.edit_message_text(text, reply_markup=kb, parse_mode='Markdown')
    
    elif data == "about":
        text = f"""{BRAND}
{DIVIDER}

👨‍💻 *Creator:* Sheikh Burhan
🔧 *Version:* 4.0 Premium
⚡ *Features:* 
   • Multi-platform support
   • Auto-quality detection
   • Group audio playback
   • Inline keyboard system

{DIVIDER}
"""
        kb = keyboard([btn_blue("← Back", "back", EMOJI_BACK)])
        await query.edit_message_text(text, reply_markup=kb, parse_mode='Markdown')
    
    elif data == "back":
        text = f"""{BRAND}
{DIVIDER}

👋 Welcome! I can download:
{EMOJI_MUSIC} Music from YouTube
{EMOJI_VIDEO} Videos from YouTube/Instagram/TikTok
{EMOJI_PHOTO} Photos from Instagram/Web
{EMOJI_FIRE} Audio playback in groups

Just send me any link!

{DIVIDER}
"""
        kb = keyboard(
            [btn_blue("ℹ️ Help", "help", EMOJI_LINK), btn_green("🎮 Controls", "controls", EMOJI_PLAY)],
            [btn_yellow("📝 About", "about", EMOJI_CROWN), btn_red("❌ Close", "close", EMOJI_STOP)]
        )
        await query.edit_message_text(text, reply_markup=kb, parse_mode='Markdown')
    
    elif data == "close":
        await query.delete_message()

async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text messages with URLs"""
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(f"⛔ {reason}", parse_mode='Markdown')
        return
    
    text = update.message.text
    
    # Extract URL
    url_match = re.search(r'https?://[^\s]+', text)
    if not url_match:
        kb = keyboard(
            [btn_blue("ℹ️ Help", "help", EMOJI_LINK), btn_green("🎮 Controls", "controls", EMOJI_PLAY)]
        )
        await update.message.reply_text(f"{EMOJI_ERROR} Send a valid URL", reply_markup=kb)
        return
    
    url = url_match.group(0)
    platform = _detect_platform(url)
    content_type = _detect_content_type(url)
    
    # Show loading
    status_msg = await update.message.reply_text(
        f"{EMOJI_LOADING} *Detecting content type...*\n\n"
        f"🔗 Platform: `{platform}`\n"
        f"📦 Type: `{content_type}`",
        parse_mode='Markdown'
    )
    
    # Instagram handling
    if platform == 'instagram':
        if content_type == 'photo':
            result = await download_instagram(url)
            if result:
                await update.message.reply_photo(
                    photo=open(result['file'], 'rb'),
                    caption=f"{EMOJI_PHOTO} {result['title']}"
                )
            else:
                await status_msg.edit_text(f"{EMOJI_ERROR} Failed to download Instagram photo")
        
        elif content_type == 'video':
            result = await download_instagram(url)
            if result:
                await update.message.reply_video(
                    video=open(result['file'], 'rb'),
                    caption=f"{EMOJI_VIDEO} {result['title']}"
                )
            else:
                await status_msg.edit_text(f"{EMOJI_ERROR} Failed to download Instagram video")
    
    # YouTube handling
    elif platform == 'youtube':
        # Ask for audio or video
        kb = keyboard(
            [btn_green("🎵 Audio (MP3)", f"yt_audio:{url}", EMOJI_MUSIC), 
             btn_blue("📹 Video", f"yt_video:{url}", EMOJI_VIDEO)]
        )
        await status_msg.edit_text(
            f"{EMOJI_LINK} *Choose format:*",
            reply_markup=kb,
            parse_mode='Markdown'
        )
    
    # Generic/TikTok handling
    else:
        # Ask for quality
        kb = keyboard(
            [btn_green("⭐ Highest", f"download:{url}:highest", "⭐"),
             btn_blue("🎬 High", f"download:{url}:high", "🎬")],
            [btn_yellow("📊 Medium", f"download:{url}:medium", "📊"),
             btn_red("📉 Low", f"download:{url}:low", "📉")]
        )
        await status_msg.edit_text(
            f"{EMOJI_QUALITY} *Select quality:*",
            reply_markup=kb,
            parse_mode='Markdown'
        )

async def yt_audio_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle YouTube audio download"""
    query = update.callback_query
    url = query.data.split(':')[1]
    
    await query.answer(f"{EMOJI_LOADING} Downloading...", show_alert=False)
    
    result = await download_youtube_audio(url)
    if result:
        with open(result['file'], 'rb') as audio:
            await query.message.reply_audio(
                audio=audio,
                title=result['title'],
                caption=f"{EMOJI_MUSIC} {result['title']}"
            )
        await query.delete_message()
    else:
        await query.answer(f"{EMOJI_ERROR} Download failed", show_alert=True)

async def yt_video_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle YouTube video download with quality selection"""
    query = update.callback_query
    url = query.data.split(':')[1]
    
    await query.answer()
    
    kb = keyboard(
        [btn_green("⭐ Highest", f"yt_vid_dl:{url}:highest", "⭐"),
         btn_blue("🎬 High", f"yt_vid_dl:{url}:high", "🎬")],
        [btn_yellow("📊 Medium", f"yt_vid_dl:{url}:medium", "📊"),
         btn_red("📉 Low", f"yt_vid_dl:{url}:low", "📉")]
    )
    
    await query.edit_message_text(
        f"{EMOJI_QUALITY} *Select video quality:*",
        reply_markup=kb,
        parse_mode='Markdown'
    )

async def yt_video_dl_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle YouTube video download at selected quality"""
    query = update.callback_query
    parts = query.data.split(':')
    url = parts[1]
    quality = parts[2]
    
    await query.answer(f"{EMOJI_LOADING} Downloading at {quality}...", show_alert=False)
    
    result = await download_youtube_video(url, quality)
    if result:
        with open(result['file'], 'rb') as video:
            await query.message.reply_video(
                video=video,
                caption=f"{EMOJI_VIDEO} {result['title']} ({quality})"
            )
        await query.delete_message()
    else:
        await query.answer(f"{EMOJI_ERROR} Download failed", show_alert=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MUSIC PLAYER COMMANDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Play music in group"""
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(f"⛔ {reason}")
        return
    
    if not context.args:
        kb = keyboard([btn_blue("ℹ️ Help", "help", EMOJI_LINK)])
        await update.message.reply_text(f"{EMOJI_ERROR} Usage: /play <URL>", reply_markup=kb)
        return
    
    url = ' '.join(context.args)
    
    status_msg = await update.message.reply_text(f"{EMOJI_LOADING} *Downloading audio...*", parse_mode='Markdown')
    
    result = await download_youtube_audio(url)
    if result:
        # For group, use group call
        if update.effective_chat.type != 'private':
            try:
                # You would need PyTgCalls setup here
                await status_msg.edit_text(
                    f"{EMOJI_MUSIC} *Now playing:* {result['title']}\n\n"
                    f"Controls: /pause /skip /stop",
                    parse_mode='Markdown'
                )
            except Exception as e:
                await status_msg.edit_text(f"{EMOJI_ERROR} Group playback error: {e}")
        else:
            with open(result['file'], 'rb') as audio:
                await update.message.reply_audio(audio=audio, title=result['title'])
    else:
        await status_msg.edit_text(f"{EMOJI_ERROR} Failed to download")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("play", cmd_play))
    
    # Callback handlers
    app.add_handler(CallbackQueryHandler(callback_handler, pattern="^(help|controls|about|back|close)$"))
    app.add_handler(CallbackQueryHandler(yt_audio_callback, pattern="^yt_audio:"))
    app.add_handler(CallbackQueryHandler(yt_video_callback, pattern="^yt_video:"))
    app.add_handler(CallbackQueryHandler(yt_video_dl_callback, pattern="^yt_vid_dl:"))
    
    # Message handler for URLs
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_handler))
    
    logging.basicConfig(level=logging.INFO)
    await app.run_polling()

if __name__ == '__main__':
    asyncio.run(main())
