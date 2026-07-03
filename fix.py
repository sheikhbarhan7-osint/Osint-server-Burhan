#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import telebot
import requests
import json
import time
from datetime import datetime, timedelta
import re
import threading
import logging
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    ForceReply
)

# ==================== CONFIGURATION ====================
BOT_TOKEN = "8875990060:AAHOyZPWzv4U0xZwRiLGJNEVJlt96EiCYTU"
YOUR_CHANNEL = "@PUBG_BGMI_IOS_HACKS"
BOT_USERNAME = "@OSINTMasterProBot"

# ADMIN IDs - Owner ID added
ADMIN_IDS = [2062068620, 788333999]  # Owner ID + Your ID

# ==================== NEW API CONFIGURATION ====================
API_KEYS = {
    'free': 'Demo',  # Free demo key (10 requests/day)
    'Demo': 'Demo'  # Premium key (unlimited)
}

APIS = {
    'aadhaar': {
        'url': 'https://aadhaar.asurpapa.workers.dev/api',
        'key_param': 'key',
        'num_param': 'aadhaar'
    },
    'number': {
        'url': 'https://num-to-info.asurpapa.workers.dev/api',
        'key_param': 'key',
        'number_param': 'number'
    },
    'vehicle': {
        'url': 'https://vehicle.asurpapa.workers.dev/api',
        'key_param': 'key',
        'rc_param': 'rc'
    },
    'pakistan': {
        'url': 'https://pakistan.asurpapa.workers.dev/api',
        'key_param': 'key',
        'number_param': 'number'
    }
}

# ==================== PREMIUM CONFIG ====================
PREMIUM_PRICES = {
    'day': {'price': 199, 'days': 7, 'label': '7 Days'},
    'week': {'price': 299, 'days': 30, 'label': '1 Month'},
    'month': {'price': 499, 'days': 90, 'label': '3 Months'},
    'year': {'price': 999, 'days': 365, 'label': '1 Year'}
}

# ==================== LOGGING ====================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== DATABASE ====================
class Database:
    def __init__(self):
        self.users = {}
        self.daily_users = {}
        self.request_log = []
        self.banned_users = set()
        self.muted_users = set()
        self.admin_ids = set(ADMIN_IDS)
        self.maintenance_mode = False
        self.broadcast_history = []
        self.user_states = {}
        self.premium_users = {}  # {user_id: expiry_timestamp}
        self.daily_requests = {}  # {user_id: {'date': date, 'count': count}}
        self.pending_payments = {}  # {user_id: {'plan': plan, 'amount': amount}}

    def add_user(self, user):
        uid = user.id
        if uid not in self.users:
            self.users[uid] = {
                'first_name': user.first_name or 'Unknown',
                'username': user.username,
                'joined': datetime.now().isoformat(),
                'requests': 0,
                'last_active': datetime.now().isoformat(),
                'warnings': 0
            }
        self.users[uid]['last_active'] = datetime.now().isoformat()

        today = datetime.now().strftime("%Y-%m-%d")
        if today not in self.daily_users:
            self.daily_users[today] = set()
        self.daily_users[today].add(uid)

        # Initialize daily request counter
        if uid not in self.daily_requests:
            self.daily_requests[uid] = {'date': today, 'count': 0}
        elif self.daily_requests[uid]['date'] != today:
            self.daily_requests[uid] = {'date': today, 'count': 0}

    def add_request(self, uid):
        if uid in self.users:
            self.users[uid]['requests'] += 1

        # Update daily counter
        today = datetime.now().strftime("%Y-%m-%d")
        if uid in self.daily_requests:
            if self.daily_requests[uid]['date'] == today:
                self.daily_requests[uid]['count'] += 1
            else:
                self.daily_requests[uid] = {'date': today, 'count': 1}
        else:
            self.daily_requests[uid] = {'date': today, 'count': 1}

        self.request_log.append({
            'user_id': uid,
            'time': datetime.now().isoformat()
        })

    def get_daily_count(self, uid):
        today = datetime.now().strftime("%Y-%m-%d")
        if uid in self.daily_requests and self.daily_requests[uid]['date'] == today:
            return self.daily_requests[uid]['count']
        return 0

    def is_premium(self, uid):
        if uid not in self.premium_users:
            return False
        expiry = self.premium_users[uid]
        if datetime.now().timestamp() > expiry:
            del self.premium_users[uid]
            return False
        return True

    def get_premium_expiry(self, uid):
        if uid in self.premium_users:
            return datetime.fromtimestamp(self.premium_users[uid])
        return None

    def add_premium(self, uid, days):
        expiry = datetime.now().timestamp() + (days * 86400)
        # If already premium, extend
        if uid in self.premium_users:
            current = self.premium_users[uid]
            if current > datetime.now().timestamp():
                expiry = current + (days * 86400)
        self.premium_users[uid] = expiry
        return expiry

    def is_banned(self, uid):
        return uid in self.banned_users

    def is_muted(self, uid):
        return uid in self.muted_users

    def is_admin(self, uid):
        return uid in self.admin_ids

    def ban_user(self, uid):
        self.banned_users.add(uid)

    def unban_user(self, uid):
        self.banned_users.discard(uid)

    def mute_user(self, uid):
        self.muted_users.add(uid)

    def unmute_user(self, uid):
        self.muted_users.discard(uid)

    def warn_user(self, uid):
        if uid in self.users:
            self.users[uid]['warnings'] += 1
            return self.users[uid]['warnings']
        return 0

    def get_stats(self):
        today = datetime.now().strftime("%Y-%m-%d")
        return {
            'total_users': len(self.users),
            'today_active': len(self.daily_users.get(today, set())),
            'total_requests': len(self.request_log),
            'banned': len(self.banned_users),
            'muted': len(self.muted_users),
            'premium': len(self.premium_users)
        }

    def get_top_users(self, limit=10):
        sorted_users = sorted(
            self.users.items(),
            key=lambda x: x[1]['requests'],
            reverse=True
        )[:limit]
        return sorted_users

    # New methods for admin commands
    def reset_user_daily(self, uid):
        today = datetime.now().strftime("%Y-%m-%d")
        if uid in self.daily_requests:
            self.daily_requests[uid] = {'date': today, 'count': 0}

    def purge_user(self, uid):
        # Completely remove user data
        self.users.pop(uid, None)
        self.daily_requests.pop(uid, None)
        self.premium_users.pop(uid, None)
        self.banned_users.discard(uid)
        self.muted_users.discard(uid)
        self.admin_ids.discard(uid)
        # remove from log (optional, keep for history)
        # keep request_log for statistics

    def remove_admin(self, uid):
        if uid in self.admin_ids and uid not in ADMIN_IDS:  # cannot remove original admins
            self.admin_ids.discard(uid)
            return True
        return False

db = Database()

# ==================== EMOJI CONSTANTS ====================
class E:
    CROWN = '\U0001F451'
    DIAMOND = '\U0001F48E'
    STAR = '\u2B50'
    SPARKLES = '\u2728'
    FIRE = '\U0001F525'
    ROCKET = '\U0001F680'
    GIFT = '\U0001F381'
    TROPHY = '\U0001F3C6'
    RAINBOW = '\U0001F308'
    PARTY = '\U0001F389'
    SEARCH = '\U0001F50D'
    BACK = '\U0001F519'
    CHECK = '\u2705'
    CROSS = '\u274C'
    WARNING = '\u26A0\uFE0F'
    INFO = '\u2139\uFE0F'
    QUESTION = '\u2753'
    LIGHTNING = '\u26A1'
    TARGET = '\U0001F3AF'
    PHONE = '\U0001F4F1'
    SHIELD = '\U0001F6E1\uFE0F'
    LOCK = '\U0001F510'
    KEY = '\U0001F511'
    GLOBE = '\U0001F310'
    SERVER = '\U0001F5A5\uFE0F'
    DATABASE = '\U0001F5C4\uFE0F'
    NINJA = '\U0001F977'
    HACKER = '\U0001F468\u200D\U0001F4BB'
    KING = '\U0001F934'
    ROBOT = '\U0001F916'
    COOL = '\U0001F60E'
    MEDAL = '\U0001F947'
    ONLINE = '\U0001F7E2'
    OFFLINE = '\U0001F534'
    ADMIN = '\U0001F6E1\uFE0F'
    BAN = '\U0001F6AB'
    MUTE = '\U0001F507'
    UNMUTE = '\U0001F50A'
    BROADCAST = '\U0001F4E2'
    MAINTENANCE = '\U0001F527'
    CHART = '\U0001F4CA'
    USERS = '\U0001F465'
    CLOCK = '\U0001F552'
    PREMIUM = '\U0001F3C6'
    CAR = '\U0001F697'
    PAKISTAN = '\U0001F1F5\U0001F1F0'
    IP = '\U0001F4E1'          # Satellite antenna for IP lookup
    INSTAGRAM = '\U0001F4F8'   # Camera for Instagram
    TELEGRAM = '\u2708\uFE0F'  # Airplane for Telegram
    EMAIL = '\U0001F4E7'       # E-mail envelope

# ==================== UI HELPER ====================
class UI:
    @staticmethod
    def header(title):
        line = E.SPARKLES + '=' * 30 + E.SPARKLES
        return '\n'.join([
            line,
            E.CROWN + ' <b>' + title + '</b> ' + E.CROWN,
            line
        ])

    @staticmethod
    def section(title, emoji=None):
        if emoji is None:
            emoji = E.STAR
        line = emoji + '\u2500' * 25 + emoji
        return '\n'.join([
            '',
            line,
            emoji + ' <b>' + title + '</b>',
            line,
            ''
        ])

    @staticmethod
    def footer():
        line1 = E.RAINBOW + '\u2500' * 25 + E.RAINBOW
        return '\n'.join([
            '',
            line1,
            E.FIRE + ' <b>For More Updates Join:</b>',
            E.STAR + ' <b>' + YOUR_CHANNEL + '</b>',
            E.ROCKET + ' <b>FREE OSINT TOOLS AND MORE!</b>',
            line1
        ])

    @staticmethod
    def glass_card(title, content):
        return '\n'.join([
            '\u2554' + '\u2550' * 24 + '\u2557',
            '\u2551 \u2728 ' + title.center(20) + ' \u2728 \u2551',
            '\u2560' + '\u2550' * 24 + '\u2563',
            '\u2551 ' + content.ljust(22) + ' \u2551',
            '\u255A' + '\u2550' * 24 + '\u255D'
        ])

# ==================== BOT INIT ====================
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')

# ==================== KEYBOARDS ====================
def main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        KeyboardButton(E.PHONE + ' NUMBER LOOKUP'),
        KeyboardButton(E.SHIELD + ' AADHAAR INFO'),
        KeyboardButton(E.CAR + ' VEHICLE INFO'),
        KeyboardButton(E.PAKISTAN + ' PAKISTAN NUMBER'),
        KeyboardButton(E.IP + ' IP LOOKUP'),
        KeyboardButton(E.INSTAGRAM + ' INSTAGRAM LOOKUP'),
        KeyboardButton(E.TELEGRAM + ' TELEGRAM LOOKUP'),
        KeyboardButton(E.EMAIL + ' EMAIL LOOKUP'),
        KeyboardButton(E.CROWN + ' MY PROFILE'),
        KeyboardButton(E.DIAMOND + ' PREMIUM'),
        KeyboardButton(E.GLOBE + ' STATISTICS'),
        KeyboardButton(E.QUESTION + ' HELP'),
        KeyboardButton(E.NINJA + ' DEVELOPER'),
    ]
    # Arrange buttons in rows of 2
    for i in range(0, len(buttons), 2):
        if i+1 < len(buttons):
            keyboard.add(buttons[i], buttons[i+1])
        else:
            keyboard.add(buttons[i])
    return keyboard

def admin_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton(E.ADMIN + ' ADMIN PANEL'),
        KeyboardButton(E.BACK + ' MAIN MENU')
    )
    return keyboard

def channel_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=1)
    channel_url = 'https://t.me/' + YOUR_CHANNEL.replace('@', '')
    keyboard.add(
        InlineKeyboardButton(
            E.CROWN + ' JOIN ' + YOUR_CHANNEL + ' - FREE TOOLS ' + E.CROWN,
            url=channel_url
        ),
        InlineKeyboardButton(
            E.FIRE + ' MORE EXCLUSIVE BOTS ' + E.FIRE,
            url=channel_url
        )
    )
    return keyboard

def premium_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(E.DIAMOND + ' 7 Days - ₹199', callback_data='premium_day'),
        InlineKeyboardButton(E.PREMIUM + ' 1 Month - ₹299', callback_data='premium_week'),
        InlineKeyboardButton(E.CROWN + ' 3 Months - ₹499', callback_data='premium_month'),
        InlineKeyboardButton(E.KING + ' 1 Year - ₹999', callback_data='premium_year')
    )
    keyboard.add(
        InlineKeyboardButton(E.BACK + ' Back to Menu', callback_data='back_to_menu')
    )
    return keyboard

# ==================== HELPER FUNCTIONS ====================
def validate_phone(number):
    cleaned = re.sub(r'[^0-9]', '', str(number))
    if cleaned.startswith('91') and len(cleaned) == 12:
        cleaned = cleaned[2:]
    elif cleaned.startswith('0') and len(cleaned) == 11:
        cleaned = cleaned[1:]
    if len(cleaned) == 10 and cleaned[0] in '6789':
        return cleaned
    return None

def validate_aadhaar(number):
    cleaned = re.sub(r'[^0-9]', '', str(number))
    if len(cleaned) == 12 and cleaned[0] not in '01':
        return cleaned
    return None

def validate_vehicle(number):
    cleaned = re.sub(r'[^A-Za-z0-9]', '', str(number)).upper()
    if len(cleaned) >= 6 and len(cleaned) <= 15:
        return cleaned
    return None

def validate_pakistan_number(number):
    cleaned = re.sub(r'[^0-9]', '', str(number))
    # Pakistan numbers are 10-11 digits (3 digit code + 7-8 digit number)
    if len(cleaned) == 10 or len(cleaned) == 11:
        return cleaned
    return None

def validate_ip(ip_str):
    # Basic IPv4 validation
    parts = ip_str.strip().split('.')
    if len(parts) != 4:
        return None
    try:
        for p in parts:
            if not 0 <= int(p) <= 255:
                return None
        return ip_str.strip()
    except:
        return None

def validate_instagram(username):
    # Basic Instagram username validation
    cleaned = username.strip().lstrip('@')
    if re.match(r'^[a-zA-Z0-9._]{1,30}$', cleaned):
        return cleaned
    return None

def validate_telegram(username):
    # Telegram username: alphanumeric + underscore, 5-32 chars
    cleaned = username.strip().lstrip('@')
    if re.match(r'^[a-zA-Z][a-zA-Z0-9_]{4,31}$', cleaned):
        return cleaned
    return None

def validate_email(email):
    # Basic email format
    if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email.strip()):
        return email.strip()
    return None

def mask_aadhaar(aadhaar):
    return aadhaar[:4] + 'XXXX' + aadhaar[8:]

def get_api_key(uid):
    if db.is_premium(uid):
        return API_KEYS['premium']
    return API_KEYS['free']

def check_rate_limit(uid):
    # Admins always unlimited
    if db.is_admin(uid):
        return True, 0
    if db.is_premium(uid):
        return True, 0

    daily_count = db.get_daily_count(uid)
    if daily_count >= 5:  # Changed from 10 to 5
        return False, 5 - daily_count

    return True, 5 - daily_count

def call_api(api_name, params):
    """Generic API caller with error handling"""
    try:
        api_config = APIS.get(api_name)
        if not api_config:
            return {"error": "API not found"}

        url = api_config['url']

        # Build params with proper key
        api_params = {}
        for key, value in params.items():
            if key == 'key':
                api_params[api_config.get('key_param', 'key')] = value
            elif key == 'number' and 'number_param' in api_config:
                api_params[api_config['number_param']] = value
            elif key == 'aadhaar' and 'num_param' in api_config:
                api_params[api_config['num_param']] = value
            elif key == 'vehicle' and 'rc_param' in api_config:
                api_params[api_config['rc_param']] = value
            else:
                api_params[key] = value

        logger.info(f"Calling API: {api_name} with params: {api_params}")

        resp = requests.get(url, params=api_params, timeout=30)

        # Try to parse JSON
        try:
            result = resp.json()
        except:
            # If response is not JSON, try to parse as text
            result = {"result": resp.text}

        # Check if result is a list
        if isinstance(result, list) and len(result) > 0:
            result = {"result": result}

        return result

    except requests.exceptions.Timeout:
        return {"error": "Request timeout. Please try again."}
    except requests.exceptions.ConnectionError:
        return {"error": "Connection error. Please check your internet."}
    except Exception as e:
        logger.error(f'API error {api_name}: {str(e)}')
        return {"error": f"Service temporarily unavailable. {str(e)}"}

def format_api_data(result):
    """Format API response data properly"""
    data_lines = []

    # Get data from different possible response keys
    data = result.get('result') or result.get('data') or result

    if isinstance(data, dict):
        for key, value in data.items():
            if value is not None and str(value).lower() != 'null' and str(value).strip():
                key_display = key.replace('_', ' ').title()

                if isinstance(value, str):
                    value = re.sub(r'[!.]{2,}', '', value)
                    value = re.sub(r'!+', ', ', value)
                    value = value.strip(', ')

                data_lines.append(
                    E.STAR + ' <b>' + key_display + ':</b> <code>' + str(value) + '</code>'
                )
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                for key, value in item.items():
                    if value is not None and str(value).lower() != 'null' and str(value).strip():
                        key_display = key.replace('_', ' ').title()
                        if isinstance(value, str):
                            value = re.sub(r'[!.]{2,}', '', value)
                            value = re.sub(r'!+', ', ', value)
                            value = value.strip(', ')
                        data_lines.append(
                            E.STAR + ' <b>' + key_display + ':</b> <code>' + str(value) + '</code>'
                        )
    elif isinstance(data, str):
        # If data is a string, try to parse it as JSON
        try:
            parsed = json.loads(data)
            return format_api_data({"result": parsed})
        except:
            data_lines.append(E.STAR + ' <b>Response:</b> <code>' + str(data)[:500] + '</code>')

    if not data_lines:
        data_lines.append(E.INFO + ' <i>No detailed data found for this query.</i>')

    return '\n'.join(data_lines)

# ==================== USER COMMANDS ====================

@bot.message_handler(commands=['start'])
def cmd_start(message):
    try:
        user = message.from_user
        uid = user.id

        # Check ban
        if db.is_banned(uid):
            bot.reply_to(message, E.CROSS + ' <b>You are banned from this bot!</b>\n' + E.INFO + ' Contact admin for appeal.')
            return

        # Check maintenance
        if db.maintenance_mode and not db.is_admin(uid):
            bot.reply_to(
                message,
                E.MAINTENANCE + ' <b>Bot is under maintenance!</b>\n' +
                E.INFO + ' Please try again later.\n' +
                E.STAR + ' Join ' + YOUR_CHANNEL + ' for updates.'
            )
            return

        db.add_user(user)

        first_name = user.first_name or 'Friend'
        username = '@' + user.username if user.username else 'User'

        # Check premium status
        premium_status = ''
        if db.is_premium(uid):
            expiry = db.get_premium_expiry(uid)
            if expiry:
                premium_status = (
                    '\n' + E.PREMIUM + ' <b>PREMIUM USER</b>\n' +
                    E.CLOCK + ' Expires: <code>' + expiry.strftime('%Y-%m-%d %H:%M') + '</code>'
                )

        remaining = 5 - db.get_daily_count(uid) if not db.is_premium(uid) and not db.is_admin(uid) else "Unlimited"

        welcome_text = (
            UI.header('WELCOME TO OSINT MASTER PRO') + '\n\n' +
            E.ROBOT + ' <b>Hello ' + first_name + '!</b>\n' +
            E.NINJA + ' <b>' + username + '</b>' +
            premium_status + '\n\n' +
            UI.section('PREMIUM FEATURES', E.DIAMOND) +
            E.STAR + ' \u2022 ' + E.PHONE + ' Phone Number OSINT\n' +
            E.STAR + ' \u2022 ' + E.SHIELD + ' Aadhaar Information\n' +
            E.STAR + ' \u2022 ' + E.CAR + ' Vehicle Information\n' +
            E.STAR + ' \u2022 ' + E.PAKISTAN + ' Pakistan Number Lookup\n' +
            E.STAR + ' \u2022 ' + E.IP + ' IP Address Lookup\n' +
            E.STAR + ' \u2022 ' + E.INSTAGRAM + ' Instagram Username OSINT\n' +
            E.STAR + ' \u2022 ' + E.TELEGRAM + ' Telegram Username OSINT\n' +
            E.STAR + ' \u2022 ' + E.EMAIL + ' Email OSINT\n' +
            E.STAR + ' \u2022 ' + E.LIGHTNING + ' Real-time Lookup\n' +
            E.STAR + ' \u2022 ' + E.ROCKET + ' Ultra Fast Speed\n' +
            UI.section('DAILY LIMITS', E.INFO) +
            E.STAR + ' \u2022 FREE: 5 requests/day\n' +
            E.STAR + ' \u2022 PREMIUM: Unlimited\n' +
            E.STAR + ' \u2022 ADMINS: Unlimited\n' +
            UI.section('QUICK STATUS', E.LIGHTNING) +
            E.ONLINE + ' <b>Bot:</b> Online\n' +
            E.ONLINE + ' <b>API:</b> Connected\n' +
            E.CHECK + ' <b>Access:</b> ' + ('PREMIUM' if db.is_premium(uid) else ('ADMIN' if db.is_admin(uid) else 'FREE')) + '\n' +
            E.INFO + ' <b>Remaining:</b> ' + (str(remaining) if isinstance(remaining, int) else remaining) + ' today\n' +
            '\n' + E.RAINBOW + '\u2500' * 25 + E.RAINBOW + '\n' +
            E.GIFT + ' <b>USE BUTTONS BELOW TO START</b>\n' +
            E.RAINBOW + '\u2500' * 25 + E.RAINBOW +
            UI.footer()
        )

        bot.send_message(message.chat.id, welcome_text, reply_markup=main_keyboard())

        # Channel promo
        time.sleep(0.5)
        promo_text = (
            E.GIFT + ' <b>Join our channel for more FREE tools!</b>\n' +
            E.STAR + ' Daily updates and exclusive content!'
        )
        bot.send_message(message.chat.id, promo_text, reply_markup=channel_keyboard())

    except Exception as e:
        logger.error('Start error: ' + str(e))
        bot.reply_to(message, E.CROSS + ' Error starting. Please try again.')

@bot.message_handler(commands=['help'])
def cmd_help(message):
    try:
        help_text = (
            UI.header('HELP CENTER') + '\n' +
            UI.section('HOW TO USE', E.TARGET) +
            E.STAR + ' <b>1. NUMBER LOOKUP:</b>\n' +
            '   ' + E.PHONE + ' Click "' + E.PHONE + ' NUMBER LOOKUP"\n' +
            '   ' + E.PHONE + ' Enter 10-digit mobile number\n' +
            '   ' + E.PHONE + ' Get instant details\n\n' +
            E.STAR + ' <b>2. AADHAAR INFO:</b>\n' +
            '   ' + E.SHIELD + ' Click "' + E.SHIELD + ' AADHAAR INFO"\n' +
            '   ' + E.SHIELD + ' Enter 12-digit Aadhaar number\n' +
            '   ' + E.SHIELD + ' Get complete information\n\n' +
            E.STAR + ' <b>3. VEHICLE INFO:</b>\n' +
            '   ' + E.CAR + ' Click "' + E.CAR + ' VEHICLE INFO"\n' +
            '   ' + E.CAR + ' Enter vehicle registration number\n' +
            '   ' + E.CAR + ' Get vehicle details\n\n' +
            E.STAR + ' <b>4. PAKISTAN NUMBER:</b>\n' +
            '   ' + E.PAKISTAN + ' Click "' + E.PAKISTAN + ' PAKISTAN NUMBER"\n' +
            '   ' + E.PAKISTAN + ' Enter Pakistan mobile number\n' +
            '   ' + E.PAKISTAN + ' Get caller info\n\n' +
            E.STAR + ' <b>5. IP LOOKUP:</b>\n' +
            '   ' + E.IP + ' Click "' + E.IP + ' IP LOOKUP"\n' +
            '   ' + E.IP + ' Enter IPv4 address (e.g. 8.8.8.8)\n' +
            '   ' + E.IP + ' Get geolocation and ISP details\n\n' +
            E.STAR + ' <b>6. INSTAGRAM LOOKUP:</b>\n' +
            '   ' + E.INSTAGRAM + ' Click "' + E.INSTAGRAM + ' INSTAGRAM LOOKUP"\n' +
            '   ' + E.INSTAGRAM + ' Enter Instagram username\n' +
            '   ' + E.INSTAGRAM + ' Get profile info\n\n' +
            E.STAR + ' <b>7. TELEGRAM LOOKUP:</b>\n' +
            '   ' + E.TELEGRAM + ' Click "' + E.TELEGRAM + ' TELEGRAM LOOKUP"\n' +
            '   ' + E.TELEGRAM + ' Enter Telegram username\n' +
            '   ' + E.TELEGRAM + ' Get account details\n\n' +
            E.STAR + ' <b>8. EMAIL LOOKUP:</b>\n' +
            '   ' + E.EMAIL + ' Click "' + E.EMAIL + ' EMAIL LOOKUP"\n' +
            '   ' + E.EMAIL + ' Enter email address\n' +
            '   ' + E.EMAIL + ' Get associated information\n' +
            UI.section('DAILY LIMITS', E.INFO) +
            E.STAR + ' FREE Users: 5 requests/day\n' +
            E.STAR + ' PREMIUM Users: Unlimited\n' +
            E.STAR + ' ADMINS: Unlimited\n' +
            E.STAR + ' Premium Plans: 7 Days ₹199, 1 Month ₹299, 3 Months ₹499, 1 Year ₹999\n' +
            UI.section('TIPS', E.INFO) +
            E.STAR + ' Use valid inputs only\n' +
            E.STAR + ' Wait 2-5 seconds for results\n' +
            E.STAR + ' All features are FREE (limited) / PREMIUM (unlimited)\n' +
            UI.footer()
        )
        bot.send_message(message.chat.id, help_text, reply_markup=main_keyboard())
    except Exception as e:
        logger.error('Help error: ' + str(e))

@bot.message_handler(commands=['profile'])
def cmd_profile(message):
    try:
        user = message.from_user
        uid = user.id
        db.add_user(user)

        user_data = db.users.get(uid, {})
        requests = user_data.get('requests', 0)
        joined = user_data.get('joined', 'Unknown')
        warnings = user_data.get('warnings', 0)

        # Determine status
        if db.is_banned(uid):
            status = E.BAN + ' BANNED'
        elif db.is_muted(uid):
            status = E.MUTE + ' MUTED'
        elif db.is_premium(uid):
            expiry = db.get_premium_expiry(uid)
            expiry_str = expiry.strftime('%Y-%m-%d %H:%M') if expiry else 'Unknown'
            status = E.PREMIUM + ' PREMIUM (Expires: ' + expiry_str + ')'
        elif db.is_admin(uid):
            status = E.ADMIN + ' ADMIN'
        else:
            status = E.CROWN + ' FREE USER'

        remaining = 5 - db.get_daily_count(uid) if not db.is_premium(uid) and not db.is_admin(uid) else 'Unlimited'
        if isinstance(remaining, int) and remaining < 0:
            remaining = 0

        profile_text = (
            UI.header('YOUR PROFILE') + '\n' +
            UI.section('USER DETAILS', E.NINJA) +
            E.NINJA + ' <b>Name:</b> <code>' + (user.first_name or 'N/A') + '</code>\n' +
            E.STAR + ' <b>Username:</b> <code>@' + (user.username or 'N/A') + '</code>\n' +
            E.KEY + ' <b>User ID:</b> <code>' + str(uid) + '</code>\n' +
            UI.section('ACCOUNT INFO', E.DIAMOND) +
            E.MEDAL + ' <b>Status:</b> ' + status + '\n' +
            E.GLOBE + ' <b>Total Requests:</b> <code>' + str(requests) + '</code>\n' +
            E.INFO + ' <b>Remaining Today:</b> <code>' + str(remaining) + '/5</code>\n' +
            E.WARNING + ' <b>Warnings:</b> <code>' + str(warnings) + '/3</code>\n' +
            E.INFO + ' <b>Joined:</b> <code>' + joined[:10] + '</code>\n' +
            UI.footer()
        )
        bot.send_message(message.chat.id, profile_text, reply_markup=main_keyboard())
    except Exception as e:
        logger.error('Profile error: ' + str(e))

# ==================== BUTTON HANDLERS ====================

@bot.message_handler(func=lambda m: m.text and 'NUMBER LOOKUP' in m.text)
def btn_number_lookup(message):
    try:
        uid = message.from_user.id
        if db.is_banned(uid):
            bot.reply_to(message, E.CROSS + ' <b>Access Denied!</b>')
            return
        if db.maintenance_mode and not db.is_admin(uid):
            bot.reply_to(message, E.MAINTENANCE + ' <b>Bot under maintenance!</b>')
            return
        can_proceed, remaining = check_rate_limit(uid)
        if not can_proceed:
            bot.reply_to(message,
                E.WARNING + ' <b>Daily limit reached!</b>\n\n' +
                E.INFO + ' You have used all 5 free requests for today.\n' +
                E.DIAMOND + ' Upgrade to PREMIUM for unlimited access!\n'
            )
            return
        db.add_user(message.from_user)
        db.user_states[uid] = 'waiting_number'
        remaining = 5 - db.get_daily_count(uid)
        prompt = (
            UI.header('NUMBER OSINT MODE') + '\n\n' +
            E.STAR + ' <b>ENTER MOBILE NUMBER</b>\n\n' +
            E.TARGET + ' <b>Format:</b> 10 Digits\n' +
            E.TARGET + ' <b>Example:</b> <code>9876543210</code>\n' +
            E.TARGET + ' <b>Only Indian Numbers</b>\n\n' +
            E.INFO + ' <b>Remaining Today:</b> <code>' + str(remaining) + '/5</code>\n' +
            E.DIAMOND + ' <b>Premium:</b> Unlimited requests\n' +
            '\n' + E.RAINBOW + '\u2500' * 25 + E.RAINBOW +
            UI.footer()
        )
        msg = bot.send_message(message.chat.id, prompt, reply_markup=ForceReply(selective=True))
        bot.register_next_step_handler(msg, process_number)
    except Exception as e:
        logger.error('Number lookup error: ' + str(e))

@bot.message_handler(func=lambda m: m.text and 'AADHAAR INFO' in m.text)
def btn_aadhaar(message):
    try:
        uid = message.from_user.id
        if db.is_banned(uid): return
        if db.maintenance_mode and not db.is_admin(uid): return
        can_proceed, remaining = check_rate_limit(uid)
        if not can_proceed:
            bot.reply_to(message, E.WARNING + ' <b>Daily limit reached!</b>')
            return
        db.add_user(message.from_user)
        db.user_states[uid] = 'waiting_aadhaar'
        remaining = 5 - db.get_daily_count(uid)
        prompt = (
            UI.header('AADHAAR INFO MODE') + '\n\n' +
            E.STAR + ' <b>ENTER AADHAAR NUMBER</b>\n\n' +
            E.TARGET + ' <b>Format:</b> 12 Digits\n' +
            E.TARGET + ' <b>Example:</b> <code>123456789012</code>\n\n' +
            E.INFO + ' <b>Remaining Today:</b> <code>' + str(remaining) + '/5</code>\n' +
            E.DIAMOND + ' <b>Premium:</b> Unlimited requests\n' +
            E.WARNING + ' <b>Use Responsibly - Legal Purposes Only</b>\n'
        )
        msg = bot.send_message(message.chat.id, prompt, reply_markup=ForceReply(selective=True))
        bot.register_next_step_handler(msg, process_aadhaar)
    except Exception as e:
        logger.error('Aadhaar lookup error: ' + str(e))

@bot.message_handler(func=lambda m: m.text and 'VEHICLE INFO' in m.text)
def btn_vehicle(message):
    try:
        uid = message.from_user.id
        if db.is_banned(uid): return
        if db.maintenance_mode and not db.is_admin(uid): return
        can_proceed, remaining = check_rate_limit(uid)
        if not can_proceed:
            bot.reply_to(message, E.WARNING + ' <b>Daily limit reached!</b>')
            return
        db.add_user(message.from_user)
        db.user_states[uid] = 'waiting_vehicle'
        remaining = 5 - db.get_daily_count(uid)
        prompt = (
            UI.header('VEHICLE INFO MODE') + '\n\n' +
            E.STAR + ' <b>ENTER VEHICLE REGISTRATION NUMBER</b>\n\n' +
            E.TARGET + ' <b>Format:</b> Indian Vehicle Number\n' +
            E.TARGET + ' <b>Example:</b> <code>MP16CB6745</code>\n' +
            E.TARGET + ' <b>Example:</b> <code>MH04AB1234</code>\n\n' +
            E.INFO + ' <b>Remaining Today:</b> <code>' + str(remaining) + '/5</code>\n'
        )
        msg = bot.send_message(message.chat.id, prompt, reply_markup=ForceReply(selective=True))
        bot.register_next_step_handler(msg, process_vehicle)
    except Exception as e:
        logger.error('Vehicle lookup error: ' + str(e))

@bot.message_handler(func=lambda m: m.text and 'PAKISTAN NUMBER' in m.text)
def btn_pakistan(message):
    try:
        uid = message.from_user.id
        if db.is_banned(uid): return
        if db.maintenance_mode and not db.is_admin(uid): return
        can_proceed, remaining = check_rate_limit(uid)
        if not can_proceed:
            bot.reply_to(message, E.WARNING + ' <b>Daily limit reached!</b>')
            return
        db.add_user(message.from_user)
        db.user_states[uid] = 'waiting_pakistan'
        remaining = 5 - db.get_daily_count(uid)
        prompt = (
            UI.header('PAKISTAN NUMBER MODE') + '\n\n' +
            E.STAR + ' <b>ENTER PAKISTAN MOBILE NUMBER</b>\n\n' +
            E.TARGET + ' <b>Format:</b> 10-11 Digits\n' +
            E.TARGET + ' <b>Example:</b> <code>3362006909</code>\n' +
            E.TARGET + ' <b>Example:</b> <code>3123456789</code>\n\n' +
            E.INFO + ' <b>Remaining Today:</b> <code>' + str(remaining) + '/5</code>\n'
        )
        msg = bot.send_message(message.chat.id, prompt, reply_markup=ForceReply(selective=True))
        bot.register_next_step_handler(msg, process_pakistan)
    except Exception as e:
        logger.error('Pakistan lookup error: ' + str(e))

# New buttons
@bot.message_handler(func=lambda m: m.text and 'IP LOOKUP' in m.text)
def btn_ip_lookup(message):
    try:
        uid = message.from_user.id
        if db.is_banned(uid): return
        if db.maintenance_mode and not db.is_admin(uid): return
        can_proceed, remaining = check_rate_limit(uid)
        if not can_proceed:
            bot.reply_to(message, E.WARNING + ' <b>Daily limit reached!</b>')
            return
        db.add_user(message.from_user)
        db.user_states[uid] = 'waiting_ip'
        remaining = 5 - db.get_daily_count(uid)
        prompt = (
            UI.header('IP LOOKUP MODE') + '\n\n' +
            E.STAR + ' <b>ENTER IP ADDRESS</b>\n\n' +
            E.TARGET + ' <b>Format:</b> IPv4 (e.g. 8.8.8.8)\n' +
            E.TARGET + ' <b>Example:</b> <code>192.168.1.1</code>\n\n' +
            E.INFO + ' <b>Remaining Today:</b> <code>' + str(remaining) + '/5</code>\n' +
            E.DIAMOND + ' <b>Premium:</b> Unlimited\n'
        )
        msg = bot.send_message(message.chat.id, prompt, reply_markup=ForceReply(selective=True))
        bot.register_next_step_handler(msg, process_ip)
    except Exception as e:
        logger.error('IP lookup button error: ' + str(e))

@bot.message_handler(func=lambda m: m.text and 'INSTAGRAM LOOKUP' in m.text)
def btn_instagram_lookup(message):
    try:
        uid = message.from_user.id
        if db.is_banned(uid): return
        if db.maintenance_mode and not db.is_admin(uid): return
        can_proceed, remaining = check_rate_limit(uid)
        if not can_proceed:
            bot.reply_to(message, E.WARNING + ' <b>Daily limit reached!</b>')
            return
        db.add_user(message.from_user)
        db.user_states[uid] = 'waiting_instagram'
        remaining = 5 - db.get_daily_count(uid)
        prompt = (
            UI.header('INSTAGRAM USERNAME OSINT') + '\n\n' +
            E.STAR + ' <b>ENTER INSTAGRAM USERNAME</b>\n\n' +
            E.TARGET + ' <b>Format:</b> e.g. username (no @)\n' +
            E.TARGET + ' <b>Example:</b> <code>john_doe</code>\n\n' +
            E.INFO + ' <b>Remaining Today:</b> <code>' + str(remaining) + '/5</code>\n'
        )
        msg = bot.send_message(message.chat.id, prompt, reply_markup=ForceReply(selective=True))
        bot.register_next_step_handler(msg, process_instagram)
    except Exception as e:
        logger.error('Instagram lookup error: ' + str(e))

@bot.message_handler(func=lambda m: m.text and 'TELEGRAM LOOKUP' in m.text)
def btn_telegram_lookup(message):
    try:
        uid = message.from_user.id
        if db.is_banned(uid): return
        if db.maintenance_mode and not db.is_admin(uid): return
        can_proceed, remaining = check_rate_limit(uid)
        if not can_proceed:
            bot.reply_to(message, E.WARNING + ' <b>Daily limit reached!</b>')
            return
        db.add_user(message.from_user)
        db.user_states[uid] = 'waiting_telegram'
        remaining = 5 - db.get_daily_count(uid)
        prompt = (
            UI.header('TELEGRAM USERNAME OSINT') + '\n\n' +
            E.STAR + ' <b>ENTER TELEGRAM USERNAME</b>\n\n' +
            E.TARGET + ' <b>Format:</b> e.g. username (no @)\n' +
            E.TARGET + ' <b>Example:</b> <code>johndoe</code>\n\n' +
            E.INFO + ' <b>Remaining Today:</b> <code>' + str(remaining) + '/5</code>\n'
        )
        msg = bot.send_message(message.chat.id, prompt, reply_markup=ForceReply(selective=True))
        bot.register_next_step_handler(msg, process_telegram)
    except Exception as e:
        logger.error('Telegram lookup error: ' + str(e))

@bot.message_handler(func=lambda m: m.text and 'EMAIL LOOKUP' in m.text)
def btn_email_lookup(message):
    try:
        uid = message.from_user.id
        if db.is_banned(uid): return
        if db.maintenance_mode and not db.is_admin(uid): return
        can_proceed, remaining = check_rate_limit(uid)
        if not can_proceed:
            bot.reply_to(message, E.WARNING + ' <b>Daily limit reached!</b>')
            return
        db.add_user(message.from_user)
        db.user_states[uid] = 'waiting_email'
        remaining = 5 - db.get_daily_count(uid)
        prompt = (
            UI.header('EMAIL OSINT MODE') + '\n\n' +
            E.STAR + ' <b>ENTER EMAIL ADDRESS</b>\n\n' +
            E.TARGET + ' <b>Format:</b> user@domain.com\n' +
            E.TARGET + ' <b>Example:</b> <code>example@gmail.com</code>\n\n' +
            E.INFO + ' <b>Remaining Today:</b> <code>' + str(remaining) + '/5</code>\n'
        )
        msg = bot.send_message(message.chat.id, prompt, reply_markup=ForceReply(selective=True))
        bot.register_next_step_handler(msg, process_email)
    except Exception as e:
        logger.error('Email lookup error: ' + str(e))

@bot.message_handler(func=lambda m: m.text and 'MY PROFILE' in m.text)
def btn_profile(message):
    cmd_profile(message)

@bot.message_handler(func=lambda m: m.text and 'STATISTICS' in m.text)
def btn_stats(message):
    try:
        db.add_user(message.from_user)
        stats = db.get_stats()
        stats_text = (
            UI.header('LIVE STATISTICS') + '\n' +
            UI.section('GLOBAL DATA', E.GLOBE) +
            E.STAR + ' <b>Total Users:</b> <code>' + '{:,}'.format(stats['total_users']) + '</code>\n' +
            E.STAR + ' <b>Today Active:</b> <code>' + '{:,}'.format(stats['today_active']) + '</code>\n' +
            E.STAR + ' <b>Total Lookups:</b> <code>' + '{:,}'.format(stats['total_requests']) + '</code>\n' +
            E.DIAMOND + ' <b>Premium Users:</b> <code>' + '{:,}'.format(stats['premium']) + '</code>\n' +
            UI.section('MODERATION', E.SHIELD) +
            E.BAN + ' <b>Banned Users:</b> <code>' + '{:,}'.format(stats['banned']) + '</code>\n' +
            E.MUTE + ' <b>Muted Users:</b> <code>' + '{:,}'.format(stats['muted']) + '</code>\n' +
            UI.section('SYSTEM', E.SERVER) +
            E.ONLINE + ' <b>Bot:</b> Online\n' +
            E.ONLINE + ' <b>API:</b> Connected\n' +
            E.ONLINE + ' <b>Database:</b> Active\n' +
            E.CHECK + ' <b>Uptime:</b> 99.9%\n' +
            '\n' + E.RAINBOW + '\u2500' * 25 + E.RAINBOW + '\n' +
            E.PARTY + ' <b>GROWING FAST! SHARE NOW!</b>' +
            UI.footer()
        )
        bot.send_message(message.chat.id, stats_text, reply_markup=main_keyboard())
    except Exception as e:
        logger.error('Stats error: ' + str(e))

@bot.message_handler(func=lambda m: m.text and 'PREMIUM' in m.text)
def btn_premium(message):
    try:
        uid = message.from_user.id
        db.add_user(message.from_user)
        premium_status = ''
        if db.is_premium(uid):
            expiry = db.get_premium_expiry(uid)
            if expiry:
                premium_status = (
                    '\n' + E.PREMIUM + ' <b>You are a PREMIUM member!</b>\n' +
                    E.CLOCK + ' Expires: <code>' + expiry.strftime('%Y-%m-%d %H:%M') + '</code>\n' +
                    E.CHECK + ' Unlimited requests!'
                )
        else:
            premium_status = (
                '\n' + E.CROWN + ' <b>FREE User</b>\n' +
                E.INFO + ' 5 requests/day remaining: <code>' + str(5 - db.get_daily_count(uid)) + '/5</code>'
            )
        premium_text = (
            UI.header('PREMIUM PLANS') + '\n\n' +
            E.DIAMOND + ' <b>Upgrade to PREMIUM for unlimited access!</b>\n\n' +
            premium_status + '\n\n' +
            UI.section('PLANS', E.PREMIUM) +
            E.STAR + ' <b>7 Days:</b> ₹199\n' +
            E.STAR + ' <b>1 Month:</b> ₹299\n' +
            E.STAR + ' <b>3 Months:</b> ₹499\n' +
            E.STAR + ' <b>1 Year:</b> ₹999\n' +
            E.LIGHTNING + ' <b>How to Pay:</b>\n' +
            E.STAR + ' 1. Select your plan below\n' +
            E.STAR + ' 2. Pay via UPI/PhonePe/GPay\n' +
            E.STAR + ' 3. Send payment screenshot to admin\n' +
            E.STAR + ' 4. Get premium access instantly!\n' +
            UI.footer()
        )
        bot.send_message(message.chat.id, premium_text, reply_markup=premium_keyboard())
    except Exception as e:
        logger.error('Premium error: ' + str(e))

@bot.message_handler(func=lambda m: m.text and 'HELP' in m.text)
def btn_help(message):
    cmd_help(message)

@bot.message_handler(func=lambda m: m.text and 'DEVELOPER' in m.text)
def btn_developer(message):
    try:
        db.add_user(message.from_user)
        dev_text = (
            UI.header('DEVELOPER ZONE') + '\n' +
            UI.section('CREATOR', E.CROWN) +
            E.HACKER + ' <b>Developer:</b> RAHUL\n' +
            E.STAR + ' <b>Channel:</b> ' + YOUR_CHANNEL + '\n' +
            E.ROBOT + ' <b>Bot:</b> ' + BOT_USERNAME + '\n' +
            E.SPARKLES + ' <b>Version:</b> 7.0 PRODUCTION\n' +
            E.ROCKET + ' <b>Update:</b> 2026 Latest\n' +
            UI.section('SKILLS', E.DIAMOND) +
            E.STAR + ' \u2022 OSINT Tools Development\n' +
            E.STAR + ' \u2022 Telegram Bot Creation\n' +
            E.STAR + ' \u2022 API Integration\n' +
            E.STAR + ' \u2022 Security Research\n' +
            E.STAR + ' \u2022 Premium System\n' +
            UI.section('CONTACT', E.GLOBE) +
            E.STAR + ' Channel: ' + YOUR_CHANNEL + '\n' +
            E.STAR + ' Support: 24/7 Available\n' +
            E.STAR + ' Updates: Daily\n' +
            UI.footer()
        )
        bot.send_message(message.chat.id, dev_text, reply_markup=channel_keyboard())
    except Exception as e:
        logger.error('Developer error: ' + str(e))

@bot.message_handler(func=lambda m: m.text and 'MAIN MENU' in m.text)
def btn_main_menu(message):
    try:
        uid = message.from_user.id
        if uid in db.user_states:
            del db.user_states[uid]
        bot.send_message(
            message.chat.id,
            E.SPARKLES + ' <b>Main Menu</b> ' + E.SPARKLES + '\n\n' +
            E.STAR + ' Choose an option below\n' +
            E.ROCKET + ' All features are FREE (limited) / PREMIUM (unlimited)!',
            reply_markup=main_keyboard()
        )
    except Exception as e:
        logger.error('Main menu error: ' + str(e))

# ==================== PROCESSING FUNCTIONS ====================
def process_number(message):
    try:
        uid = message.from_user.id
        phone = validate_phone(message.text or '')
        if not phone:
            bot.send_message(message.chat.id, E.CROSS + ' <b>Invalid Number!</b>', reply_markup=main_keyboard())
            return
        db.add_request(uid)
        if uid in db.user_states: del db.user_states[uid]
        proc_msg = bot.send_message(message.chat.id, E.SEARCH + ' <b>Searching...</b>')
        bot.send_chat_action(message.chat.id, 'typing')
        api_key = get_api_key(uid)
        result = call_api('number', {'key': api_key, 'number': phone})
        try: bot.delete_message(message.chat.id, proc_msg.message_id)
        except: pass
        response = build_response('NUMBER DETAILS FOUND', phone, result, uid)
        bot.send_message(message.chat.id, response, reply_markup=main_keyboard())
        if not db.is_premium(uid) and not db.is_admin(uid):
            remaining = 5 - db.get_daily_count(uid)
            if remaining > 0:
                time.sleep(0.3)
                bot.send_message(message.chat.id, E.INFO + ' <b>Remaining today:</b> <code>' + str(remaining) + '/5</code>')
    except Exception as e:
        logger.error('Process number error: ' + str(e))

def process_aadhaar(message):
    try:
        uid = message.from_user.id
        aadhaar = validate_aadhaar(message.text or '')
        if not aadhaar:
            bot.send_message(message.chat.id, E.CROSS + ' <b>Invalid Aadhaar!</b>', reply_markup=main_keyboard())
            return
        db.add_request(uid)
        masked = mask_aadhaar(aadhaar)
        if uid in db.user_states: del db.user_states[uid]
        proc_msg = bot.send_message(message.chat.id, E.SEARCH + ' <b>Fetching Records...</b>')
        bot.send_chat_action(message.chat.id, 'typing')
        api_key = get_api_key(uid)
        result = call_api('aadhaar', {'key': api_key, 'aadhaar': aadhaar})
        try: bot.delete_message(message.chat.id, proc_msg.message_id)
        except: pass
        response = build_response('AADHAAR DETAILS FOUND', masked, result, uid)
        bot.send_message(message.chat.id, response, reply_markup=main_keyboard())
        if not db.is_premium(uid) and not db.is_admin(uid):
            remaining = 5 - db.get_daily_count(uid)
            if remaining > 0:
                time.sleep(0.3)
                bot.send_message(message.chat.id, E.INFO + ' <b>Remaining today:</b> <code>' + str(remaining) + '/5</code>')
    except Exception as e:
        logger.error('Process aadhaar error: ' + str(e))

def process_vehicle(message):
    try:
        uid = message.from_user.id
        vehicle = validate_vehicle(message.text or '')
        if not vehicle:
            bot.send_message(message.chat.id, E.CROSS + ' <b>Invalid Vehicle Number!</b>', reply_markup=main_keyboard())
            return
        db.add_request(uid)
        if uid in db.user_states: del db.user_states[uid]
        proc_msg = bot.send_message(message.chat.id, E.SEARCH + ' <b>Searching Vehicle Records...</b>')
        bot.send_chat_action(message.chat.id, 'typing')
        api_key = get_api_key(uid)
        result = call_api('vehicle', {'key': api_key, 'vehicle': vehicle})
        try: bot.delete_message(message.chat.id, proc_msg.message_id)
        except: pass
        response = build_response('VEHICLE DETAILS FOUND', vehicle, result, uid)
        bot.send_message(message.chat.id, response, reply_markup=main_keyboard())
        if not db.is_premium(uid) and not db.is_admin(uid):
            remaining = 5 - db.get_daily_count(uid)
            if remaining > 0:
                time.sleep(0.3)
                bot.send_message(message.chat.id, E.INFO + ' <b>Remaining today:</b> <code>' + str(remaining) + '/5</code>')
    except Exception as e:
        logger.error('Process vehicle error: ' + str(e))

def process_pakistan(message):
    try:
        uid = message.from_user.id
        number = validate_pakistan_number(message.text or '')
        if not number:
            bot.send_message(message.chat.id, E.CROSS + ' <b>Invalid Number!</b>', reply_markup=main_keyboard())
            return
        db.add_request(uid)
        if uid in db.user_states: del db.user_states[uid]
        proc_msg = bot.send_message(message.chat.id, E.SEARCH + ' <b>Searching Pakistan Records...</b>')
        bot.send_chat_action(message.chat.id, 'typing')
        api_key = get_api_key(uid)
        result = call_api('pakistan', {'key': api_key, 'number': number})
        try: bot.delete_message(message.chat.id, proc_msg.message_id)
        except: pass
        response = build_response('PAKISTAN NUMBER DETAILS', number, result, uid)
        bot.send_message(message.chat.id, response, reply_markup=main_keyboard())
        if not db.is_premium(uid) and not db.is_admin(uid):
            remaining = 5 - db.get_daily_count(uid)
            if remaining > 0:
                time.sleep(0.3)
                bot.send_message(message.chat.id, E.INFO + ' <b>Remaining today:</b> <code>' + str(remaining) + '/5</code>')
    except Exception as e:
        logger.error('Process pakistan error: ' + str(e))

# New placeholder processing functions
def process_ip(message):
    try:
        uid = message.from_user.id
        ip = validate_ip(message.text or '')
        if not ip:
            bot.send_message(message.chat.id, E.CROSS + ' <b>Invalid IP Address!</b>', reply_markup=main_keyboard())
            return
        db.add_request(uid)
        if uid in db.user_states: del db.user_states[uid]
        # Placeholder - API integration to be added
        placeholder_data = {"result": {"message": "IP lookup module will be integrated soon.", "ip": ip, "status": "Placeholder"}}
        response = build_response('IP LOOKUP (DEV)', ip, placeholder_data, uid)
        bot.send_message(message.chat.id, response, reply_markup=main_keyboard())
        if not db.is_premium(uid) and not db.is_admin(uid):
            remaining = 5 - db.get_daily_count(uid)
            if remaining > 0:
                bot.send_message(message.chat.id, E.INFO + ' <b>Remaining today:</b> <code>' + str(remaining) + '/5</code>')
    except Exception as e:
        logger.error('Process ip error: ' + str(e))

def process_instagram(message):
    try:
        uid = message.from_user.id
        username = validate_instagram(message.text or '')
        if not username:
            bot.send_message(message.chat.id, E.CROSS + ' <b>Invalid Instagram username!</b>', reply_markup=main_keyboard())
            return
        db.add_request(uid)
        if uid in db.user_states: del db.user_states[uid]
        placeholder_data = {"result": {"message": "Instagram OSINT module will be integrated soon.", "username": username, "status": "Placeholder"}}
        response = build_response('INSTAGRAM LOOKUP (DEV)', username, placeholder_data, uid)
        bot.send_message(message.chat.id, response, reply_markup=main_keyboard())
        if not db.is_premium(uid) and not db.is_admin(uid):
            remaining = 5 - db.get_daily_count(uid)
            if remaining > 0:
                bot.send_message(message.chat.id, E.INFO + ' <b>Remaining today:</b> <code>' + str(remaining) + '/5</code>')
    except Exception as e:
        logger.error('Process instagram error: ' + str(e))

def process_telegram(message):
    try:
        uid = message.from_user.id
        username = validate_telegram(message.text or '')
        if not username:
            bot.send_message(message.chat.id, E.CROSS + ' <b>Invalid Telegram username!</b>', reply_markup=main_keyboard())
            return
        db.add_request(uid)
        if uid in db.user_states: del db.user_states[uid]
        placeholder_data = {"result": {"message": "Telegram OSINT module will be integrated soon.", "username": username, "status": "Placeholder"}}
        response = build_response('TELEGRAM LOOKUP (DEV)', username, placeholder_data, uid)
        bot.send_message(message.chat.id, response, reply_markup=main_keyboard())
        if not db.is_premium(uid) and not db.is_admin(uid):
            remaining = 5 - db.get_daily_count(uid)
            if remaining > 0:
                bot.send_message(message.chat.id, E.INFO + ' <b>Remaining today:</b> <code>' + str(remaining) + '/5</code>')
    except Exception as e:
        logger.error('Process telegram error: ' + str(e))

def process_email(message):
    try:
        uid = message.from_user.id
        email = validate_email(message.text or '')
        if not email:
            bot.send_message(message.chat.id, E.CROSS + ' <b>Invalid Email address!</b>', reply_markup=main_keyboard())
            return
        db.add_request(uid)
        if uid in db.user_states: del db.user_states[uid]
        placeholder_data = {"result": {"message": "Email OSINT module will be integrated soon.", "email": email, "status": "Placeholder"}}
        response = build_response('EMAIL LOOKUP (DEV)', email, placeholder_data, uid)
        bot.send_message(message.chat.id, response, reply_markup=main_keyboard())
        if not db.is_premium(uid) and not db.is_admin(uid):
            remaining = 5 - db.get_daily_count(uid)
            if remaining > 0:
                bot.send_message(message.chat.id, E.INFO + ' <b>Remaining today:</b> <code>' + str(remaining) + '/5</code>')
    except Exception as e:
        logger.error('Process email error: ' + str(e))

def build_response(title, identifier, result, uid):
    if result.get('error'):
        return (
            E.CROSS + '\u2550' * 25 + E.CROSS + '\n' +
            E.WARNING + ' <b>ERROR OCCURRED</b>\n' +
            E.CROSS + '\u2550' * 25 + E.CROSS + '\n\n' +
            E.INFO + ' <i>' + str(result['error']) + '</i>\n\n' +
            E.STAR + ' <b>Tips:</b>\n' +
            '\u2022 Check input format\n' +
            '\u2022 Try again after few seconds\n' +
            UI.footer()
        )
    data = format_api_data(result)
    premium_badge = (E.PREMIUM + ' <b>Premium API</b>\n') if db.is_premium(uid) else ''
    if db.is_admin(uid) and not db.is_premium(uid):
        premium_badge = E.ADMIN + ' <b>Admin Access</b>\n'
    return (
        UI.header(title) + '\n\n' +
        E.TARGET + ' <b>Query:</b> <code>' + identifier + '</code>\n' +
        E.CHECK + ' <b>Status:</b> Success\n' +
        premium_badge +
        UI.section('INFORMATION', E.DIAMOND) +
        data + '\n' +
        UI.footer()
    )

# ==================== CALLBACK QUERY HANDLERS ====================
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        uid = call.from_user.id
        data = call.data
        if data == 'back_to_menu':
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            bot.send_message(call.message.chat.id, E.BACK + ' <b>Back to main menu</b>', reply_markup=main_keyboard())
            return
        if data.startswith('premium_'):
            plan = data.replace('premium_', '')
            if plan not in PREMIUM_PRICES:
                bot.answer_callback_query(call.id, "Invalid plan selected!")
                return
            plan_info = PREMIUM_PRICES[plan]
            db.pending_payments[uid] = {'plan': plan, 'amount': plan_info['price']}
            payment_text = (
                UI.header('PAYMENT DETAILS') + '\n\n' +
                E.DIAMOND + ' <b>Plan:</b> ' + plan_info['label'] + '\n' +
                E.STAR + ' <b>Price:</b> ₹' + str(plan_info['price']) + '\n' +
                E.INFO + ' <b>Valid for:</b> ' + str(plan_info['days']) + ' days\n' +
                E.CHECK + ' <b>Features:</b> Unlimited requests\n\n' +
                E.LIGHTNING + ' <b>How to Pay:</b>\n' +
                E.STAR + ' 1. Pay ₹' + str(plan_info['price']) + ' via UPI\n' +
                E.STAR + ' 2. Take a screenshot of payment\n' +
                E.STAR + ' 3. Send to admin: @Sheikh_barhan\n' +
                E.STAR + ' 4. Admin will activate your premium\n\n' +
                E.WARNING + ' <b>Note:</b> Send payment proof to admin manually.'
            )
            bot.edit_message_text(payment_text, call.message.chat.id, call.message.message_id, parse_mode='HTML')
            bot.answer_callback_query(call.id, "Plan selected! Please pay and contact admin.")
    except Exception as e:
        logger.error('Callback error: ' + str(e))
        bot.answer_callback_query(call.id, "Error processing request!")

# ==================== ADMIN COMMANDS ====================
@bot.message_handler(commands=['admin'])
def cmd_admin(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Access Denied! Admin only!</b>')
            return
        stats = db.get_stats()
        admin_text = (
            UI.header('ADMIN CONTROL PANEL') + '\n\n' +
            E.ADMIN + ' <b>Welcome Admin!</b>\n' +
            UI.section('BOT STATS', E.SERVER) +
            E.STAR + ' Total Users: <code>' + '{:,}'.format(stats['total_users']) + '</code>\n' +
            E.STAR + ' Today Active: <code>' + '{:,}'.format(stats['today_active']) + '</code>\n' +
            E.STAR + ' Total Requests: <code>' + '{:,}'.format(stats['total_requests']) + '</code>\n' +
            E.DIAMOND + ' Premium Users: <code>' + '{:,}'.format(stats['premium']) + '</code>\n' +
            E.BAN + ' Banned: <code>' + '{:,}'.format(stats['banned']) + '</code>\n' +
            E.MUTE + ' Muted: <code>' + '{:,}'.format(stats['muted']) + '</code>\n' +
            E.MAINTENANCE + ' Maintenance: <code>' + ('ON' if db.maintenance_mode else 'OFF') + '</code>\n' +
            UI.section('ADMIN COMMANDS', E.KEY) +
            E.STAR + ' /admin - Show this panel\n' +
            E.STAR + ' /adminhelp - Full command list\n' +
            E.STAR + ' /ban [user_id] - Ban user\n' +
            E.STAR + ' /unban [user_id] - Unban user\n' +
            E.STAR + ' /mute [user_id] - Mute user\n' +
            E.STAR + ' /unmute [user_id] - Unmute user\n' +
            E.STAR + ' /warn [user_id] - Warn user\n' +
            E.STAR + ' /broadcast [message] - Send to all\n' +
            E.STAR + ' /maintenance - Toggle maintenance\n' +
            E.STAR + ' /userinfo [user_id] - User details\n' +
            E.STAR + ' /topusers - Top 10 users\n' +
            E.STAR + ' /clearlogs - Clear request logs\n' +
            E.STAR + ' /addadmin [user_id] - Add admin\n' +
            E.STAR + ' /removeadmin [user_id] - Remove admin\n' +
            E.STAR + ' /addpremium [user_id] [days] - Add premium\n' +
            E.STAR + ' /removepremium [user_id] - Remove premium\n' +
            E.STAR + ' /resetuser [user_id] - Reset daily requests\n' +
            E.STAR + ' /purgeuser [user_id] - Delete all user data\n' +
            E.STAR + ' /userrequests [user_id] - Last 10 requests\n'
        )
        bot.send_message(message.chat.id, admin_text, reply_markup=admin_keyboard())
    except Exception as e:
        logger.error('Admin error: ' + str(e))

@bot.message_handler(commands=['adminhelp'])
def cmd_adminhelp(message):
    try:
        if not db.is_admin(message.from_user.id):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        help_text = (
            UI.header('ADMIN COMMANDS REFERENCE') + '\n\n' +
            E.STAR + ' <b>/admin</b> - Summary panel\n' +
            E.STAR + ' <b>/ban [uid]</b> - Ban user from bot\n' +
            E.STAR + ' <b>/unban [uid]</b> - Remove ban\n' +
            E.STAR + ' <b>/mute [uid]</b> - Mute user (cannot send messages)\n' +
            E.STAR + ' <b>/unmute [uid]</b> - Unmute user\n' +
            E.STAR + ' <b>/warn [uid]</b> - Give warning (3 = auto ban)\n' +
            E.STAR + ' <b>/broadcast [msg]</b> - Send message to all users (max 1000)\n' +
            E.STAR + ' <b>/maintenance</b> - Toggle maintenance mode\n' +
            E.STAR + ' <b>/userinfo [uid]</b> - Full info on a user\n' +
            E.STAR + ' <b>/topusers</b> - Top 10 users by requests\n' +
            E.STAR + ' <b>/clearlogs</b> - Clear request log\n' +
            E.STAR + ' <b>/addadmin [uid]</b> - Promote to admin\n' +
            E.STAR + ' <b>/removeadmin [uid]</b> - Demote admin (cannot remove original admins)\n' +
            E.STAR + ' <b>/addpremium [uid] [days]</b> - Give premium access\n' +
            E.STAR + ' <b>/removepremium [uid]</b> - Revoke premium\n' +
            E.STAR + ' <b>/resetuser [uid]</b> - Reset daily request counter for today\n' +
            E.STAR + ' <b>/purgeuser [uid]</b> - Completely delete user data\n' +
            E.STAR + ' <b>/userrequests [uid]</b> - Show last 10 request timestamps\n'
        )
        bot.send_message(message.chat.id, help_text)
    except Exception as e:
        logger.error('Adminhelp error: ' + str(e))

@bot.message_handler(commands=['addpremium'])
def cmd_addpremium(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        parts = message.text.split()
        if len(parts) < 3:
            bot.reply_to(message, E.WARNING + ' <b>Usage:</b> /addpremium [user_id] [days]')
            return
        target_id = int(parts[1])
        days = int(parts[2])
        expiry = db.add_premium(target_id, days)
        bot.reply_to(message,
            E.CHECK + ' <b>User <code>' + str(target_id) + '</code> is now premium!</b>\n' +
            E.CLOCK + ' Expires: <code>' + datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M') + '</code>')
        try:
            bot.send_message(target_id,
                E.PREMIUM + ' <b>You are now a PREMIUM member!</b>\n' +
                E.CLOCK + ' Expires: <code>' + datetime.fromtimestamp(expiry).strftime('%Y-%m-%d %H:%M') + '</code>\n' +
                E.CHECK + ' Unlimited requests unlocked!')
        except: pass
        logger.info('Admin ' + str(uid) + ' added premium to ' + str(target_id) + ' for ' + str(days) + ' days')
    except Exception as e:
        logger.error('Addpremium error: ' + str(e))

@bot.message_handler(commands=['removepremium'])
def cmd_removepremium(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, E.WARNING + ' <b>Usage:</b> /removepremium [user_id]')
            return
        target_id = int(parts[1])
        if target_id in db.premium_users:
            del db.premium_users[target_id]
            bot.reply_to(message, E.CHECK + ' <b>User <code>' + str(target_id) + '</code> premium removed!</b>')
            try:
                bot.send_message(target_id, E.WARNING + ' <b>Your premium access has expired!</b>')
            except: pass
        else:
            bot.reply_to(message, E.CROSS + ' <b>User is not premium!</b>')
        logger.info('Admin ' + str(uid) + ' removed premium from ' + str(target_id))
    except Exception as e:
        logger.error('Removepremium error: ' + str(e))

@bot.message_handler(commands=['ban'])
def cmd_ban(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, E.WARNING + ' <b>Usage:</b> /ban [user_id]')
            return
        target_id = int(parts[1])
        db.ban_user(target_id)
        bot.reply_to(message, E.CHECK + ' <b>User <code>' + str(target_id) + '</code> banned!</b>')
        try: bot.send_message(target_id, E.BAN + ' <b>You have been banned!</b>')
        except: pass
        logger.info('Admin ' + str(uid) + ' banned user ' + str(target_id))
    except Exception as e:
        logger.error('Ban error: ' + str(e))

@bot.message_handler(commands=['unban'])
def cmd_unban(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, E.WARNING + ' <b>Usage:</b> /unban [user_id]')
            return
        target_id = int(parts[1])
        db.unban_user(target_id)
        bot.reply_to(message, E.CHECK + ' <b>User <code>' + str(target_id) + '</code> unbanned!</b>')
        try: bot.send_message(target_id, E.CHECK + ' <b>You have been unbanned!</b>')
        except: pass
        logger.info('Admin ' + str(uid) + ' unbanned user ' + str(target_id))
    except Exception as e:
        logger.error('Unban error: ' + str(e))

@bot.message_handler(commands=['broadcast'])
def cmd_broadcast(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        broadcast_msg = message.text.replace('/broadcast', '', 1).strip()
        if not broadcast_msg:
            bot.reply_to(message, E.WARNING + ' <b>Usage:</b> /broadcast [message]')
            return
        bot.reply_to(message, E.BROADCAST + ' <b>Broadcasting...</b>')
        sent = 0
        failed = 0
        for user_id in list(db.users.keys())[:1000]:
            try:
                full_msg = E.BROADCAST + ' <b>ANNOUNCEMENT</b>\n\n' + broadcast_msg + '\n\n' + E.STAR + ' - ' + YOUR_CHANNEL
                bot.send_message(user_id, full_msg)
                sent += 1
                time.sleep(0.05)
            except:
                failed += 1
        db.broadcast_history.append({
            'admin': uid,
            'message': broadcast_msg,
            'sent': sent,
            'failed': failed,
            'time': datetime.now().isoformat()
        })
        result_msg = E.CHECK + ' <b>Broadcast Complete!</b>\n\n' + E.CHECK + ' Sent: <code>' + str(sent) + '</code>\n' + E.CROSS + ' Failed: <code>' + str(failed) + '</code>'
        bot.reply_to(message, result_msg)
        logger.info('Admin ' + str(uid) + ' broadcasted to ' + str(sent) + ' users')
    except Exception as e:
        logger.error('Broadcast error: ' + str(e))

@bot.message_handler(commands=['maintenance'])
def cmd_maintenance(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        db.maintenance_mode = not db.maintenance_mode
        status = 'ON' if db.maintenance_mode else 'OFF'
        bot.reply_to(message, E.MAINTENANCE + ' <b>Maintenance Mode: ' + status + '</b>')
        logger.info('Admin ' + str(uid) + ' toggled maintenance to ' + status)
    except Exception as e:
        logger.error('Maintenance error: ' + str(e))

@bot.message_handler(commands=['userinfo'])
def cmd_userinfo(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, E.WARNING + ' <b>Usage:</b> /userinfo [user_id]')
            return
        target_id = int(parts[1])
        user_data = db.users.get(target_id, {})
        if not user_data:
            bot.reply_to(message, E.CROSS + ' <b>User not found!</b>')
            return
        premium_status = 'Yes (Expires: ' + db.get_premium_expiry(target_id).strftime('%Y-%m-%d %H:%M') + ')' if db.is_premium(target_id) else 'No'
        info = (
            UI.header('USER INFORMATION') + '\n\n' +
            E.KEY + ' <b>User ID:</b> <code>' + str(target_id) + '</code>\n' +
            E.NINJA + ' <b>Name:</b> ' + str(user_data.get('first_name', 'Unknown')) + '\n' +
            E.STAR + ' <b>Username:</b> @' + str(user_data.get('username', 'N/A')) + '\n' +
            E.GLOBE + ' <b>Requests:</b> ' + str(user_data.get('requests', 0)) + '\n' +
            E.WARNING + ' <b>Warnings:</b> ' + str(user_data.get('warnings', 0)) + '/3\n' +
            E.INFO + ' <b>Joined:</b> ' + str(user_data.get('joined', 'Unknown'))[:10] + '\n\n' +
            E.PREMIUM + ' <b>Premium:</b> ' + premium_status + '\n' +
            E.BAN + ' <b>Banned:</b> ' + ('Yes' if db.is_banned(target_id) else 'No') + '\n' +
            E.MUTE + ' <b>Muted:</b> ' + ('Yes' if db.is_muted(target_id) else 'No') + '\n' +
            E.ADMIN + ' <b>Admin:</b> ' + ('Yes' if db.is_admin(target_id) else 'No')
        )
        bot.reply_to(message, info)
    except Exception as e:
        logger.error('Userinfo error: ' + str(e))

@bot.message_handler(commands=['topusers'])
def cmd_topusers(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        top = db.get_top_users(10)
        leaderboard = UI.header('TOP 10 USERS') + '\n'
        medals = ['\U0001F947', '\U0001F948', '\U0001F949'] + ['\U0001F3C5'] * 7
        for i, (uid_val, data) in enumerate(top):
            name = str(data.get('first_name', 'Unknown'))[:15]
            requests = data.get('requests', 0)
            premium_badge = E.PREMIUM if db.is_premium(uid_val) else ''
            leaderboard += medals[i] + ' <b>' + name + '</b> ' + premium_badge + ' - <code>' + str(requests) + '</code> requests\n'
        bot.reply_to(message, leaderboard)
    except Exception as e:
        logger.error('Topusers error: ' + str(e))

@bot.message_handler(commands=['warn'])
def cmd_warn(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, E.WARNING + ' <b>Usage:</b> /warn [user_id]')
            return
        target_id = int(parts[1])
        warnings = db.warn_user(target_id)
        result = E.WARNING + ' <b>User <code>' + str(target_id) + '</code> warned!</b>\n' + E.INFO + ' Total warnings: ' + str(warnings) + '/3'
        if warnings >= 3:
            db.ban_user(target_id)
            result += '\n' + E.BAN + ' <b>User auto-banned after 3 warnings!</b>'
        bot.reply_to(message, result)
        try: bot.send_message(target_id, E.WARNING + ' <b>Warning ' + str(warnings) + '/3!</b>')
        except: pass
        logger.info('Admin ' + str(uid) + ' warned user ' + str(target_id) + ' (' + str(warnings) + '/3)')
    except Exception as e:
        logger.error('Warn error: ' + str(e))

@bot.message_handler(commands=['mute'])
def cmd_mute(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, E.WARNING + ' <b>Usage:</b> /mute [user_id]')
            return
        target_id = int(parts[1])
        db.mute_user(target_id)
        bot.reply_to(message, E.CHECK + ' <b>User <code>' + str(target_id) + '</code> muted!</b>')
        logger.info('Admin ' + str(uid) + ' muted user ' + str(target_id))
    except Exception as e:
        logger.error('Mute error: ' + str(e))

@bot.message_handler(commands=['unmute'])
def cmd_unmute(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, E.WARNING + ' <b>Usage:</b> /unmute [user_id]')
            return
        target_id = int(parts[1])
        db.unmute_user(target_id)
        bot.reply_to(message, E.CHECK + ' <b>User <code>' + str(target_id) + '</code> unmuted!</b>')
        logger.info('Admin ' + str(uid) + ' unmuted user ' + str(target_id))
    except Exception as e:
        logger.error('Unmute error: ' + str(e))

@bot.message_handler(commands=['clearlogs'])
def cmd_clearlogs(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        count = len(db.request_log)
        db.request_log.clear()
        bot.reply_to(message, E.CHECK + ' <b>' + str(count) + ' logs cleared!</b>')
        logger.info('Admin ' + str(uid) + ' cleared ' + str(count) + ' logs')
    except Exception as e:
        logger.error('Clearlogs error: ' + str(e))

@bot.message_handler(commands=['addadmin'])
def cmd_addadmin(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, E.WARNING + ' <b>Usage:</b> /addadmin [user_id]')
            return
        new_admin = int(parts[1])
        db.admin_ids.add(new_admin)
        bot.reply_to(message, E.CHECK + ' <b>User <code>' + str(new_admin) + '</code> is now admin!</b>')
        logger.info('Admin ' + str(uid) + ' added new admin ' + str(new_admin))
    except Exception as e:
        logger.error('Addadmin error: ' + str(e))

@bot.message_handler(commands=['removeadmin'])
def cmd_removeadmin(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, E.WARNING + ' <b>Usage:</b> /removeadmin [user_id]')
            return
        target = int(parts[1])
        if db.remove_admin(target):
            bot.reply_to(message, E.CHECK + ' <b>Admin removed!</b>')
            logger.info('Admin ' + str(uid) + ' removed admin ' + str(target))
        else:
            bot.reply_to(message, E.CROSS + ' <b>Cannot remove that admin (protected or not found).</b>')
    except Exception as e:
        logger.error('Removeadmin error: ' + str(e))

@bot.message_handler(commands=['resetuser'])
def cmd_resetuser(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, E.WARNING + ' <b>Usage:</b> /resetuser [user_id]')
            return
        target = int(parts[1])
        db.reset_user_daily(target)
        bot.reply_to(message, E.CHECK + ' <b>Daily requests reset for user <code>' + str(target) + '</code>!</b>')
        logger.info('Admin ' + str(uid) + ' reset daily count for ' + str(target))
    except Exception as e:
        logger.error('Resetuser error: ' + str(e))

@bot.message_handler(commands=['purgeuser'])
def cmd_purgeuser(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, E.WARNING + ' <b>Usage:</b> /purgeuser [user_id]')
            return
        target = int(parts[1])
        db.purge_user(target)
        bot.reply_to(message, E.CHECK + ' <b>All data for user <code>' + str(target) + '</code> purged!</b>')
        logger.info('Admin ' + str(uid) + ' purged user ' + str(target))
    except Exception as e:
        logger.error('Purgeuser error: ' + str(e))

@bot.message_handler(commands=['userrequests'])
def cmd_userrequests(message):
    try:
        uid = message.from_user.id
        if not db.is_admin(uid):
            bot.reply_to(message, E.CROSS + ' <b>Admin only!</b>')
            return
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, E.WARNING + ' <b>Usage:</b> /userrequests [user_id]')
            return
        target = int(parts[1])
        user_logs = [log for log in db.request_log if log['user_id'] == target][-10:]
        if not user_logs:
            bot.reply_to(message, E.INFO + ' <b>No requests found for this user.</b>')
            return
        log_text = UI.header('LAST 10 REQUESTS') + '\n'
        for i, log in enumerate(user_logs, 1):
            log_text += E.CLOCK + ' <code>' + log['time'][:19] + '</code>\n'
        bot.reply_to(message, log_text)
    except Exception as e:
        logger.error('Userrequests error: ' + str(e))

@bot.message_handler(func=lambda m: m.text and 'ADMIN PANEL' in m.text)
def btn_admin_panel(message):
    cmd_admin(message)

# ==================== MEDIA HANDLER ====================
@bot.message_handler(content_types=['photo', 'video', 'document', 'audio', 'sticker', 'voice', 'contact', 'location'])
def handle_media(message):
    bot.reply_to(
        message,
        E.WARNING + ' <b>Only text commands supported!</b>\n' +
        E.INFO + ' Please use buttons to interact.',
        reply_markup=main_keyboard()
    )

# ==================== FALLBACK HANDLER ====================
@bot.message_handler(func=lambda m: True)
def handle_unknown(message):
    try:
        uid = message.from_user.id
        if db.is_banned(uid):
            return
        if db.is_muted(uid):
            return
        # Check if user has a pending state
        if uid in db.user_states:
            state = db.user_states[uid]
            if state == 'waiting_number':
                process_number(message)
                return
            elif state == 'waiting_aadhaar':
                process_aadhaar(message)
                return
            elif state == 'waiting_vehicle':
                process_vehicle(message)
                return
            elif state == 'waiting_pakistan':
                process_pakistan(message)
                return
            elif state == 'waiting_ip':
                process_ip(message)
                return
            elif state == 'waiting_instagram':
                process_instagram(message)
                return
            elif state == 'waiting_telegram':
                process_telegram(message)
                return
            elif state == 'waiting_email':
                process_email(message)
                return
        bot.reply_to(
            message,
            E.WARNING + ' <b>Please use the buttons below!</b>\n' +
            E.STAR + ' All features are FREE (limited) / PREMIUM (unlimited)',
            reply_markup=main_keyboard()
        )
    except Exception as e:
        logger.error('Fallback error: ' + str(e))

# ==================== MAIN ====================
def safe_polling():
    while True:
        try:
            logger.info('Bot polling started...')
            bot.polling(none_stop=True, interval=0, timeout=30, skip_pending=True)
        except requests.exceptions.ReadTimeout:
            logger.warning('Read timeout. Restarting...')
            time.sleep(5)
        except requests.exceptions.ConnectionError:
            logger.warning('Connection error. Retrying in 10s...')
            time.sleep(10)
        except Exception as e:
            logger.error('Critical error: ' + str(e))
            time.sleep(5)

if __name__ == '__main__':
    print('=' * 50)
    print('OSINT MASTER PRO v7.0 PRODUCTION')
    print('=' * 50)
    print('Token: ' + BOT_TOKEN[:20] + '...')
    print('Channel: ' + YOUR_CHANNEL)
    print('Bot: ' + BOT_USERNAME)
    print('Admin IDs: ' + str(ADMIN_IDS))
    print('=' * 50)
    print('Bot is RUNNING...')
    print('Developer: RAHUL')
    print('Channel: ' + YOUR_CHANNEL)
    print('=' * 50)

    safe_polling()