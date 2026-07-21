"""
╔══════════════════════════════════════════╗
║         SHEIKH BURHAN MUSIC BOT          ║
║         Premium Telegram Music Bot       ║
╚══════════════════════════════════════════╝
"""

import os
import re
import time
import random
import logging
import asyncio
import uuid
import requests
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
)

from pyrogram import Client
import pyrogram.errors as _pyro_errors
for _n in ['GroupCallForbidden', 'GroupcallForbidden']:
    if not hasattr(_pyro_errors, _n):
        class _Dummy(Exception): pass
        _Dummy.__name__ = _n
        setattr(_pyro_errors, _n, _Dummy)

from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream
import yt_dlp

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOT_TOKEN      = os.environ.get('BOT_TOKEN')
API_ID         = int(os.environ.get('API_ID', 0))
API_HASH       = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('SESSION_STRING')

AUTHORIZED_USERS  = [5804726533, 2062068620]
AUTHORIZED_GROUPS = [-1001954191240]
BOT_OWNER_USERNAME = "@Sheikh_barhan"

BRAND   = "🎵 *Sheikh Burhan Music*"
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SHEIKH BURHAN QUOTES  (shown randomly)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SB_QUOTES = [
    "🌟 *Sheikh Burhan says:* Music is the language of the soul — let it speak.",
    "🎶 *Sheikh Burhan says:* Every beat carries a story. Listen carefully.",
    "💫 *Sheikh Burhan says:* The best moments in life have a soundtrack. Make yours unforgettable.",
    "🔥 *Sheikh Burhan says:* Music has no boundaries — it unites hearts across the world.",
    "✨ *Sheikh Burhan says:* A good song can change your entire mood. Choose wisely.",
    "🎵 *Sheikh Burhan says:* Life without music is just noise. Tune into what matters.",
    "🌙 *Sheikh Burhan says:* Even the stars hum a melody — you just have to listen.",
    "🎤 *Sheikh Burhan says:* Play the music that makes your heart feel alive.",
    "💎 *Sheikh Burhan says:* Quality music, quality life — that's the Sheikh Burhan way.",
]

SB_LOADING_QUOTES = [
    "⏳ *Sheikh Burhan's bot is on it...* Great music is worth waiting for!",
    "🔍 *Searching the Sheikh Burhan way...* Only the best results for you.",
    "🎵 *Sheikh Burhan Music Bot at work...* Finding your perfect track.",
    "⚡ *Powered by Sheikh Burhan...* Loading at full speed!",
    "🌟 *Sheikh Burhan's premium bot...* Your music is almost ready!",
]

def get_quote() -> str:
    return random.choice(SB_QUOTES)

def get_loading_quote() -> str:
    return random.choice(SB_LOADING_QUOTES)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LOGGING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
logging.basicConfig(
    format='%(asctime)s | %(levelname)s | %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GLOBALS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
pyrogram_app: Client    = None
calls:        PyTgCalls = None
active_chats  = {}   # chat_id -> {current, playing, temp_file, start_time, pause_start, total_pause, duration, paused}
pending_video = {}

COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
TMP_DIR      = '/tmp/sbmusic'
os.makedirs(TMP_DIR, exist_ok=True)

YT_REGEX = re.compile(
    r'(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)([a-zA-Z0-9_\-]{11})'
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AUTH HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def is_auth_user(uid: int)  -> bool: return uid in AUTHORIZED_USERS
def is_auth_group(cid: int) -> bool: return cid in AUTHORIZED_GROUPS

def check_auth(update: Update) -> tuple:
    uid = update.effective_user.id
    cid = update.effective_chat.id
    if not is_auth_user(uid):
        return False, "user"
    if update.effective_chat.type in ('group', 'supergroup'):
        if not is_auth_group(cid):
            return False, "group"
    return True, "ok"

def is_private(update: Update) -> bool:
    return update.effective_chat.type == 'private'

def extract_yt_id(text: str) -> Optional[str]:
    m = YT_REGEX.search(text)
    return m.group(5) if m else None

def dur_str(sec: int) -> str:
    if not sec: return "—"
    h, m = divmod(sec, 3600)
    m, s = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"

def clean(path: Optional[str]):
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

def get_elapsed(chat_id: int) -> float:
    """Return seconds elapsed in current song (accounts for pauses)."""
    ch = active_chats.get(chat_id, {})
    if not ch.get('start_time'):
        return 0.0
    elapsed = time.time() - ch['start_time'] - ch.get('total_pause', 0)
    if ch.get('pause_start'):
        elapsed -= (time.time() - ch['pause_start'])
    return max(0.0, elapsed)

def unauthorized_msg(update: Update, reason: str) -> str:
    uid = update.effective_user.id
    if reason == "user":
        return (
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ *Access Denied*\n\n"
            f"You are not authorized to use this bot.\n"
            f"Your Telegram ID: `{uid}`\n\n"
            f"📩 To request access, please contact the bot owner:\n"
            f"👑 {BOT_OWNER_USERNAME}\n\n"
            f"Send a request like:\n"
            f"_\"Please authorize my ID: {uid}\"_"
        )
    else:
        return (
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ *Group Not Authorized*\n\n"
            f"This bot is not allowed in this group.\n\n"
            f"📩 To request authorization, the group admin must contact:\n"
            f"👑 {BOT_OWNER_USERNAME}\n\n"
            f"Your ID: `{uid}`"
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MUSIC SOURCES  (internal, no branding shown)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ── Source A: JioSaavn (Best for Indian/Bollywood) ──────────────────────────
def _saavn_search(query: str) -> Optional[dict]:
    try:
        r = requests.get(
            f"https://saavn.dev/api/search/songs?query={requests.utils.quote(query)}&limit=10",
            timeout=15
        )
        d = r.json()
        if not d.get('success'): return None
        results = d.get('data', {}).get('results', [])
        if not results: return None
        song = results[0]
        dl   = song.get('downloadUrl', [])
        url  = next((x['url'] for x in reversed(dl) if x.get('url')), None)
        if not url: return None
        return {
            'title'     : song.get('name', 'Unknown'),
            'artist'    : song.get('primaryArtists', ''),
            'duration'  : int(song.get('duration', 0)),
            'direct_url': url,
        }
    except Exception as e:
        logger.debug(f"saavn: {e}")
        return None

def _saavn_download(info: dict) -> Optional[str]:
    try:
        uid  = uuid.uuid4().hex
        path = os.path.join(TMP_DIR, f"{uid}.mp3")
        r    = requests.get(info['direct_url'], timeout=60, stream=True)
        r.raise_for_status()
        with open(path, 'wb') as f:
            for chunk in r.iter_content(65536):
                if chunk: f.write(chunk)
        if os.path.exists(path) and os.path.getsize(path) > 10_000:
            return path
        clean(path)
    except Exception as e:
        logger.debug(f"saavn_dl: {e}")
    return None

# ── Source B: SoundCloud (International/Nasheeds) ───────────────────────────
def _soundcloud_dl(query: str) -> Optional[dict]:
    uid  = uuid.uuid4().hex
    tmpl = os.path.join(TMP_DIR, f"{uid}.%(ext)s")
    opts = {
        'quiet': True, 'no_warnings': True, 'nocheckcertificate': True,
        'format': 'bestaudio/best', 'outtmpl': tmpl,
        'socket_timeout': 30, 'retries': 3,
        'postprocessors': [{'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3', 'preferredquality': '128'}],
    }
    try:
        info = None
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"scsearch1:{query}", download=True)
            if info and 'entries' in info:
                info = info['entries'][0]
        mp3 = os.path.join(TMP_DIR, f"{uid}.mp3")
        if os.path.exists(mp3) and os.path.getsize(mp3) > 10_000:
            return {'file': mp3,
                    'title': info.get('title','') if info else '',
                    'artist': info.get('uploader','') if info else '',
                    'duration': int(info.get('duration',0)) if info else 0}
    except Exception as e:
        logger.debug(f"scloud: {e}")
    for f in os.listdir(TMP_DIR):
        if f.startswith(uid):
            try: os.remove(os.path.join(TMP_DIR, f))
            except: pass
    return None

# ── Source C: YouTube Audio (fallback) ──────────────────────────────────────
def _yt_audio_dl(query_or_url: str, is_url: bool = False) -> Optional[dict]:
    uid  = uuid.uuid4().hex
    tmpl = os.path.join(TMP_DIR, f"{uid}.%(ext)s")
    for player in [['android_creator'], ['android_testsuite'], ['android'], []]:
        opts = {
            'quiet': True, 'no_warnings': True, 'nocheckcertificate': True,
            'format': 'bestaudio/best', 'outtmpl': tmpl,
            'socket_timeout': 30, 'retries': 3,
            'postprocessors': [{'key': 'FFmpegExtractAudio',
                                'preferredcodec': 'mp3', 'preferredquality': '128'}],
        }
        if player:
            opts['extractor_args'] = {'youtube': {'player_client': player}}
        if os.path.exists(COOKIES_FILE):
            opts['cookiefile'] = COOKIES_FILE
        target = query_or_url if is_url else f"ytsearch1:{query_or_url}"
        try:
            info = None
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(target, download=True)
                if info and 'entries' in info:
                    info = info['entries'][0]
            mp3 = os.path.join(TMP_DIR, f"{uid}.mp3")
            if os.path.exists(mp3) and os.path.getsize(mp3) > 10_000:
                return {'file': mp3,
                        'title': info.get('title','') if info else '',
                        'artist': info.get('uploader','') if info else '',
                        'duration': int(info.get('duration',0)) if info else 0}
        except Exception as e:
            logger.debug(f"yt_audio {player}: {e}")
        for f in os.listdir(TMP_DIR):
            if f.startswith(uid):
                try: os.remove(os.path.join(TMP_DIR, f))
                except: pass
    return None

# ── Source: YouTube VIDEO ────────────────────────────────────────────────────
def _yt_video_dl(url: str, quality: str) -> Optional[dict]:
    uid  = uuid.uuid4().hex
    tmpl = os.path.join(TMP_DIR, f"{uid}.%(ext)s")
    if quality == 'best':
        fmt = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    else:
        h   = quality.replace('p', '')
        fmt = (f'bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]'
               f'/best[height<={h}][ext=mp4]/best[height<={h}]')
    opts = {
        'quiet': True, 'no_warnings': True, 'nocheckcertificate': True,
        'format': fmt, 'outtmpl': tmpl,
        'socket_timeout': 60, 'retries': 3,
        'merge_output_format': 'mp4',
    }
    if os.path.exists(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE
    for player in [['android_creator'], ['android_testsuite'], []]:
        if player:
            opts['extractor_args'] = {'youtube': {'player_client': player}}
        try:
            info = None
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            for f in os.listdir(TMP_DIR):
                if f.startswith(uid) and f.endswith('.mp4'):
                    fp = os.path.join(TMP_DIR, f)
                    if os.path.getsize(fp) > 10_000:
                        return {'file': fp, 'is_video': True,
                                'title': info.get('title','') if info else '',
                                'artist': info.get('uploader','') if info else '',
                                'duration': int(info.get('duration',0)) if info else 0}
        except Exception as e:
            logger.debug(f"yt_video {player} {quality}: {e}")
        for f in os.listdir(TMP_DIR):
            if f.startswith(uid):
                try: os.remove(os.path.join(TMP_DIR, f))
                except: pass
    return None

def _yt_info(url: str) -> dict:
    opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'socket_timeout': 20}
    if os.path.exists(COOKIES_FILE):
        opts['cookiefile'] = COOKIES_FILE
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            i = ydl.extract_info(url, download=False)
            return {'title': i.get('title',''), 'artist': i.get('uploader',''),
                    'duration': int(i.get('duration',0))}
    except Exception:
        return {'title': '', 'artist': '', 'duration': 0}

# ── Unified search+download (keyword) ───────────────────────────────────────
def find_and_download(query: str) -> Optional[dict]:
    # 1. JioSaavn — best for Bollywood/Hindi/Indian
    info = _saavn_search(query)
    if info:
        fp = _saavn_download(info)
        if fp:
            return {'file': fp, 'title': info['title'],
                    'artist': info['artist'], 'duration': info['duration']}

    # 2. SoundCloud — International / Nasheeds / Hollywood
    res = _soundcloud_dl(query)
    if res:
        return res

    # 3. YouTube — absolute fallback
    res = _yt_audio_dl(query, is_url=False)
    if res:
        return res

    return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  VOICE CHAT HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_player_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for music controls in group."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏮ -10s",       callback_data="seek_back"),
            InlineKeyboardButton("⏸ Pause",       callback_data="pause_resume"),
            InlineKeyboardButton("⏭ +10s",        callback_data="seek_fwd"),
        ],
        [
            InlineKeyboardButton("⏹ Stop",        callback_data="stop"),
        ],
    ])

def make_paused_kb() -> InlineKeyboardMarkup:
    """Inline keyboard when song is paused."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏮ -10s",       callback_data="seek_back"),
            InlineKeyboardButton("▶️ Resume",     callback_data="pause_resume"),
            InlineKeyboardButton("⏭ +10s",        callback_data="seek_fwd"),
        ],
        [
            InlineKeyboardButton("⏹ Stop",        callback_data="stop"),
        ],
    ])

async def vc_play(chat_id: int, file_path: str, title: str, duration: int = 0,
                  seek_sec: int = 0) -> bool:
    """Join VC (if not already) and play/seek the given file."""
    try:
        # Build ffmpeg parameters for seeking
        ff_params = f"-ss {seek_sec}" if seek_sec > 0 else None

        # Leave first to avoid duplicate join
        try:
            await calls.leave_group_call(chat_id)
            await asyncio.sleep(0.5)
        except Exception:
            pass

        if ff_params:
            await calls.play(chat_id, MediaStream(file_path, ffmpeg_parameters=ff_params))
        else:
            await calls.play(chat_id, MediaStream(file_path))

        ch = active_chats.setdefault(chat_id, {
            'current': None, 'playing': False, 'temp_file': None,
            'start_time': None, 'pause_start': None, 'total_pause': 0,
            'duration': 0, 'paused': False,
        })
        clean(ch.get('temp_file') if seek_sec == 0 else None)
        ch.update({
            'current'     : title,
            'playing'     : True,
            'temp_file'   : file_path,
            'start_time'  : time.time() - seek_sec,
            'pause_start' : None,
            'total_pause' : 0,
            'duration'    : duration,
            'paused'      : False,
        })
        return True
    except _pyro_errors.GroupCallForbidden:
        logger.error("vc_play: GroupCallForbidden — make the userbot an admin or enable VC")
        clean(file_path)
        return False
    except Exception as e:
        logger.error(f"vc_play: {e}")
        clean(file_path)
        return False

async def vc_stop(chat_id: int):
    for fn in ('leave_group_call', 'stop_stream'):
        try:
            await getattr(calls, fn)(chat_id)
        except Exception:
            pass
    if chat_id in active_chats:
        clean(active_chats[chat_id].get('temp_file'))
        active_chats[chat_id] = {
            'current': None, 'playing': False, 'temp_file': None,
            'start_time': None, 'pause_start': None, 'total_pause': 0,
            'duration': 0, 'paused': False,
        }

async def vc_pause(chat_id: int) -> bool:
    ch = active_chats.get(chat_id, {})
    if not ch.get('playing') or ch.get('paused'):
        return False
    try:
        await calls.pause(chat_id)
        ch['paused']      = True
        ch['pause_start'] = time.time()
        return True
    except Exception as e:
        logger.error(f"vc_pause: {e}")
        return False

async def vc_resume(chat_id: int) -> bool:
    ch = active_chats.get(chat_id, {})
    if not ch.get('paused'):
        return False
    try:
        await calls.resume(chat_id)
        if ch.get('pause_start'):
            ch['total_pause'] = ch.get('total_pause', 0) + (time.time() - ch['pause_start'])
        ch['paused']      = False
        ch['pause_start'] = None
        return True
    except Exception as e:
        logger.error(f"vc_resume: {e}")
        return False

async def vc_seek(chat_id: int, delta: int) -> bool:
    """Seek forward/backward by `delta` seconds in the current track."""
    ch = active_chats.get(chat_id, {})
    if not ch.get('temp_file') or not ch.get('current'):
        return False

    current_pos = get_elapsed(chat_id)
    new_pos     = max(0, int(current_pos) + delta)

    dur = ch.get('duration', 0)
    if dur and new_pos >= dur:
        return False

    # Re-play from new position — this also re-joins VC which makes the
    # userbot visible in the participants list
    fp    = ch['temp_file']
    title = ch['current']
    ok    = await vc_play(chat_id, fp, title, duration=dur, seek_sec=new_pos)
    return ok

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  UI HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def card(title: str, artist: str, duration: int, state: str = "▶️ Playing") -> str:
    lines = [
        BRAND, "",
        f"{state}  *{title}*",
    ]
    if artist:
        lines.append(f"🎤  {artist}")
    if duration:
        lines.append(f"⏱  {dur_str(duration)}")
    lines.append(DIVIDER)
    lines.append(f"\n_{get_quote()}_")
    return "\n".join(lines)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  COMMANDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "Friend"
    text = (
        f"{BRAND}\n"
        f"{DIVIDER}\n\n"
        f"Welcome *{name}* 👋\n\n"
        f"I am a Premium Music Bot by Sheikh Burhan.\n\n"
        f"📋 *Commands:*\n"
        f"• /play — Play a song in VC or download\n"
        f"• /stop — Stop the music\n"
        f"• /current — What's playing now\n"
        f"• /myid — Your Telegram ID\n"
        f"• /help — Help & commands\n\n"
        f"{DIVIDER}\n"
        f"_Your ID: `{uid}`_\n\n"
        f"_{get_quote()}_"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Anyone can use this."""
    uid  = update.effective_user.id
    name = update.effective_user.full_name or "—"
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"👤 *Name:* {name}\n"
        f"🆔 *Your Telegram ID:*\n`{uid}`\n\n"
        f"_{DIVIDER}_",
        parse_mode='Markdown'
    )


async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(
            unauthorized_msg(update, reason),
            parse_mode='Markdown'
        )
        return

    if not context.args:
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ *Usage:*\n"
            f"`/play <song name>`\n"
            f"`/play <YouTube link>`",
            parse_mode='Markdown'
        )
        return

    query   = ' '.join(context.args).strip()
    chat_id = update.effective_chat.id
    private = is_private(update)

    # ── YouTube URL ──────────────────────────────────────────────────────────
    yt_id = extract_yt_id(query)
    if yt_id:
        yt_url = f"https://www.youtube.com/watch?v={yt_id}"
        msg    = await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"⏳ Link detected, fetching info...\n\n"
            f"_{get_loading_quote()}_",
            parse_mode='Markdown'
        )
        info = await asyncio.get_event_loop().run_in_executor(None, _yt_info, yt_url)
        title    = info['title']    or "Unknown"
        artist   = info['artist']   or ""
        duration = info['duration']
        tok      = uuid.uuid4().hex
        pending_video[tok] = {
            'url': yt_url, 'title': title, 'artist': artist,
            'duration': duration, 'chat_id': chat_id, 'private': private,
        }
        kb = [
            [InlineKeyboardButton("🎵 Audio Only", callback_data=f"q|{tok}|audio")],
            [
                InlineKeyboardButton("360p",  callback_data=f"q|{tok}|360p"),
                InlineKeyboardButton("480p",  callback_data=f"q|{tok}|480p"),
                InlineKeyboardButton("720p",  callback_data=f"q|{tok}|720p"),
            ],
            [
                InlineKeyboardButton("1080p",        callback_data=f"q|{tok}|1080p"),
                InlineKeyboardButton("Best Quality",  callback_data=f"q|{tok}|best"),
            ],
        ]
        await msg.edit_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"🎬  *{title}*\n"
            + (f"🎤  {artist}\n" if artist else "")
            + (f"⏱  {dur_str(duration)}\n" if duration else "")
            + f"\n{DIVIDER}\n\n📥 *Select download quality:*\n\n"
            + f"_{get_quote()}_",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # ── Keyword search ───────────────────────────────────────────────────────
    msg = await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"🔍 Searching: *{query}*...\n\n"
        f"_{get_loading_quote()}_",
        parse_mode='Markdown'
    )
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, find_and_download, query
        )
        if not result:
            await msg.edit_text(
                f"{BRAND}\n{DIVIDER}\n\n"
                f"❌ Song not found.\n"
                f"Try a different name or spelling.",
                parse_mode='Markdown'
            )
            return

        fp       = result['file']
        title    = result.get('title') or query
        artist   = result.get('artist', '')
        duration = result.get('duration', 0)

        if private:
            # DM → send audio file
            await msg.edit_text(
                f"{BRAND}\n{DIVIDER}\n\n"
                f"✅ Found!\n🎵 *{title}*\n\n📤 Sending...\n\n"
                f"_{get_quote()}_",
                parse_mode='Markdown'
            )
            with open(fp, 'rb') as af:
                await update.message.reply_audio(
                    audio=af, title=title,
                    performer=artist, duration=duration,
                )
            await msg.delete()
            clean(fp)
        else:
            # Group → voice chat with player controls
            await msg.edit_text(
                card(title, artist, duration, state="▶️ Playing"),
                parse_mode='Markdown',
                reply_markup=make_player_kb()
            )
            ok = await vc_play(chat_id, fp, title, duration=duration)
            if not ok:
                await msg.edit_text(
                    f"{BRAND}\n{DIVIDER}\n\n"
                    f"❌ Could not join Voice Chat.\n"
                    f"Please make the bot admin and ensure Voice Chat is open.\n\n"
                    f"📩 Contact {BOT_OWNER_USERNAME} for help.",
                    parse_mode='Markdown'
                )
    except Exception as e:
        logger.error(f"cmd_play: {e}")
        await msg.edit_text(
            f"{BRAND}\n{DIVIDER}\n\n❌ Error: {e}",
            parse_mode='Markdown'
        )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(
            unauthorized_msg(update, reason),
            parse_mode='Markdown'
        )
        return
    await vc_stop(update.effective_chat.id)
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n⏹ *Music stopped.*",
        parse_mode='Markdown'
    )


async def cmd_current(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(
            unauthorized_msg(update, reason),
            parse_mode='Markdown'
        )
        return
    ch  = active_chats.get(update.effective_chat.id, {})
    cur = ch.get('current')
    if not cur:
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n❌ Nothing is playing right now.",
            parse_mode='Markdown'
        )
        return
    elapsed = get_elapsed(update.effective_chat.id)
    dur     = ch.get('duration', 0)
    status  = "⏸ Paused" if ch.get('paused') else "▶️ Playing"
    text    = (
        f"{BRAND}\n{DIVIDER}\n\n"
        f"{status}  *{cur}*\n"
        f"⏱  {dur_str(int(elapsed))} / {dur_str(dur)}\n\n"
        f"_{get_quote()}_"
    )
    await update.message.reply_text(text, parse_mode='Markdown',
                                    reply_markup=make_paused_kb() if ch.get('paused') else make_player_kb())


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"📋 *Commands:*\n\n"
        f"🎵 `/play <song name>`\n"
        f"   → Play in VC or download as MP3\n\n"
        f"🔗 `/play <YouTube link>`\n"
        f"   → Choose quality and download\n\n"
        f"⏹ `/stop`\n"
        f"   → Stop music immediately\n\n"
        f"🎵 `/current`\n"
        f"   → What's playing now\n\n"
        f"🆔 `/myid`\n"
        f"   → Your Telegram ID\n\n"
        f"{DIVIDER}\n"
        f"_In groups: plays in Voice Chat_\n"
        f"_In DM: sends MP3 file_\n\n"
        f"🎛 *Player Controls (in group):*\n"
        f"⏮ -10s  |  ⏸ Pause/▶️ Resume  |  ⏭ +10s  |  ⏹ Stop\n\n"
        f"_{get_quote()}_",
        parse_mode='Markdown'
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CALLBACK HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    await q.answer()

    chat_id = update.effective_chat.id
    auth, reason = check_auth(update)

    # ── Stop ────────────────────────────────────────────────────────────────
    if data == "stop":
        if not auth:
            await q.answer(f"❌ Not authorized! Your ID: {update.effective_user.id}", show_alert=True)
            return
        await vc_stop(chat_id)
        await q.edit_message_text(
            f"{BRAND}\n{DIVIDER}\n\n⏹ *Music stopped.*",
            parse_mode='Markdown'
        )
        return

    # ── Pause / Resume ───────────────────────────────────────────────────────
    if data == "pause_resume":
        if not auth:
            await q.answer(f"❌ Not authorized! Your ID: {update.effective_user.id}", show_alert=True)
            return
        ch = active_chats.get(chat_id, {})
        if ch.get('paused'):
            ok = await vc_resume(chat_id)
            if ok:
                title  = ch.get('current', 'Unknown')
                artist = ''
                dur    = ch.get('duration', 0)
                try:
                    await q.edit_message_text(
                        card(title, artist, dur, state="▶️ Playing"),
                        parse_mode='Markdown',
                        reply_markup=make_player_kb()
                    )
                except Exception:
                    pass
            else:
                await q.answer("Could not resume.", show_alert=True)
        else:
            ok = await vc_pause(chat_id)
            if ok:
                title = ch.get('current', 'Unknown')
                dur   = ch.get('duration', 0)
                try:
                    await q.edit_message_text(
                        card(title, '', dur, state="⏸ Paused"),
                        parse_mode='Markdown',
                        reply_markup=make_paused_kb()
                    )
                except Exception:
                    pass
            else:
                await q.answer("Nothing is playing.", show_alert=True)
        return

    # ── Seek Forward / Backward ──────────────────────────────────────────────
    if data in ("seek_fwd", "seek_back"):
        if not auth:
            await q.answer(f"❌ Not authorized! Your ID: {update.effective_user.id}", show_alert=True)
            return
        delta = +10 if data == "seek_fwd" else -10
        ch    = active_chats.get(chat_id, {})
        ok    = await vc_seek(chat_id, delta)
        if ok:
            title = ch.get('current', 'Unknown')
            dur   = ch.get('duration', 0)
            pos   = get_elapsed(chat_id)
            label = f"⏭ +10s" if delta > 0 else "⏮ -10s"
            try:
                await q.edit_message_text(
                    f"{BRAND}\n{DIVIDER}\n\n"
                    f"▶️  *{title}*\n"
                    f"⏱  {dur_str(int(pos))} / {dur_str(dur)}\n"
                    f"_{label} skipped_\n\n"
                    f"_{get_quote()}_",
                    parse_mode='Markdown',
                    reply_markup=make_player_kb()
                )
            except Exception:
                pass
        else:
            await q.answer("Cannot seek right now.", show_alert=True)
        return

    # ── Quality selection: q|token|quality ──────────────────────────────────
    if data.startswith("q|"):
        parts = data.split("|")
        if len(parts) != 3:
            return
        _, tok, quality = parts
        pv = pending_video.get(tok)
        if not pv:
            await q.edit_message_text(
                f"{BRAND}\n{DIVIDER}\n\n❌ Request expired. Please try /play again.",
                parse_mode='Markdown'
            )
            return

        if not auth:
            await q.answer(f"❌ Not authorized! Your ID: {update.effective_user.id}", show_alert=True)
            return

        url      = pv['url']
        title    = pv['title']
        artist   = pv['artist']
        duration = pv['duration']

        label_map = {
            'audio': '🎵 Audio', '360p': '📹 360p', '480p': '📹 480p',
            '720p': '📹 720p', '1080p': '📹 1080p', 'best': '📹 Best'
        }
        label = label_map.get(quality, quality)

        await q.edit_message_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"⬇️ Downloading ({label})\n"
            f"🎵 *{title}*\n"
            + (f"🎤 {artist}\n" if artist else "")
            + f"\n_{get_loading_quote()}_",
            parse_mode='Markdown'
        )

        def do_dl():
            if quality == 'audio':
                return _yt_audio_dl(url, is_url=True)
            return _yt_video_dl(url, quality)

        result = await asyncio.get_event_loop().run_in_executor(None, do_dl)
        pending_video.pop(tok, None)

        if not result:
            await q.edit_message_text(
                f"{BRAND}\n{DIVIDER}\n\n"
                f"❌ Download failed.\n"
                f"Try another quality or try again later.",
                parse_mode='Markdown'
            )
            return

        fp      = result['file']
        is_vid  = result.get('is_video', False)
        size_mb = os.path.getsize(fp) / (1024 * 1024)

        if size_mb > 1900:
            clean(fp)
            await q.edit_message_text(
                f"{BRAND}\n{DIVIDER}\n\n"
                f"❌ File too large ({size_mb:.0f} MB).\n"
                f"Telegram's limit is 2GB. Please choose a lower quality.",
                parse_mode='Markdown'
            )
            return

        await q.edit_message_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"✅ *{title}*\n"
            f"📤 Sending... ({size_mb:.1f} MB)\n\n"
            f"_{get_quote()}_",
            parse_mode='Markdown'
        )

        try:
            cid = update.effective_chat.id
            if is_vid:
                with open(fp, 'rb') as vf:
                    await context.bot.send_video(
                        chat_id=cid, video=vf,
                        caption=f"🎬 {title}",
                        duration=duration, supports_streaming=True,
                        read_timeout=300, write_timeout=300, connect_timeout=60,
                    )
            else:
                with open(fp, 'rb') as af:
                    await context.bot.send_audio(
                        chat_id=cid, audio=af,
                        title=title, performer=artist, duration=duration,
                        read_timeout=300, write_timeout=300, connect_timeout=60,
                    )
            try:
                await q.delete_message()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"send error: {e}")
            await q.edit_message_text(
                f"{BRAND}\n{DIVIDER}\n\n❌ Send error: {e}",
                parse_mode='Markdown'
            )
        finally:
            clean(fp)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def main():
    global pyrogram_app, calls

    pyrogram_app = Client(
        "sbmusic", api_id=API_ID, api_hash=API_HASH,
        session_string=SESSION_STRING
    )
    calls = PyTgCalls(pyrogram_app)
    await pyrogram_app.start()
    await calls.start()

    app = Application.builder().token(BOT_TOKEN).build()

    # Commands  (English only)
    app.add_handler(CommandHandler(["start"],                 cmd_start))
    app.add_handler(CommandHandler(["play"],                  cmd_play))
    app.add_handler(CommandHandler(["stop"],                  cmd_stop))
    app.add_handler(CommandHandler(["current"],               cmd_current))
    app.add_handler(CommandHandler(["myid"],                  cmd_myid))
    app.add_handler(CommandHandler(["help"],                  cmd_help))
    app.add_handler(CallbackQueryHandler(cb_handler))

    print("━" * 45)
    print("  SHEIKH BURHAN MUSIC BOT — STARTED")
    print("━" * 45)

    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)

    stop_event = asyncio.Event()
    try:
        await stop_event.wait()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
        for fn in ('stop', ):
            try:
                await getattr(calls, fn)()
            except Exception:
                pass
        try:
            await pyrogram_app.stop()
        except Exception:
            pass


if __name__ == "__main__":
    asyncio.run(main())
