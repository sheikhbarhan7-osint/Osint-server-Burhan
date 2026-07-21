"""
╔══════════════════════════════════════════╗
║         SHEIKH BURHAN MUSIC BOT          ║
║         Premium Telegram Music Bot       ║
╚══════════════════════════════════════════╝
"""

import os
import re
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

AUTHORIZED_USERS = [5804726533, 2062068620]
AUTHORIZED_GROUPS = [-1001954191240]

BRAND = "🎵 *Sheikh Burhan Music*"

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
pyrogram_app: Client     = None
calls:        PyTgCalls  = None
active_chats  = {}
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
async def vc_play(chat_id: int, file_path: str, title: str) -> bool:
    try:
        try:
            await calls.leave_group_call(chat_id)
            await asyncio.sleep(0.5)
        except Exception:
            pass
        await calls.play(chat_id, MediaStream(file_path))
        ch = active_chats.setdefault(chat_id, {
            'current': None, 'queue': [], 'playing': False, 'temp_file': None
        })
        clean(ch.get('temp_file'))
        ch.update({'current': title, 'playing': True, 'temp_file': file_path})
        return True
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
            'current': None, 'queue': [], 'playing': False, 'temp_file': None
        }

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  UI HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DIVIDER = "━━━━━━━━━━━━━━━━━━━━━━"

def card(title: str, artist: str, duration: int) -> str:
    lines = [
        BRAND,
        "",
        f"🎵  *{title}*",
    ]
    if artist:
        lines.append(f"🎤  {artist}")
    if duration:
        lines.append(f"⏱  {dur_str(duration)}")
    lines.append(DIVIDER)
    return "\n".join(lines)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  COMMANDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid  = update.effective_user.id
    name = update.effective_user.first_name or "दोस्त"
    text = (
        f"{BRAND}\n"
        f"{DIVIDER}\n\n"
        f"नमस्ते *{name}* 👋\n\n"
        f"मैं एक Premium Music Bot हूँ।\n\n"
        f"📋 *Commands:*\n"
        f"• /bajao — गाना बजाओ या download करो\n"
        f"• /roko — बजना बंद करो\n"
        f"• /abhi — अभी क्या बज रहा है\n"
        f"• /meri\\_id — अपना Telegram ID देखो\n"
        f"• /madad — सहायता\n\n"
        f"{DIVIDER}\n"
        f"_Your ID: `{uid}`_"
    )
    await update.message.reply_text(text, parse_mode='Markdown')


async def cmd_myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Anyone can use this."""
    uid  = update.effective_user.id
    name = update.effective_user.full_name or "—"
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"👤 *नाम:* {name}\n"
        f"🆔 *आपका Telegram ID:*\n`{uid}`\n\n"
        f"_{DIVIDER}_",
        parse_mode='Markdown'
    )


async def cmd_play(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, reason = check_auth(update)
    if not auth:
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n❌ आपको इस bot का उपयोग करने की अनुमति नहीं है।"
        )
        return

    if not context.args:
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"❌ *तरीका:*\n"
            f"`/bajao <गाने का नाम>`\n"
            f"`/bajao <YouTube link>`",
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
            f"{BRAND}\n{DIVIDER}\n\n⏳ Link मिल गया, जानकारी ला रहा हूँ...",
            parse_mode='Markdown'
        )
        info = await asyncio.get_event_loop().run_in_executor(None, _yt_info, yt_url)
        title    = info['title']   or "अज्ञात"
        artist   = info['artist']  or ""
        duration = info['duration']
        tok      = uuid.uuid4().hex
        pending_video[tok] = {
            'url': yt_url, 'title': title, 'artist': artist,
            'duration': duration, 'chat_id': chat_id, 'private': private,
        }
        kb = [
            [InlineKeyboardButton("🎵 सिर्फ ऑडियो", callback_data=f"q|{tok}|audio")],
            [
                InlineKeyboardButton("360p",  callback_data=f"q|{tok}|360p"),
                InlineKeyboardButton("480p",  callback_data=f"q|{tok}|480p"),
                InlineKeyboardButton("720p",  callback_data=f"q|{tok}|720p"),
            ],
            [
                InlineKeyboardButton("1080p",       callback_data=f"q|{tok}|1080p"),
                InlineKeyboardButton("Best Quality", callback_data=f"q|{tok}|best"),
            ],
        ]
        await msg.edit_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"🎬  *{title}*\n"
            + (f"🎤  {artist}\n" if artist else "")
            + (f"⏱  {dur_str(duration)}\n" if duration else "")
            + f"\n{DIVIDER}\n\n📥 *किस quality में download करें?*",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(kb)
        )
        return

    # ── Keyword search ───────────────────────────────────────────────────────
    msg = await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n🔍 ढूंढ रहा हूँ: *{query}*...",
        parse_mode='Markdown'
    )
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None, find_and_download, query
        )
        if not result:
            await msg.edit_text(
                f"{BRAND}\n{DIVIDER}\n\n"
                f"❌ गाना नहीं मिला।\n"
                f"थोड़ा अलग नाम लिखकर कोशिश करें।",
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
                f"✅ मिल गया!\n🎵 *{title}*\n\n📤 भेज रहा हूँ...",
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
            # Group → voice chat
            kb = [[InlineKeyboardButton("⏹ रोको", callback_data="stop")]]
            await msg.edit_text(
                card(title, artist, duration) + "\n\n▶️ *बज रहा है...*",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(kb)
            )
            ok = await vc_play(chat_id, fp, title)
            if not ok:
                await msg.edit_text(
                    f"{BRAND}\n{DIVIDER}\n\n"
                    f"❌ Voice chat join नहीं हो पाया।\n"
                    f"Bot को Admin बनाओ और Voice Chat खुला रखो।",
                    parse_mode='Markdown'
                )
    except Exception as e:
        logger.error(f"cmd_play: {e}")
        await msg.edit_text(
            f"{BRAND}\n{DIVIDER}\n\n❌ Error: {e}",
            parse_mode='Markdown'
        )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, _ = check_auth(update)
    if not auth:
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n❌ अनुमति नहीं है।"
        )
        return
    await vc_stop(update.effective_chat.id)
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n⏹ *रोक दिया गया।*",
        parse_mode='Markdown'
    )


async def cmd_current(update: Update, context: ContextTypes.DEFAULT_TYPE):
    auth, _ = check_auth(update)
    if not auth:
        return
    cur = active_chats.get(update.effective_chat.id, {}).get('current')
    if not cur:
        await update.message.reply_text(
            f"{BRAND}\n{DIVIDER}\n\n❌ अभी कुछ नहीं बज रहा।",
            parse_mode='Markdown'
        )
        return
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n▶️ *अभी बज रहा है:*\n🎵 {cur}",
        parse_mode='Markdown'
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"{BRAND}\n{DIVIDER}\n\n"
        f"📋 *Commands:*\n\n"
        f"🎵 `/bajao <गाने का नाम>`\n"
        f"   → गाना बजाओ या MP3 download करो\n\n"
        f"🔗 `/bajao <YouTube link>`\n"
        f"   → Quality चुनो और download करो\n\n"
        f"⏹ `/roko`\n"
        f"   → Voice chat बंद करो\n\n"
        f"🎵 `/abhi`\n"
        f"   → अभी क्या बज रहा है\n\n"
        f"🆔 `/meri_id`\n"
        f"   → अपना Telegram ID देखो\n\n"
        f"{DIVIDER}\n"
        f"_Group में: Voice chat में बजेगा_\n"
        f"_DM में: MP3 file मिलेगी_",
        parse_mode='Markdown'
    )


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  CALLBACK HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q    = update.callback_query
    data = q.data
    await q.answer()

    # Stop button
    if data == "stop":
        auth, _ = check_auth(update)
        if not auth:
            await q.answer("❌ अनुमति नहीं है!", show_alert=True)
            return
        await vc_stop(update.effective_chat.id)
        await q.edit_message_text(
            f"{BRAND}\n{DIVIDER}\n\n⏹ *रोक दिया गया।*",
            parse_mode='Markdown'
        )
        return

    # Quality selection: q|token|quality
    if data.startswith("q|"):
        parts = data.split("|")
        if len(parts) != 3:
            return
        _, tok, quality = parts
        pv = pending_video.get(tok)
        if not pv:
            await q.edit_message_text(
                f"{BRAND}\n{DIVIDER}\n\n❌ Request expire हो गई। फिर से /bajao करें।",
                parse_mode='Markdown'
            )
            return

        auth, _ = check_auth(update)
        if not auth:
            await q.answer("❌ अनुमति नहीं है!", show_alert=True)
            return

        url      = pv['url']
        title    = pv['title']
        artist   = pv['artist']
        duration = pv['duration']

        label_map = {
            'audio': '🎵 ऑडियो', '360p': '📹 360p', '480p': '📹 480p',
            '720p': '📹 720p', '1080p': '📹 1080p', 'best': '📹 Best'
        }
        label = label_map.get(quality, quality)

        await q.edit_message_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"⬇️ Download हो रहा है ({label})\n"
            f"🎵 *{title}*\n"
            + (f"🎤 {artist}\n" if artist else "")
            + f"\nकृपया प्रतीक्षा करें...",
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
                f"❌ Download नहीं हो पाया।\n"
                f"दूसरी quality आज़माएं या थोड़ी देर बाद try करें।",
                parse_mode='Markdown'
            )
            return

        fp       = result['file']
        is_vid   = result.get('is_video', False)
        size_mb  = os.path.getsize(fp) / (1024 * 1024)

        if size_mb > 1900:
            clean(fp)
            await q.edit_message_text(
                f"{BRAND}\n{DIVIDER}\n\n"
                f"❌ File बहुत बड़ी है ({size_mb:.0f} MB)।\n"
                f"Telegram की limit 2GB है। छोटी quality चुनें।",
                parse_mode='Markdown'
            )
            return

        await q.edit_message_text(
            f"{BRAND}\n{DIVIDER}\n\n"
            f"✅ *{title}*\n"
            f"📤 भेज रहा हूँ... ({size_mb:.1f} MB)",
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
                f"{BRAND}\n{DIVIDER}\n\n❌ भेजने में error: {e}",
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

    # Commands
    app.add_handler(CommandHandler(["start", "shuru"],    cmd_start))
    app.add_handler(CommandHandler(["play",  "bajao"],    cmd_play))
    app.add_handler(CommandHandler(["stop",  "roko"],     cmd_stop))
    app.add_handler(CommandHandler(["current", "abhi"],   cmd_current))
    app.add_handler(CommandHandler(["myid", "meri_id"],   cmd_myid))
    app.add_handler(CommandHandler(["help", "madad"],     cmd_help))
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
