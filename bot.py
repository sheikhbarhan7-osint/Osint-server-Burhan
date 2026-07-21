import os
import logging
import asyncio
import uuid
import requests
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler

from pyrogram import Client
import pyrogram.errors as _pyro_errors
for _n in ['GroupCallForbidden', 'GroupcallForbidden']:
    if not hasattr(_pyro_errors, _n):
        class _E(Exception): pass
        _E.__name__ = _n
        setattr(_pyro_errors, _n, _E)

from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream

import yt_dlp

BOT_TOKEN      = os.environ.get('BOT_TOKEN')
API_ID         = int(os.environ.get('API_ID', 0))
API_HASH       = os.environ.get('API_HASH')
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

app: Client     = None
call: PyTgCalls = None
active_chats    = {}

COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
TMP_DIR      = '/tmp/burhan_music'
os.makedirs(TMP_DIR, exist_ok=True)

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

def is_private_chat(update: Update) -> bool:
    return update.effective_chat.type == 'private'

def delete_temp(path: Optional[str]):
    try:
        if path and os.path.exists(path):
            os.remove(path)
            logger.info(f"Deleted temp: {path}")
    except Exception:
        pass

# ─── SOURCE 1: JioSaavn ────────────────────────────────────────────────────
def search_jiosaavn(query: str) -> Optional[dict]:
    try:
        url  = f"https://saavn.dev/api/search/songs?query={requests.utils.quote(query)}&limit=5"
        resp = requests.get(url, timeout=15)
        data = resp.json()
        if not data.get('success'):
            return None
        results = data.get('data', {}).get('results', [])
        if not results:
            return None
        song = results[0]
        download_urls = song.get('downloadUrl', [])
        best_url = None
        for item in reversed(download_urls):
            if item.get('url'):
                best_url = item['url']
                break
        if not best_url:
            return None
        return {
            'title'      : song.get('name', 'Unknown'),
            'duration'   : int(song.get('duration', 0)),
            'uploader'   : song.get('primaryArtists', 'Unknown'),
            'direct_url' : best_url,
            'source'     : 'jiosaavn',
        }
    except Exception as e:
        logger.warning(f"JioSaavn search error: {e}")
        return None

def download_from_jiosaavn(info: dict) -> Optional[str]:
    try:
        uid      = uuid.uuid4().hex
        mp3_path = os.path.join(TMP_DIR, f"{uid}.mp3")
        resp = requests.get(info['direct_url'], timeout=60, stream=True)
        resp.raise_for_status()
        with open(mp3_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 10000:
            logger.info(f"JioSaavn download OK: {mp3_path}")
            return mp3_path
        delete_temp(mp3_path)
        return None
    except Exception as e:
        logger.warning(f"JioSaavn download error: {e}")
        return None

# ─── SOURCE 2: SoundCloud ─────────────────────────────────────────────────
def search_and_download_soundcloud(query: str) -> Optional[dict]:
    uid      = uuid.uuid4().hex
    out_tmpl = os.path.join(TMP_DIR, f"{uid}.%(ext)s")
    opts = {
        'quiet'          : True,
        'no_warnings'    : True,
        'nocheckcertificate': True,
        'format'         : 'bestaudio/best',
        'outtmpl'        : out_tmpl,
        'socket_timeout' : 30,
        'retries'        : 3,
        'postprocessors' : [{
            'key'             : 'FFmpegExtractAudio',
            'preferredcodec'  : 'mp3',
            'preferredquality': '128',
        }],
        'default_search' : 'scsearch',
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"scsearch1:{query}", download=True)
            if info and 'entries' in info:
                info = info['entries'][0]
        mp3_path = os.path.join(TMP_DIR, f"{uid}.mp3")
        if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 10000:
            logger.info(f"SoundCloud download OK")
            return {
                'file'    : mp3_path,
                'title'   : info.get('title', 'Unknown'),
                'duration': int(info.get('duration', 0)),
                'uploader': info.get('uploader', 'SoundCloud'),
            }
        for f in os.listdir(TMP_DIR):
            if f.startswith(uid):
                fpath = os.path.join(TMP_DIR, f)
                if os.path.getsize(fpath) > 10000:
                    return {
                        'file'    : fpath,
                        'title'   : info.get('title', 'Unknown') if info else 'Unknown',
                        'duration': 0,
                        'uploader': 'SoundCloud',
                    }
    except Exception as e:
        logger.warning(f"SoundCloud error: {e}")
    return None

# ─── SOURCE 3: YouTube (last resort) ──────────────────────────────────────
def search_and_download_youtube(query: str) -> Optional[dict]:
    uid      = uuid.uuid4().hex
    out_tmpl = os.path.join(TMP_DIR, f"{uid}.%(ext)s")
    for player in [['android_creator'], ['android_testsuite'], ['android'], []]:
        opts = {
            'quiet'          : True,
            'no_warnings'    : True,
            'nocheckcertificate': True,
            'format'         : 'bestaudio/best',
            'outtmpl'        : out_tmpl,
            'socket_timeout' : 30,
            'retries'        : 3,
            'postprocessors' : [{
                'key'             : 'FFmpegExtractAudio',
                'preferredcodec'  : 'mp3',
                'preferredquality': '128',
            }],
            'default_search' : 'ytsearch',
        }
        if player:
            opts['extractor_args'] = {'youtube': {'player_client': player}}
        if os.path.exists(COOKIES_FILE):
            opts['cookiefile'] = COOKIES_FILE
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch1:{query}", download=True)
                if info and 'entries' in info:
                    info = info['entries'][0]
            mp3_path = os.path.join(TMP_DIR, f"{uid}.mp3")
            if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 10000:
                logger.info(f"YouTube download OK with {player}")
                return {
                    'file'    : mp3_path,
                    'title'   : info.get('title', 'Unknown') if info else 'Unknown',
                    'duration': int(info.get('duration', 0)) if info else 0,
                    'uploader': info.get('uploader', 'YouTube') if info else 'YouTube',
                }
        except Exception as e:
            logger.warning(f"YouTube error with {player}: {e}")
            for f in os.listdir(TMP_DIR):
                if f.startswith(uid):
                    try: os.remove(os.path.join(TMP_DIR, f))
                    except: pass
    return None

# ─── MAIN SEARCH + DOWNLOAD ───────────────────────────────────────────────
def search_and_download(query: str) -> Optional[dict]:
    # 1. JioSaavn
    logger.info(f"Trying JioSaavn for: {query}")
    info = search_jiosaavn(query)
    if info:
        file_path = download_from_jiosaavn(info)
        if file_path:
            return {
                'file'    : file_path,
                'title'   : info['title'],
                'duration': info['duration'],
                'uploader': info['uploader'],
            }

    # 2. SoundCloud
    logger.info(f"Trying SoundCloud for: {query}")
    result = search_and_download_soundcloud(query)
    if result:
        return result

    # 3. YouTube
    logger.info(f"Trying YouTube for: {query}")
    result = search_and_download_youtube(query)
    if result:
        return result

    return None

# ─── VOICE CHAT ───────────────────────────────────────────────────────────
async def play_in_voice_chat(chat_id: int, file_path: str, title: str):
    try:
        try:
            await call.leave_group_call(chat_id)
        except Exception:
            pass
        await call.play(chat_id, MediaStream(file_path))
        if chat_id not in active_chats:
            active_chats[chat_id] = {'queue': [], 'current': None,
                                     'playing': False, 'temp_file': None}
        delete_temp(active_chats[chat_id].get('temp_file'))
        active_chats[chat_id]['current']   = {'title': title, 'path': file_path}
        active_chats[chat_id]['playing']   = True
        active_chats[chat_id]['temp_file'] = file_path
        logger.info(f"Playing: {title}")
        return True
    except Exception as e:
        logger.error(f"Play error: {e}")
        delete_temp(file_path)
        return False

async def stop_voice_chat(chat_id: int):
    try:
        await call.leave_group_call(chat_id)
    except Exception:
        pass
    if chat_id in active_chats:
        delete_temp(active_chats[chat_id].get('temp_file'))
        active_chats[chat_id] = {'queue': [], 'current': None,
                                 'playing': False, 'temp_file': None}

# ─── COMMANDS ─────────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized_user(update.effective_user.id):
        await update.message.reply_text("❌ Unauthorized!")
        return
    await update.message.reply_text(
        "*🎵 BURHAN MUSIC BOT*\n\n"
        "*Group mein:*\n"
        "/play <song> — Voice chat mein bajao\n"
        "/stop — Roko\n"
        "/current — Kya baj raha hai\n"
        "/queue — Queue dekho\n\n"
        "*DM mein:*\n"
        "/play <song> — MP3 file bhejo\n\n"
        "/authcheck — Auth check\n"
        "/help — Help",
        parse_mode='Markdown'
    )

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = is_authorized(update)
    if not auth:
        await update.message.reply_text(
            "❌ Unauthorized User!" if reason == "user" else "❌ Unauthorized Group!"
        )
        return
    if not context.args:
        await update.message.reply_text("❌ Usage: /play <song name>")
        return

    query   = ' '.join(context.args)
    chat_id = update.effective_chat.id
    private = is_private_chat(update)

    msg = await update.message.reply_text(
        f"🔍 Searching: *{query}*...", parse_mode='Markdown'
    )
    try:
        await msg.edit_text(
            f"🔍 Searching & downloading: *{query}*...\n_(JioSaavn → SoundCloud → YouTube)_",
            parse_mode='Markdown'
        )

        result = await asyncio.get_event_loop().run_in_executor(
            None, search_and_download, query
        )

        if not result:
            await msg.edit_text(
                "❌ Koi bhi source se nahi mila!\n"
                "Thoda aur specific naam likho."
            )
            return

        file_path = result['file']
        title     = result['title']
        dur       = result['duration']
        dur_str   = f"{dur//60}:{dur%60:02d}" if dur else "?"
        uploader  = result['uploader']

        if private:
            await msg.edit_text(
                f"✅ *Downloaded:* {title}\n📤 Bhej raha hoon...",
                parse_mode='Markdown'
            )
            with open(file_path, 'rb') as audio_file:
                await update.message.reply_audio(
                    audio=audio_file,
                    title=title,
                    performer=uploader,
                    duration=dur,
                    caption=f"🎵 {title}"
                )
            await msg.delete()
            delete_temp(file_path)
        else:
            keyboard     = [[InlineKeyboardButton("⏹ Stop", callback_data="stop")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await msg.edit_text(
                f"▶️ *Now Playing:*\n🎵 {title}\n⏱ {dur_str} | 📺 {uploader}",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )
            success = await play_in_voice_chat(chat_id, file_path, title)
            if not success:
                await msg.edit_text(
                    "❌ Voice chat join nahi hua!\n"
                    "Bot ko Admin banao aur Voice Chat khula rakho."
                )
    except Exception as e:
        logger.error(f"play_command error: {e}")
        await msg.edit_text(f"❌ Error: {e}")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, _ = is_authorized(update)
    if not auth:
        await update.message.reply_text("❌ Unauthorized!")
        return
    await stop_voice_chat(update.effective_chat.id)
    await update.message.reply_text("⏹ Stopped!")

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, _ = is_authorized(update)
    if not auth:
        await update.message.reply_text("❌ Unauthorized!")
        return
    chat_id = update.effective_chat.id
    q = active_chats.get(chat_id, {}).get('queue', [])
    if not q:
        await update.message.reply_text("📭 Queue is empty!")
        return
    text = "📋 *Queue:*\n" + "\n".join(
        f"{i+1}. {s['title']}" for i, s in enumerate(q)
    )
    await update.message.reply_text(text, parse_mode='Markdown')

async def current_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, _ = is_authorized(update)
    if not auth:
        await update.message.reply_text("❌ Unauthorized!")
        return
    chat_id = update.effective_chat.id
    cur = active_chats.get(chat_id, {}).get('current')
    if not cur:
        await update.message.reply_text("❌ Nothing playing!")
        return
    await update.message.reply_text(
        f"▶️ *Now Playing:*\n🎵 {cur['title']}", parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, _ = is_authorized(update)
    if not auth:
        await update.message.reply_text("❌ Unauthorized!")
        return
    await update.message.reply_text(
        "*🎵 BURHAN MUSIC — Commands:*\n\n"
        "/play <song> — Gana bajao / download karo\n"
        "/stop — Voice chat roko\n"
        "/current — Abhi kya baj raha hai\n"
        "/queue — Queue dekho\n"
        "/authcheck — Auth check",
        parse_mode='Markdown'
    )

async def authcheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    await update.message.reply_text(
        f"🔒 *Authorization Status*\n\n"
        f"👤 User:  {'✅' if is_authorized_user(uid) else '❌'}\n"
        f"💬 Group: {'✅' if is_authorized_group(cid) else '❌'}",
        parse_mode='Markdown'
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    auth, _ = is_authorized(update)
    if not auth:
        await q.edit_message_text("❌ Unauthorized!")
        return
    if q.data == "stop":
        await stop_voice_chat(update.effective_chat.id)
        await q.edit_message_text("⏹ Stopped!")

async def main():
    global app, call
    app  = Client("music_bot", api_id=API_ID, api_hash=API_HASH,
                  session_string=SESSION_STRING)
    call = PyTgCalls(app)
    await app.start()
    await call.start()
    application = Application.builder().token(BOT_TOKEN).build()
    for cmd, handler in [
        ("start",     start),
        ("help",      help_command),
        ("play",      play_command),
        ("stop",      stop_command),
        ("queue",     queue_command),
        ("current",   current_command),
        ("authcheck", authcheck_command),
    ]:
        application.add_handler(CommandHandler(cmd, handler))
    application.add_handler(CallbackQueryHandler(callback_handler))
    print("=" * 50)
    print("BURHAN MUSIC BOT STARTED")
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
