"""
╔══════════════════════════════════════════════════════════╗
║             SHEIKH BURHAN MUSIC BOT  v4.0               ║
║         + 100% Real Instagram Follower Checker          ║
║         + High-Quality IG Downloader (No Login)         ║
║         + Crash Guard (No more VC crashes)              ║
╚══════════════════════════════════════════════════════════╝
"""

import os, re, time, random, logging, asyncio, uuid, hashlib, json
import requests
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher
from urllib.parse import urlparse

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
    MessageHandler, filters
)
from telegram.error import BadRequest as TgBadRequest

from pyrogram import Client
import pyrogram.errors as _pyro_errors
for _n in ['GroupCallForbidden', 'GroupcallForbidden']:
    if not hasattr(_pyro_errors, _n):
        class _Dummy(Exception): pass
        _Dummy.__name__ = _n
        setattr(_pyro_errors, _n, _Dummy)

from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
try:
    from pytgcalls.types import Update as PyTgUpdate
except ImportError:
    PyTgUpdate = None

import yt_dlp
from instagrapi import Client as InstaClient

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOT_TOKEN      = os.environ.get('BOT_TOKEN')
API_ID         = int(os.environ.get('API_ID', 0))
API_HASH       = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('SESSION_STRING')

# 🔑 Instagram Verification Setup
IG_SESSION_ID = os.environ.get('IG_SESSION_ID', '')
IG_PAGE_USERNAME = "sheikh_barhan"  # <--- YAHAN APNA INSTAGRAM PAGE DAALO (Bina @ ke)
IG_PAGE_URL = f"https://instagram.com/{IG_PAGE_USERNAME}"

AUDD_API_KEY    = os.environ.get('AUDD_API_KEY', 'your_audd_api_key_here')
AUTHORIZED_USERS   = [5804726533, 2062068620]
AUTHORIZED_GROUPS  = [-1001954191240]
BOT_OWNER_USERNAME = "@sheikh_barhan"

VERIFIED_USERS = set()
WAITING_FOR_IG = set()

BRAND   = "🎵 *Sheikh Burhan Music*"
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LOGGING & GLOBALS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

pyrogram_app : Client    = None
calls        : PyTgCalls = None

active_chats    : Dict[int, dict] = {}
pending_download: Dict[str, dict] = {}
_np_tasks       : Dict[int, asyncio.Task] = {}
_messages_to_delete: List[Message] = []

_pool = ThreadPoolExecutor(max_workers=6)

TMP_DIR      = '/tmp/sbmusic'
CACHE_DIR    = '/tmp/sbmusic_cache'
os.makedirs(TMP_DIR,   exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AUTH & HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def check_auth(update: Update) -> tuple:
    uid = update.effective_user.id
    cid = update.effective_chat.id
    
    # Owner is always authorized
    if uid in AUTHORIZED_USERS:
        return True, "ok"
        
    # Check if user verified via Instagram
    if uid not in VERIFIED_USERS:
        return False, "ig_gate"
        
    # Check group auth if applicable
    if update.effective_chat.type in ('group', 'supergroup'):
        if cid not in AUTHORIZED_GROUPS:
            return False, "group"
            
    return True, "ok"

def is_private(update: Update) -> bool:
    return update.effective_chat.type == 'private'

def extract_yt_id(text: str) -> Optional[str]:
    m = re.search(r'(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)([a-zA-Z0-9_\-]{11})', text)
    return m.group(5) if m else None

def dur_str(sec: int) -> str:
    if not sec: return "—"
    h, m = divmod(int(sec), 3600)
    m, s = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def progress_bar(elapsed: float, duration: int, length: int = 14) -> str:
    if not duration: return "░" * length
    ratio  = min(elapsed / duration, 1.0)
    filled = int(ratio * length)
    return "▓" * filled + "░" * (length - filled)

def clean(path: Optional[str]):
    try:
        if path and os.path.exists(path): os.remove(path)
    except Exception: pass

def get_elapsed(chat_id: int) -> float:
    ch = active_chats.get(chat_id, {})
    if not ch.get('start_time'): return 0.0
    elapsed = time.time() - ch['start_time'] - ch.get('total_pause', 0)
    if ch.get('pause_start'): elapsed -= (time.time() - ch['pause_start'])
    return max(0.0, elapsed)

def unauthorized_msg(update: Update, reason: str) -> str:
    uid = update.effective_user.id
    if reason == "ig_gate":
        return f"{BRAND}\n{DIVIDER}\n\n🔒 *Instagram Follow Required!*\n\nTo use this bot, you must follow our Instagram page.\n\nUse /start to verify."
    if reason == "group":
        return f"{BRAND}\n{DIVIDER}\n\n❌ *Group Not Authorized*\n\nContact: {BOT_OWNER_USERNAME}"
    return f"❌ Unauthorized. ID: `{uid}`"

def _new_chat_state() -> dict:
    return {
        'current': None, 'current_file': None, 'playing': False, 'paused': False,
        'queue': [], 'loop': False, 'loop_queue': False,
        'start_time': None, 'pause_start': None, 'total_pause': 0,
        'duration': 0, 'volume': 100, 'np_msg_id': None,
    }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  INSTAGRAM REAL CHECKER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def check_ig_follow(username: str) -> bool:
    if not IG_SESSION_ID: return False
    try:
        cl = InstaClient()
        cl.login_by_sessionid(IG_SESSION_ID)
        username = username.replace("@", "").strip()
        user_id = cl.user_id_from_username(username)
        target_id = cl.user_id_from_username(IG_PAGE_USERNAME)
        return cl.user_follows(user_id, target_id)
    except Exception as e:
        logger.error(f"IG Check Error: {e}")
        return False

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DOWNLOADERS (YT, IG, Images)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _generate_cookies() -> str:
    timestamp = int(time.time())
    cookies = [
        "# Netscape HTTP Cookie File", f"# Generated at {timestamp}",
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tPREF\tf6=40000000&tz=Asia.Calcutta",
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tAPISID\tTZ_hNr0W_8WjDd7M/A-9nIPCdJqzTkk-12",
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tSAPISID\tkKZNwPwDRk3lvBpL/APhgEcr8PvbVl8FhB",
    ]
    cp = os.path.join(TMP_DIR, f"cookies_{timestamp}.txt")
    with open(cp, 'w', encoding='utf-8') as f: f.write("\n".join(cookies) + "\n")
    return cp

def _yt_audio_dl(query_or_url: str, is_url: bool = False) -> Optional[dict]:
    uid = uuid.uuid4().hex
    tmpl = os.path.join(TMP_DIR, f"{uid}.%(ext)s")
    opts = {
        'quiet': True, 'no_warnings': True, 'format': 'bestaudio/best', 'outtmpl': tmpl,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'cookiefile': _generate_cookies()
    }
    target = query_or_url if is_url else f"ytsearch1:{query_or_url}"
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(target, download=True)
            if info and 'entries' in info: info = info['entries'][0]
        mp3 = os.path.join(TMP_DIR, f"{uid}.mp3")
        if os.path.exists(mp3) and os.path.getsize(mp3) > 10_000:
            return {'file': mp3, 'title': (info or {}).get('title', ''), 'artist': (info or {}).get('uploader', ''), 'duration': int((info or {}).get('duration', 0)), 'source': 'youtube'}
    except Exception as e: logger.warning(f"yt_audio failed: {e}")
    return None

def _instagram_dl(url: str) -> Optional[dict]:
    uid = uuid.uuid4().hex
    try:
        res = requests.get(f"https://api.vreden.web.id/api/igdl?url={url}", timeout=15).json()
        if res.get('status') and res.get('result'):
            media_url = res['result'][0]['url']
            ext = '.mp4' if '.mp4' in media_url else '.jpg'
            fp = os.path.join(TMP_DIR, f"ig_{uid}{ext}")
            with requests.get(media_url, stream=True, timeout=30) as r:
                with open(fp, 'wb') as f:
                    for chunk in r.iter_content(8192): f.write(chunk)
            if os.path.getsize(fp) > 10000:
                return {'file': fp, 'title': 'Instagram Video', 'source': 'instagram', 'is_video': ext == '.mp4'}
    except Exception as e: logger.warning(f"IG API failed: {e}")
    return None

def _generic_audio_dl(url: str) -> Optional[dict]: return _instagram_dl(url) if 'instagram.com' in url else _yt_audio_dl(url, is_url=True)
def _generic_video_dl(url: str, quality: str) -> Optional[dict]: return _instagram_dl(url) if 'instagram.com' in url else _yt_audio_dl(url, is_url=True)

async def _run_in_pool(fn, *args): return await asyncio.get_event_loop().run_in_executor(_pool, fn, *args)
async def _delete_later(msg: Message, delay: int = 10):
    await asyncio.sleep(delay)
    try: await msg.delete()
    except: pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  VOICE CHAT LOGIC
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_player_kb(paused: bool = False, loop: bool = False) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("▶️ Resume" if paused else "⏸ Pause", callback_data="pause_resume"),
        InlineKeyboardButton("⏭ Skip", callback_data="skip"),
        InlineKeyboardButton("⏹ Stop", callback_data="stop"),
    ],[InlineKeyboardButton("🔁 Loop ✅" if loop else "🔁 Loop", callback_data="toggle_loop")]])

def np_text(title: str, artist: str, duration: int, elapsed: float, paused: bool, loop: bool, queue_len: int) -> str:
    bar = progress_bar(elapsed, duration)
    status = "⏸ Paused" if paused else "▶️ Now Playing"
    txt = f"{BRAND}\n{DIVIDER}\n\n{status}\n\n🎵 *{title}*\n"
    if artist: txt += f"🎤 {artist}\n"
    txt += f"\n`{dur_str(int(elapsed))}` {bar} `{dur_str(duration)}`\n"
    if queue_len: txt += f"\n📋 *{queue_len} song(s) in queue*\n"
    return txt

async def vc_play_item(chat_id: int, item: dict, bot, seek_sec: int = 0):
    if not calls: return False, "Userbot offline (Invalid SESSION_STRING)."
    ch = active_chats.setdefault(chat_id, _new_chat_state())
    try:
        await calls.play(chat_id, MediaStream(item['file']))
        ch.update({'current': item['title'], 'current_file': item['file'], 'playing': True, 'paused': False, 'start_time': time.time(), 'duration': item.get('duration', 0)})
        return True, ''
    except Exception as e:
        ch['playing'] = False
        return False, str(e)

async def vc_stop(chat_id: int):
    if calls:
        try: await calls.leave_group_call(chat_id)
        except: pass
    active_chats[chat_id] = _new_chat_state()

async def vc_pause(chat_id: int) -> bool:
    if not calls: return False
    try: await calls.pause(chat_id); active_chats[chat_id]['paused'] = True; return True
    except: return False

async def vc_resume(chat_id: int) -> bool:
    if not calls: return False
    try: await calls.resume(chat_id); active_chats[chat_id]['paused'] = False; return True
    except: return False

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  COMMAND HANDLERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name or "Friend"
    
    if uid in AUTHORIZED_USERS or uid in VERIFIED_USERS:
        await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\nWelcome *{name}* 👋\n\n✅ You are verified. Use /help to see commands.", parse_mode='Markdown')
        return

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📸 Follow on Instagram", url=IG_PAGE_URL)],
        [InlineKeyboardButton("✅ I have followed (Verify)", callback_data="verify_ig")]
    ])
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"Welcome *{name}*!\n\n"
        f"🔒 *Bot Access Locked.*\n"
        f"You must follow our Instagram page to use this bot.\n\n"
        f"1️⃣ Click the button below to follow.\n"
        f"2️⃣ Come back and click Verify.",
        parse_mode='Markdown',
        reply_markup=kb
    )

async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth: return await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
    if not context.args: return await update.message.reply_text("❌ Usage: `/play <song>`", parse_mode='Markdown')
    
    query = ' '.join(context.args).strip()
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text(f"🔍 Searching: *{query}*...", parse_mode='Markdown')
    result = await _run_in_pool(_generic_audio_dl, query)
    
    if not result: return await msg.edit_text("❌ Song not found.")
    
    if is_private(update):
        with open(result['file'], 'rb') as af:
            await context.bot.send_audio(chat_id, audio=af, title=result['title'], performer=result['artist'])
        await msg.delete()
        clean(result['file'])
    else:
        ch = active_chats.setdefault(chat_id, _new_chat_state())
        if ch.get('playing'): await vc_stop(chat_id)
        ok, err = await vc_play_item(chat_id, result, context.bot)
        if ok:
            await msg.edit_text(np_text(result['title'], result['artist'], result['duration'], 0, False, False, 0), parse_mode='Markdown', reply_markup=make_player_kb())
        else:
            await msg.edit_text(f"⚠️ VC Error: {err}. Sending as file.\n")
            with open(result['file'], 'rb') as af:
                await context.bot.send_audio(chat_id, audio=af, title=result['title'], performer=result['artist'])
            clean(result['file'])

async def cmd_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth: return await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
    if not context.args: return await update.message.reply_text("❌ Usage: `/download <link>`", parse_mode='Markdown')
    
    url = context.args[0]
    msg = await update.message.reply_text(f"⏳ Downloading...")
    result = await _run_in_pool(_generic_video_dl, url, 'best')
    
    if not result: return await msg.edit_text("❌ Download failed. Link private or unsupported.")
    
    try:
        with open(result['file'], 'rb') as f:
            if result.get('is_video'):
                await context.bot.send_video(update.effective_chat.id, video=f, caption=f"🎬 {result['title']}")
            else:
                await context.bot.send_audio(update.effective_chat.id, audio=f, title=result['title'])
        await msg.delete()
    except Exception as e:
        await msg.edit_text(f"❌ Error sending: {e}")
    finally:
        clean(result['file'])

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await vc_stop(update.effective_chat.id)
    msg = await update.message.reply_text("⏹ Stopped & Queue Cleared.")
    asyncio.create_task(_delete_later(msg, 10))

async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await vc_stop(update.effective_chat.id)
    await update.message.reply_text("⏭ Skipped.")

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok = await vc_pause(update.effective_chat.id)
    await update.message.reply_text("⏸ Paused." if ok else "❌ Nothing to pause.")

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ok = await vc_resume(update.effective_chat.id)
    await update.message.reply_text("▶️ Resumed." if ok else "❌ Nothing to resume.")

async def cmd_current(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ch = active_chats.get(update.effective_chat.id, {})
    if not ch.get('current'): return await update.message.reply_text("❌ Nothing is playing.")
    await update.message.reply_text(np_text(ch['current'], ch.get('artist',''), ch.get('duration',0), get_elapsed(update.effective_chat.id), ch.get('paused',False), ch.get('loop',False), 0), parse_mode='Markdown', reply_markup=make_player_kb(ch.get('paused',False), ch.get('loop',False)))

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"📋 *Commands:*\n"
        f"• /play `<song/URL>` — Play audio\n"
        f"• /download `<URL>` — Download Video/Reels (YT/IG)\n"
        f"• /stop, /skip, /pause, /resume, /current\n"
        f"• /ping — Check status\n",
        parse_mode='Markdown'
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MESSAGE & CALLBACK HANDLERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "verify_ig":
        WAITING_FOR_IG.add(update.effective_user.id)
        await q.edit_message_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"📝 *Please send your Instagram Username.*\n\n"
            f"Format: `@your_username` or `your_username`\n\n"
            f"Our bot will check if you follow `{IG_PAGE_USERNAME}`.\n"
            f"⚠️ _Do not send a link, just the username._",
            parse_mode='Markdown'
        )
    elif q.data == "stop":
        await vc_stop(update.effective_chat.id)
        await q.edit_message_text("⏹ Stopped.")
    elif q.data == "pause_resume":
        ch = active_chats.get(update.effective_chat.id, {})
        if ch.get('paused'): await vc_resume(update.effective_chat.id)
        else: await vc_pause(update.effective_chat.id)
        await q.edit_message_reply_markup(reply_markup=make_player_kb(not ch.get('paused'), ch.get('loop',False)))

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text.strip()
    
    if uid in WAITING_FOR_IG:
        WAITING_FOR_IG.remove(uid)
        msg = await update.message.reply_text("🔍 Checking Instagram... Please wait.")
        is_following = await _run_in_pool(check_ig_follow, text)
        
        if is_following:
            VERIFIED_USERS.add(uid)
            await msg.edit_text(
                f"{BRAND}\n{DIVIDER}\n\n"
                f"✅ *Verification Successful!*\n\n"
                f"You are now following `{IG_PAGE_USERNAME}`.\n"
                f"Access Granted! Send /help to see commands.",
                parse_mode='Markdown'
            )
        else:
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("📸 Follow Now", url=IG_PAGE_URL)]])
            await msg.edit_text(
                f"{BRAND}\n{DIVIDER}\n\n"
                f"❌ *Verification Failed!*\n\n"
                f"Our bot checked `{text}` but you are NOT following `{IG_PAGE_USERNAME}`.\n\n"
                f"1. Make sure your account is PUBLIC.\n"
                f"2. Follow the page.\n"
                f"3. Send /start again to retry.",
                parse_mode='Markdown',
                reply_markup=kb
            )
        return

    if text.startswith('http'):
        class FakeContext:
            def __init__(self, bot):
                self.bot = bot
                self.args = [text]
        await cmd_download(update, FakeContext(context.bot))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def main():
    global pyrogram_app, calls
    try:
        pyrogram_app = Client("sbmusic", api_id=API_ID, api_hash=API_HASH, session_string=SESSION_STRING)
        calls = PyTgCalls(pyrogram_app)
        await pyrogram_app.start()
        await calls.start()
        print("✅ Userbot started (Voice Chat enabled)")
    except Exception as e:
        print(f"⚠️ Userbot failed: {e}\nBot will run without Voice Chat.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("play", cmd_play))
    app.add_handler(CommandHandler(["download", "dl"], cmd_download))
    app.add_handler(CommandHandler("stop", cmd_stop))
    app.add_handler(CommandHandler("skip", cmd_skip))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("current", cmd_current))
    app.add_handler(CommandHandler("help", cmd_help))
    
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    print("━" * 50)
    print("  BOT STARTED WITH 100% REAL IG CHECKER")
    print("━" * 50)

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    
    stop_event = asyncio.Event()
    try: await stop_event.wait()
    except: pass
    finally:
        await app.updater.stop(); await app.stop()

if __name__ == "__main__":
    asyncio.run(main())
