"""
╔══════════════════════════════════════════════════════════╗
║             SHEIKH BURHAN MUSIC BOT  v3.0               ║
║         Premium Professional Telegram Music Bot          ║
╚══════════════════════════════════════════════════════════╝
"""

import os, re, time, random, logging, asyncio, uuid, hashlib, json
import requests
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.ext import (
    Application, CommandHandler, ContextTypes, CallbackQueryHandler,
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
    from pytgcalls.types import Update as PyTgUpdate      # pytgcalls ≥ 1.x
except ImportError:
    PyTgUpdate = None

import yt_dlp

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOT_TOKEN      = os.environ.get('BOT_TOKEN')
API_ID         = int(os.environ.get('API_ID', 0))
API_HASH       = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('SESSION_STRING')

AUTHORIZED_USERS   = [5804726533, 2062068620]
AUTHORIZED_GROUPS  = [-1001954191240]          # only 1 group allowed
BOT_OWNER_USERNAME = "@shikh_baran"

BRAND   = "🎵 *Sheikh Burhan Music*"
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━━━"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SHEIKH BURHAN QUOTES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
    "🌊 *Sheikh Burhan says:* Let the rhythm wash over you — music heals what words cannot.",
    "⭐ *Sheikh Burhan says:* The right song at the right moment is pure magic.",
]

SB_LOADING_QUOTES = [
    "⏳ *Sheikh Burhan's bot is on it...* Great music is worth a moment!",
    "🔍 *Searching the Sheikh Burhan way...* Only the best for you.",
    "🎵 *Sheikh Burhan Music Bot at work...* Finding your perfect track.",
    "⚡ *Powered by Sheikh Burhan...* Loading at full speed!",
    "🌟 *Sheikh Burhan's premium bot...* Your music is almost ready!",
    "🎯 *Sheikh Burhan's servers are hunting...* Top-quality audio incoming!",
]

def get_quote()         -> str: return random.choice(SB_QUOTES)
def get_loading_quote() -> str: return random.choice(SB_LOADING_QUOTES)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LOGGING
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
logging.basicConfig(format='%(asctime)s | %(levelname)s | %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  GLOBALS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
pyrogram_app : Client    = None
calls        : PyTgCalls = None

# active_chats[chat_id] schema:
# {
#   current, current_file, playing, paused,
#   queue: [{title, artist, duration, file, query}],
#   loop: bool, loop_queue: bool,
#   start_time, pause_start, total_pause, duration,
#   volume: int (100=default),
#   np_msg_id: int (now-playing message id to update)
# }
active_chats : Dict[int, dict] = {}
pending_video: Dict[str, dict] = {}

# Thread pool for blocking I/O
_pool = ThreadPoolExecutor(max_workers=6)

COOKIES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.txt')
TMP_DIR      = '/tmp/sbmusic'
CACHE_DIR    = '/tmp/sbmusic_cache'
os.makedirs(TMP_DIR,   exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

YT_REGEX = re.compile(
    r'(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)([a-zA-Z0-9_\-]{11})'
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AUTH HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

def get_elapsed(chat_id: int) -> float:
    ch = active_chats.get(chat_id, {})
    if not ch.get('start_time'): return 0.0
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
            f"🆔 Your Telegram ID: `{uid}`\n\n"
            f"📩 To request access, contact the bot owner:\n"
            f"👑 {BOT_OWNER_USERNAME}\n\n"
            f"Send: _\"Please authorize my ID: {uid}\"_"
        )
    return (
        f"{BRAND}\n{DIVIDER}\n\n"
        f"❌ *Group Not Authorized*\n\n"
        f"This bot is not permitted in this group.\n"
        f"📩 Group admin must request authorization from:\n"
        f"👑 {BOT_OWNER_USERNAME}\n\n"
        f"🆔 Your ID: `{uid}`"
    )

def _new_chat_state() -> dict:
    return {
        'current': None, 'current_file': None, 'playing': False, 'paused': False,
        'queue': [], 'loop': False, 'loop_queue': False,
        'start_time': None, 'pause_start': None, 'total_pause': 0,
        'duration': 0, 'volume': 100, 'np_msg_id': None,
    }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  SONG CACHE  (avoid re-downloading same query)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_cache_index: dict = {}     # query_hash -> {file, title, artist, duration, ts}
CACHE_TTL    = 3600 * 2     # 2 hours

def _cache_key(query: str) -> str:
    return hashlib.md5(query.lower().strip().encode()).hexdigest()

def _cache_get(query: str) -> Optional[dict]:
    k = _cache_key(query)
    e = _cache_index.get(k)
    if not e: return None
    if time.time() - e['ts'] > CACHE_TTL: _cache_index.pop(k, None); return None
    if not os.path.exists(e['file']): _cache_index.pop(k, None); return None
    return e

def _cache_put(query: str, result: dict):
    k = _cache_key(query)
    _cache_index[k] = {**result, 'ts': time.time()}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MUSIC SOURCES  (sync, run in thread pool)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _saavn_search_and_dl(query: str) -> Optional[dict]:
    """JioSaavn — best for Bollywood / Hindi / Indian."""
    try:
        r = requests.get(
            f"https://saavn.dev/api/search/songs?query={requests.utils.quote(query)}&limit=5",
            timeout=10
        )
        if not r.ok: return None
        d = r.json()
        if not d.get('success'): return None
        results = d.get('data', {}).get('results', [])
        if not results: return None
        song = results[0]
        dl   = song.get('downloadUrl', [])
        url  = next((x['url'] for x in reversed(dl) if x.get('url')), None)
        if not url: return None

        uid  = uuid.uuid4().hex
        path = os.path.join(TMP_DIR, f"{uid}.mp3")
        r2   = requests.get(url, timeout=30, stream=True)
        r2.raise_for_status()
        with open(path, 'wb') as f:
            for chunk in r2.iter_content(65536):
                if chunk: f.write(chunk)
        if os.path.exists(path) and os.path.getsize(path) > 10_000:
            return {
                'file'    : path,
                'title'   : song.get('name', 'Unknown'),
                'artist'  : song.get('primaryArtists', ''),
                'duration': int(song.get('duration', 0)),
                'source'  : 'saavn',
            }
        clean(path)
    except Exception as e:
        logger.debug(f"saavn: {e}")
    return None


def _soundcloud_dl(query: str) -> Optional[dict]:
    """SoundCloud — International / Nasheeds."""
    uid  = uuid.uuid4().hex
    tmpl = os.path.join(TMP_DIR, f"{uid}.%(ext)s")
    opts = {
        'quiet': True, 'no_warnings': True, 'nocheckcertificate': True,
        'format': 'bestaudio/best', 'outtmpl': tmpl,
        'socket_timeout': 20, 'retries': 2,
        'postprocessors': [{'key': 'FFmpegExtractAudio',
                            'preferredcodec': 'mp3', 'preferredquality': '128'}],
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"scsearch1:{query}", download=True)
            if info and 'entries' in info:
                info = info['entries'][0]
        mp3 = os.path.join(TMP_DIR, f"{uid}.mp3")
        if os.path.exists(mp3) and os.path.getsize(mp3) > 10_000:
            return {
                'file'    : mp3,
                'title'   : (info or {}).get('title', ''),
                'artist'  : (info or {}).get('uploader', ''),
                'duration': int((info or {}).get('duration', 0)),
                'source'  : 'soundcloud',
            }
    except Exception as e:
        logger.debug(f"scloud: {e}")
    for f in os.listdir(TMP_DIR):
        if f.startswith(uid):
            try: os.remove(os.path.join(TMP_DIR, f))
            except: pass
    return None


def _yt_audio_dl(query_or_url: str, is_url: bool = False) -> Optional[dict]:
    """YouTube — absolute fallback."""
    uid  = uuid.uuid4().hex
    tmpl = os.path.join(TMP_DIR, f"{uid}.%(ext)s")
    for player in [['android_creator'], ['android_testsuite'], ['android'], []]:
        opts = {
            'quiet': True, 'no_warnings': True, 'nocheckcertificate': True,
            'format': 'bestaudio/best', 'outtmpl': tmpl,
            'socket_timeout': 25, 'retries': 2,
            'postprocessors': [{'key': 'FFmpegExtractAudio',
                                'preferredcodec': 'mp3', 'preferredquality': '128'}],
        }
        if player: opts['extractor_args'] = {'youtube': {'player_client': player}}
        if os.path.exists(COOKIES_FILE): opts['cookiefile'] = COOKIES_FILE
        target = query_or_url if is_url else f"ytsearch1:{query_or_url}"
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(target, download=True)
                if info and 'entries' in info:
                    info = info['entries'][0]
            mp3 = os.path.join(TMP_DIR, f"{uid}.mp3")
            if os.path.exists(mp3) and os.path.getsize(mp3) > 10_000:
                return {
                    'file'    : mp3,
                    'title'   : (info or {}).get('title', ''),
                    'artist'  : (info or {}).get('uploader', ''),
                    'duration': int((info or {}).get('duration', 0)),
                    'source'  : 'youtube',
                }
        except Exception as e:
            logger.debug(f"yt_audio {player}: {e}")
        for f in os.listdir(TMP_DIR):
            if f.startswith(uid):
                try: os.remove(os.path.join(TMP_DIR, f))
                except: pass
    return None


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
        'socket_timeout': 60, 'retries': 2,
        'merge_output_format': 'mp4',
    }
    if os.path.exists(COOKIES_FILE): opts['cookiefile'] = COOKIES_FILE
    for player in [['android_creator'], ['android_testsuite'], []]:
        if player: opts['extractor_args'] = {'youtube': {'player_client': player}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
            for f in os.listdir(TMP_DIR):
                if f.startswith(uid) and f.endswith('.mp4'):
                    fp = os.path.join(TMP_DIR, f)
                    if os.path.getsize(fp) > 10_000:
                        return {
                            'file': fp, 'is_video': True,
                            'title'   : (info or {}).get('title', ''),
                            'artist'  : (info or {}).get('uploader', ''),
                            'duration': int((info or {}).get('duration', 0)),
                            'source'  : 'youtube',
                        }
        except Exception as e:
            logger.debug(f"yt_video {player} {quality}: {e}")
        for f in os.listdir(TMP_DIR):
            if f.startswith(uid):
                try: os.remove(os.path.join(TMP_DIR, f))
                except: pass
    return None


def _yt_info(url: str) -> dict:
    opts = {'quiet': True, 'no_warnings': True, 'skip_download': True, 'socket_timeout': 15}
    if os.path.exists(COOKIES_FILE): opts['cookiefile'] = COOKIES_FILE
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            i = ydl.extract_info(url, download=False)
            return {'title': i.get('title',''), 'artist': i.get('uploader',''),
                    'duration': int(i.get('duration', 0))}
    except Exception:
        return {'title': '', 'artist': '', 'duration': 0}


def _fetch_lyrics(title: str, artist: str) -> Optional[str]:
    """Fetch lyrics via lyrics.ovh (free, no key needed)."""
    try:
        t = re.sub(r'\(.*?\)|\[.*?\]', '', title).strip()
        a = artist.split(',')[0].strip() if artist else t
        r = requests.get(
            f"https://api.lyrics.ovh/v1/{requests.utils.quote(a)}/{requests.utils.quote(t)}",
            timeout=10
        )
        if r.ok:
            ly = r.json().get('lyrics', '')
            if ly: return ly[:3000]   # cap at 3000 chars for Telegram
    except Exception:
        pass
    return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PARALLEL ASYNC DOWNLOADER  (race all 3 sources)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def _run_in_pool(fn, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_pool, fn, *args)


async def find_parallel(query: str) -> Optional[dict]:
    """Race Saavn / SoundCloud / YouTube — return whichever finishes first."""
    cached = _cache_get(query)
    if cached:
        logger.info(f"Cache hit: {query}")
        return cached

    async def try_saavn():
        try:
            return await asyncio.wait_for(_run_in_pool(_saavn_search_and_dl, query), timeout=25)
        except Exception: return None

    async def try_sc():
        try:
            return await asyncio.wait_for(_run_in_pool(_soundcloud_dl, query), timeout=40)
        except Exception: return None

    async def try_yt():
        try:
            return await asyncio.wait_for(_run_in_pool(_yt_audio_dl, query, False), timeout=50)
        except Exception: return None

    tasks   = [asyncio.create_task(f()) for f in (try_saavn, try_sc, try_yt)]
    result  = None
    pending = set(tasks)

    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for t in done:
            try:
                r = t.result()
                if r:
                    result = r
                    break
            except Exception:
                pass
        if result:
            break

    for t in pending:
        t.cancel()

    if result:
        _cache_put(query, result)
    return result

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  VOICE CHAT HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_player_kb(paused: bool = False, loop: bool = False, loop_q: bool = False) -> InlineKeyboardMarkup:
    pause_lbl = "▶️ Resume" if paused else "⏸ Pause"
    loop_lbl  = "🔁 Loop ✅" if loop else "🔁 Loop"
    lq_lbl    = "🔀 LoopQ ✅" if loop_q else "🔀 LoopQ"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏮ -10s",   callback_data="seek_back"),
            InlineKeyboardButton(pause_lbl,   callback_data="pause_resume"),
            InlineKeyboardButton("⏭ +10s",   callback_data="seek_fwd"),
        ],
        [
            InlineKeyboardButton("⏭ Skip",    callback_data="skip"),
            InlineKeyboardButton("⏹ Stop",    callback_data="stop"),
        ],
        [
            InlineKeyboardButton(loop_lbl,    callback_data="toggle_loop"),
            InlineKeyboardButton(lq_lbl,      callback_data="toggle_loop_queue"),
            InlineKeyboardButton("📋 Queue",  callback_data="show_queue"),
        ],
    ])


def np_text(title: str, artist: str, duration: int, elapsed: float,
            paused: bool, loop: bool, loop_q: bool, queue_len: int,
            source: str = '') -> str:
    bar    = progress_bar(elapsed, duration)
    status = "⏸ Paused" if paused else "▶️ Now Playing"
    src_icon = {'saavn': '🇮🇳', 'soundcloud': '🔶', 'youtube': '🔴'}.get(source, '🎵')
    txt = (
        f"{BRAND}\n{DIVIDER}\n\n"
        f"{status}  {src_icon}\n\n"
        f"🎵 *{title}*\n"
    )
    if artist: txt += f"🎤 {artist}\n"
    txt += f"\n`{dur_str(int(elapsed))}` {bar} `{dur_str(duration)}`\n"
    flags = []
    if loop:   flags.append("🔁 Loop ON")
    if loop_q: flags.append("🔀 Queue Loop ON")
    if flags:  txt += "  ".join(flags) + "\n"
    if queue_len: txt += f"\n📋 *{queue_len} song(s) in queue*\n"
    txt += f"\n_{get_quote()}_"
    return txt


async def vc_play_item(chat_id: int, item: dict, bot, seek_sec: int = 0) -> bool:
    """Play a queue item dict {file, title, artist, duration, source}."""
    fp      = item['file']
    title   = item.get('title', 'Unknown')
    duration = item.get('duration', 0)
    source  = item.get('source', '')

    try:
        try:
            await calls.leave_group_call(chat_id)
            await asyncio.sleep(0.4)
        except Exception:
            pass

        ff = f"-ss {seek_sec}" if seek_sec > 0 else None
        if ff:
            await calls.play(chat_id, MediaStream(fp, ffmpeg_parameters=ff))
        else:
            await calls.play(chat_id, MediaStream(fp))

        ch = active_chats.setdefault(chat_id, _new_chat_state())
        # don't clean file if same file (seek)
        if ch.get('current_file') != fp:
            clean(ch.get('current_file'))
        ch.update({
            'current'     : title,
            'current_file': fp,
            'playing'     : True,
            'paused'      : False,
            'start_time'  : time.time() - seek_sec,
            'pause_start' : None,
            'total_pause' : 0,
            'duration'    : duration,
            'source'      : source,
        })

        # try to set volume
        vol = ch.get('volume', 100)
        try:
            if vol != 100:
                await calls.change_volume_call(chat_id, vol)
        except Exception:
            pass

        return True

    except _pyro_errors.GroupCallForbidden:
        logger.error("GroupCallForbidden — make userbot admin & open VC")
        clean(fp)
        return False
    except Exception as e:
        logger.error(f"vc_play_item: {e}")
        clean(fp)
        return False


async def vc_stop(chat_id: int):
    for fn in ('leave_group_call', 'stop_stream'):
        try:
            await getattr(calls, fn)(chat_id)
        except Exception:
            pass
    ch = active_chats.get(chat_id)
    if ch:
        clean(ch.get('current_file'))
        for q in ch.get('queue', []):
            clean(q.get('file'))
        active_chats[chat_id] = _new_chat_state()


async def vc_pause(chat_id: int) -> bool:
    ch = active_chats.get(chat_id, {})
    if not ch.get('playing') or ch.get('paused'): return False
    try:
        await calls.pause(chat_id)
        ch['paused'] = True
        ch['pause_start'] = time.time()
        return True
    except Exception as e:
        logger.error(f"vc_pause: {e}"); return False


async def vc_resume(chat_id: int) -> bool:
    ch = active_chats.get(chat_id, {})
    if not ch.get('paused'): return False
    try:
        await calls.resume(chat_id)
        if ch.get('pause_start'):
            ch['total_pause'] = ch.get('total_pause', 0) + (time.time() - ch['pause_start'])
        ch['paused'] = False
        ch['pause_start'] = None
        return True
    except Exception as e:
        logger.error(f"vc_resume: {e}"); return False


async def vc_seek(chat_id: int, delta: int, bot) -> bool:
    ch = active_chats.get(chat_id, {})
    if not ch.get('current_file') or not ch.get('current'): return False
    pos     = max(0, int(get_elapsed(chat_id)) + delta)
    dur     = ch.get('duration', 0)
    if dur and pos >= dur: return False
    item    = {
        'file'    : ch['current_file'],
        'title'   : ch['current'],
        'artist'  : ch.get('artist', ''),
        'duration': dur,
        'source'  : ch.get('source', ''),
    }
    return await vc_play_item(chat_id, item, bot, seek_sec=pos)


async def play_next(chat_id: int, bot) -> bool:
    """Pop next item from queue and play it. Returns False if queue empty."""
    ch = active_chats.get(chat_id, _new_chat_state())
    active_chats[chat_id] = ch

    if ch.get('loop') and ch.get('current_file'):
        # replay current
        item = {
            'file'    : ch['current_file'],
            'title'   : ch['current'],
            'artist'  : ch.get('artist', ''),
            'duration': ch.get('duration', 0),
            'source'  : ch.get('source', ''),
        }
        return await vc_play_item(chat_id, item, bot)

    queue = ch.get('queue', [])
    if not queue:
        if ch.get('loop_queue'):
            pass  # nothing to loop
        ch.update({'playing': False, 'current': None, 'current_file': None})
        return False

    item = queue.pop(0)
    if ch.get('loop_queue'):
        queue.append(item)   # push to end for loop
    ch['queue'] = queue

    ok = await vc_play_item(chat_id, item, bot)
    if ok and bot and ch.get('np_msg_id'):
        # send new now-playing message
        try:
            kb = make_player_kb(loop=ch.get('loop', False), loop_q=ch.get('loop_queue', False))
            txt = np_text(
                item['title'], item.get('artist',''), item.get('duration',0),
                0, False, ch.get('loop',False), ch.get('loop_queue',False),
                len(ch.get('queue',[])), item.get('source','')
            )
            await bot.send_message(chat_id, txt, parse_mode='Markdown', reply_markup=kb)
        except Exception:
            pass
    return ok

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  STREAM END CALLBACK  (auto-next in queue)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_tg_bot_ref = None   # set after Application.build()

def _register_stream_end():
    """Register pytgcalls stream-end handler after calls is ready."""
    try:
        from pytgcalls.types import StreamAudioEnded, StreamVideoEnded
        stream_end_types = (StreamAudioEnded, StreamVideoEnded)
    except ImportError:
        stream_end_types = None

    async def _on_stream_end(client, update):
        try:
            cid = update.chat_id
        except AttributeError:
            return
        ch = active_chats.get(cid, {})
        if not ch.get('playing'): return
        await play_next(cid, _tg_bot_ref)

    try:
        if stream_end_types:
            for t in stream_end_types:
                calls.on_stream_end()(lambda c, u: _on_stream_end(c, u))
        else:
            calls.on_stream_end()(_on_stream_end)
    except Exception as e:
        logger.warning(f"stream_end registration: {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  COMMANDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "Friend"
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"Welcome *{name}* 👋\n\n"
        f"I am a Premium Music Bot — powered by Sheikh Burhan.\n\n"
        f"📋 *Core Commands:*\n"
        f"• /play `<name or URL>` — Play / download\n"
        f"• /stop — Stop music & clear queue\n"
        f"• /skip — Skip to next song\n"
        f"• /pause — Pause playback\n"
        f"• /resume — Resume playback\n"
        f"• /queue — View current queue\n"
        f"• /current — Now playing info\n\n"
        f"🎛 *Extra Commands:*\n"
        f"• /volume `<0-200>` — Set volume\n"
        f"• /loop — Toggle loop current song\n"
        f"• /loopqueue — Toggle loop entire queue\n"
        f"• /shuffle — Shuffle the queue\n"
        f"• /clear — Clear queue\n"
        f"• /lyrics — Get lyrics of current song\n"
        f"• /ping — Bot latency\n"
        f"• /myid — Your Telegram ID\n"
        f"• /help — Full help\n\n"
        f"{DIVIDER}\n"
        f"🆔 Your ID: `{uid}`\n\n"
        f"_{get_quote()}_",
        parse_mode='Markdown'
    )


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.full_name or "—"
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"👤 *Name:* {name}\n"
        f"🆔 *Your Telegram ID:*\n`{uid}`\n\n"
        f"_{DIVIDER}_",
        parse_mode='Markdown'
    )


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t0  = time.time()
    msg = await update.message.reply_text("🏓 Pinging...")
    lat = int((time.time() - t0) * 1000)
    await msg.edit_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"🏓 *Pong!*\n"
        f"⚡ Latency: `{lat} ms`\n"
        f"🤖 Status: Running smoothly!\n\n"
        f"_{get_quote()}_",
        parse_mode='Markdown'
    )


async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
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
            f"⏳ YouTube link detected, fetching info...\n\n"
            f"_{get_loading_quote()}_",
            parse_mode='Markdown'
        )
        try:
            info = await asyncio.wait_for(_run_in_pool(_yt_info, yt_url), timeout=20)
        except asyncio.TimeoutError:
            await msg.edit_text(f"{BRAND}\n{DIVIDER}\n\n❌ Timed out fetching video info. Try again.")
            return

        title    = info['title']   or "Unknown"
        artist   = info['artist']  or ""
        duration = info['duration']
        tok      = uuid.uuid4().hex
        pending_video[tok] = {
            'url': yt_url, 'title': title, 'artist': artist,
            'duration': duration, 'chat_id': chat_id, 'private': private,
        }
        kb = [
            [InlineKeyboardButton("🎵 Audio Only",   callback_data=f"q|{tok}|audio")],
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
            f"🎬 *{title}*\n"
            + (f"🎤 {artist}\n" if artist else "")
            + (f"⏱ {dur_str(duration)}\n" if duration else "")
            + f"\n{DIVIDER}\n\n📥 *Select quality:*\n\n_{get_quote()}_",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # ── Keyword search ───────────────────────────────────────────────────────
    msg = await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"🔍 Searching: *{query}*\n\n"
        f"_{get_loading_quote()}_",
        parse_mode='Markdown'
    )

    try:
        result = await asyncio.wait_for(find_parallel(query), timeout=55)
    except asyncio.TimeoutError:
        await msg.edit_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ Search timed out. Please try again or use a more specific name.",
            parse_mode='Markdown'
        )
        return
    except Exception as e:
        await msg.edit_text(f"{BRAND}\n{DIVIDER}\n\n❌ Error: {e}", parse_mode='Markdown')
        return

    if not result:
        await msg.edit_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ Song not found.\n"
            f"Try a different name, spelling, or paste a YouTube link.",
            parse_mode='Markdown'
        )
        return

    fp       = result['file']
    title    = result.get('title') or query
    artist   = result.get('artist', '')
    duration = result.get('duration', 0)
    source   = result.get('source', '')

    if private:
        await msg.edit_text(
            f"{BRAND}\n{DIVIDER}\n\n✅ Found!\n🎵 *{title}*\n\n📤 Sending...\n\n_{get_quote()}_",
            parse_mode='Markdown'
        )
        with open(fp, 'rb') as af:
            await update.message.reply_audio(audio=af, title=title, performer=artist, duration=duration)
        await msg.delete()
        clean(fp)
    else:
        ch     = active_chats.setdefault(chat_id, _new_chat_state())
        src_ic = {'saavn': '🇮🇳', 'soundcloud': '🔶', 'youtube': '🔴'}.get(source, '🎵')

        # if something already playing → add to queue
        if ch.get('playing'):
            item = {'file': fp, 'title': title, 'artist': artist, 'duration': duration, 'source': source}
            ch['queue'].append(item)
            pos = len(ch['queue'])
            await msg.edit_text(
                f"{BRAND}\n{DIVIDER}\n\n"
                f"✅ Added to Queue #{pos}\n\n"
                f"{src_ic} *{title}*\n"
                + (f"🎤 {artist}\n" if artist else "")
                + (f"⏱ {dur_str(duration)}\n" if duration else "")
                + f"\n_{get_quote()}_",
                parse_mode='Markdown'
            )
            return

        # play now
        item = {'file': fp, 'title': title, 'artist': artist, 'duration': duration, 'source': source}
        kb   = make_player_kb(loop=ch.get('loop', False), loop_q=ch.get('loop_queue', False))
        np   = np_text(title, artist, duration, 0, False,
                       ch.get('loop', False), ch.get('loop_queue', False),
                       len(ch.get('queue', [])), source)
        np_msg = await msg.edit_text(np, parse_mode='Markdown', reply_markup=kb)
        ch['np_msg_id'] = np_msg.message_id

        ok = await vc_play_item(chat_id, item, context.bot)
        if not ok:
            await np_msg.edit_text(
                f"{BRAND}\n{DIVIDER}\n\n"
                f"❌ Could not join Voice Chat.\n"
                f"Ensure the bot is admin and Voice Chat is active.\n\n"
                f"📩 Contact {BOT_OWNER_USERNAME} for help.",
                parse_mode='Markdown'
            )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    await vc_stop(update.effective_chat.id)
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n⏹ *Music stopped. Queue cleared.*",
        parse_mode='Markdown'
    )


async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    chat_id = update.effective_chat.id
    ch      = active_chats.get(chat_id, {})
    if not ch.get('playing'):
        await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n❌ Nothing is playing.")
        return
    # stop current, then play next
    try: await calls.leave_group_call(chat_id)
    except: pass
    clean(ch.get('current_file'))
    ch['playing']      = False
    ch['current']      = None
    ch['current_file'] = None
    ok = await play_next(chat_id, context.bot)
    if not ok:
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n⏭ Skipped. Queue is now empty.",
            parse_mode='Markdown'
        )


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    ok = await vc_pause(update.effective_chat.id)
    txt = "⏸ *Paused.*" if ok else "❌ Nothing to pause."
    await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n{txt}", parse_mode='Markdown')


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    ok = await vc_resume(update.effective_chat.id)
    txt = "▶️ *Resumed.*" if ok else "❌ Nothing to resume."
    await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n{txt}", parse_mode='Markdown')


async def cmd_current(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    chat_id = update.effective_chat.id
    ch      = active_chats.get(chat_id, {})
    cur     = ch.get('current')
    if not cur:
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n❌ Nothing is playing right now.",
            parse_mode='Markdown'
        )
        return
    elapsed = get_elapsed(chat_id)
    kb      = make_player_kb(paused=ch.get('paused', False),
                             loop=ch.get('loop', False), loop_q=ch.get('loop_queue', False))
    txt = np_text(
        cur, ch.get('artist', ''), ch.get('duration', 0),
        elapsed, ch.get('paused', False),
        ch.get('loop', False), ch.get('loop_queue', False),
        len(ch.get('queue', [])), ch.get('source', '')
    )
    await update.message.reply_text(txt, parse_mode='Markdown', reply_markup=kb)


async def cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    chat_id = update.effective_chat.id
    ch      = active_chats.get(chat_id, {})
    cur     = ch.get('current')
    queue   = ch.get('queue', [])

    if not cur and not queue:
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n❌ Queue is empty.", parse_mode='Markdown'
        )
        return

    txt = f"{BRAND}\n{DIVIDER}\n\n"
    if cur:
        elapsed = get_elapsed(chat_id)
        bar     = progress_bar(elapsed, ch.get('duration', 0))
        state   = "⏸ Paused" if ch.get('paused') else "▶️ Playing"
        txt += f"{state}\n🎵 *{cur}*\n`{dur_str(int(elapsed))}` {bar} `{dur_str(ch.get('duration',0))}`\n\n"

    if queue:
        txt += f"📋 *Queue ({len(queue)} songs):*\n"
        for i, item in enumerate(queue[:15], 1):
            txt += f"`{i}.` {item.get('title','?')} — {dur_str(item.get('duration',0))}\n"
        if len(queue) > 15:
            txt += f"_...and {len(queue)-15} more_\n"
    else:
        txt += "_Queue is empty — use /play to add songs._\n"

    txt += f"\n_{get_quote()}_"
    await update.message.reply_text(txt, parse_mode='Markdown')


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    ch = active_chats.setdefault(update.effective_chat.id, _new_chat_state())
    for item in ch.get('queue', []):
        clean(item.get('file'))
    ch['queue'] = []
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n🗑 *Queue cleared.*",
        parse_mode='Markdown'
    )


async def cmd_shuffle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    ch = active_chats.setdefault(update.effective_chat.id, _new_chat_state())
    q  = ch.get('queue', [])
    if not q:
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n❌ Queue is empty.", parse_mode='Markdown'
        )
        return
    random.shuffle(q)
    ch['queue'] = q
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n🔀 *Queue shuffled!* {len(q)} songs in random order.",
        parse_mode='Markdown'
    )


async def cmd_loop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    ch = active_chats.setdefault(update.effective_chat.id, _new_chat_state())
    ch['loop'] = not ch.get('loop', False)
    state = "✅ ON" if ch['loop'] else "❌ OFF"
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n🔁 *Loop current song: {state}*",
        parse_mode='Markdown'
    )


async def cmd_loop_queue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    ch = active_chats.setdefault(update.effective_chat.id, _new_chat_state())
    ch['loop_queue'] = not ch.get('loop_queue', False)
    state = "✅ ON" if ch['loop_queue'] else "❌ OFF"
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n🔀 *Loop entire queue: {state}*",
        parse_mode='Markdown'
    )


async def cmd_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ Usage: `/volume <0-200>`\n"
            f"Default: 100 | Max: 200",
            parse_mode='Markdown'
        )
        return
    vol     = max(0, min(200, int(context.args[0])))
    chat_id = update.effective_chat.id
    ch      = active_chats.setdefault(chat_id, _new_chat_state())
    ch['volume'] = vol
    try:
        await calls.change_volume_call(chat_id, vol)
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n🔊 *Volume set to {vol}%*",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n⚠️ Volume saved to {vol}% (applies on next track).\n_Reason: {e}_",
            parse_mode='Markdown'
        )


async def cmd_lyrics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    ch = active_chats.get(update.effective_chat.id, {})
    # allow custom query: /lyrics <song name>
    if context.args:
        title  = ' '.join(context.args)
        artist = ''
    else:
        title  = ch.get('current', '')
        artist = ch.get('artist', '')

    if not title:
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ Nothing is playing.\n"
            f"Usage: `/lyrics <song name>`",
            parse_mode='Markdown'
        )
        return

    msg = await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n🔍 Fetching lyrics for *{title}*...", parse_mode='Markdown'
    )
    lyrics = await asyncio.wait_for(
        _run_in_pool(_fetch_lyrics, title, artist), timeout=15
    )
    if lyrics:
        header = f"{BRAND}\n{DIVIDER}\n\n🎤 *{title}*\n\n"
        # Telegram message limit 4096 chars
        body   = lyrics[:4000 - len(header)]
        await msg.edit_text(header + body, parse_mode='Markdown')
    else:
        await msg.edit_text(
            f"{BRAND}\n{DIVIDER}\n\n❌ Lyrics not found for *{title}*.\n"
            f"Try: `/lyrics <exact song name>`",
            parse_mode='Markdown'
        )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"📋 *All Commands:*\n\n"
        f"🎵 `/play <name or URL>` — Play in VC or download as audio/video\n"
        f"⏹ `/stop` — Stop & clear everything\n"
        f"⏭ `/skip` — Skip to next song in queue\n"
        f"⏸ `/pause` — Pause playback\n"
        f"▶️ `/resume` — Resume playback\n"
        f"📋 `/queue` — Show current queue\n"
        f"🗑 `/clear` — Clear queue (keeps current)\n"
        f"🔀 `/shuffle` — Shuffle the queue\n"
        f"🔁 `/loop` — Toggle loop current song\n"
        f"🔄 `/loopqueue` — Toggle loop entire queue\n"
        f"🔊 `/volume <0-200>` — Set volume\n"
        f"🎤 `/lyrics [song]` — Get lyrics\n"
        f"▶️ `/current` — Now playing details\n"
        f"🏓 `/ping` — Bot latency\n"
        f"🆔 `/myid` — Your Telegram ID\n\n"
        f"{DIVIDER}\n"
        f"🎛 *Inline Controls (group):*\n"
        f"⏮-10s | ⏸Pause | ⏭+10s | ⏭Skip | ⏹Stop | 🔁Loop | 🔀LoopQ | 📋Queue\n\n"
        f"_In groups: streams in Voice Chat_\n"
        f"_In DM: sends audio/video file_\n\n"
        f"_{get_quote()}_",
        parse_mode='Markdown'
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CALLBACK HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def _edit_safe(q, text, kb=None, pm='Markdown'):
    try:
        if kb:
            await q.edit_message_text(text, parse_mode=pm, reply_markup=kb)
        else:
            await q.edit_message_text(text, parse_mode=pm)
    except TgBadRequest:
        pass


async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q       = update.callback_query
    data    = q.data
    chat_id = update.effective_chat.id
    auth, reason = check_auth(update)

    await q.answer()

    # ── Stop ────────────────────────────────────────────────────────────────
    if data == "stop":
        if not auth:
            await q.answer(f"❌ Not authorized! Your ID: {update.effective_user.id}", show_alert=True)
            return
        await vc_stop(chat_id)
        await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n⏹ *Music stopped. Queue cleared.*")
        return

    # ── Skip ────────────────────────────────────────────────────────────────
    if data == "skip":
        if not auth:
            await q.answer(f"❌ Not authorized! Your ID: {update.effective_user.id}", show_alert=True)
            return
        ch = active_chats.get(chat_id, {})
        try: await calls.leave_group_call(chat_id)
        except: pass
        clean(ch.get('current_file'))
        ch['playing'] = False; ch['current'] = None; ch['current_file'] = None
        ok = await play_next(chat_id, context.bot)
        if not ok:
            await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n⏭ Skipped. Queue is empty.")
        return

    # ── Pause / Resume ───────────────────────────────────────────────────────
    if data == "pause_resume":
        if not auth:
            await q.answer(f"❌ Not authorized! Your ID: {update.effective_user.id}", show_alert=True)
            return
        ch = active_chats.get(chat_id, {})
        if ch.get('paused'):
            ok = await vc_resume(chat_id)
            action = "▶️ Resumed" if ok else None
        else:
            ok = await vc_pause(chat_id)
            action = "⏸ Paused" if ok else None
        if not ok:
            await q.answer("Nothing is playing.", show_alert=True); return
        cur = ch.get('current', 'Unknown')
        elapsed = get_elapsed(chat_id)
        paused  = ch.get('paused', False)
        kb  = make_player_kb(paused=paused, loop=ch.get('loop',False), loop_q=ch.get('loop_queue',False))
        txt = np_text(cur, ch.get('artist',''), ch.get('duration',0),
                      elapsed, paused, ch.get('loop',False), ch.get('loop_queue',False),
                      len(ch.get('queue',[])), ch.get('source',''))
        await _edit_safe(q, txt, kb)
        return

    # ── Seek ────────────────────────────────────────────────────────────────
    if data in ("seek_fwd", "seek_back"):
        if not auth:
            await q.answer(f"❌ Not authorized! Your ID: {update.effective_user.id}", show_alert=True)
            return
        delta = +10 if data == "seek_fwd" else -10
        ch    = active_chats.get(chat_id, {})
        ok    = await vc_seek(chat_id, delta, context.bot)
        if ok:
            cur = ch.get('current', 'Unknown')
            elapsed = get_elapsed(chat_id)
            kb  = make_player_kb(paused=ch.get('paused',False),
                                 loop=ch.get('loop',False), loop_q=ch.get('loop_queue',False))
            txt = np_text(cur, ch.get('artist',''), ch.get('duration',0),
                          elapsed, ch.get('paused',False),
                          ch.get('loop',False), ch.get('loop_queue',False),
                          len(ch.get('queue',[])), ch.get('source',''))
            await _edit_safe(q, txt, kb)
        else:
            await q.answer("Cannot seek right now.", show_alert=True)
        return

    # ── Toggle Loop ─────────────────────────────────────────────────────────
    if data == "toggle_loop":
        if not auth:
            await q.answer(f"❌ Not authorized!", show_alert=True); return
        ch = active_chats.setdefault(chat_id, _new_chat_state())
        ch['loop'] = not ch.get('loop', False)
        cur = ch.get('current','Unknown'); elapsed = get_elapsed(chat_id)
        kb  = make_player_kb(paused=ch.get('paused',False), loop=ch['loop'], loop_q=ch.get('loop_queue',False))
        txt = np_text(cur, ch.get('artist',''), ch.get('duration',0),
                      elapsed, ch.get('paused',False), ch['loop'], ch.get('loop_queue',False),
                      len(ch.get('queue',[])), ch.get('source',''))
        await _edit_safe(q, txt, kb)
        return

    # ── Toggle Loop Queue ───────────────────────────────────────────────────
    if data == "toggle_loop_queue":
        if not auth:
            await q.answer(f"❌ Not authorized!", show_alert=True); return
        ch = active_chats.setdefault(chat_id, _new_chat_state())
        ch['loop_queue'] = not ch.get('loop_queue', False)
        cur = ch.get('current','Unknown'); elapsed = get_elapsed(chat_id)
        kb  = make_player_kb(paused=ch.get('paused',False),
                             loop=ch.get('loop',False), loop_q=ch['loop_queue'])
        txt = np_text(cur, ch.get('artist',''), ch.get('duration',0),
                      elapsed, ch.get('paused',False), ch.get('loop',False), ch['loop_queue'],
                      len(ch.get('queue',[])), ch.get('source',''))
        await _edit_safe(q, txt, kb)
        return

    # ── Show Queue ──────────────────────────────────────────────────────────
    if data == "show_queue":
        ch    = active_chats.get(chat_id, {})
        cur   = ch.get('current')
        queue = ch.get('queue', [])
        txt   = f"{BRAND}\n{DIVIDER}\n\n"
        if cur:
            elapsed = get_elapsed(chat_id)
            bar     = progress_bar(elapsed, ch.get('duration',0))
            txt    += f"▶️ *{cur}*\n`{dur_str(int(elapsed))}` {bar} `{dur_str(ch.get('duration',0))}`\n\n"
        if queue:
            txt += f"📋 *Queue ({len(queue)}):*\n"
            for i, item in enumerate(queue[:10], 1):
                txt += f"`{i}.` {item.get('title','?')} — {dur_str(item.get('duration',0))}\n"
        else:
            txt += "_Queue empty_"
        await q.answer(); await q.message.reply_text(txt, parse_mode='Markdown')
        return

    # ── Quality selection q|token|quality ────────────────────────────────────
    if data.startswith("q|"):
        parts = data.split("|")
        if len(parts) != 3: return
        _, tok, quality = parts
        pv = pending_video.get(tok)
        if not pv:
            await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n❌ Request expired. Please /play again.")
            return
        if not auth:
            await q.answer(f"❌ Not authorized! Your ID: {update.effective_user.id}", show_alert=True)
            return

        url      = pv['url'];  title    = pv['title']
        artist   = pv['artist']; duration = pv['duration']
        private  = pv.get('private', False)

        label = {'audio':'🎵 Audio','360p':'📹 360p','480p':'📹 480p',
                 '720p':'📹 720p','1080p':'📹 1080p','best':'📹 Best'}.get(quality, quality)

        await _edit_safe(q,
            f"{BRAND}\n{DIVIDER}\n\n"
            f"⬇️ Downloading ({label})\n🎵 *{title}*\n"
            + (f"🎤 {artist}\n" if artist else "")
            + f"\n_{get_loading_quote()}_"
        )

        def do_dl():
            if quality == 'audio': return _yt_audio_dl(url, is_url=True)
            return _yt_video_dl(url, quality)

        try:
            result = await asyncio.wait_for(_run_in_pool(do_dl), timeout=120)
        except asyncio.TimeoutError:
            await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n❌ Download timed out. Try a lower quality.")
            pending_video.pop(tok, None); return
        pending_video.pop(tok, None)

        if not result:
            await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n❌ Download failed. Try another quality.")
            return

        fp      = result['file']
        is_vid  = result.get('is_video', False)
        size_mb = os.path.getsize(fp) / (1024 * 1024)

        if size_mb > 1900:
            clean(fp)
            await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n❌ File too large ({size_mb:.0f} MB). Choose lower quality.")
            return

        await _edit_safe(q,
            f"{BRAND}\n{DIVIDER}\n\n✅ *{title}*\n📤 Sending... ({size_mb:.1f} MB)\n\n_{get_quote()}_"
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
            try: await q.delete_message()
            except: pass
        except Exception as e:
            logger.error(f"send: {e}")
            await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n❌ Send error: {e}")
        finally:
            clean(fp)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  MAIN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def main():
    global pyrogram_app, calls, _tg_bot_ref

    pyrogram_app = Client(
        "sbmusic", api_id=API_ID, api_hash=API_HASH,
        session_string=SESSION_STRING
    )
    calls = PyTgCalls(pyrogram_app)
    await pyrogram_app.start()
    await calls.start()
    _register_stream_end()

    app = Application.builder().token(BOT_TOKEN).build()
    _tg_bot_ref = app.bot

    # ── Register commands ────────────────────────────────────────────────────
    app.add_handler(CommandHandler(["start"],              cmd_start))
    app.add_handler(CommandHandler(["play"],               cmd_play))
    app.add_handler(CommandHandler(["stop"],               cmd_stop))
    app.add_handler(CommandHandler(["skip"],               cmd_skip))
    app.add_handler(CommandHandler(["pause"],              cmd_pause))
    app.add_handler(CommandHandler(["resume"],             cmd_resume))
    app.add_handler(CommandHandler(["current", "np"],      cmd_current))
    app.add_handler(CommandHandler(["queue", "q"],         cmd_queue))
    app.add_handler(CommandHandler(["clear"],              cmd_clear))
    app.add_handler(CommandHandler(["shuffle"],            cmd_shuffle))
    app.add_handler(CommandHandler(["loop"],               cmd_loop))
    app.add_handler(CommandHandler(["loopqueue", "lq"],    cmd_loop_queue))
    app.add_handler(CommandHandler(["volume", "vol"],      cmd_volume))
    app.add_handler(CommandHandler(["lyrics", "ly"],       cmd_lyrics))
    app.add_handler(CommandHandler(["ping"],               cmd_ping))
    app.add_handler(CommandHandler(["myid"],               cmd_myid))
    app.add_handler(CommandHandler(["help"],               cmd_help))
    app.add_handler(CallbackQueryHandler(cb_handler))

    print("━" * 50)
    print("  SHEIKH BURHAN MUSIC BOT v3.0 — STARTED")
    print("━" * 50)

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
        try: await calls.stop()
        except: pass
        try: await pyrogram_app.stop()
        except: pass


if __name__ == "__main__":
    asyncio.run(main())
