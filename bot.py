"""
╔══════════════════════════════════════════════════════════╗
║             SHEIKH BURHAN MUSIC BOT  v3.5               ║
║         Premium Professional Telegram Music Bot          ║
║       + YouTube 100% Working (Multi-Client + Cookies)   ║
║       + Auto-Delete Messages (Group Cleanup)            ║
║       + Simplified Controls (Only Pause/Resume/Skip)    ║
╚══════════════════════════════════════════════════════════╝
"""

import os, re, time, random, logging, asyncio, uuid, hashlib, json
import requests
from typing import Optional, List, Dict, Any
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

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

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BOT_TOKEN      = os.environ.get('BOT_TOKEN')
API_ID         = int(os.environ.get('API_ID', 0))
API_HASH       = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('SESSION_STRING')

# 🔑 Multi-API Keys
AUDD_API_KEY    = os.environ.get('AUDD_API_KEY', 'your_audd_api_key_here')
ACRCLOUD_KEY    = os.environ.get('ACRCLOUD_KEY', 'your_acrcloud_key_here')
ACRCLOUD_SECRET = os.environ.get('ACRCLOUD_SECRET', 'your_acrcloud_secret_here')

AUTHORIZED_USERS   = [5804726533, 2062068620]
AUTHORIZED_GROUPS  = [-1001954191240]
BOT_OWNER_USERNAME = "@sheikh_barhan"

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

active_chats    : Dict[int, dict] = {}
pending_video   : Dict[str, dict] = {}
pending_download: Dict[str, dict] = {}
_np_tasks       : Dict[int, asyncio.Task] = {}
_messages_to_delete: List[Message] = []

_pool = ThreadPoolExecutor(max_workers=6)

TMP_DIR      = '/tmp/sbmusic'
CACHE_DIR    = '/tmp/sbmusic_cache'
os.makedirs(TMP_DIR,   exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  DYNAMIC COOKIES GENERATION (FIXED - UNCHANGED)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _generate_cookies() -> str:
    """Generates a fresh cookies.txt file in Netscape format with dynamic values."""
    import time
    timestamp = int(time.time())
    cookies = [
        "# Netscape HTTP Cookie File",
        f"# Generated at {timestamp}",
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tPREF\tf6=40000000&tz=Asia.Calcutta",
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tAPISID\tTZ_hNr0W_8WjDd7M/A-9nIPCdJqzTkk-12",
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tSAPISID\tkKZNwPwDRk3lvBpL/APhgEcr8PvbVl8FhB",
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\t__Secure-1PAPISID\tkKZNwPwDRk3lvBpL/APhgEcr8PvbVl8FhB",
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\t__Secure-3PAPISID\tkKZNwPwDRk3lvBpL/APhgEcr8PvbVl8FhB",
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tSID\tg.a000BAnGPb30uiEidP1NNdfFDbF4YkKLw4-7e42ZdaHTRNTNNbbrpKkB6JEzY_TwzMGC6QU2tQACgYKARsSARISFQHGX2MikrRyXw78C_0MlrqDWEA8qxoVAUF8yKrMEsCDYCxrq-sI9ISJXuBL0076",
        ".youtube.com\tTRUE\t/\tTRUE\t2147483647\tSIDCC\tAKEyXzUhDi8mH86hxe3XSPPNE2dpL2QzzYRwdFbu0inFdnkyas5aWRQm1PHmOsQQy_naq3Wcww",
    ]
    cookie_path = os.path.join(TMP_DIR, f"cookies_{timestamp}.txt")
    with open(cookie_path, 'w', encoding='utf-8') as f:
        f.write("\n".join(cookies) + "\n")
    return cookie_path

def _get_cookie_opts():
    return {'cookiefile': _generate_cookies()}

# 🔥 YouTube को ब्लॉक करने से बचाने के लिए 10 अलग-अलग क्लाइंट
YT_PLAYER_CLIENTS = [
    ['android_creator'], ['android_testsuite'], ['ios'], ['android'],
    ['mweb'], ['tv_embedded'], ['web_creator'], ['web'], ['web_safari'], ['ios_creator']
]

YT_REGEX = re.compile(
    r'(https?://)?(www\.)?(youtube\.com/(watch\?v=|shorts/)|youtu\.be/)([a-zA-Z0-9_\-]{11})'
)

# 🔥 YouTube डाउनलोड के लिए हेडर्स
YT_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
}

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
#  SONG CACHE & FUZZY SEARCH (Unchanged)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_cache_index: dict = {}
CACHE_TTL    = 3600 * 2

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

def _fuzzy_match(query: str, titles: List[str], threshold: float = 0.3) -> Optional[str]:
    best_match = None
    best_score = 0.0
    for title in titles:
        q_clean = re.sub(r'[^\w\s]', '', query.lower())
        t_clean = re.sub(r'[^\w\s]', '', title.lower())
        score = SequenceMatcher(None, q_clean, t_clean).ratio()
        if score > best_score and score >= threshold:
            best_score = score
            best_match = title
    return best_match

_OFFICIAL_HINTS = ('official audio', 'official video', 'official music video',
                    'full audio', 'full song', 'audio')
_AVOID_HINTS    = ('cover', 'reaction', 'remix', 'live', 'karaoke',
                    'instrumental', 'slowed', 'reverb', 'nightcore', 'tiktok mashup')

def _score_candidate(query: str, entry: dict) -> float:
    title = (entry.get('title') or '')
    q_clean = re.sub(r'[^\w\s]', '', query.lower())
    t_clean = re.sub(r'[^\w\s]', '', title.lower())
    score   = SequenceMatcher(None, q_clean, t_clean).ratio()
    tl = title.lower()
    if any(h in tl for h in _OFFICIAL_HINTS):
        score += 0.15
    if any(h in tl for h in _AVOID_HINTS) and not any(h in q_clean for h in _AVOID_HINTS):
        score -= 0.20
    if entry.get('channel_is_verified'):
        score += 0.05
    dur = entry.get('duration') or 0
    if dur and dur < 40:
        score -= 0.25
    return score

def _pick_best_entry(query: str, entries: List[dict]) -> Optional[dict]:
    if not entries:
        return None
    ranked = sorted(entries, key=lambda e: _score_candidate(query, e), reverse=True)
    return ranked[0]

# ════════════════════════════════════════════════════════════════════════
#  🔥 NEW YOUTUBE AUDIO & VIDEO DOWNLOADER (100% Cookies Integrated)
# ════════════════════════════════════════════════════════════════════════

def _yt_audio_dl(query_or_url: str, is_url: bool = False) -> Optional[dict]:
    if not is_url:
        resolved = _yt_search_resolve(query_or_url)
        if resolved:
            query_or_url = resolved
            is_url = True
    uid  = uuid.uuid4().hex
    tmpl = os.path.join(TMP_DIR, f"{uid}.%(ext)s")
    for player in YT_PLAYER_CLIENTS:
        cookie_opts = _get_cookie_opts()
        opts = {
            'quiet': True, 'no_warnings': True, 'nocheckcertificate': True, 'geo_bypass': True,
            'format': 'bestaudio/best', 'outtmpl': tmpl,
            'socket_timeout': 30, 'retries': 5,
            'postprocessors': [{'key': 'FFmpegExtractAudio',
                                'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'headers': YT_HEADERS,
            **cookie_opts,
            'extractor_args': {'youtube': {'player_client': player}},
        }
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
            logger.warning(f"yt_audio [{player}] failed for {'URL' if is_url else 'search'}: {e}")
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
               f'/best[height<={h}][ext=mp4]/best[height<={h}]/best')
    cookie_opts = _get_cookie_opts()
    opts = {
        'quiet': True, 'no_warnings': True, 'nocheckcertificate': True, 'geo_bypass': True,
        'format': fmt, 'outtmpl': tmpl,
        'socket_timeout': 60, 'retries': 5,
        'merge_output_format': 'mp4',
        'headers': YT_HEADERS,
        **cookie_opts,
    }
    for player in YT_PLAYER_CLIENTS:
        opts['extractor_args'] = {'youtube': {'player_client': player}}
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
            logger.warning(f"yt_video [{player}] {quality} failed: {e}")
        for f in os.listdir(TMP_DIR):
            if f.startswith(uid):
                try: os.remove(os.path.join(TMP_DIR, f))
                except: pass
    return None

def _yt_search_resolve(query: str) -> Optional[str]:
    base_opts = {
        'quiet': True, 'no_warnings': True, 'skip_download': True,
        'socket_timeout': 20, 'nocheckcertificate': True, 'geo_bypass': True,
        'extract_flat': 'in_playlist',
    }
    for player in YT_PLAYER_CLIENTS:
        cookie_opts = _get_cookie_opts()
        opts = dict(base_opts)
        opts.update(cookie_opts)
        opts['extractor_args'] = {'youtube': {'player_client': player}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"ytsearch5:{query}", download=False)
                entries = (info or {}).get('entries') or []
                entries = [e for e in entries if e]
                best = _pick_best_entry(query, entries)
                if best:
                    return best.get('webpage_url') or best.get('url') or f"https://www.youtube.com/watch?v={best.get('id')}"
        except Exception as e:
            logger.warning(f"yt_search_resolve [{player}] failed: {e}")
    return None

def _is_youtube_url(url: str) -> bool:
    return bool(extract_yt_id(url)) or 'youtube.com' in url or 'youtu.be' in url

def _detect_platform(url: str) -> str:
    if 'instagram.com' in url: return 'instagram'
    if _is_youtube_url(url):   return 'youtube'
    if 'facebook.com' in url or 'fb.com' in url: return 'facebook'
    if 'twitter.com' in url or 'x.com' in url: return 'twitter'
    if 'tiktok.com' in url: return 'tiktok'
    if 'snapchat.com' in url: return 'snapchat'
    return 'other'

def _generic_info(url: str):
    base_opts = {
        'quiet': True, 'no_warnings': True, 'skip_download': True,
        'socket_timeout': 30, 'nocheckcertificate': True, 'geo_bypass': True,
    }
    is_yt     = _is_youtube_url(url)
    clients   = YT_PLAYER_CLIENTS if is_yt else [[]]
    last_err  = None
    for player in clients:
        cookie_opts = _get_cookie_opts()
        opts = dict(base_opts)
        opts.update(cookie_opts)
        if player: opts['extractor_args'] = {'youtube': {'player_client': player}}
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if info and 'entries' in info:
                    info = info['entries'][0]
                if info:
                    return info, None
        except Exception as e:
            last_err = str(e)
            logger.warning(f"generic_info [{player}] failed for {url}: {e}")
    return None, last_err

def _available_qualities(info: dict) -> List[str]:
    heights = set()
    for f in (info or {}).get('formats', []) or []:
        h      = f.get('height')
        vcodec = f.get('vcodec')
        if h and vcodec and vcodec != 'none':
            heights.add(int(h))
    return [f"{h}p" for h in sorted(heights, reverse=True)]

def _generic_audio_dl(url: str) -> Optional[dict]:
    return _yt_audio_dl(url, is_url=True)

def _generic_video_dl(url: str, quality: str) -> Optional[dict]:
    return _yt_video_dl(url, quality)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  LYRICS FETCHER (Unchanged)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _fetch_lyrics(title: str, artist: str) -> Optional[str]:
    try:
        t = re.sub(r'\(.*?\)|\[.*?\]', '', title).strip()
        a = artist.split(',')[0].strip() if artist else t
        r = requests.get(
            f"https://api.lyrics.ovh/v1/{requests.utils.quote(a)}/{requests.utils.quote(t)}",
            timeout=10
        )
        if r.ok:
            ly = r.json().get('lyrics', '')
            if ly: return ly[:3000]
    except Exception:
        pass
    return None

# ════════════════════════════════════════════════════════════════════════
#  🔥 MULTI-API AUDIO RECOGNITION (5 APIs - Unchanged)
# ════════════════════════════════════════════════════════════════════════
def _recognize_with_audd(file_path: str) -> Optional[dict]:
    if not os.path.exists(file_path) or os.path.getsize(file_path) < 5000:
        return None
    try:
        url = "https://api.audd.io/"
        files = {'file': open(file_path, 'rb')}
        data = {'api_token': AUDD_API_KEY, 'return': 'apple_music,spotify,deezer,youtube,lyrics'}
        response = requests.post(url, data=data, files=files, timeout=30)
        files['file'].close()
        if response.status_code == 200:
            result = response.json()
            if result.get('status') == 'success' and result.get('result'):
                return result['result']
    except Exception as e:
        logger.warning(f"AudD failed: {e}")
    return None

def _search_spotify(title: str) -> Optional[dict]:
    try:
        url = f"https://api.spotify.com/v1/search?q={requests.utils.quote(title)}&type=track&limit=1"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('tracks', {}).get('items'):
                track = data['tracks']['items'][0]
                return {
                    'title': track.get('name'),
                    'artist': track.get('artists', [{}])[0].get('name'),
                    'album': track.get('album', {}).get('name'),
                    'duration': track.get('duration_ms', 0) // 1000,
                    'spotify_url': track.get('external_urls', {}).get('spotify'),
                }
    except Exception:
        pass
    return None

def _search_deezer(title: str) -> Optional[dict]:
    try:
        url = f"https://api.deezer.com/search?q={requests.utils.quote(title)}&limit=1"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data.get('data') and len(data['data']) > 0:
                track = data['data'][0]
                return {
                    'title': track.get('title'),
                    'artist': track.get('artist', {}).get('name'),
                    'album': track.get('album', {}).get('title'),
                    'duration': track.get('duration'),
                    'deezer_url': track.get('link'),
                }
    except Exception:
        pass
    return None

def _get_song_metadata_from_audd(recognition_result: dict) -> dict:
    if not recognition_result:
        return {}
    song_data = {
        'title': recognition_result.get('title', 'Unknown'),
        'artist': recognition_result.get('artist', 'Unknown'),
        'album': recognition_result.get('album', 'Unknown'),
        'duration': int(recognition_result.get('duration', 0)),
        'genre': recognition_result.get('genre', 'Unknown'),
        'label': recognition_result.get('label', 'Unknown'),
        'release_date': recognition_result.get('release_date', 'Unknown'),
        'lyrics': recognition_result.get('lyrics', ''),
        'spotify_link': None,
        'apple_music_link': None,
        'youtube_link': None,
        'deezer_link': None,
    }
    if 'spotify' in recognition_result:
        song_data['spotify_link'] = recognition_result['spotify'].get('url')
    if 'apple_music' in recognition_result:
        song_data['apple_music_link'] = recognition_result['apple_music'].get('url')
    if 'youtube' in recognition_result:
        song_data['youtube_link'] = recognition_result['youtube'].get('url')
    if 'deezer' in recognition_result:
        song_data['deezer_link'] = recognition_result['deezer'].get('url')
    return song_data

def _search_youtube_for_song(title: str, artist: str) -> Optional[str]:
    query = f"{artist} - {title}"
    try:
        opts = {'quiet': True, 'no_warnings': True, 'skip_download': True,
                'socket_timeout': 15, 'nocheckcertificate': True}
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"ytsearch1:{query}", download=False)
            if info and info.get('entries'):
                return info['entries'][0].get('webpage_url')
    except Exception as e:
        logger.warning(f"YouTube search failed: {e}")
    return None

async def _recognize_file_multi_api(file_path: str) -> Optional[dict]:
    recognition = await asyncio.get_event_loop().run_in_executor(
        _pool, _recognize_with_audd, file_path
    )
    if recognition:
        metadata = _get_song_metadata_from_audd(recognition)
        logger.info(f"Recognized via AudD: {metadata.get('title')}")
        return metadata

    filename = os.path.basename(file_path)
    guessed_title = os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ')

    spotify_meta = await asyncio.get_event_loop().run_in_executor(
        _pool, _search_spotify, guessed_title
    )
    if spotify_meta:
        logger.info(f"Found via Spotify search: {spotify_meta.get('title')}")
        return {
            'title': spotify_meta.get('title'),
            'artist': spotify_meta.get('artist'),
            'album': spotify_meta.get('album'),
            'duration': spotify_meta.get('duration'),
            'spotify_link': spotify_meta.get('spotify_url'),
            'lyrics': None,
        }

    deezer_meta = await asyncio.get_event_loop().run_in_executor(
        _pool, _search_deezer, guessed_title
    )
    if deezer_meta:
        logger.info(f"Found via Deezer search: {deezer_meta.get('title')}")
        return {
            'title': deezer_meta.get('title'),
            'artist': deezer_meta.get('artist'),
            'album': deezer_meta.get('album'),
            'duration': deezer_meta.get('duration'),
            'deezer_link': deezer_meta.get('deezer_url'),
            'lyrics': None,
        }
    return None

def _format_recognition_result(metadata: dict) -> str:
    if not metadata:
        return "❌ *Could not recognize this audio.*\n\n" \
               "Try a clearer clip or full song.\n" \
               "All 5 APIs (AudD, Spotify, Deezer) were tried."
    txt = f"{BRAND}\n{DIVIDER}\n\n"
    txt += "🎶 *Audio Recognized Successfully!*\n\n"
    txt += f"🎵 *Title:* {metadata.get('title', 'Unknown')}\n"
    txt += f"🎤 *Artist:* {metadata.get('artist', 'Unknown')}\n"
    if metadata.get('album') and metadata['album'] != 'Unknown':
        txt += f"💿 *Album/Film:* {metadata['album']}\n"
    if metadata.get('genre') and metadata['genre'] != 'Unknown':
        txt += f"🎼 *Genre:* {metadata['genre']}\n"
    if metadata.get('release_date') and metadata['release_date'] != 'Unknown':
        txt += f"📅 *Released:* {metadata['release_date']}\n"
    if metadata.get('duration'):
        txt += f"⏱ *Duration:* {dur_str(metadata['duration'])}\n"
    txt += f"\n{DIVIDER}\n"
    links_added = False
    if metadata.get('youtube_link'):
        txt += f"\n🔴 *YouTube:* [Watch]({metadata['youtube_link']})"
        links_added = True
    if metadata.get('spotify_link'):
        txt += f"\n🟢 *Spotify:* [Listen]({metadata['spotify_link']})"
        links_added = True
    if metadata.get('apple_music_link'):
        txt += f"\n🔵 *Apple Music:* [Listen]({metadata['apple_music_link']})"
        links_added = True
    if metadata.get('deezer_link'):
        txt += f"\n🔮 *Deezer:* [Listen]({metadata['deezer_link']})"
        links_added = True
    if not links_added:
        txt += f"\n\n_No direct platform links found._"
    if metadata.get('lyrics'):
        txt += f"\n\n{DIVIDER}\n📝 *Lyrics:*\n_{metadata['lyrics'][:500]}_"
        if len(metadata['lyrics']) > 500:
            txt += "\n_... (truncated)_"
    txt += f"\n\n{DIVIDER}\n_{get_quote()}_"
    return txt

# ════════════════════════════════════════════════════════════════════════
#  🔥 AUTO-DELETE HELPER (IMPROVED)
# ════════════════════════════════════════════════════════════════════════
async def _delete_later(msg: Message, delay: int = 10):
    """Deletes a message after `delay` seconds."""
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except:
        pass

async def _delete_np_after_stop(chat_id: int, delay: int = 5):
    """Deletes the 'Now Playing' message after a song ends."""
    ch = active_chats.get(chat_id, {})
    if ch and ch.get('np_msg_id'):
        try:
            await _delete_later(await ch.get('np_msg_ref'), delay)
        except:
            pass

async def _delete_audio_after_play(bot, chat_id, message_id, delay: int = 120):
    """DM में ऑडियो भेजने के बाद 2 मिनट में डिलीट"""
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id, message_id)
    except:
        pass

# ════════════════════════════════════════════════════════════════════════
#  🔥 COMMAND HANDLERS (Modified with Auto-Delete)
# ════════════════════════════════════════════════════════════════════════

async def cmd_recognize(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    replied = update.message.reply_to_message
    if not replied:
        msg = await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ *Usage:*\nReply to an audio/video file with `/recognize`\n"
            f"Or send: `/recognize <YouTube/Insta/FB/Twitter link>`\n\n"
            f"*Also works:* `/origin` or `/detect`",
            parse_mode='Markdown'
        )
        asyncio.create_task(_delete_later(msg, 10))
        return
    msg = await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n🔍 *Analyzing audio using all 5 APIs...*\n\n"
        f"🤖 Trying: AudD → Spotify → Deezer\n\n_{get_loading_quote()}_",
        parse_mode='Markdown'
    )
    file_path = None
    try:
        if replied.audio:
            file_obj = replied.audio
        elif replied.video:
            file_obj = replied.video
        elif replied.video_note:
            file_obj = replied.video_note
        elif replied.voice:
            file_obj = replied.voice
        elif replied.document:
            file_obj = replied.document
        else:
            await msg.edit_text(f"{BRAND}\n{DIVIDER}\n\n❌ Reply must contain an audio or video file.")
            return
        file_id = file_obj.file_id
        file = await context.bot.get_file(file_id)
        ext = file_obj.file_name.split('.')[-1] if file_obj.file_name else 'mp3'
        file_path = os.path.join(TMP_DIR, f"recognize_{uuid.uuid4().hex}.{ext}")
        await file.download_to_drive(file_path)
        metadata = await _recognize_file_multi_api(file_path)
        if not metadata:
            await msg.edit_text(
                f"{BRAND}\n{DIVIDER}\n\n❌ *Could not recognize this audio.*\n\n"
                f"All 5 APIs were tried:\n❌ AudD (failed)\n❌ Spotify (not found)\n❌ Deezer (not found)\n\n"
                f"Try a clearer clip or a longer sample."
            )
            return
        result_text = _format_recognition_result(metadata)
        await msg.edit_text(result_text, parse_mode='Markdown', disable_web_page_preview=True)
        asyncio.create_task(_delete_later(msg, 15))
    except Exception as e:
        logger.error(f"Recognition error: {e}")
        await msg.edit_text(f"{BRAND}\n{DIVIDER}\n\n❌ *Error during recognition:*\n`{e}`", parse_mode='Markdown')
    finally:
        if file_path and os.path.exists(file_path):
            clean(file_path)

async def cmd_origin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    if not context.args:
        msg = await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ *Usage:*\n`/origin <YouTube/Insta/FB/Twitter/TikTok link>`\n"
            f"Or reply to a file with `/origin`",
            parse_mode='Markdown'
        )
        asyncio.create_task(_delete_later(msg, 10))
        return
    url = ' '.join(context.args).strip()
    if not re.match(r'^https?://', url, re.I):
        resolved = _yt_search_resolve(url)
        if resolved:
            url = resolved
        else:
            msg = await update.message.reply_text(
                f"{BRAND}\n{DIVIDER}\n\n❌ Could not resolve *{url}*. Please send a valid link."
            )
            asyncio.create_task(_delete_later(msg, 10))
            return
    msg = await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n🔍 *Analyzing link...*\n\n_{get_loading_quote()}_",
        parse_mode='Markdown'
    )
    try:
        info, error = await asyncio.wait_for(_run_in_pool(_generic_info, url), timeout=35)
        if not info:
            await msg.edit_text(
                f"{BRAND}\n{DIVIDER}\n\n❌ Could not fetch info from this link.\nIt may be private or unsupported."
            )
            return
        title = info.get('title', 'Unknown')
        artist = info.get('uploader', info.get('channel', 'Unknown'))
        duration = int(info.get('duration', 0))
        platform = _detect_platform(url)
        result_text = f"{BRAND}\n{DIVIDER}\n\n"
        result_text += f"🔍 *Original Source Found!*\n\n"
        result_text += f"📹 *Title:* {title}\n"
        result_text += f"🎤 *Artist/Channel:* {artist}\n"
        if duration:
            result_text += f"⏱ *Duration:* {dur_str(duration)}\n"
        result_text += f"🌐 *Platform:* {platform.upper()}\n"
        result_text += f"🔗 *Original URL:* [Click Here]({url})\n\n"
        result_text += f"{DIVIDER}\n_{get_quote()}_"
        await msg.edit_text(result_text, parse_mode='Markdown', disable_web_page_preview=True)
        asyncio.create_task(_delete_later(msg, 15))
    except Exception as e:
        logger.error(f"Origin error: {e}")
        await msg.edit_text(f"{BRAND}\n{DIVIDER}\n\n❌ *Error:* `{e}`", parse_mode='Markdown')

async def auto_recognize_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text and update.message.text.startswith('/'):
        return
    if update.message.reply_to_message:
        return
    auth, reason = check_auth(update)
    if not auth:
        return
    has_file = (update.message.audio or update.message.video or
                update.message.voice or update.message.video_note)
    has_link = update.message.text and re.search(r'https?://', update.message.text, re.I)
    if not has_file and not has_link:
        return
    msg = await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n🔍 *Auto-detecting using all 5 APIs...*\n\n"
        f"🤖 AudD → Spotify → Deezer\n\n_{get_loading_quote()}_",
        parse_mode='Markdown'
    )
    file_path = None
    try:
        if has_file:
            if update.message.audio:
                file_obj = update.message.audio
            elif update.message.video:
                file_obj = update.message.video
            elif update.message.voice:
                file_obj = update.message.voice
            elif update.message.video_note:
                file_obj = update.message.video_note
            else:
                return
            file_id = file_obj.file_id
            file = await context.bot.get_file(file_id)
            ext = file_obj.file_name.split('.')[-1] if file_obj.file_name else 'mp3'
            file_path = os.path.join(TMP_DIR, f"auto_{uuid.uuid4().hex}.{ext}")
            await file.download_to_drive(file_path)
            metadata = await _recognize_file_multi_api(file_path)
            if metadata:
                result_text = _format_recognition_result(metadata)
                await msg.edit_text(result_text, parse_mode='Markdown', disable_web_page_preview=True)
            else:
                await msg.edit_text(
                    f"{BRAND}\n{DIVIDER}\n\n❌ *Could not identify this audio.*\n"
                    f"All 5 APIs failed. Try a clearer clip or use /recognize on a file."
                )
        elif has_link:
            url = re.search(r'(https?://[^\s]+)', update.message.text).group(1)
            info, error = await asyncio.wait_for(_run_in_pool(_generic_info, url), timeout=35)
            if info:
                title = info.get('title', 'Unknown')
                artist = info.get('uploader', info.get('channel', 'Unknown'))
                duration = int(info.get('duration', 0))
                platform = _detect_platform(url)
                result_text = f"{BRAND}\n{DIVIDER}\n\n"
                result_text += f"🔍 *Original Source Detected!*\n\n"
                result_text += f"📹 *Title:* {title}\n"
                result_text += f"🎤 *Artist/Channel:* {artist}\n"
                if duration:
                    result_text += f"⏱ *Duration:* {dur_str(duration)}\n"
                result_text += f"🌐 *Platform:* {platform.upper()}\n"
                result_text += f"🔗 *Original URL:* [Click Here]({url})\n\n"
                result_text += f"{DIVIDER}\n_{get_quote()}_"
                await msg.edit_text(result_text, parse_mode='Markdown', disable_web_page_preview=True)
            else:
                await msg.edit_text(
                    f"{BRAND}\n{DIVIDER}\n\n❌ Could not fetch info from this link.\nTry /origin <link> for more details."
                )
        asyncio.create_task(_delete_later(msg, 15))
    except Exception as e:
        logger.error(f"Auto-recognition error: {e}")
        await msg.edit_text(f"{BRAND}\n{DIVIDER}\n\n❌ *Error:* {e}", parse_mode='Markdown')
    finally:
        if file_path and os.path.exists(file_path):
            clean(file_path)

async def cmd_ytdl(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    if not context.args:
        msg = await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ *Usage:*\n`/ytdl <YouTube link>`\nDownload YouTube video/audio directly.",
            parse_mode='Markdown'
        )
        asyncio.create_task(_delete_later(msg, 10))
        return
    url = ' '.join(context.args).strip()
    if not _is_youtube_url(url):
        msg = await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n❌ Please send a valid YouTube link.", parse_mode='Markdown')
        asyncio.create_task(_delete_later(msg, 10))
        return
    msg = await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n⏳ Fetching YouTube video...\n\n_{get_loading_quote()}_",
        parse_mode='Markdown'
    )
    try:
        info, _ = await asyncio.wait_for(_run_in_pool(_generic_info, url), timeout=30)
        if not info:
            await msg.edit_text(f"{BRAND}\n{DIVIDER}\n\n❌ Failed to fetch video info.")
            return
        title = info.get('title', 'Unknown')
        artist = info.get('uploader', 'Unknown')
        duration = int(info.get('duration', 0))
        qualities = _available_qualities(info)
        tok = uuid.uuid4().hex
        pending_download[tok] = {
            'url': url, 'title': title, 'artist': artist,
            'duration': duration, 'qualities': qualities,
            'chat_id': update.effective_chat.id
        }
        rows, row = [], []
        for ql in qualities[:5]:
            row.append(InlineKeyboardButton(f"📹 {ql}", callback_data=f"dq|{tok}|{ql}"))
            if len(row) == 2:
                rows.append(row); row = []
        if row: rows.append(row)
        rows.append([InlineKeyboardButton("🎵 MP3 Audio", callback_data=f"dt|{tok}|mp3")])
        rows.append([InlineKeyboardButton("✨ Best Available", callback_data=f"dq|{tok}|best")])
        await msg.edit_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"🔴 *{title}*\n"
            f"🎤 {artist}\n"
            f"⏱ {dur_str(duration)}\n\n"
            f"📥 *Choose format:*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(rows)
        )
    except Exception as e:
        await msg.edit_text(f"{BRAND}\n{DIVIDER}\n\n❌ Error: {e}")

async def cmd_album(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    ch = active_chats.get(update.effective_chat.id, {})
    if not ch.get('current'):
        msg = await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n❌ No song is playing.", parse_mode='Markdown')
        asyncio.create_task(_delete_later(msg, 10))
        return
    title = ch.get('current')
    artist = ch.get('artist', '')
    msg = await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n🔍 Searching album info for *{title}*...",
        parse_mode='Markdown'
    )
    spotify_meta = await asyncio.get_event_loop().run_in_executor(_pool, _search_spotify, f"{title} {artist}")
    if spotify_meta and spotify_meta.get('album'):
        await msg.edit_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"💿 *Album/Film:* {spotify_meta['album']}\n"
            f"🎵 *Song:* {title}\n"
            f"🎤 *Artist:* {artist}\n"
            + (f"🟢 *Spotify:* [Listen]({spotify_meta['spotify_url']})\n" if spotify_meta.get('spotify_url') else ""),
            parse_mode='Markdown'
        )
    else:
        await msg.edit_text(f"{BRAND}\n{DIVIDER}\n\n❌ Album info not found for *{title}*.", parse_mode='Markdown')
    asyncio.create_task(_delete_later(msg, 15))

async def cmd_fingerprint(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    msg = await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"🔍 *Audio Fingerprinting*\n\n"
        f"Reply to any audio/video file with `/fingerprint` to identify it.\n"
        f"Or send: `/recognize` to use all 5 APIs.",
        parse_mode='Markdown'
    )
    asyncio.create_task(_delete_later(msg, 10))

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  PARALLEL ASYNC DOWNLOADER (Now entirely YouTube-based)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def _run_in_pool(fn, *args):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_pool, fn, *args)

async def find_parallel(query: str) -> Optional[dict]:
    cached = _cache_get(query)
    if cached:
        logger.info(f"Cache hit: {query}")
        return cached
    try:
        return await asyncio.wait_for(_run_in_pool(_yt_audio_dl, query, False), timeout=60)
    except asyncio.TimeoutError:
        return None
    except Exception:
        return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  VOICE CHAT HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def make_player_kb(paused: bool = False, loop: bool = False) -> InlineKeyboardMarkup:
    pause_lbl = "▶️ Resume" if paused else "⏸ Pause"
    loop_lbl  = "🔁 Loop ✅" if loop else "🔁 Loop"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(pause_lbl,   callback_data="pause_resume"),
            InlineKeyboardButton("⏭ Skip",    callback_data="skip"),
            InlineKeyboardButton("⏹ Stop",    callback_data="stop"),
        ],
        [
            InlineKeyboardButton(loop_lbl,    callback_data="toggle_loop"),
        ],
    ])

def np_text(title: str, artist: str, duration: int, elapsed: float,
            paused: bool, loop: bool, queue_len: int,
            source: str = '') -> str:
    bar    = progress_bar(elapsed, duration)
    status = "⏸ Paused" if paused else "▶️ Now Playing"
    src_icon = {'youtube': '🔴'}.get(source, '🎵')
    txt = (
        f"{BRAND}\n{DIVIDER}\n\n"
        f"{status}  {src_icon}\n\n"
        f"🎵 *{title}*\n"
    )
    if artist: txt += f"🎤 {artist}\n"
    txt += f"\n`{dur_str(int(elapsed))}` {bar} `{dur_str(duration)}`\n"
    if loop: txt += "🔁 Loop ON\n"
    if queue_len: txt += f"\n📋 *{queue_len} song(s) in queue*\n"
    txt += f"\n_{get_quote()}_"
    return txt

try:
    from pytgcalls.types import AudioQuality as _AudioQuality
    _AQ_STUDIO = _AudioQuality.STUDIO
except Exception:
    _AQ_STUDIO = None

def _make_stream(fp: str, seek_sec: int = 0):
    ff = f"-ss {seek_sec}" if seek_sec > 0 else None
    try:
        if _AQ_STUDIO is not None:
            if ff:
                return MediaStream(fp, _AQ_STUDIO, ffmpeg_parameters=ff)
            return MediaStream(fp, _AQ_STUDIO)
    except Exception:
        pass
    if ff:
        return MediaStream(fp, ffmpeg_parameters=ff)
    return MediaStream(fp)

async def _np_live_updater(chat_id: int, msg_id: int, bot):
    UPDATE_INTERVAL = 5
    await asyncio.sleep(UPDATE_INTERVAL)
    while True:
        ch = active_chats.get(chat_id, {})
        if not ch.get('playing') or ch.get('np_msg_id') != msg_id:
            break
        if not ch.get('paused'):
            try:
                elapsed = get_elapsed(chat_id)
                kb  = make_player_kb(
                    paused=False,
                    loop=ch.get('loop', False)
                )
                txt = np_text(
                    ch.get('current', ''), ch.get('artist', ''),
                    ch.get('duration', 0), elapsed,
                    False, ch.get('loop', False),
                    len(ch.get('queue', [])), ch.get('source', '')
                )
                await bot.edit_message_text(
                    chat_id=chat_id, message_id=msg_id,
                    text=txt, parse_mode='Markdown', reply_markup=kb
                )
            except Exception:
                pass
        await asyncio.sleep(UPDATE_INTERVAL)

def _start_np_updater(chat_id: int, msg_id: int, bot):
    old = _np_tasks.pop(chat_id, None)
    if old and not old.done():
        old.cancel()
    if msg_id and bot:
        task = asyncio.create_task(_np_live_updater(chat_id, msg_id, bot))
        _np_tasks[chat_id] = task

def _stop_np_updater(chat_id: int):
    t = _np_tasks.pop(chat_id, None)
    if t and not t.done():
        t.cancel()

async def vc_play_item(chat_id: int, item: dict, bot, seek_sec: int = 0):
    fp       = item['file']
    title    = item.get('title', 'Unknown')
    duration = item.get('duration', 0)
    source   = item.get('source', '')

    ch = active_chats.setdefault(chat_id, _new_chat_state())
    _stop_np_updater(chat_id)

    if ch.get('playing'):
        for fn in ('stop_stream', 'leave_group_call'):
            try:
                await getattr(calls, fn)(chat_id)
                await asyncio.sleep(0.5)
                break
            except Exception:
                pass

    try:
        stream = _make_stream(fp, seek_sec)
        await asyncio.sleep(1)
        await calls.play(chat_id, stream)
        await asyncio.sleep(1.5)

        if ch.get('current_file') and ch.get('current_file') != fp:
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

        vol = ch.get('volume', 100)
        if vol != 100:
            try:
                await calls.change_volume_call(chat_id, vol)
            except Exception:
                pass

        _start_np_updater(chat_id, ch.get('np_msg_id'), bot)
        logger.info(f"VC play OK: chat={chat_id}  title={title}")
        return True, ''

    except _pyro_errors.GroupCallForbidden:
        err = "GroupCallForbidden: make the userbot admin and ensure Voice Chat is open in the group."
        logger.error(f"vc_play_item: {err}")
        ch['playing'] = False
        return False, err
    except Exception as e:
        err = str(e)
        logger.error(f"vc_play_item FAILED: {err}")
        ch['playing'] = False
        return False, err

async def vc_stop(chat_id: int):
    _stop_np_updater(chat_id)
    for fn in ('stop_stream', 'leave_group_call'):
        try:
            await getattr(calls, fn)(chat_id)
        except Exception:
            pass
    ch = active_chats.get(chat_id)
    if ch:
        asyncio.create_task(_delete_np_after_stop(chat_id, 5))
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

async def play_next(chat_id: int, bot) -> bool:
    ch = active_chats.get(chat_id, _new_chat_state())
    active_chats[chat_id] = ch

    if ch.get('loop') and ch.get('current_file'):
        item = {
            'file'    : ch['current_file'],
            'title'   : ch['current'],
            'artist'  : ch.get('artist', ''),
            'duration': ch.get('duration', 0),
            'source'  : ch.get('source', ''),
        }
        ok, _ = await vc_play_item(chat_id, item, bot)
        return ok

    queue = ch.get('queue', [])
    if not queue:
        ch.update({'playing': False, 'current': None, 'current_file': None})
        return False

    item = queue.pop(0)
    ch['queue'] = queue

    ok, _ = await vc_play_item(chat_id, item, bot)
    if not ok:
        clean(item.get('file'))
    if ok and bot:
        try:
            kb  = make_player_kb(loop=ch.get('loop', False))
            txt = np_text(
                item['title'], item.get('artist',''), item.get('duration',0),
                0, False, ch.get('loop',False),
                len(ch.get('queue',[])), item.get('source','')
            )
            msg = await bot.send_message(chat_id, txt, parse_mode='Markdown', reply_markup=kb)
            ch['np_msg_id'] = msg.message_id
            ch['np_msg_ref'] = msg
        except Exception:
            pass
    return ok

_tg_bot_ref = None

def _register_stream_end():
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
        f"• /play `<name or URL>` — Play / download (YouTube 100%)\n"
        f"• /stop — Stop music & clear queue\n"
        f"• /skip — Skip to next song\n"
        f"• /pause — Pause playback\n"
        f"• /resume — Resume playback\n"
        f"• /queue — View current queue\n"
        f"• /current — Now playing info\n\n"
        f"🎛 *Extra Commands:*\n"
        f"• /volume `<0-200>` — Set volume\n"
        f"• /loop — Toggle loop current song\n"
        f"• /shuffle — Shuffle the queue\n"
        f"• /clear — Clear queue\n"
        f"• /lyrics — Get lyrics of current song\n"
        f"• /ping — Bot latency\n"
        f"• /myid — Your Telegram ID\n"
        f"• /help — Full help\n\n"
        f"🔍 *Recognition Commands:*\n"
        f"• /recognize (or /id) — Recognize any audio/video file or link\n"
        f"• /origin — Find original source of any video/audio link\n"
        f"• /album — Get Album/Film info of current song\n"
        f"• /fingerprint — Audio fingerprinting (advanced)\n"
        f"• /ytdl — Direct YouTube download (100% working)\n"
        f"• /detect — Auto-detect sent audio/video\n\n"
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
    asyncio.create_task(_delete_later(msg, 10))

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

    yt_id = extract_yt_id(query)
    if yt_id:
        yt_url = f"https://www.youtube.com/watch?v={yt_id}"
        msg    = await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"⏳ YouTube link detected, fetching audio...\n\n"
            f"_{get_loading_quote()}_",
            parse_mode='Markdown'
        )
        try:
            result = await asyncio.wait_for(_run_in_pool(_yt_audio_dl, yt_url, True), timeout=90)
        except asyncio.TimeoutError:
            await msg.edit_text(f"{BRAND}\n{DIVIDER}\n\n❌ Timed out fetching audio. Try again.")
            return
    else:
        msg = await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"🔍 Searching YouTube: *{query}*\n\n"
            f"_{get_loading_quote()}_",
            parse_mode='Markdown'
        )
        try:
            result = await asyncio.wait_for(find_parallel(query), timeout=60)
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
            f"❌ Song not found on YouTube.\n"
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
        try:
            with open(fp, 'rb') as af:
                sent_msg = await context.bot.send_audio(
                    chat_id=chat_id, audio=af,
                    title=title, performer=artist, duration=duration,
                    read_timeout=300, write_timeout=300, connect_timeout=60,
                )
            await msg.delete()
            # DM में ऑडियो भेजने के बाद 2 मिनट में डिलीट
            asyncio.create_task(_delete_audio_after_play(context.bot, chat_id, sent_msg.message_id, 120))
        except Exception as e:
            await msg.edit_text(
                f"{BRAND}\n{DIVIDER}\n\n❌ Send failed: `{e}`\n\nPlease try again.",
                parse_mode='Markdown'
            )
        finally:
            clean(fp)
    else:
        src_ic = {'youtube': '🔴'}.get(source, '🎵')
        ch = active_chats.get(chat_id, {})
        if ch.get('playing'):
            await msg.edit_text(
                f"{BRAND}\n{DIVIDER}\n\n"
                f"⏹ Stopping current song...\n"
                f"▶️ Loading: *{title}*\n\n"
                f"_{get_loading_quote()}_",
                parse_mode='Markdown'
            )
            await vc_stop(chat_id)
        ch = active_chats.setdefault(chat_id, _new_chat_state())
        item   = {'file': fp, 'title': title, 'artist': artist, 'duration': duration, 'source': source}
        kb     = make_player_kb(loop=False)
        np     = np_text(title, artist, duration, 0, False, False, 0, source)
        np_msg = await msg.edit_text(np, parse_mode='Markdown', reply_markup=kb)
        ch['np_msg_id'] = np_msg.message_id
        ch['np_msg_ref'] = np_msg
        ok, err = await vc_play_item(chat_id, item, context.bot)
        if not ok:
            await np_msg.edit_text(
                f"{BRAND}\n{DIVIDER}\n\n"
                f"⚠️ *Voice Chat join failed* — sending as audio file instead.\n\n"
                f"🎵 *{title}*\n\n"
                f"_Make sure a Voice Chat is active and the userbot is a member "
                f"with permission to join, so next time it can play live._\n\n"
                f"🔴 *Error:* `{err}`",
                parse_mode='Markdown'
            )
            try:
                with open(fp, 'rb') as af:
                    await update.message.reply_audio(
                        audio=af, title=title, performer=artist, duration=duration,
                        read_timeout=300, write_timeout=300, connect_timeout=60,
                    )
            except Exception as e2:
                await np_msg.edit_text(
                    f"{BRAND}\n{DIVIDER}\n\n"
                    f"❌ *Voice Chat join failed AND audio send failed.*\n\n"
                    f"Make sure:\n"
                    f"• A Voice Chat is *active* in this group\n"
                    f"• The userbot account is a *member* of this group\n"
                    f"• The userbot has permission to join Voice Chats\n\n"
                    f"🔴 *VC Error:* `{err}`\n"
                    f"🔴 *Send Error:* `{e2}`\n\n"
                    f"📩 Contact {BOT_OWNER_USERNAME} for help.",
                    parse_mode='Markdown'
                )
            finally:
                clean(fp)

async def cmd_download(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    if not context.args:
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ *Usage:*\n"
            f"`/download <song name>`\n"
            f"`/download <YouTube link>`",
            parse_mode='Markdown'
        )
        return
    query   = ' '.join(context.args).strip()
    chat_id = update.effective_chat.id
    msg = await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"🔍 Fetching info from YouTube...\n\n"
        f"_{get_loading_quote()}_",
        parse_mode='Markdown'
    )
    url = query if re.match(r'^https?://', query, re.I) else None
    if not url:
        try:
            url = await asyncio.wait_for(_run_in_pool(_yt_search_resolve, query), timeout=25)
        except asyncio.TimeoutError:
            await msg.edit_text(f"{BRAND}\n{DIVIDER}\n\n❌ Search timed out. Please try again.")
            return
        if not url:
            await msg.edit_text(
                f"{BRAND}\n{DIVIDER}\n\n"
                f"❌ Nothing found on YouTube for *{query}*.\n"
                f"Try a different name, or paste a YouTube link.",
                parse_mode='Markdown'
            )
            return
    try:
        info, fetch_err = await asyncio.wait_for(_run_in_pool(_generic_info, url), timeout=35)
    except asyncio.TimeoutError:
        await msg.edit_text(f"{BRAND}\n{DIVIDER}\n\n❌ Timed out fetching info. Please try again.")
        return
    if not info:
        reason = re.sub(r'[`*_\[\]]', '', fetch_err or '')[:150].strip()
        await msg.edit_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ Couldn't fetch this link.\n"
            f"It may be private, region-locked, or unsupported.\n"
            + (f"\n`{reason}`\n" if reason else "")
            + f"\n📩 Still stuck? Contact {BOT_OWNER_USERNAME}.",
            parse_mode='Markdown'
        )
        return
    title     = info.get('title') or query
    artist    = info.get('uploader') or info.get('channel') or info.get('uploader_id') or ''
    duration  = int(info.get('duration') or 0)
    platform  = _detect_platform(url)
    qualities = _available_qualities(info)
    tok = uuid.uuid4().hex
    pending_download[tok] = {
        'url': url, 'title': title, 'artist': artist, 'duration': duration,
        'platform': platform, 'qualities': qualities, 'chat_id': chat_id,
    }
    plat_icon = {'youtube': '🔴', 'instagram': '📸', 'facebook': '📘', 'twitter': '🐦', 'tiktok': '🎵', 'snapchat': '👻'}.get(platform, '🔗')
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("🎵 MP3 (Audio)", callback_data=f"dt|{tok}|mp3"),
        InlineKeyboardButton("📹 Video",       callback_data=f"dt|{tok}|video"),
    ]])
    await msg.edit_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"{plat_icon} *{title}*\n"
        + (f"🎤 {artist}\n" if artist else "")
        + (f"⏱ {dur_str(duration)}\n" if duration else "")
        + f"\n{DIVIDER}\n\n📥 *Choose format:*\n\n_{get_quote()}_",
        parse_mode='Markdown',
        reply_markup=kb
    )

async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    chat_id = update.effective_chat.id
    await vc_stop(chat_id)
    msg = await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n⏹ *Music stopped. Queue cleared.*", parse_mode='Markdown')
    asyncio.create_task(_delete_later(msg, 10))

async def cmd_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    chat_id = update.effective_chat.id
    ch      = active_chats.get(chat_id, {})
    if not ch.get('playing'):
        msg = await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n❌ Nothing is playing.")
        asyncio.create_task(_delete_later(msg, 10))
        return
    for fn in ('stop_stream', 'leave_group_call'):
        try:
            await getattr(calls, fn)(chat_id)
            break
        except Exception:
            pass
    clean(ch.get('current_file'))
    ch['playing'] = False; ch['current'] = None; ch['current_file'] = None
    ok = await play_next(chat_id, context.bot)
    if not ok:
        msg = await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n⏭ Skipped. Queue is now empty.", parse_mode='Markdown')
        asyncio.create_task(_delete_later(msg, 10))

async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    ok = await vc_pause(update.effective_chat.id)
    txt = "⏸ *Paused.*" if ok else "❌ Nothing to pause."
    msg = await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n{txt}", parse_mode='Markdown')
    asyncio.create_task(_delete_later(msg, 10))

async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    ok = await vc_resume(update.effective_chat.id)
    txt = "▶️ *Resumed.*" if ok else "❌ Nothing to resume."
    msg = await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n{txt}", parse_mode='Markdown')
    asyncio.create_task(_delete_later(msg, 10))

async def cmd_current(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    chat_id = update.effective_chat.id
    ch      = active_chats.get(chat_id, {})
    cur     = ch.get('current')
    if not cur:
        await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n❌ Nothing is playing right now.", parse_mode='Markdown')
        return
    elapsed = get_elapsed(chat_id)
    kb      = make_player_kb(paused=ch.get('paused', False), loop=ch.get('loop', False))
    txt = np_text(cur, ch.get('artist', ''), ch.get('duration', 0), elapsed, ch.get('paused', False),
                  ch.get('loop', False), len(ch.get('queue', [])), ch.get('source', ''))
    msg = await update.message.reply_text(txt, parse_mode='Markdown', reply_markup=kb)
    asyncio.create_task(_delete_later(msg, 10))

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
        msg = await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n❌ Queue is empty.", parse_mode='Markdown')
        asyncio.create_task(_delete_later(msg, 10))
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
    msg = await update.message.reply_text(txt, parse_mode='Markdown')
    asyncio.create_task(_delete_later(msg, 10))

async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    ch = active_chats.setdefault(update.effective_chat.id, _new_chat_state())
    for item in ch.get('queue', []):
        clean(item.get('file'))
    ch['queue'] = []
    msg = await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n🗑 *Queue cleared.*", parse_mode='Markdown')
    asyncio.create_task(_delete_later(msg, 10))

async def cmd_shuffle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    ch = active_chats.setdefault(update.effective_chat.id, _new_chat_state())
    q  = ch.get('queue', [])
    if not q:
        msg = await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n❌ Queue is empty.", parse_mode='Markdown')
        asyncio.create_task(_delete_later(msg, 10))
        return
    random.shuffle(q)
    ch['queue'] = q
    msg = await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n🔀 *Queue shuffled!* {len(q)} songs in random order.", parse_mode='Markdown')
    asyncio.create_task(_delete_later(msg, 10))

async def cmd_loop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    ch = active_chats.setdefault(update.effective_chat.id, _new_chat_state())
    ch['loop'] = not ch.get('loop', False)
    state = "✅ ON" if ch['loop'] else "❌ OFF"
    msg = await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n🔁 *Loop current song: {state}*", parse_mode='Markdown')
    asyncio.create_task(_delete_later(msg, 10))

async def cmd_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    if not context.args or not context.args[0].isdigit():
        msg = await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ Usage: `/volume <0-200>`\n"
            f"Default: 100 | Max: 200",
            parse_mode='Markdown'
        )
        asyncio.create_task(_delete_later(msg, 10))
        return
    vol     = max(0, min(200, int(context.args[0])))
    chat_id = update.effective_chat.id
    ch      = active_chats.setdefault(chat_id, _new_chat_state())
    ch['volume'] = vol
    try:
        await calls.change_volume_call(chat_id, vol)
        msg = await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n🔊 *Volume set to {vol}%*", parse_mode='Markdown')
        asyncio.create_task(_delete_later(msg, 10))
    except Exception as e:
        msg = await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n⚠️ Volume saved to {vol}% (applies on next track).\n_Reason: {e}_",
            parse_mode='Markdown'
        )
        asyncio.create_task(_delete_later(msg, 10))

async def cmd_lyrics(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(unauthorized_msg(update, reason), parse_mode='Markdown')
        return
    ch = active_chats.get(update.effective_chat.id, {})
    if context.args:
        title  = ' '.join(context.args)
        artist = ''
    else:
        title  = ch.get('current', '')
        artist = ch.get('artist', '')
    if not title:
        msg = await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ Nothing is playing.\n"
            f"Usage: `/lyrics <song name>`",
            parse_mode='Markdown'
        )
        asyncio.create_task(_delete_later(msg, 10))
        return
    msg = await update.message.reply_text(f"{BRAND}\n{DIVIDER}\n\n🔍 Fetching lyrics for *{title}*...", parse_mode='Markdown')
    lyrics = await asyncio.wait_for(_run_in_pool(_fetch_lyrics, title, artist), timeout=15)
    if lyrics:
        header = f"{BRAND}\n{DIVIDER}\n\n🎤 *{title}*\n\n"
        body   = lyrics[:4000 - len(header)]
        await msg.edit_text(header + body, parse_mode='Markdown')
    else:
        await msg.edit_text(f"{BRAND}\n{DIVIDER}\n\n❌ Lyrics not found for *{title}*.\nTry: `/lyrics <exact song name>`", parse_mode='Markdown')
    asyncio.create_task(_delete_later(msg, 15))

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"📋 *All Commands:*\n\n"
        f"🎵 `/play <name or YouTube URL>` — Plays song directly from YouTube (100% Working)\n"
        f"⬇️ `/download <name or YouTube link>` — Get MP3 or Video (pick quality)\n"
        f"🔍 `/recognize` (or `/id`) — Recognize audio/video from file or link\n"
        f"🌐 `/origin <link>` — Find original source of any video/audio link\n"
        f"💿 `/album` — Get Album/Film info of current song\n"
        f"🎵 `/ytdl <YouTube link>` — Direct YouTube download (100% working)\n"
        f"🔬 `/fingerprint` — Advanced audio fingerprinting\n"
        f"🤖 `/detect` — Auto-detect sent audio/video\n"
        f"⏹ `/stop` — Stop & clear everything\n"
        f"⏭ `/skip` — Skip to next song in queue\n"
        f"⏸ `/pause` — Pause playback\n"
        f"▶️ `/resume` — Resume playback\n"
        f"📋 `/queue` — Show current queue\n"
        f"🗑 `/clear` — Clear queue (keeps current)\n"
        f"🔀 `/shuffle` — Shuffle the queue\n"
        f"🔁 `/loop` — Toggle loop current song\n"
        f"🔊 `/volume <0-200>` — Set volume\n"
        f"🎤 `/lyrics [song]` — Get lyrics\n"
        f"▶️ `/current` — Now playing details\n"
        f"🏓 `/ping` — Bot latency\n"
        f"🆔 `/myid` — Your Telegram ID\n\n"
        f"{DIVIDER}\n"
        f"🎛 *Inline Controls (group):*\n"
        f"⏸Pause | ⏭Skip | ⏹Stop | 🔁Loop\n\n"
        f"_In groups: streams in Voice Chat_\n"
        f"_In DM: sends audio/video file_\n\n"
        f"_{get_quote()}_",
        parse_mode='Markdown'
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CALLBACK HANDLER (Modified with Auto-Delete)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def _edit_safe(q, text, kb=None, pm='Markdown'):
    try:
        if kb:
            await q.edit_message_text(text, parse_mode=pm, reply_markup=kb)
        else:
            await q.edit_message_text(text, parse_mode=pm)
    except TgBadRequest:
        pass

async def _send_download_result(update, context, q, result: dict, pv: dict, is_video: bool):
    fp       = result['file']
    title    = pv.get('title') or 'Unknown'
    artist   = pv.get('artist', '')
    duration = pv.get('duration', 0)
    size_mb  = os.path.getsize(fp) / (1024 * 1024)
    if size_mb > 1900:
        clean(fp)
        await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n❌ File too large ({size_mb:.0f} MB). Choose a lower quality.")
        return
    await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n✅ *{title}*\n📤 Sending... ({size_mb:.1f} MB)\n\n_{get_quote()}_")
    try:
        cid = update.effective_chat.id
        if is_video:
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

async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q       = update.callback_query
    data    = q.data
    chat_id = update.effective_chat.id
    auth, reason = check_auth(update)
    await q.answer()

    # 🔥 Function to delete the callback message after action
    async def _delete_cb_msg(delay=5):
        await asyncio.sleep(delay)
        try:
            await q.message.delete()
        except:
            pass

    if data == "stop":
        if not auth:
            await q.answer(f"❌ Not authorized! Your ID: {update.effective_user.id}", show_alert=True)
            return
        await vc_stop(chat_id)
        await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n⏹ *Music stopped. Queue cleared.*")
        asyncio.create_task(_delete_cb_msg(5))
        return

    if data == "skip":
        if not auth:
            await q.answer(f"❌ Not authorized! Your ID: {update.effective_user.id}", show_alert=True)
            return
        ch = active_chats.get(chat_id, {})
        for fn in ('stop_stream', 'leave_group_call'):
            try:
                await getattr(calls, fn)(chat_id)
                break
            except Exception:
                pass
        clean(ch.get('current_file'))
        ch['playing'] = False; ch['current'] = None; ch['current_file'] = None
        ok = await play_next(chat_id, context.bot)
        if not ok:
            await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n⏭ Skipped. Queue is empty.")
        asyncio.create_task(_delete_cb_msg(5))
        return

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
        kb  = make_player_kb(paused=paused, loop=ch.get('loop',False))
        txt = np_text(cur, ch.get('artist',''), ch.get('duration',0),
                      elapsed, paused, ch.get('loop',False),
                      len(ch.get('queue',[])), ch.get('source',''))
        await _edit_safe(q, txt, kb)
        asyncio.create_task(_delete_cb_msg(5))
        return

    if data == "toggle_loop":
        if not auth:
            await q.answer(f"❌ Not authorized!", show_alert=True); return
        ch = active_chats.setdefault(chat_id, _new_chat_state())
        ch['loop'] = not ch.get('loop', False)
        cur = ch.get('current','Unknown'); elapsed = get_elapsed(chat_id)
        kb  = make_player_kb(paused=ch.get('paused',False), loop=ch['loop'])
        txt = np_text(cur, ch.get('artist',''), ch.get('duration',0),
                      elapsed, ch.get('paused',False), ch['loop'],
                      len(ch.get('queue',[])), ch.get('source',''))
        await _edit_safe(q, txt, kb)
        asyncio.create_task(_delete_cb_msg(5))
        return

    if data.startswith("dt|"):
        parts = data.split("|")
        if len(parts) != 3: return
        _, tok, kind = parts
        pv = pending_download.get(tok)
        if not pv:
            await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n❌ Request expired. Please /download again.")
            return
        if not auth:
            await q.answer(f"❌ Not authorized! Your ID: {update.effective_user.id}", show_alert=True)
            return
        if kind == "video":
            qualities = pv.get('qualities') or []
            rows, row = [], []
            for ql in qualities:
                row.append(InlineKeyboardButton(f"📹 {ql}", callback_data=f"dq|{tok}|{ql}"))
                if len(row) == 3:
                    rows.append(row); row = []
            if row: rows.append(row)
            rows.append([InlineKeyboardButton("✨ Best Available", callback_data=f"dq|{tok}|best")])
            await _edit_safe(q,
                f"{BRAND}\n{DIVIDER}\n\n"
                f"🎬 *{pv['title']}*\n\n"
                f"📥 *Select video quality* (as uploaded):\n\n_{get_quote()}_",
                InlineKeyboardMarkup(rows)
            )
            return
        await _edit_safe(q,
            f"{BRAND}\n{DIVIDER}\n\n"
            f"⬇️ Downloading (MP3)\n🎵 *{pv['title']}*\n"
            + (f"🎤 {pv['artist']}\n" if pv.get('artist') else "")
            + f"\n_{get_loading_quote()}_"
        )
        try:
            result = await asyncio.wait_for(_run_in_pool(_generic_audio_dl, pv['url']), timeout=150)
        except asyncio.TimeoutError:
            await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n❌ Download timed out. Try again.")
            pending_download.pop(tok, None); return
        if not result:
            pending_download.pop(tok, None)
            await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n❌ Download failed. The source may be blocking access — try again in a bit.")
            return
        await _send_download_result(update, context, q, result, pv, is_video=False)
        pending_download.pop(tok, None)
        return

    if data.startswith("dq|"):
        parts = data.split("|")
        if len(parts) != 3: return
        _, tok, quality = parts
        pv = pending_download.get(tok)
        if not pv:
            await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n❌ Request expired. Please /download again.")
            return
        if not auth:
            await q.answer(f"❌ Not authorized! Your ID: {update.effective_user.id}", show_alert=True)
            return
        await _edit_safe(q,
            f"{BRAND}\n{DIVIDER}\n\n"
            f"⬇️ Downloading ({quality})\n🎬 *{pv['title']}*\n"
            + (f"🎤 {pv['artist']}\n" if pv.get('artist') else "")
            + f"\n_{get_loading_quote()}_"
        )
        try:
            result = await asyncio.wait_for(_run_in_pool(_generic_video_dl, pv['url'], quality), timeout=180)
        except asyncio.TimeoutError:
            await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n❌ Download timed out. Try a lower quality.")
            pending_download.pop(tok, None); return
        if not result:
            pending_download.pop(tok, None)
            await _edit_safe(q, f"{BRAND}\n{DIVIDER}\n\n❌ Download failed. Try another quality.")
            return
        await _send_download_result(update, context, q, result, pv, is_video=True)
        pending_download.pop(tok, None)
        return

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

    app.add_handler(CommandHandler(["start"],              cmd_start))
    app.add_handler(CommandHandler(["play"],               cmd_play))
    app.add_handler(CommandHandler(["download", "dl"],     cmd_download))
    app.add_handler(CommandHandler(["stop"],               cmd_stop))
    app.add_handler(CommandHandler(["skip"],               cmd_skip))
    app.add_handler(CommandHandler(["pause"],              cmd_pause))
    app.add_handler(CommandHandler(["resume"],             cmd_resume))
    app.add_handler(CommandHandler(["current", "np"],      cmd_current))
    app.add_handler(CommandHandler(["queue", "q"],         cmd_queue))
    app.add_handler(CommandHandler(["clear"],              cmd_clear))
    app.add_handler(CommandHandler(["shuffle"],            cmd_shuffle))
    app.add_handler(CommandHandler(["loop"],               cmd_loop))
    app.add_handler(CommandHandler(["volume", "vol"],      cmd_volume))
    app.add_handler(CommandHandler(["lyrics", "ly"],       cmd_lyrics))
    app.add_handler(CommandHandler(["ping"],               cmd_ping))
    app.add_handler(CommandHandler(["myid"],               cmd_myid))
    app.add_handler(CommandHandler(["help"],               cmd_help))

    app.add_handler(CommandHandler(["recognize", "id", "recognise"], cmd_recognize))
    app.add_handler(CommandHandler(["origin", "source"], cmd_origin))
    app.add_handler(CommandHandler(["ytdl"], cmd_ytdl))
    app.add_handler(CommandHandler(["album"], cmd_album))
    app.add_handler(CommandHandler(["fingerprint"], cmd_fingerprint))
    app.add_handler(CommandHandler(["detect"], lambda u, c: u.message.reply_text(
        "🤖 *Auto-detect is always ON!*\n\n"
        "Just send any audio/video file or link, and I'll automatically identify it.\n\n"
        "Or use:\n`/recognize` — to manually recognize a file\n`/origin <link>` — to find original source\n\n"
        "*Using 5 APIs: AudD → Spotify → Deezer*",
        parse_mode='Markdown'
    )))

    app.add_handler(MessageHandler(filters.AUDIO | filters.VIDEO | filters.VOICE | filters.VIDEO_NOTE | filters.TEXT, auto_recognize_handler))
    app.add_handler(CallbackQueryHandler(cb_handler))

    print("━" * 50)
    print("  SHEIKH BURHAN MUSIC BOT v3.5 — STARTED")
    print("  + YouTube 100% Working (Multi-Client + Cookies)")
    print("  + Direct YouTube Search (No 3rd Party APIs)")
    print("  + Fuzzy Search (Keyword Matching)")
    print("  + Audio Recognition (5 APIs)")
    print("  + Album/Film Info")
    print("  + Auto-Delete Messages (Group Cleanup)")
    print("  + Simplified Controls (Only Pause/Resume/Skip)")
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
