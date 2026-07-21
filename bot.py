import os
import logging
import asyncio
import uuid
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

def delete_temp(path: Optional[str]):
    try:
        if path and os.path.exists(path):
            os.remove(path)
            logger.info(f"Deleted temp: {path}")
    except Exception:
        pass

def search_youtube(query: str) -> Optional[str]:
    search_opts = {
        'quiet'              : True,
        'no_warnings'        : True,
        'nocheckcertificate' : True,
        'extract_flat'       : 'in_playlist',
        'skip_download'      : True,
        'socket_timeout'     : 20,
        'retries'            : 5,
        'http_headers'       : {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            ),
        },
    }
    if os.path.exists(COOKIES_FILE):
        search_opts['cookiefile'] = COOKIES_FILE

    queries_to_try = [
        f"ytsearch3:{query}",
        f"ytsearch5:{query} song",
        f"ytsearch3:{query} lyrics",
    ]

    for search_query in queries_to_try:
        try:
            with yt_dlp.YoutubeDL(search_opts) as ydl:
                results = ydl.extract_info(search_query, download=False)
                if results and 'entries' in results:
                    for entry in results['entries']:
                        if entry and entry.get('id'):
                            url = f"https://www.youtube.com/watch?v={entry['id']}"
                            logger.info(f"Found: {entry.get('title')} -> {url}")
                            return url
        except Exception as e:
            logger.warning(f"Search failed for '{search_query}': {e}")
            continue

    logger.error(f"All search attempts failed for: {query}")
    return None

def download_audio(youtube_url: str) -> Optional[str]:
    uid      = uuid.uuid4().hex
    out_tmpl = os.path.join(TMP_DIR, f"{uid}.%(ext)s")

    player_clients = [
        ['android_testsuite'],
        ['android_creator'],
        ['android'],
        ['web'],
    ]

    for player in player_clients:
        opts = {
            'quiet'              : True,
            'no_warnings'        : True,
            'nocheckcertificate' : True,
            'source_address'     : '0.0.0.0',
            'geo_bypass'         : True,
            'socket_timeout'     : 30,
            'retries'            : 5,
            'format'             : 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl'            : out_tmpl,
            'postprocessors'     : [{
                'key'             : 'FFmpegExtractAudio',
                'preferredcodec'  : 'mp3',
                'preferredquality': '128',
            }],
            'extractor_args'     : {
                'youtube': {
                    'player_client': player,
                }
            },
            'http_headers'       : {
                'User-Agent': (
                    'com.google.android.youtube/17.31.35 '
                    '(Linux; U; Android 11) gzip'
                ),
            },
        }
        if os.path.exists(COOKIES_FILE):
            opts['cookiefile'] = COOKIES_FILE

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([youtube_url])

            mp3_path = os.path.join(TMP_DIR, f"{uid}.mp3")
            if os.path.exists(mp3_path):
                logger.info(f"Downloaded OK with {player}")
                return mp3_path
            for f in os.listdir(TMP_DIR):
                if f.startswith(uid):
                    return os.path.join(TMP_DIR, f)
        except Exception as e:
            logger.warning(f"Download failed with {player}: {e}")
            continue

    logger.error("All download attempts failed")
    return None

def get_song_info(url: str) -> dict:
    try:
        opts = {
            'quiet'              : True,
            'no_warnings'        : True,
            'nocheckcertificate' : True,
            'skip_download'      : True,
            'socket_timeout'     : 20,
        }
        if os.path.exists(COOKIES_FILE):
            opts['cookiefile'] = COOKIES_FILE
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return {
                'title'   : info.get('title',    'Unknown'),
                'duration': info.get('duration', 0),
                'uploader': info.get('uploader', 'Unknown'),
                'url'     : url,
            }
    except Exception as e:
        logger.error(f"Info error: {e}")
        return {'title': 'Unknown', 'duration': 0, 'uploader': 'Unknown', 'url': url}

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
        logger.info(f"Playing: {title} in {chat_id}")
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
    return True

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized_user(update.effective_user.id):
        await update.message.reply_text("Unauthorized!")
        return
    await update.message.reply_text(
        "*BURHAN MUSIC BOT*\n\n"
        "/play <song> — गाना बजाओ\n"
        "/stop — रोको\n"
        "/current — अभी क्या बज रहा है\n"
        "/queue — queue देखो\n"
        "/authcheck — authorization check\n"
        "/help — help",
        parse_mode='Markdown'
    )

async def play_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = is_authorized(update)
    if not auth:
        msg = "Unauthorized User!" if reason == "user" else "Unauthorized Group!"
        await update.message.reply_text(msg)
        return
    if not context.args:
        await update.message.reply_text("Usage: /play <song name>")
        return
    query   = ' '.join(context.args)
    chat_id = update.effective_chat.id
    msg     = await update.message.reply_text(
        f"Searching: *{query}*...", parse_mode='Markdown'
    )
    try:
        song_url = search_youtube(query)
        if not song_url:
            await msg.edit_text("No results found! Thoda aur specific naam likho.")
            return
        info     = get_song_info(song_url)
        title    = info['title']
        dur      = info['duration']
        dur_str  = f"{dur//60}:{dur%60:02d}" if dur else "?"
        uploader = info['uploader']
        await msg.edit_text(
            f"*Downloading:* {title}\n{dur_str} | {uploader}",
            parse_mode='Markdown'
        )
        file_path = await asyncio.get_event_loop().run_in_executor(
            None, download_audio, song_url
        )
        if not file_path:
            await msg.edit_text("Could not download audio! Thodi der baad try karo.")
            return
        keyboard     = [[InlineKeyboardButton("Stop", callback_data="stop")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await msg.edit_text(
            f"*Now Playing:*\n{title}\n{dur_str} | {uploader}",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        success = await play_in_voice_chat(chat_id, file_path, title)
        if not success:
            await msg.edit_text(
                "Voice chat join nahi hua!\n"
                "Bot ko Admin banao aur Voice Chat khula rakho."
            )
    except Exception as e:
        logger.error(f"play_command error: {e}")
        await msg.edit_text(f"Error: {e}")

async def stop_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, _ = is_authorized(update)
    if not auth:
        await update.message.reply_text("Unauthorized!")
        return
    await stop_voice_chat(update.effective_chat.id)
    await update.message.reply_text("Stopped!")

async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, _ = is_authorized(update)
    if not auth:
        await update.message.reply_text("Unauthorized!")
        return
    chat_id = update.effective_chat.id
    q = active_chats.get(chat_id, {}).get('queue', [])
    if not q:
        await update.message.reply_text("Queue is empty!")
        return
    text = "*Queue:*\n" + "\n".join(f"{i+1}. {s['title']}" for i, s in enumerate(q))
    await update.message.reply_text(text, parse_mode='Markdown')

async def current_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, _ = is_authorized(update)
    if not auth:
        await update.message.reply_text("Unauthorized!")
        return
    chat_id = update.effective_chat.id
    cur = active_chats.get(chat_id, {}).get('current')
    if not cur:
        await update.message.reply_text("Nothing playing!")
        return
    await update.message.reply_text(
        f"*Now Playing:*\n{cur['title']}", parse_mode='Markdown'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, _ = is_authorized(update)
    if not auth:
        await update.message.reply_text("Unauthorized!")
        return
    await update.message.reply_text(
        "*BURHAN MUSIC — Commands:*\n\n"
        "/play <song> — गाना बजाओ\n"
        "/stop — रोको\n"
        "/current — अभी क्या बज रहा है\n"
        "/queue — queue देखो\n"
        "/authcheck — authorization check",
        parse_mode='Markdown'
    )

async def authcheck_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    cid = update.effective_chat.id
    await update.message.reply_text(
        f"*Authorization Status*\n\n"
        f"User:  {'YES' if is_authorized_user(uid) else 'NO'}\n"
        f"Group: {'YES' if is_authorized_group(cid) else 'NO'}",
        parse_mode='Markdown'
    )

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    auth, _ = is_authorized(update)
    if not auth:
        await q.edit_message_text("Unauthorized!")
        return
    if q.data == "stop":
        await stop_voice_chat(update.effective_chat.id)
        await q.edit_message_text("Stopped!")

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
