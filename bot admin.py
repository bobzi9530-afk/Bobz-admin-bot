import os
import json
import random
import uuid
import threading
import time
import re
import shlex
from datetime import datetime, date
from typing import Optional
import html
import telebot
from telebot import types
from telebot.types import ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from telebot.apihelper import ApiTelegramException


UPD_VOICE_FILES = [
    "upd1.mp3",
    "upd2.mp3",
]

UPD_SLEEP = 0.08
UPD_PROGRESS_EVERY = 50

RP_ACTIONS = {
    "ударить": {
        "emoji": "🤜",
        "verb": "ударил",
        "female_verb": "ударила",
    },
    "пнуть": {
        "emoji": "🦵",
        "verb": "пнул",
        "female_verb": "пнула",
    },
    "убить": {
        "emoji": "🔪",
        "verb": "убил",
        "female_verb": "убила",
    },
    "расстрелять": {
        "emoji": "🔫",
        "verb": "расстрелял",
        "female_verb": "расстреляла",
    },
    "сжечь": {
        "emoji": "🔥",
        "verb": "сжёг",
        "female_verb": "сожгла",
    },
    "счежь": {
        "emoji": "🔥",
        "verb": "сжёг",
        "female_verb": "сожгла",
    },
}

WARNING_VOICE_FILES = [
    "предупреждение.mp3",
    "благодарим.mp3",
]

MAT_MUTE_SECONDS = 60 * 60
MAT_DEFAULT_ACTION = "warn"

MAT_ACTION_NAMES = {
    "warn": "варнить",
    "mute": "мутить",
    "ban": "банить",
}

MAT_BAD_WORD_PATTERNS = [
    r"\bх[уy][йяеёюи]",
    r"\bп[иi]зд",
    r"\b[еёe]б",
    r"\bбл[яа]",
    r"\bмуд[ао]",
    r"\bсу[кч]",
]

WARNING_SLEEP = 0.08
WARNING_PROGRESS_EVERY = 50

botik_token = os.getenv("BOT_TOKEN", "BOT_TOKEN")
DATA_FILE = "data.json"
GREETINGS_FILE = "greetings.json"

try:
    from telebot.handler_backends import ContinueHandling
except Exception:
    ContinueHandling = None


MESSAGE_STATS_FILE = "message_stats.json"
MESSAGE_STATS_LOCK = threading.Lock()

ADMIN_ID = {6301107206}

RP_COOLDOWN_SECONDS = 10
RP_COOLDOWNS = {}

BROADCAST_SLEEP = 0.06
BROADCAST_PROGRESS_EVERY = 50

CLAN_CREATE_COST = 1500
PRIME_COST = 5000
BOX_COST = 2500

DAILY_WITHDRAW_LIMIT = 3000
MAX_HISTORY = 500

EARN_MIN = 50
EARN_MAX = 200
EARN_COOLDOWN_SECONDS = 120

TOP_LIMIT = 30

EMO_TROPHY = "🏆"
EMO_TODAY = "📅"
EMO_MSG = "💬"
EMO_FIRST = " 1"
EMO_SECOND = " 2"
EMO_THIRD = " 3"

OPEN_CHAT_CB = "chat_open_btn"

DUELS = {}
USER_ACTIVE_DUEL = {}
USERNAME_TO_ID = {}
WHO_DUEL = {}
WHO_DUEL_TTL = 180

DUEL_MODES = {
    "clicker": "🖱️ Кликер",
    "rps": "✊✋✌️ Камень-ножницы-бумага",
}

bot = telebot.TeleBot(botik_token, parse_mode="HTML")
_lock = threading.RLock()

data = {
    "users": {},
    "clans": {},
    "chats": {}
}


def load_data():
    global data
    if not os.path.exists(DATA_FILE):
        return

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            loaded = json.load(f)

        if not isinstance(loaded, dict):
            raise ValueError("data.json is not dict")

        loaded.setdefault("users", {})
        loaded.setdefault("clans", {})
        loaded.setdefault("chats", {})
        data = loaded
    except Exception as e:
        print("load_data error:", e)
        data = {"users": {}, "clans": {}, "chats": {}}


def save_data():
    with _lock:
        tmp = DATA_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, DATA_FILE)

def _save_data_safe():
    try:
        if callable(globals().get("save_data")):
            save_data()
    except Exception as e:
        print(f"save_data error: {e}")


def _mat_init_storage():
    data.setdefault("mat_filter", {})
    data["mat_filter"].setdefault("chats", {})


def _mat_get_chat_settings(chat_id):
    _mat_init_storage()

    chat_id = str(chat_id)

    if chat_id not in data["mat_filter"]["chats"]:
        data["mat_filter"]["chats"][chat_id] = {
            "enabled": False,
            "action": MAT_DEFAULT_ACTION,
            "warns": {},
        }

    settings = data["mat_filter"]["chats"][chat_id]
    settings.setdefault("enabled", False)
    settings.setdefault("action", MAT_DEFAULT_ACTION)
    settings.setdefault("warns", {})

    return settings


def _mat_is_enabled(chat_id):
    settings = _mat_get_chat_settings(chat_id)
    return bool(settings.get("enabled", False))


def _mat_set_enabled(chat_id, enabled):
    settings = _mat_get_chat_settings(chat_id)
    settings["enabled"] = bool(enabled)
    _save_data_safe()


def _mat_set_action(chat_id, action):
    settings = _mat_get_chat_settings(chat_id)
    settings["enabled"] = True
    settings["action"] = action
    _save_data_safe()


def _mat_normalize_text(text):
    text = text or ""
    text = text.lower()
    text = text.replace("ё", "е")

    replacements = {
        "@": "а",
        "a": "а",
        "o": "о",
        "0": "о",
        "e": "е",
        "3": "з",
        "x": "х",
        "y": "у",
        "u": "у",
        "i": "и",
        "1": "и",
        "b": "б",
        "6": "б",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    text = re.sub(r"[^а-яa-z0-9\s]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def _mat_contains_bad_word(text):
    normalized = _mat_normalize_text(text)

    if not normalized:
        return False

    for pattern in MAT_BAD_WORD_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            return True

    return False


def _mat_user_link(user):
    if not user:
        return "Пользователь"

    name = " ".join(filter(None, [
        getattr(user, "first_name", None),
        getattr(user, "last_name", None),
    ])).strip()

    if not name:
        username = getattr(user, "username", None)

        if username:
            name = f"@{username}"
        else:
            name = f"ID {user.id}"

    return f'<a href="tg://user?id={int(user.id)}">{html.escape(name)}</a>'


def _mat_is_chat_admin(chat_id, user_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ["creator", "administrator"]
    except Exception:
        return False


def _mat_can_manage(message):
    if _is_admin_id(message.from_user.id):
        return True

    if message.chat.type in ["group", "supergroup"]:
        return _mat_is_chat_admin(message.chat.id, message.from_user.id)

    return False


def _mat_can_manage_callback(call):
    if _is_admin_id(call.from_user.id):
        return True

    try:
        chat_id = int(call.data.split(":")[2])
        return _mat_is_chat_admin(chat_id, call.from_user.id)
    except Exception:
        return False


def _mat_delete_message(message):
    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception as e:
        print(f"mat delete error: {e}")


def _mat_warn_user(message):
    settings = _mat_get_chat_settings(message.chat.id)

    user_id = str(message.from_user.id)
    warns = settings.setdefault("warns", {})
    warns[user_id] = int(warns.get(user_id, 0)) + 1

    _save_data_safe()

    _mat_delete_message(message)

    bot.send_message(
        message.chat.id,
        f"⚠️ {_mat_user_link(message.from_user)}, не используй маты.\n"
        f"Предупреждений: {warns[user_id]}",
        parse_mode="HTML",
        disable_web_page_preview=True
    )


def _mat_mute_user(message):
    _mat_delete_message(message)

    until_date = int(time.time()) + MAT_MUTE_SECONDS

    try:
        permissions = types.ChatPermissions(
            can_send_messages=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
            can_change_info=False,
            can_invite_users=False,
            can_pin_messages=False,
            can_manage_topics=False,
        )

        bot.restrict_chat_member(
            message.chat.id,
            message.from_user.id,
            permissions=permissions,
            until_date=until_date
        )

        bot.send_message(
            message.chat.id,
            f"🔇 {_mat_user_link(message.from_user)} получил мут за мат.\n"
            f"Время мута: {MAT_MUTE_SECONDS // 60} мин.",
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Не удалось замутить пользователя.\nОшибка: {e}",
            parse_mode=None
        )


def _mat_ban_user(message):
    _mat_delete_message(message)

    try:
        bot.ban_chat_member(
            message.chat.id,
            message.from_user.id
        )

        bot.send_message(
            message.chat.id,
            f"⛔ {_mat_user_link(message.from_user)} забанен за мат.",
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    except Exception as e:
        bot.send_message(
            message.chat.id,
            f"❌ Не удалось забанить пользователя.\nОшибка: {e}",
            parse_mode=None
        )




def _rp_get_user_link(user):
    if not user:
        return "Пользователь"

    first_name = getattr(user, "first_name", None) or ""
    last_name = getattr(user, "last_name", None) or ""
    username = getattr(user, "username", None) or ""

    name = f"{first_name} {last_name}".strip()

    if not name:
        name = f"@{username}" if username else f"ID {user.id}"

    name = html.escape(name)

    return f'<a href="tg://user?id={int(user.id)}">{name}</a>'


def _rp_get_command(text):
    if not text:
        return None

    text = " ".join(text.strip().lower().split())

    if not text:
        return None

    if text.startswith("/"):
        return None

    first_word = text.split(maxsplit=1)[0]

    if first_word in RP_ACTIONS:
        return first_word

    return None


def _rp_get_cooldown_left(user_id):
    now = time.time()
    last = RP_COOLDOWNS.get(int(user_id), 0)
    left = RP_COOLDOWN_SECONDS - int(now - last)

    if left > 0:
        return left

    return 0


def _rp_set_cooldown(user_id):
    RP_COOLDOWNS[int(user_id)] = time.time()

def format_count_number(value):
    try:
        return f"{int(value):,}".replace(",", " ")
    except Exception:
        return str(value)


def get_chat_top_data(chat_id):
    chat_key = get_chat_key(chat_id)

    with MESSAGE_STATS_LOCK:
        chat_stats = message_stats.get(chat_key)

        if not chat_stats:
            return [], 0

        users = chat_stats.get("users", {})
        total_messages = int(chat_stats.get("total_messages", 0))

        top_users = []

        for user_id, data in users.items():
            if not isinstance(data, dict):
                continue

            name = data.get("name") or data.get("username") or str(user_id)
            count = int(data.get("messages", 0))

            if count <= 0:
                continue

            top_users.append((name, count))

        top_users.sort(key=lambda x: x[1], reverse=True)

        return top_users, total_messages


def format_top_message(top_users, total_messages):
    lines = []

    for index, item in enumerate(top_users, start=1):
        name = item[0]
        count = item[1]

        lines.append(f"{index}. {name} — {format_count_number(count)}")

    lines.append("")
    lines.append("")
    lines.append(f"Всего сообщений: {format_count_number(total_messages)}")

    return "\n".join(lines)


def send_long_message(chat_id, text, reply_to_message_id=None):
    max_len = 3900

    if len(text) <= max_len:
        bot.send_message(
            chat_id,
            text,
            reply_to_message_id=reply_to_message_id,
            parse_mode=None
        )
        return

    parts = []
    current = ""

    for line in text.split("\n"):
        if len(current) + len(line) + 1 > max_len:
            parts.append(current)
            current = line
        else:
            if current:
                current += "\n" + line
            else:
                current = line

    if current:
        parts.append(current)

    for index, part in enumerate(parts):
        bot.send_message(
            chat_id,
            part,
            reply_to_message_id=reply_to_message_id if index == 0 else None,
            parse_mode=None
        )


def cmd_top(message):
    top_users, total_messages = get_chat_top_data(message.chat.id)

    if not top_users:
        bot.reply_to(
            message,
            "Статистика пустая. Напишите несколько сообщений в чат, чтобы она появилась.",
            parse_mode=None
        )
        return

    top_users = top_users[:TOP_LIMIT]

    text = format_top_message(top_users, total_messages)

    bot.reply_to(
        message,
        text,
        parse_mode=None
    )


def cmd_top_all(message):
    top_users, total_messages = get_chat_top_data(message.chat.id)

    if not top_users:
        bot.reply_to(
            message,
            "Статистика пустая. Напишите несколько сообщений в чат, чтобы она появилась.",
            parse_mode=None
        )
        return

    text = format_top_message(top_users, total_messages)

    send_long_message(
        message.chat.id,
        text,
        reply_to_message_id=message.message_id
    )


def cmd_top_today(message):
    return cmd_top(message)

def load_message_stats():
    if not os.path.exists(MESSAGE_STATS_FILE):
        return {}

    try:
        with open(MESSAGE_STATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data
    except Exception as e:
        print(f"Ошибка загрузки статистики сообщений: {e}")

    return {}


def save_message_stats():
    try:
        temp_file = MESSAGE_STATS_FILE + ".tmp"

        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(message_stats, f, ensure_ascii=False, indent=2)

        os.replace(temp_file, MESSAGE_STATS_FILE)
    except Exception as e:
        print(f"Ошибка сохранения статистики сообщений: {e}")


message_stats = load_message_stats()


def get_chat_key(chat_id):
    return str(chat_id)


def get_user_key(user_id):
    return str(user_id)


def get_user_name(user):
    parts = []

    if getattr(user, "first_name", None):
        parts.append(user.first_name)

    if getattr(user, "last_name", None):
        parts.append(user.last_name)

    name = " ".join(parts).strip()

    if name:
        return name

    if getattr(user, "username", None):
        return user.username

    return str(user.id)

def _safe_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default

def ensure_chat_stats(chat_id):
    chat_key = get_chat_key(chat_id)

    if chat_key not in message_stats:
        message_stats[chat_key] = {
            "total_messages": 0,
            "users": {}
        }

    if "total_messages" not in message_stats[chat_key]:
        message_stats[chat_key]["total_messages"] = 0

    if "users" not in message_stats[chat_key]:
        message_stats[chat_key]["users"] = {}

    return message_stats[chat_key]


def add_message_to_stats(message):
    if not message:
        return

    if not getattr(message, "chat", None):
        return

    if not getattr(message, "from_user", None):
        return

    user = message.from_user

    if getattr(user, "is_bot", False):
        return

    chat_id = message.chat.id
    user_id = user.id

    chat_key = get_chat_key(chat_id)
    user_key = get_user_key(user_id)

    with MESSAGE_STATS_LOCK:
        chat_stats = ensure_chat_stats(chat_key)
        users = chat_stats["users"]

        if user_key not in users:
            users[user_key] = {
                "id": user_id,
                "name": get_user_name(user),
                "username": user.username if getattr(user, "username", None) else None,
                "messages": 0,
                "first_seen": int(time.time()),
                "last_seen": int(time.time())
            }

        users[user_key]["name"] = get_user_name(user)
        users[user_key]["username"] = user.username if getattr(user, "username", None) else users[user_key].get("username")
        users[user_key]["messages"] = int(users[user_key].get("messages", 0)) + 1
        users[user_key]["last_seen"] = int(time.time())

        chat_stats["total_messages"] = int(chat_stats.get("total_messages", 0)) + 1

        save_message_stats()

def _load_greetings():
    if not os.path.exists(GREETINGS_FILE):
        return {}

    try:
        with open(GREETINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_greetings(greetings):
    with open(GREETINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(greetings, f, ensure_ascii=False, indent=2)


GREETINGS = _load_greetings()

def _list_split_send(chat_id, text, reply_to_message_id=None):
    chunks = _wr_split_text(text, limit=3800)

    first = True

    for chunk in chunks:
        bot.send_message(
            chat_id,
            chunk,
            reply_to_message_id=reply_to_message_id if first else None,
            parse_mode=None,
            disable_web_page_preview=True
        )
        first = False


def _pun_expires_at(record):
    duration = record.get("duration")
    created_at = _safe_int(record.get("time", 0), 0)

    if duration is None:
        return None

    duration = _safe_int(duration, 0)

    if duration <= 0:
        return None

    return created_at + duration


def _pun_is_expired(record):
    expires_at = _pun_expires_at(record)

    if not expires_at:
        return False

    return expires_at <= int(time.time())


def _pun_get_active_records(chat_id, action_type):
    """
    action_type:
    - mute
    - ban
    """

    if action_type == "mute":
        add_action = "mute"
        remove_action = "unmute"
    elif action_type == "ban":
        add_action = "ban"
        remove_action = "unban"
    else:
        return []

    punishments = data.setdefault("punishments", [])

    records = []

    for item in punishments:
        if not isinstance(item, dict):
            continue

        if str(item.get("chat_id")) != str(chat_id):
            continue

        if item.get("action") not in (add_action, remove_action):
            continue

        records.append(item)

    records.sort(key=lambda x: _safe_int(x.get("time", 0), 0))

    active = {}

    for record in records:
        target_id = str(record.get("target_id"))

        if not target_id:
            continue

        if record.get("action") == remove_action:
            active.pop(target_id, None)
            continue

        if record.get("action") == add_action:
            active[target_id] = record

    result = []

    for target_id, record in active.items():
        if _pun_is_expired(record):
            continue

        result.append(record)

    result.sort(key=lambda x: _safe_int(x.get("time", 0), 0), reverse=True)

    return result

def _is_admin_id(user_id):
    try:
        if isinstance(ADMIN_ID, int):
            return int(user_id) == ADMIN_ID

        return int(user_id) in ADMIN_ID
    except Exception:
        return False


def _is_chat_admin(message):
    user_id = message.from_user.id
    chat_id = message.chat.id

    if _is_admin_id(user_id):
        return True

    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ["creator", "administrator"]
    except Exception:
        return False


def _get_chat_greeting(chat_id):
    return GREETINGS.get(str(chat_id), "")


def _set_chat_greeting(chat_id, text):
    GREETINGS[str(chat_id)] = text
    _save_greetings(GREETINGS)


def _format_greeting(text, user, chat):
    first_name = html.escape(user.first_name or "Пользователь")
    full_name = html.escape(
        ((user.first_name or "") + " " + (user.last_name or "")).strip()
        or "Пользователь"
    )

    username = user.username

    if username:
        user_link = f'<a href="https://t.me/{html.escape(username)}">{full_name}</a>'
    else:
        user_link = f'<a href="tg://user?id={user.id}">{full_name}</a>'

    chat_title = html.escape(chat.title or "чат")

    return (
        text
        .replace("{user}", user_link)
        .replace("{name}", first_name)
        .replace("{full_name}", full_name)
        .replace("{id}", str(user.id))
        .replace("{chat}", chat_title)
    )

def _weather_get_city_from_message(message):
    text = (message.text or "").strip()

    if not text:
        return ""

    low = text.lower()

    if low.startswith("/weather"):
        parts = text.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ""

    if low.startswith("погода"):
        parts = text.split(maxsplit=1)
        return parts[1].strip() if len(parts) > 1 else ""

    return ""


def _weather_code_to_text(code):
    codes = {
        0: "Ясно",
        1: "Преимущественно ясно",
        2: "Переменная облачность",
        3: "Пасмурно",
        45: "Туман",
        48: "Изморозь, туман",
        51: "Лёгкая морось",
        53: "Умеренная морось",
        55: "Сильная морось",
        56: "Лёгкая ледяная морось",
        57: "Сильная ледяная морось",
        61: "Небольшой дождь",
        63: "Умеренный дождь",
        65: "Сильный дождь",
        66: "Лёгкий ледяной дождь",
        67: "Сильный ледяной дождь",
        71: "Небольшой снег",
        73: "Умеренный снег",
        75: "Сильный снег",
        77: "Снежные зёрна",
        80: "Небольшой ливень",
        81: "Умеренный ливень",
        82: "Сильный ливень",
        85: "Небольшой снегопад",
        86: "Сильный снегопад",
        95: "Гроза",
        96: "Гроза с небольшим градом",
        99: "Гроза с сильным градом",
    }

    return codes.get(int(code), "Неизвестно")

def _weather_fetch_open_meteo(city):
    from urllib.parse import quote
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
    import ssl

    try:
        try:
            import certifi
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            # Если certifi не установлен или не работает
            ssl_context = ssl._create_unverified_context()

        city_q = quote(city)

        geo_url = (
            f"https://geocoding-api.open-meteo.com/v1/search"
            f"?name={city_q}"
            f"&count=1"
            f"&language=ru"
            f"&format=json"
        )

        geo_req = Request(
            geo_url,
            headers={
                "User-Agent": "Mozilla/5.0 TelegramBot Weather"
            }
        )

        with urlopen(geo_req, timeout=15, context=ssl_context) as response:
            geo_raw = response.read().decode("utf-8")

        geo_data = json.loads(geo_raw)

        results = geo_data.get("results") or []

        if not results:
            return None, f"Город «{city}» не найден."

        place = results[0]

        latitude = place.get("latitude")
        longitude = place.get("longitude")

        if latitude is None or longitude is None:
            return None, "Не удалось получить координаты города."

        weather_url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={latitude}"
            f"&longitude={longitude}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,"
            f"precipitation,weather_code,cloud_cover,pressure_msl,wind_speed_10m,wind_direction_10m"
            f"&timezone=auto"
        )

        weather_req = Request(
            weather_url,
            headers={
                "User-Agent": "Mozilla/5.0 TelegramBot Weather"
            }
        )

        with urlopen(weather_req, timeout=15, context=ssl_context) as response:
            weather_raw = response.read().decode("utf-8")

        weather_data = json.loads(weather_raw)

        return {
            "place": place,
            "weather": weather_data,
        }, None

    except HTTPError as e:
        return None, f"HTTP ошибка: {e.code}"

    except URLError as e:
        return None, f"Не удалось подключиться к сервису погоды: {e.reason}"

    except TimeoutError:
        return None, "Сервис погоды слишком долго не отвечает."

    except Exception as e:
        return None, str(e)


def _weather_format_open_meteo(city, data):
    try:
        place = data["place"]
        weather = data["weather"]
        current = weather["current"]

        city_name = place.get("name") or city
        region = place.get("admin1") or ""
        country = place.get("country") or ""

        location_parts = [city_name]

        if region and region != city_name:
            location_parts.append(region)

        if country:
            location_parts.append(country)

        location = ", ".join(location_parts)

        temp = current.get("temperature_2m", "—")
        feels = current.get("apparent_temperature", "—")
        humidity = current.get("relative_humidity_2m", "—")
        wind = current.get("wind_speed_10m", "—")
        wind_dir = current.get("wind_direction_10m", "—")
        pressure = current.get("pressure_msl", "—")
        cloud = current.get("cloud_cover", "—")
        precipitation = current.get("precipitation", "—")
        code = current.get("weather_code", 0)
        time_weather = current.get("time", "—")

        desc = _weather_code_to_text(code)

        return (
            f"🌤️ Погода: {location}\n\n"
            f"🌡️ Температура: {temp}°C\n"
            f"🤔 Ощущается как: {feels}°C\n"
            f"☁️ Состояние: {desc}\n"
            f"💧 Влажность: {humidity}%\n"
            f"💨 Ветер: {wind} км/ч\n"
            f"🧭 Направление ветра: {wind_dir}°\n"
            f"🔽 Давление: {pressure} гПа\n"
            f"☁️ Облачность: {cloud}%\n"
            f"🌧️ Осадки: {precipitation} мм\n"
            f"🕒 Время данных: {time_weather}"
        )

    except Exception:
        return None


def _parse_money_amount(message):
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        return None

    amount_text = parts[1].strip().replace(" ", "")

    if not amount_text.isdigit():
        return None

    amount = int(amount_text)

    if amount <= 0:
        return None

    return amount


def _get_money_target(message):
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        target_id = int(target_user.id)
        return target_id, target_user

    target_user = message.from_user
    target_id = int(message.from_user.id)
    return target_id, target_user





def rebuild_username_index():
    USERNAME_TO_ID.clear()
    for uid_str, u in data.get("users", {}).items():
        if not isinstance(u, dict):
            continue
        username = (u.get("username") or "").strip().lower()
        if username:
            try:
                USERNAME_TO_ID[username] = int(uid_str)
            except Exception:
                pass


load_data()
rebuild_username_index()


def tg_escape_html(s) -> str:
    s = "" if s is None else str(s)
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _to_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default

def _pun_is_group(message):
    return message.chat.type in ("group", "supergroup")


def _pun_now():
    return int(time.time())

def _wr_now():
    return int(time.time())


def _wr_is_group(message):
    return message.chat.type in ("group", "supergroup")


def _wr_save():
    try:
        save_data()
    except Exception:
        pass


def _wr_parse_duration(token):
    """
    Примеры:
    10s / 10сек
    5m / 5мин
    2h / 2ч
    7d / 7д
    1w / 1н
    forever / навсегда
    """
    if not token:
        return None, False

    t = token.strip().lower()

    if t in ("forever", "навсегда", "перма", "perm", "permanent", "0"):
        return 0, True

    m = re.fullmatch(r"(\d+)\s*([a-zа-яё]+)", t, flags=re.I)

    if not m:
        return None, False

    num = int(m.group(1))
    unit = m.group(2).lower()

    if num <= 0:
        return None, False

    if unit in ("s", "sec", "secs", "сек", "секунд", "секунда", "секунды"):
        return num, True

    if unit in ("m", "min", "mins", "мин", "минута", "минут", "минуты"):
        return num * 60, True

    if unit in ("h", "hr", "hrs", "ч", "час", "часа", "часов"):
        return num * 60 * 60, True

    if unit in ("d", "day", "days", "д", "день", "дня", "дней", "сутки", "суток"):
        return num * 60 * 60 * 24, True

    if unit in ("w", "week", "weeks", "н", "нед", "неделя", "недели", "недель"):
        return num * 60 * 60 * 24 * 7, True

    return None, False


def _wr_format_duration(seconds):
    if seconds is None:
        return "навсегда ♾️"

    if int(seconds) == 0:
        return "навсегда ♾️"

    seconds = int(seconds)

    if seconds < 60:
        return f"{seconds} сек."

    if seconds < 3600:
        return f"{seconds // 60} мин."

    if seconds < 86400:
        return f"{seconds // 3600} ч."

    if seconds < 604800:
        return f"{seconds // 86400} д."

    return f"{seconds // 604800} нед."


def _wr_format_time(ts):
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return "неизвестно"


def _wr_message_link(chat, message_id):
    try:
        if getattr(chat, "username", None):
            return f"https://t.me/{chat.username}/{message_id}"

        chat_id_str = str(chat.id)

        if chat_id_str.startswith("-100"):
            clean_id = chat_id_str[4:]
            return f"https://t.me/c/{clean_id}/{message_id}"

    except Exception:
        pass

    return None


def _wr_save_user(tg_user, chat_id=None):
    if not tg_user:
        return

    try:
        users = data.setdefault("users", {})
        u = users.setdefault(str(tg_user.id), {})

        username = getattr(tg_user, "username", None) or ""
        first_name = getattr(tg_user, "first_name", None) or ""
        last_name = getattr(tg_user, "last_name", None) or ""

        full_name = f"{first_name} {last_name}".strip()

        if not full_name and username:
            full_name = "@" + username

        if not full_name:
            full_name = "Без имени"

        u["id"] = int(tg_user.id)
        u["user_id"] = int(tg_user.id)
        u["username"] = username
        u["first_name"] = first_name
        u["last_name"] = last_name
        u["name"] = full_name
        u["full_name"] = full_name
        u["nick"] = full_name
        u["is_bot"] = bool(getattr(tg_user, "is_bot", False))

        if chat_id is not None:
            u["last_chat_id"] = int(chat_id)

    except Exception:
        pass


def _wr_get_name(user_id):
    u = data.get("users", {}).get(str(user_id), {})

    if isinstance(u, dict):
        username = u.get("username") or ""

        if username:
            return "@" + username

        name = u.get("name") or u.get("full_name") or u.get("nick") or ""

        if name:
            return name

        first_name = u.get("first_name") or ""
        last_name = u.get("last_name") or ""
        full = f"{first_name} {last_name}".strip()

        if full:
            return full

    return f"ID {user_id}"


def _wr_find_user_id_by_arg(arg):
    if not arg:
        return None

    a = arg.strip()

    if a.startswith("@"):
        username = a[1:].lower()

        for uid_str, u in data.get("users", {}).items():
            if not isinstance(u, dict):
                continue

            if str(u.get("username", "")).lower() == username:
                try:
                    return int(uid_str)
                except Exception:
                    pass

        try:
            if "resolve_username" in globals():
                uid = resolve_username("@" + username)
                if uid:
                    return int(uid)
        except Exception:
            pass

        return None

    if a.isdigit():
        return int(a)

    if a.startswith("-") and a[1:].isdigit():
        return int(a)

    return None


def _wr_get_cmd_and_args(message):
    text = getattr(message, "text", None) or ""
    text = text.strip()

    if not text:
        return None, ""

    text_norm = " ".join(text.split())
    low_full = text_norm.lower()

    # Команды из нескольких слов
    phrase_aliases = {
        "снять варн": "unwarn",
        "все репорты": "reports",
    }

    for phrase, alias in phrase_aliases.items():
        if low_full == phrase:
            return alias, ""
        if low_full.startswith(phrase + " "):
            return alias, text_norm[len(phrase):].strip()

    parts = text_norm.split(maxsplit=1)
    cmd = parts[0].strip()
    args = parts[1].strip() if len(parts) > 1 else ""

    if cmd.startswith("/"):
        cmd = cmd[1:]
        cmd = cmd.split("@")[0]

    cmd_l = cmd.lower()

    aliases = {
        "warn": "warn",
        "варн": "warn",

        "unwarn": "unwarn",
        "-варн": "unwarn",
        "анварн": "unwarn",
        "разварн": "unwarn",

        "report": "report",
        "репорт": "report",
        "+репорт": "report",
        "зарепортить": "report",

        "reports": "reports",
        "репорты": "reports",
        "репортs": "reports",
        "репортыы": "reports",
    }

    return aliases.get(cmd_l), args

def _wr_text_starts_with_any(message, variants):
    text = getattr(message, "text", None) or ""

    if not text:
        return False

    t = " ".join(text.strip().lower().split())

    for v in variants:
        v = v.lower().strip()
        if t == v or t.startswith(v + " "):
            return True

    return False


def _wr_is_warn_cmd(message):
    cmd, _ = _wr_get_cmd_and_args(message)
    return cmd == "warn"


def _wr_is_unwarn_cmd(message):
    cmd, _ = _wr_get_cmd_and_args(message)
    return cmd == "unwarn"


def _wr_is_report_cmd(message):
    cmd, _ = _wr_get_cmd_and_args(message)
    return cmd == "report"


def _wr_is_reports_cmd(message):
    cmd, _ = _wr_get_cmd_and_args(message)
    return cmd == "reports"


def _wr_warns_storage(chat_id):
    warns = data.setdefault("warns", {})
    return warns.setdefault(str(chat_id), {})


def _wr_cleanup_expired_warns(chat_id):
    chat_warns = _wr_warns_storage(chat_id)
    now = _wr_now()
    changed = False

    for uid_str in list(chat_warns.keys()):
        old_list = chat_warns.get(uid_str, [])

        if not isinstance(old_list, list):
            chat_warns[uid_str] = []
            changed = True
            continue

        new_list = []

        for w in old_list:
            if not isinstance(w, dict):
                changed = True
                continue

            expires_at = w.get("expires_at")

            if expires_at and int(expires_at) <= now:
                changed = True
                continue

            new_list.append(w)

        chat_warns[uid_str] = new_list

    if changed:
        _wr_save()

    return changed


def _wr_get_active_warns(chat_id, user_id):
    _wr_cleanup_expired_warns(chat_id)

    chat_warns = _wr_warns_storage(chat_id)
    user_warns = chat_warns.setdefault(str(user_id), [])

    result = []

    for w in user_warns:
        if not isinstance(w, dict):
            continue

        expires_at = w.get("expires_at")

        if expires_at and int(expires_at) <= _wr_now():
            continue

        result.append(w)

    return result


def _wr_add_warn(chat_id, target_id, moderator_id, reason, duration, message_id):
    chat_warns = _wr_warns_storage(chat_id)
    user_warns = chat_warns.setdefault(str(target_id), [])

    now = _wr_now()

    expires_at = None

    if duration is not None and int(duration) > 0:
        expires_at = now + int(duration)

    warn_id = int(time.time() * 1000)

    user_warns.append({
        "id": warn_id,
        "chat_id": int(chat_id),
        "target_id": int(target_id),
        "moderator_id": int(moderator_id),
        "reason": reason or "не указана",
        "time": now,
        "expires_at": expires_at,
        "duration": duration,
        "message_id": int(message_id),
    })

    _wr_save()

    return warn_id


def _wr_parse_warn_target_duration_reason(message, args_text):
    args = args_text.split() if args_text else []

    target_id = None
    target_user = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        target_id = int(target_user.id)

        duration = None
        reason_parts = args

        if args:
            parsed_duration, ok = _wr_parse_duration(args[0])

            if ok:
                duration = parsed_duration
                reason_parts = args[1:]

        reason = " ".join(reason_parts).strip()

        return target_id, target_user, duration, reason

    if not args:
        return None, None, None, ""

    target_id = _wr_find_user_id_by_arg(args[0])

    duration = None
    reason_parts = args[1:]

    if len(args) >= 2:
        parsed_duration, ok = _wr_parse_duration(args[1])

        if ok:
            duration = parsed_duration
            reason_parts = args[2:]

    reason = " ".join(reason_parts).strip()

    return target_id, target_user, duration, reason


def _wr_check_admin_command(message):
    if not _wr_is_group(message):
        bot.reply_to(message, "❌ Эта команда работает только в группе.", parse_mode=None)
        return False

    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "🚫 Эту команду могут использовать только админы.", parse_mode=None)
        return False

    return True


def _wr_check_target(message, target_id):
    if not target_id:
        bot.reply_to(
            message,
            "❌ Пользователь не найден.\n\n"
            "Используй команду ответом на сообщение или так:\n"
            "/warn @username 7d причина",
            parse_mode=None
        )
        return False

    if int(target_id) == int(message.from_user.id):
        bot.reply_to(message, "🤨 Нельзя выдать варн самому себе.", parse_mode=None)
        return False

    try:
        me = bot.get_me()

        if int(target_id) == int(me.id):
            bot.reply_to(message, "🤖 Нельзя выдать варн боту.", parse_mode=None)
            return False
    except Exception:
        pass

    try:
        if is_admin(message.chat.id, target_id):
            bot.reply_to(message, "👮 Нельзя выдать варн администратору.", parse_mode=None)
            return False
    except Exception:
        pass

    return True

def _pun_parse_duration(token):
    """
    Поддерживает:
    10s / 10сек
    5m / 5мин
    2h / 2ч
    7d / 7д
    1w / 1н
    forever / навсегда
    """
    if not token:
        return None, False

    t = token.strip().lower()

    if t in ("forever", "навсегда", "перма", "perm", "permanent", "0"):
        return 0, True

    m = re.fullmatch(r"(\d+)\s*([a-zа-я]+)", t, flags=re.I)

    if not m:
        return None, False

    num = int(m.group(1))
    unit = m.group(2).lower()

    if num <= 0:
        return None, False

    if unit in ("s", "sec", "secs", "сек", "секунд", "секунда", "секунды"):
        return num, True

    if unit in ("m", "min", "mins", "мин", "минута", "минут", "минуты"):
        return num * 60, True

    if unit in ("h", "hr", "hrs", "ч", "час", "часа", "часов"):
        return num * 60 * 60, True

    if unit in ("d", "day", "days", "д", "день", "дня", "дней", "сутки"):
        return num * 60 * 60 * 24, True

    if unit in ("w", "week", "weeks", "н", "нед", "неделя", "недели", "недель"):
        return num * 60 * 60 * 24 * 7, True

    return None, False


def _pun_format_duration(seconds):
    if seconds == 0:
        return "навсегда ♾️"

    if seconds is None:
        return "навсегда ♾️"

    seconds = int(seconds)

    if seconds < 60:
        return f"{seconds} сек."

    if seconds < 3600:
        return f"{seconds // 60} мин."

    if seconds < 86400:
        return f"{seconds // 3600} ч."

    if seconds < 604800:
        return f"{seconds // 86400} д."

    return f"{seconds // 604800} нед."


def _pun_save_user_minimal(tg_user, chat_id=None):
    if not tg_user:
        return

    try:
        users = data.setdefault("users", {})
        u = users.setdefault(str(tg_user.id), {})

        username = getattr(tg_user, "username", None) or ""
        first_name = getattr(tg_user, "first_name", None) or ""
        last_name = getattr(tg_user, "last_name", None) or ""

        full_name = f"{first_name} {last_name}".strip()

        if not full_name and username:
            full_name = "@" + username

        if not full_name:
            full_name = "Без имени"

        u["id"] = int(tg_user.id)
        u["user_id"] = int(tg_user.id)
        u["username"] = username
        u["first_name"] = first_name
        u["last_name"] = last_name
        u["name"] = full_name
        u["full_name"] = full_name
        u["nick"] = full_name
        u["is_bot"] = bool(getattr(tg_user, "is_bot", False))

        if chat_id is not None:
            u["last_chat_id"] = int(chat_id)

    except Exception:
        pass


def _pun_get_name_by_id(user_id):
    u = data.get("users", {}).get(str(user_id), {})

    if isinstance(u, dict):
        username = u.get("username") or ""
        first_name = u.get("first_name") or ""
        last_name = u.get("last_name") or ""
        name = u.get("name") or u.get("full_name") or u.get("nick") or ""

        if username:
            return "@" + username

        full = f"{first_name} {last_name}".strip()

        if full:
            return full

        if name:
            return name

    return f"ID {user_id}"


def _pun_find_user_id_by_arg(arg):
    if not arg:
        return None

    a = arg.strip()

    if a.startswith("@"):
        username = a[1:].lower()

        for uid_str, u in data.get("users", {}).items():
            if not isinstance(u, dict):
                continue

            if str(u.get("username", "")).lower() == username:
                try:
                    return int(uid_str)
                except Exception:
                    pass

        try:
            if "resolve_username" in globals():
                uid = resolve_username("@" + username)
                if uid:
                    return int(uid)
        except Exception:
            pass

        return None

    if a.isdigit():
        return int(a)

    if a.startswith("-") and a[1:].isdigit():
        return int(a)

    return None


def _pun_parse_target_duration_reason(message):
    """
    Варианты:
    Ответом:
    /ban 1h причина
    /mute 30m причина

    Без ответа:
    /ban @username 1h причина
    /mute 123456789 30m причина
    """
    text = message.text or ""
    parts = text.split()

    args = parts[1:] if len(parts) > 1 else []

    target_id = None
    target_user = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        target_id = int(target_user.id)

        duration = None
        reason_parts = args

        if args:
            parsed_duration, ok = _pun_parse_duration(args[0])

            if ok:
                duration = parsed_duration
                reason_parts = args[1:]

        reason = " ".join(reason_parts).strip()

        return target_id, target_user, duration, reason

    if not args:
        return None, None, None, ""

    target_id = _pun_find_user_id_by_arg(args[0])

    duration = None
    reason_parts = args[1:]

    if len(args) >= 2:
        parsed_duration, ok = _pun_parse_duration(args[1])

        if ok:
            duration = parsed_duration
            reason_parts = args[2:]

    reason = " ".join(reason_parts).strip()

    return target_id, target_user, duration, reason


def _pun_until_date(duration_seconds):
    if duration_seconds is None:
        return None

    if duration_seconds == 0:
        return None

    return _pun_now() + int(duration_seconds)


def _pun_add_log(chat_id, action, moderator_id, target_id, duration=None, reason=""):
    try:
        punishments = data.setdefault("punishments", [])
        punishments.append({
            "chat_id": int(chat_id),
            "action": action,
            "moderator_id": int(moderator_id),
            "target_id": int(target_id),
            "duration": duration,
            "reason": reason or "",
            "time": _pun_now()
        })
        save_data()
    except Exception:
        pass


def _pun_check_common(message, target_id):
    if not _pun_is_group(message):
        bot.reply_to(message, "❌ Эта команда работает только в группе.", parse_mode=None)
        return False

    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "🚫 У тебя нет прав администратора.", parse_mode=None)
        return False

    if not target_id:
        bot.reply_to(
            message,
            "❌ Не найден пользователь.\n\n"
            "Используй команду ответом на сообщение или так:\n"
            "/ban @username 1h причина\n"
            "/mute @username 30m причина",
            parse_mode=None
        )
        return False

    if int(target_id) == int(message.from_user.id):
        bot.reply_to(message, "🤨 Нельзя применить наказание к самому себе.", parse_mode=None)
        return False

    try:
        me = bot.get_me()

        if int(target_id) == int(me.id):
            bot.reply_to(message, "🤖 Я не могу наказать сам себя.", parse_mode=None)
            return False
    except Exception:
        pass

    try:
        if is_admin(message.chat.id, target_id):
            bot.reply_to(message, "👮 Нельзя банить или мутить администратора.", parse_mode=None)
            return False
    except Exception:
        pass

    return True




def get_full_name_from_tg_user(tg_user) -> str:
    first_name = getattr(tg_user, "first_name", None) or ""
    last_name = getattr(tg_user, "last_name", None) or ""

    full_name = f"{first_name} {last_name}".strip()

    if full_name:
        return full_name

    username = getattr(tg_user, "username", None)

    if username:
        return f"@{username}"

    return "Без имени"


def save_tg_user_to_data(tg_user, chat_id=None, status=None, custom_title=None):
    if not tg_user:
        return False

    uid = int(tg_user.id)

    users = data.setdefault("users", {})
    u = users.setdefault(str(uid), {})

    username = getattr(tg_user, "username", None)
    first_name = getattr(tg_user, "first_name", None)
    last_name = getattr(tg_user, "last_name", None)
    is_bot = getattr(tg_user, "is_bot", False)

    full_name = get_full_name_from_tg_user(tg_user)

    u["id"] = uid
    u["user_id"] = uid
    u["username"] = username or ""
    u["first_name"] = first_name or ""
    u["last_name"] = last_name or ""
    u["name"] = full_name
    u["full_name"] = full_name
    u["nick"] = full_name
    u["is_bot"] = bool(is_bot)

    if chat_id is not None:
        u["last_chat_id"] = int(chat_id)

    if status:
        u["chat_status"] = status

    if custom_title:
        u["custom_title"] = custom_title

    return True


def collect_known_user_ids_from_chat(chat_id: int) -> set[int]:
    result = set()

    try:
        chat = ensure_chat(chat_id)
    except Exception:
        chat = data.get("chats", {}).get(str(chat_id), {})

    if not isinstance(chat, dict):
        return result

    # Пользователи из общей статистики этого чата
    for uid_str in chat.get("msg_count_all", {}).keys():
        try:
            result.add(int(uid_str))
        except Exception:
            pass

    # Пользователи из дневной статистики этого чата
    daily = chat.get("msg_count_daily", {})

    if isinstance(daily, dict):
        for day_data in daily.values():
            if not isinstance(day_data, dict):
                continue

            for uid_str in day_data.keys():
                try:
                    result.add(int(uid_str))
                except Exception:
                    pass

    return result

def _today() -> str:
    return date.today().isoformat()

def get_user_name_for_top(uid: int) -> str:
    u = data.get("users", {}).get(str(uid), {})

    if isinstance(u, dict):
        name = user_display_from_data(u)
        if name and name != "Без имени":
            return name

    return f"user {uid}"

def rank_emoji(pos: int) -> str:
    if pos == 0:
        return EMO_FIRST
    if pos == 1:
        return EMO_SECOND
    if pos == 2:
        return EMO_THIRD
    return f" {pos + 1}."


def is_group(chat) -> bool:
    return getattr(chat, "type", "") in ("group", "supergroup")


def is_admin(chat_id: int, user_id: int) -> bool:
    try:
        cm = bot.get_chat_member(chat_id, user_id)
        return cm.status in ("administrator", "creator")
    except Exception:
        return False


def mention_by_id(user_id: int, name: str = None) -> str:
    if name is None:
        name = f"user {user_id}"
    return f'<a href="tg://user?id={int(user_id)}">{tg_escape_html(name)}</a>'


def user_display_from_data(u: dict) -> str:
    if not isinstance(u, dict):
        return "Без имени"

    nickname = str(u.get("nickname") or u.get("nick") or "").strip()
    first_name = str(u.get("first_name") or "").strip()
    last_name = str(u.get("last_name") or "").strip()
    username = str(u.get("username") or "").strip()
    name = str(u.get("name") or "").strip()

    display = nickname or f"{first_name} {last_name}".strip() or name or username or f"ID {u.get('id') or ''}"
    display = display.replace("\n", " ").replace("@", "＠").strip()
    return display or "Без имени"


def user_label_from_tg(user) -> str:
    if not user:
        return "Игрок"

    first = (getattr(user, "first_name", None) or "").strip()
    last = (getattr(user, "last_name", None) or "").strip()
    username = (getattr(user, "username", None) or "").strip()

    name = f"{first} {last}".strip()
    if name:
        return name
    if username:
        return f"@{username}"
    return "Игрок"


def ensure_user(user_id: int, tg_user=None) -> dict:
    global data

    users = data.setdefault("users", {})
    key = str(int(user_id))

    first_name = ""
    last_name = ""
    username = ""

    if tg_user is not None:
        first_name = (getattr(tg_user, "first_name", None) or "").strip()
        last_name = (getattr(tg_user, "last_name", None) or "").strip()
        username = (getattr(tg_user, "username", None) or "").strip()

    full_name = f"{first_name} {last_name}".strip() or first_name or username or f"ID {user_id}"

    u = users.get(key)
    changed = False

    if u is None or not isinstance(u, dict):
        u = {}
        users[key] = u
        changed = True

    defaults = {
        "id": int(user_id),
        "name": full_name,
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "balance": 0,
        "prime": 0,
        "clan": "",
        "clan_withdraw_day": None,
        "clan_withdrawn_today": 0,
        "msg_total": 0,
        "msg_today": 0,
        "msg_day": None,
        "duel_wins": 0,
        "awards_by_chat": {},
        "last_earn_at": 0,
        "created_at": int(time.time()),
        "free_box": 0,
        "free_clan_ticket": 0,
    }

    for k, v in defaults.items():
        if k not in u:
            u[k] = v
            changed = True

    if u.get("id") != int(user_id):
        u["id"] = int(user_id)
        changed = True

    if tg_user is not None:
        old_username = (u.get("username") or "").strip().lower()

        fields = {
            "first_name": first_name,
            "last_name": last_name,
            "username": username,
            "name": full_name,
        }

        for k, v in fields.items():
            if u.get(k) != v:
                u[k] = v
                changed = True

        try:
            if old_username and USERNAME_TO_ID.get(old_username) == int(user_id):
                USERNAME_TO_ID.pop(old_username, None)
            if username:
                USERNAME_TO_ID[username.lower()] = int(user_id)
        except Exception:
            pass

    for k in ("balance", "prime", "clan_withdrawn_today", "msg_total", "msg_today", "duel_wins", "last_earn_at", "free_box", "free_clan_ticket"):
        u[k] = _to_int(u.get(k, 0), 0)

    if not isinstance(u.get("awards_by_chat"), dict):
        u["awards_by_chat"] = {}
        changed = True

    if changed:
        try:
            save_data()
        except Exception as e:
            print("save ensure_user error:", e)

    return u


def ensure_chat(chat_id: int) -> dict:
    chats = data.setdefault("chats", {})
    key = str(int(chat_id))
    c = chats.get(key)
    changed = False

    if c is None or not isinstance(c, dict):
        c = {}
        chats[key] = c
        changed = True

    defaults = {
        "known_users": [],
        "history": [],
        "msg_count_all": {},
        "msg_count_daily": {},
        "rules": "",
    }

    for k, v in defaults.items():
        if k not in c:
            c[k] = v.copy() if isinstance(v, (list, dict)) else v
            changed = True

    if changed:
        save_data()

    return c


def add_known_user(chat_id: int, user_id: int):
    c = ensure_chat(chat_id)
    uid = int(user_id)
    if uid not in c["known_users"]:
        c["known_users"].append(uid)
        save_data()


def push_message_history(chat_id: int, message_id: int):
    c = ensure_chat(chat_id)
    c["history"].append(int(message_id))
    if len(c["history"]) > MAX_HISTORY:
        c["history"] = c["history"][-MAX_HISTORY:]
    save_data()


def is_countable_text_message(message) -> bool:
    if not message or message.content_type != "text":
        return False

    text = message.text or ""
    low = text.strip().lower()

    if text.startswith("/"):
        return False
    if normalize_plain_cmd(text) is not None:
        return False
    if low.startswith("+правила"):
        return False
    if low.startswith("-смс") or low.startswith("смс "):
        return False
    if low == "призвать всех":
        return False
    if low.startswith("дуэль"):
        return False
    if re.match(r"^\s*кто\s+дуэ[лль]([яеи])?\s*[\?\!]*\s*$", low):
        return False

    return True


def count_user_message_global(message):
    if not message.from_user:
        return

    u = ensure_user(message.from_user.id, message.from_user)
    today = _today()

    if u.get("msg_day") != today:
        u["msg_day"] = today
        u["msg_today"] = 0

    u["msg_total"] = _to_int(u.get("msg_total", 0), 0) + 1
    u["msg_today"] = _to_int(u.get("msg_today", 0), 0) + 1
    save_data()


def inc_msg_counters(chat_id: int, user_id: int):
    c = ensure_chat(chat_id)
    uid = str(int(user_id))

    c["msg_count_all"][uid] = _to_int(c["msg_count_all"].get(uid, 0), 0) + 1

    day = _today()
    daily = c["msg_count_daily"].setdefault(day, {})
    daily[uid] = _to_int(daily.get(uid, 0), 0) + 1

    save_data()


def normalize_plain_cmd(text: str) -> str | None:
    if not text:
        return None

    t = " ".join(text.strip().lower().split())
    t = t.replace("_", " ").replace("-", " ")

    if t in {
        "топ", "top", "топ день", "топдень", "топ за день",
        "топ сегодня", "топ за сегодня", "top day", "top today"
    }:
        return "top_today"

    if t in {
        "топ вся", "топвся", "топ все", "топвсе",
        "топ за все время", "топ за всё время", "top all", "topall"
    }:
        return "top_all"

    if t in {"правила", "rules"}:
        return "rules"

    if t in {"баланс", "balance"}:
        return "balance"

    return None

def _parse_int_from_text_number(s: str) -> int:
    try:
        return int(re.sub(r"[^\d]", "", s or ""))
    except Exception:
        return 0


def _utf16_to_py_index(text: str, offset16: int) -> int:
    """
    Telegram entities используют offset в UTF-16.
    Эта функция переводит offset Telegram в обычный индекс Python.
    """
    if offset16 <= 0:
        return 0

    units = 0
    for i, ch in enumerate(text):
        units += 2 if ord(ch) > 0xFFFF else 1
        if units > offset16:
            return i + 1
        if units == offset16:
            return i + 1

    return len(text)


def _entity_py_range(text: str, ent):
    start = _utf16_to_py_index(text, int(ent.offset))
    end = _utf16_to_py_index(text, int(ent.offset) + int(ent.length))
    return start, end


def _parse_int_from_text_number(s: str) -> int:
    try:
        return int(re.sub(r"[^\d]", "", s or ""))
    except Exception:
        return 0


def _detect_iris_top_type(text: str) -> str | None:
    t = (text or "").lower()

    if any(x in t for x in [
        "сегодня",
        "за день",
        "за сутки",
        "сутки",
        "день",
        "дневной",
    ]):
        return "today"

    if any(x in t for x in [
        "всё время",
        "все время",
        "за всё",
        "за все",
        "топ вся",
        "топвся",
        "all time",
        "общий топ",
    ]):
        return "all"

    return None


def _extract_count_from_iris_line(line: str) -> int:
    line = line or ""

    patterns = [
        r"[—–-]\s*([\d\s]+)\s*(?:сообщ|сообщений|смс|msg|messages|💬)?",
        r"[:：]\s*([\d\s]+)\s*(?:сообщ|сообщений|смс|msg|messages|💬)?",
        r"([\d\s]+)\s*(?:сообщ|сообщений|сообщения|смс|msg|messages|💬)",
        r"💬\s*([\d\s]+)",
    ]

    for p in patterns:
        m = re.search(p, line, flags=re.I)
        if m:
            num = _parse_int_from_text_number(m.group(1))
            if num > 0:
                return num

    nums = re.findall(r"\d[\d\s]*", line)

    if len(nums) >= 2:
        return _parse_int_from_text_number(nums[-1])

    return 0


def _extract_uid_from_url(url: str) -> int | None:
    if not url:
        return None

    url = url.strip()

    m = re.search(r"tg://user\?id=(\d+)", url)
    if m:
        return int(m.group(1))

    m = re.search(r"t\.me/([A-Za-z0-9_]{5,32})", url)
    if m:
        uid = resolve_username("@" + m.group(1))
        if uid:
            return int(uid)

    return None


def _normalize_name_for_match(s: str) -> str:
    s = (s or "").lower()
    s = s.replace("@", "")
    s = re.sub(r"[^\wа-яё]+", " ", s, flags=re.I)
    s = " ".join(s.split())
    return s.strip()


def _find_user_by_visible_name(line: str) -> int | None:
    """
    Фолбэк: если Iris не дал кликабельную ссылку, пробуем найти пользователя по имени из базы.
    Работает только если имя в Iris совпадает с именем, которое бот уже видел.
    """
    original = line or ""

    cleaned = original

    cleaned = re.sub(r"^\s*(?:\d+[\.\)]|🥇|🥈|🥉|🏅|🎖️|#\d+)\s*", "", cleaned)
    cleaned = re.sub(r"[—–-]\s*[\d\s]+\s*(?:сообщ|сообщений|сообщения|смс|msg|messages|💬)?", "", cleaned, flags=re.I)
    cleaned = re.sub(r"[\d\s]+\s*(?:сообщ|сообщений|сообщения|смс|msg|messages|💬)", "", cleaned, flags=re.I)
    cleaned = re.sub(r"💬\s*[\d\s]+", "", cleaned)
    cleaned = cleaned.strip()

    normalized_line_name = _normalize_name_for_match(cleaned)

    if not normalized_line_name:
        return None

    candidates = []

    for uid_str, u in data.get("users", {}).items():
        if not isinstance(u, dict):
            continue

        try:
            uid = int(uid_str)
        except Exception:
            continue

        names = set()

        username = (u.get("username") or "").strip()
        first_name = (u.get("first_name") or "").strip()
        last_name = (u.get("last_name") or "").strip()
        name = (u.get("name") or "").strip()
        nick = (u.get("nick") or u.get("nickname") or "").strip()

        if username:
            names.add(username)
            names.add("@" + username)

        if first_name:
            names.add(first_name)

        if first_name or last_name:
            names.add(f"{first_name} {last_name}".strip())

        if name:
            names.add(name)

        if nick:
            names.add(nick)

        for n in names:
            nn = _normalize_name_for_match(n)

            if not nn:
                continue

            if nn == normalized_line_name:
                return uid

            if nn in normalized_line_name or normalized_line_name in nn:
                candidates.append(uid)

    if len(set(candidates)) == 1:
        return candidates[0]

    return None


def _find_user_id_in_iris_line(reply_msg, full_text: str, line_start: int, line_end: int, line: str) -> int | None:
    entities = getattr(reply_msg, "entities", None) or getattr(reply_msg, "caption_entities", None) or []

    for ent in entities:
        try:
            ent_start, ent_end = _entity_py_range(full_text, ent)

            intersects = ent_start < line_end and ent_end > line_start

            if not intersects:
                continue

            ent_type = getattr(ent, "type", "")
            ent_text = full_text[ent_start:ent_end]

            if ent_type == "text_mention" and getattr(ent, "user", None):
                return int(ent.user.id)

            if ent_type == "mention":
                uid = resolve_username(ent_text.strip())
                if uid:
                    return int(uid)

            if ent_type == "text_link":
                uid = _extract_uid_from_url(getattr(ent, "url", "") or "")
                if uid:
                    return int(uid)

            if ent_type == "url":
                uid = _extract_uid_from_url(ent_text.strip())
                if uid:
                    return int(uid)

        except Exception:
            pass

    m = re.search(r"@([A-Za-z0-9_]{5,32})", line)
    if m:
        uid = resolve_username("@" + m.group(1))
        if uid:
            return int(uid)

    uid = _find_user_by_visible_name(line)
    if uid:
        return int(uid)

    return None


def parse_iris_top_message(reply_msg):
    full_text = getattr(reply_msg, "text", None) or getattr(reply_msg, "caption", None) or ""

    result = []

    start = 0

    for raw_line in full_text.splitlines(True):
        end = start + len(raw_line)
        line = raw_line.rstrip("\n").rstrip("\r")
        line_clean = line.strip()

        if not line_clean:
            start = end
            continue

        count = _extract_count_from_iris_line(line_clean)

        if count <= 0:
            start = end
            continue

        uid = _find_user_id_in_iris_line(reply_msg, full_text, start, end, line)

        if uid:
            result.append((uid, count))

        start = end

    unique = {}

    for uid, count in result:
        unique[int(uid)] = int(count)

    return list(unique.items())


def _sorted_users_by_key_positive(users_dict: dict, key: str) -> list:
    arr = []
    for _, u in (users_dict or {}).items():
        if not isinstance(u, dict):
            continue
        val = _to_int(u.get(key, 0), 0)
        if val > 0:
            arr.append((val, u))
    arr.sort(key=lambda x: x[0], reverse=True)
    return arr


def _sorted_users_today_positive(users_dict: dict) -> list:
    today = _today()
    arr = []
    for _, u in (users_dict or {}).items():
        if not isinstance(u, dict):
            continue
        if u.get("msg_day") != today:
            continue
        val = _to_int(u.get("msg_today", 0), 0)
        if val > 0:
            arr.append((val, u))
    arr.sort(key=lambda x: x[0], reverse=True)
    return arr


def bot_can_manage(chat_id: int) -> bool:
    try:
        me = bot.get_me()
        cm = bot.get_chat_member(chat_id, me.id)
        if cm.status not in ("administrator", "creator"):
            return False
        return bool(getattr(cm, "can_restrict_members", True))
    except Exception:
        return False


def make_closed_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
    )


def make_open_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
        can_invite_users=True,
    )


def send_long_message(chat_id: int, text: str, reply_to_message_id=None):
    chunks = []
    while len(text) > 3900:
        cut = text.rfind("\n", 0, 3900)
        if cut <= 0:
            cut = 3900
        chunks.append(text[:cut])
        text = text[cut:].lstrip()
    chunks.append(text)

    first = True
    for ch in chunks:
        if first and reply_to_message_id:
            bot.send_message(chat_id, ch, reply_to_message_id=reply_to_message_id, disable_web_page_preview=True)
        else:
            bot.send_message(chat_id, ch, disable_web_page_preview=True)
        first = False


def _fmt_dt(ts) -> str:
    try:
        if not ts:
            return "—"
        return datetime.fromtimestamp(int(ts)).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return "—"


def resolve_username(arg: str) -> Optional[int]:
    if not arg:
        return None

    key = arg.strip()
    if key.startswith("@"):
        key = key[1:]
    key = key.lower()

    if key in USERNAME_TO_ID:
        return USERNAME_TO_ID[key]

    for uid_str, u in data.get("users", {}).items():
        if not isinstance(u, dict):
            continue
        if (u.get("username") or "").strip().lower() == key:
            try:
                uid = int(uid_str)
                USERNAME_TO_ID[key] = uid
                return uid
            except Exception:
                pass

    return None


def get_target_from_message(message):
    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        ensure_user(user.id, user)
        return user.id, user

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) > 1:
        arg = parts[1].strip()
        if arg.isdigit():
            uid = int(arg)
            return uid, None

        uid = resolve_username(arg)
        if uid:
            return uid, None

    return message.from_user.id, message.from_user


def ensure_clan(name: str) -> dict:
    name = (name or "").strip()
    if not name:
        raise ValueError("Некорректное название клана")

    clans = data.setdefault("clans", {})
    clan = clans.get(name)

    if clan is None or not isinstance(clan, dict):
        clan = {"owner": None, "members": [], "treasury": 0}
        clans[name] = clan

    clan.setdefault("owner", None)
    clan.setdefault("members", [])
    clan.setdefault("treasury", 0)

    if not isinstance(clan["members"], list):
        clan["members"] = []

    clan["members"] = [_to_int(x, 0) for x in clan["members"] if _to_int(x, 0) > 0]
    clan["treasury"] = _to_int(clan.get("treasury", 0), 0)

    save_data()
    return clan



def clan_members(clan_name: str, clan: dict):
    result = {}

    for uid_str, u in data.get("users", {}).items():
        if not isinstance(u, dict):
            continue
        if (u.get("clan") or "").strip() == clan_name:
            try:
                result[int(uid_str)] = u
            except Exception:
                pass

    for uid in clan.get("members", []):
        try:
            uid = int(uid)
            result[uid] = data.get("users", {}).get(str(uid), {"id": uid})
        except Exception:
            pass

    return list(result.items())


def award_text(chat_id: int, uid: int, limit=10) -> str:
    u = data.get("users", {}).get(str(uid), {})
    arr = u.get("awards_by_chat", {}).get(str(chat_id), [])
    if not arr:
        return ""

    lines = ["🏅 Награды:"]
    for i, a in enumerate(reversed(arr[-limit:]), start=1):
        icon = (a.get("icon") or "").strip()
        title = tg_escape_html(a.get("title") or "Награда")
        note = tg_escape_html(a.get("note") or "")
        lines.append(f" • {i}. {icon + ' ' if icon else ''}{title}{' — ' + note if note else ''}")

    return "\n".join(lines)


@bot.message_handler(commands=["ping"])
def cmd_ping(message):
    bot.reply_to(message, "pong", parse_mode=None)

@bot.message_handler(commands=["now"])
def cmd_now(message):
    text = (
        "Добавленные/обнавленные функции:.\n\n"
        "Команды:\n"
        "Админ-команды:\n"
        "• +маты - включить фильтр на маты\n"
        "• -маты - выключить фильтр на маты\n"
        "• /warn_list - посмотреть варны пользователей в чате\n"
        "• /ban_list - посмотреть забаненых пользователей в чате\n"
        "• /mute_list - посмотреть замученых пользователей в чате\n"
    )
    bot.reply_to(message, text, parse_mode=None)


@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    ensure_user(message.from_user.id, message.from_user)
    text = (
        "Привет! Я админ-бот с экономикой, кланами, топом сообщений и дуэлями.\n\n"
        "Команды:\n"
        "• /earn - заработать валюту\n"
        "• /balance - баланс\n"
        "• /profile - профиль\n"
        "• /awards - посмотреть свои награды\n"
        "• /shop - магазин за валюту\n"
        "• /rules - правила чата\n\n"
        "• /top - топ сообщений за сегодня\n"
        "• /report - кинуть репорт на пользователя\n"
        "• /weather - посмореть погоду в городе\n"
        #"• /top_all - топ сообщений за всё время\n"
        "• /clan_create название - создать клан\n"
        "• /clan_join название - вступить в клан\n"
        "• /clans - список кланов\n"
        "• /clan_info - информация о клане\n"
        "• /clan_deposit сумма - пополнить казну\n"
        "• /clan_withdraw сумма - забрать из казны\n"
        "• /duel - дуэль, лучше ответом на сообщение\n"
        "• /who_duel - найти соперника на дуэль\n"
        "Админ-команды:\n"
        "• +маты - включить фильтр на маты\n"
        "• -маты - выключить фильтр на маты\n"
        "• -смс - удалить сообщения\n"
        "• +правила - установить правила"
        "• /call_everyone — созвать всех участников\n"
        "• /off_chat - закрыть чат\n"
        "• /on_chat - открыть чат\n"
        "• /mute - замутить пользователя\n"
        "• /unmute - размутить пользователя\n"
        "• /ban - забанить пользователя\n"
        "• /unban - разбанить пользователя\n"
        "• /award - выдать награду ответом на сообщение\n"
        "• /add_greetings - поставить приветствие\n"
        "• /reports - посмотреть репорты от пользователей\n"
        "• /warn_list - посмотреть варны пользователей в чате\n"
        "• /ban_list - посмотреть забаненых пользователей в чате\n"
        "• /mute_list - посмотреть замученых пользователей в чате\n"
    )
    bot.reply_to(message, text, parse_mode=None)


@bot.message_handler(commands=["balance"])
def cmd_balance(message):
    u = ensure_user(message.from_user.id, message.from_user)
    balance = _to_int(u.get("balance", 0), 0)
    prime = "есть" if _to_int(u.get("prime", 0), 0) else "нет"
    bot.reply_to(message, f"💰 Баланс: {balance}", parse_mode=None)


@bot.message_handler(commands=["earn"])
def cmd_earn(message):
    u = ensure_user(message.from_user.id, message.from_user)

    now = int(time.time())
    last = _to_int(u.get("last_earn_at", 0), 0)
    remain = last + EARN_COOLDOWN_SECONDS - now

    if remain > 0:
        bot.reply_to(message, f"⏳ /earn будет доступна через {remain // 60}:{remain % 60:02d}.", parse_mode=None)
        return

    reward = random.randint(EARN_MIN, EARN_MAX)
    if _to_int(u.get("prime", 0), 0):
        reward *= 2

    u["balance"] = _to_int(u.get("balance", 0), 0) + reward
    u["last_earn_at"] = now
    save_data()

    bot.reply_to(message, f"💸 Вы заработали {reward} валюты.\n💰 Баланс: {u['balance']}", parse_mode=None)

@bot.message_handler(func=lambda m: bool(m.text) and m.text.strip().lower() == "заработать")
def cmd_earn(message):
    u = ensure_user(message.from_user.id, message.from_user)

    now = int(time.time())
    last = _to_int(u.get("last_earn_at", 0), 0)
    remain = last + EARN_COOLDOWN_SECONDS - now

    if remain > 0:
        bot.reply_to(message, f"⏳ /earn будет доступна через {remain // 60}:{remain % 60:02d}.", parse_mode=None)
        return

    reward = random.randint(EARN_MIN, EARN_MAX)
    if _to_int(u.get("prime", 0), 0):
        reward *= 2

    u["balance"] = _to_int(u.get("balance", 0), 0) + reward
    u["last_earn_at"] = now
    save_data()

    bot.reply_to(message, f"💸 Вы заработали {reward} валюты.\n💰 Баланс: {u['balance']}", parse_mode=None)


@bot.message_handler(commands=["reset_earn_cooldown"])
def cmd_reset_earn_cooldown(message):
    if ADMIN_ID and message.from_user.id not in ADMIN_ID:
        bot.reply_to(message, "❌ Команда доступна только администратору.", parse_mode=None)
        return

    changed = 0
    for u in data.get("users", {}).values():
        if isinstance(u, dict):
            if _to_int(u.get("last_earn_at", 0), 0) != 0:
                changed += 1
            u["last_earn_at"] = 0

    save_data()
    bot.reply_to(message, f"✅ Кулдаун сброшен у {changed} пользователей.", parse_mode=None)


def shop_text_and_markup(uid: int):
    u = ensure_user(uid)
    kb = InlineKeyboardMarkup(row_width=1)

    kb.add(InlineKeyboardButton(f"📦 Купить бокс ({BOX_COST})", callback_data="shop:box"))
    kb.add(InlineKeyboardButton(f"💎 Купить Прайм ({PRIME_COST})", callback_data="shop:prime"))

    if _to_int(u.get("free_box", 0), 0) > 0:
        kb.add(InlineKeyboardButton("🎁 Открыть бесплатный бокс", callback_data="shop:freebox"))

    text = (
        "🛒 Магазин\n"
        f"💰 Баланс: {_to_int(u.get('balance', 0), 0)}\n"
        f"✨ Прайм: {'активен' if _to_int(u.get('prime', 0), 0) else 'нет'}\n"
        f"🎁 Бесплатные боксы: {_to_int(u.get('free_box', 0), 0)}"
    )

    return text, kb


def apply_box_reward(uid: int) -> str:
    u = ensure_user(uid)
    r = random.random()

    if r < 0.70:
        amount = random.randint(1000, 5000)
        u["balance"] = _to_int(u.get("balance", 0), 0) + amount
        save_data()
        return f"📦 Вы получили 💰 {amount} валюты!"

    if r < 0.80:
        if not _to_int(u.get("prime", 0), 0):
            u["prime"] = 1
            save_data()
            return "📦 Вы получили ✨ Прайм!"
        amount = random.randint(200, 600)
        u["balance"] = _to_int(u.get("balance", 0), 0) + amount
        save_data()
        return f"📦 Прайм уже был, вместо него вы получили 💰 {amount}."

    if r < 0.95:
        u["free_box"] = _to_int(u.get("free_box", 0), 0) + 1
        save_data()
        return "📦 Вы получили 🎁 бесплатный бокс!"

    u["free_clan_ticket"] = _to_int(u.get("free_clan_ticket", 0), 0) + 1
    save_data()
    return "📦 Вы получили 🆓 билет на бесплатное создание клана!"


@bot.message_handler(commands=["shop"])
def cmd_shop(message):
    ensure_user(message.from_user.id, message.from_user)
    text, kb = shop_text_and_markup(message.from_user.id)
    bot.reply_to(message, text, reply_markup=kb, parse_mode=None)


@bot.callback_query_handler(func=lambda c: c.data in ("shop:box", "shop:prime", "shop:freebox"))
def cb_shop(call):
    uid = call.from_user.id
    u = ensure_user(uid, call.from_user)

    if call.data == "shop:box":
        if _to_int(u.get("balance", 0), 0) < BOX_COST:
            bot.answer_callback_query(call.id, "Недостаточно средств.")
            return
        u["balance"] -= BOX_COST
        save_data()
        result = apply_box_reward(uid)

    elif call.data == "shop:prime":
        if _to_int(u.get("prime", 0), 0):
            bot.answer_callback_query(call.id, "Прайм уже активен.")
            return
        if _to_int(u.get("balance", 0), 0) < PRIME_COST:
            bot.answer_callback_query(call.id, "Недостаточно средств.")
            return
        u["balance"] -= PRIME_COST
        u["prime"] = 1
        save_data()
        result = "✨ Вы купили Прайм!"

    else:
        if _to_int(u.get("free_box", 0), 0) <= 0:
            bot.answer_callback_query(call.id, "Нет бесплатных боксов.")
            return
        u["free_box"] -= 1
        save_data()
        result = apply_box_reward(uid)

    text, kb = shop_text_and_markup(uid)

    try:
        bot.edit_message_text(f"{result}\n\n{text}", call.message.chat.id, call.message.message_id, reply_markup=kb, parse_mode=None)
    except Exception:
        bot.send_message(call.message.chat.id, f"{result}\n\n{text}", reply_markup=kb, parse_mode=None)

    bot.answer_callback_query(call.id, "Готово")


@bot.message_handler(commands=["profile"])
def cmd_profile(message):
    target_id, tg_user = get_target_from_message(message)
    u = ensure_user(target_id, tg_user)

    name = user_display_from_data(u)
    username = f"@{u.get('username')}" if u.get("username") else "—"
    clan = u.get("clan") or "—"

    text = (
        "👤 Профиль пользователя\n\n"
        
        f"• 🪪 Имя: {tg_escape_html(name)}\n"
        f"• 🔗 Username: {tg_escape_html(username)}\n\n"
        
        f"📦 Аккаунт:"
        f"• 💰 Баланс: {_to_int(u.get('balance', 0), 0)}\n"
        f"• 💎 Прайм: {'Активен' if _to_int(u.get('prime', 0), 0) else 'Нету'}\n"
        f"• 🛡️ Клан: {tg_escape_html(clan)}\n"
        f"• 📅 Зарегистрировался в боте: {_fmt_dt(u.get('created_at'))}\n\n"
        
        f"📊 Статистика:\n"
        f"• 🏆 Победы в дуэлях: {_to_int(u.get('duel_wins', 0), 0)}\n"
        f"• 💬 Сообщений в чатах с ботом: {_to_int(u.get('msg_total', 0), 0)}\n"

    )

    awards = award_text(message.chat.id, target_id)
    if awards:
        text += "\n\n" + (f"{awards}")

    bot.reply_to(message, text)


@bot.message_handler(commands=["top"])
def handle_slash_top(message):
    return cmd_top(message)


@bot.message_handler(commands=["top_all"])
def handle_slash_top_all(message):
    return cmd_top_all(message)


@bot.message_handler(func=lambda m: bool(m.text) and m.text.strip().lower() == "топ")
def handle_text_top(message):
    return cmd_top(message)


@bot.message_handler(func=lambda m: bool(m.text) and m.text.strip().lower() == "топ вся")
def handle_text_top_all(message):
    return cmd_top_all(message)

@bot.message_handler(commands=["clan_create"])
def cmd_clan_create(message):
    u = ensure_user(message.from_user.id, message.from_user)
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /clan_create Название", parse_mode=None)
        return

    clan_name = parts[1].strip()

    if clan_name in data.setdefault("clans", {}):
        bot.reply_to(message, "❌ Клан с таким названием уже существует.", parse_mode=None)
        return

    if u.get("clan"):
        bot.reply_to(message, "❌ Вы уже состоите в клане.", parse_mode=None)
        return

    if _to_int(u.get("free_clan_ticket", 0), 0) > 0:
        u["free_clan_ticket"] -= 1
        paid = 0
    else:
        if _to_int(u.get("balance", 0), 0) < CLAN_CREATE_COST:
            bot.reply_to(message, f"❌ Нужно {CLAN_CREATE_COST} валюты.", parse_mode=None)
            return
        u["balance"] -= CLAN_CREATE_COST
        paid = CLAN_CREATE_COST

    data["clans"][clan_name] = {
        "owner": message.from_user.id,
        "members": [message.from_user.id],
        "treasury": 0,
    }

    u["clan"] = clan_name
    save_data()

    bot.reply_to(message, f"🛡️ Клан <b>{tg_escape_html(clan_name)}</b> создан! {'🆓 Бесплатно' if paid == 0 else f'💰 Списано: {paid}'}")


@bot.message_handler(commands=["clan_join"])
def cmd_clan_join(message):
    u = ensure_user(message.from_user.id, message.from_user)
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, "Использование: /clan_join Название", parse_mode=None)
        return

    clan_name = parts[1].strip()
    clan = data.setdefault("clans", {}).get(clan_name)

    if not clan:
        bot.reply_to(message, "❌ Клан не найден.", parse_mode=None)
        return

    if u.get("clan"):
        bot.reply_to(message, f"❌ Вы уже состоите в клане: {u['clan']}", parse_mode=None)
        return

    members = clan.setdefault("members", [])
    if message.from_user.id not in members:
        members.append(message.from_user.id)

    u["clan"] = clan_name
    save_data()

    bot.reply_to(message, f"✅ Вы вступили в клан <b>{tg_escape_html(clan_name)}</b>!")


@bot.message_handler(commands=["clans"])
def cmd_clans(message):
    clans = data.setdefault("clans", {})

    if not clans:
        bot.reply_to(message, "Кланов пока нет.", parse_mode=None)
        return

    lines = ["🏰 Список кланов:\n"]

    for clan_name in sorted(clans.keys(), key=lambda x: x.lower()):
        clan = ensure_clan(clan_name)
        members = clan_members(clan_name, clan)
        owner = clan.get("owner")
        owner_text = "—"

        if owner:
            ou = data.get("users", {}).get(str(owner), {})
            owner_text = user_display_from_data(ou)

        lines.append(
            f"🛡️ {clan_name}\n"
            f"👑 Владелец: {owner_text}\n"
            f"👥 Участников: {len(members)}\n"
            f"💰 Казна: {_to_int(clan.get('treasury', 0), 0)}\n"
        )

    send_long_message(message.chat.id, "\n".join(lines), reply_to_message_id=message.message_id)


@bot.message_handler(commands=["clan_info"])
def cmd_clan_info(message):
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) > 1:
        clan_name = parts[1].strip()
    else:
        u = ensure_user(message.from_user.id, message.from_user)
        clan_name = (u.get("clan") or "").strip()

    if not clan_name:
        bot.reply_to(message, "Использование: /clan_info Название", parse_mode=None)
        return

    clan = data.setdefault("clans", {}).get(clan_name)

    if not clan:
        bot.reply_to(message, "❌ Клан не найден.", parse_mode=None)
        return

    clan = ensure_clan(clan_name)
    members = clan_members(clan_name, clan)
    owner = clan.get("owner")

    lines = [
        f"🛡️ Клан: {clan_name}",
        f"💰 Казна: {_to_int(clan.get('treasury', 0), 0)}",
        f"👥 Участников: {len(members)}",
        "",
        "📋 Состав:"
    ]

    for uid, u in members:
        icon = "👑" if owner and int(uid) == int(owner) else "👤"
        lines.append(f"• {icon} {user_display_from_data(u)}")

    bot.reply_to(message, "\n".join(lines), parse_mode=None)


@bot.message_handler(commands=["clan_deposit"])
def cmd_clan_deposit(message):
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2:
        bot.reply_to(message, "Использование: /clan_deposit сумма", parse_mode=None)
        return

    u = ensure_user(message.from_user.id, message.from_user)
    clan_name = (u.get("clan") or "").strip()

    if not clan_name:
        bot.reply_to(message, "Вы не состоите в клане.", parse_mode=None)
        return

    arg = parts[1].strip().lower()

    if arg in ("все", "all", "max"):
        amount = _to_int(u.get("balance", 0), 0)
    else:
        amount = _to_int(arg, -1)

    if amount <= 0:
        bot.reply_to(message, "Сумма должна быть положительной.", parse_mode=None)
        return

    if amount > _to_int(u.get("balance", 0), 0):
        bot.reply_to(message, "Недостаточно средств.", parse_mode=None)
        return

    clan = ensure_clan(clan_name)
    clan["treasury"] = _to_int(clan.get("treasury", 0), 0) + amount
    u["balance"] -= amount
    save_data()

    bot.reply_to(message, f"✅ Внесено в казну: {amount}\n💰 Казна: {clan['treasury']}\nВаш баланс: {u['balance']}", parse_mode=None)


@bot.message_handler(commands=["clan_withdraw"])
def cmd_clan_withdraw(message):
    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2:
        bot.reply_to(message, f"Использование: /clan_withdraw сумма\nЛимит в сутки: {DAILY_WITHDRAW_LIMIT}", parse_mode=None)
        return

    amount = _to_int(parts[1], -1)

    if amount <= 0:
        bot.reply_to(message, "Сумма должна быть положительной.", parse_mode=None)
        return

    u = ensure_user(message.from_user.id, message.from_user)
    clan_name = (u.get("clan") or "").strip()

    if not clan_name:
        bot.reply_to(message, "Вы не состоите в клане.", parse_mode=None)
        return

    today = _today()

    if u.get("clan_withdraw_day") != today:
        u["clan_withdraw_day"] = today
        u["clan_withdrawn_today"] = 0

    already = _to_int(u.get("clan_withdrawn_today", 0), 0)
    left = DAILY_WITHDRAW_LIMIT - already

    if left <= 0:
        bot.reply_to(message, f"Лимит на сегодня исчерпан: {DAILY_WITHDRAW_LIMIT}", parse_mode=None)
        return

    if amount > left:
        bot.reply_to(message, f"Можно забрать максимум: {left}", parse_mode=None)
        return

    clan = ensure_clan(clan_name)

    if amount > _to_int(clan.get("treasury", 0), 0):
        bot.reply_to(message, "В казне недостаточно средств.", parse_mode=None)
        return

    clan["treasury"] -= amount
    u["balance"] += amount
    u["clan_withdrawn_today"] = already + amount
    save_data()

    bot.reply_to(message, f"✅ Получено: {amount}\n💰 Ваш баланс: {u['balance']}\n🏦 Казна: {clan['treasury']}", parse_mode=None)


@bot.message_handler(commands=["rules"])
def cmd_rules(message):
    if not is_group(message.chat):
        bot.reply_to(message, "Правила доступны только в группе.", parse_mode=None)
        return

    c = ensure_chat(message.chat.id)
    rules = (c.get("rules") or "").strip()

    if not rules:
        bot.reply_to(message, "Правила ещё не установлены. Админ может написать: +правила текст", parse_mode=None)
        return

    bot.reply_to(message, f"📜 Правила чата:\n\n{rules}", parse_mode=None)


@bot.message_handler(func=lambda m: bool(m.text) and m.text.strip().lower().startswith("+правила"))
def cmd_set_rules(message):
    if not is_group(message.chat):
        bot.reply_to(message, "Команда доступна только в группе.", parse_mode=None)
        return

    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "Устанавливать правила могут только администраторы.", parse_mode=None)
        return

    text = message.text.strip()[len("+правила"):].strip()

    if not text:
        bot.reply_to(message, "Напишите текст правил после +правила", parse_mode=None)
        return

    c = ensure_chat(message.chat.id)
    c["rules"] = text
    save_data()

    bot.reply_to(message, "✅ Правила сохранены.", parse_mode=None)


def _pname(st, uid):
    if uid == st["initiator"]:
        return st.get("initiator_name") or "Игрок 1"
    if uid == st["target"]:
        return st.get("target_name") or "Игрок 2"
    return "Игрок"


def _user_in_duel(uid: int):
    return USER_ACTIVE_DUEL.get(int(uid))


def _set_user_duel(uid: int, duel_id: Optional[str]):
    uid = int(uid)
    if duel_id is None:
        USER_ACTIVE_DUEL.pop(uid, None)
    else:
        USER_ACTIVE_DUEL[uid] = duel_id


def _new_duel_state(chat_id: int, initiator_id: int, target_id: int):
    did = uuid.uuid4().hex[:8]
    st = {
        "id": did,
        "chat_id": chat_id,
        "initiator": int(initiator_id),
        "target": int(target_id),
        "initiator_name": "Игрок 1",
        "target_name": "Игрок 2",
        "status": "choose_mode",
        "mode": None,
        "lock": threading.RLock(),
        "rps": {
            "round": 1,
            "choices": {},
            "scores": {int(initiator_id): 0, int(target_id): 0},
            "panel_msg_id": None,
        },
        "click": {
            "counts": {int(initiator_id): 0, int(target_id): 0},
            "panel_msg_id": None,
            "end_at": None,
        },
    }

    DUELS[did] = st
    _set_user_duel(initiator_id, did)
    _set_user_duel(target_id, did)
    return st


def _cleanup_duel(st):
    _set_user_duel(st["initiator"], None)
    _set_user_duel(st["target"], None)
    DUELS.pop(st["id"], None)


def kb_choose_mode(did):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✊✋✌️ КНБ", callback_data=f"duel:mode:{did}:rps"))
    kb.add(InlineKeyboardButton("🖱️ Кликер", callback_data=f"duel:mode:{did}:clicker"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data=f"duel:cancel:{did}"))
    return kb


def kb_confirm(did):
    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Принять", callback_data=f"duel:accept:{did}"),
        InlineKeyboardButton("❌ Отклонить", callback_data=f"duel:decline:{did}"),
    )
    return kb


def kb_rps(did):
    kb = InlineKeyboardMarkup()
    kb.row(
        InlineKeyboardButton("🪨 Камень", callback_data=f"duel:rps:{did}:R"),
        InlineKeyboardButton("✂️ Ножницы", callback_data=f"duel:rps:{did}:S"),
        InlineKeyboardButton("📄 Бумага", callback_data=f"duel:rps:{did}:P"),
    )
    return kb


def kb_click(did):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("👆 Клик!", callback_data=f"duel:click:{did}"))
    return kb


@bot.message_handler(commands=["duel"])
def cmd_duel(message):
    ensure_user(message.from_user.id, message.from_user)

    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        target_name = user_label_from_tg(message.reply_to_message.from_user)
        ensure_user(target_id, message.reply_to_message.from_user)
    else:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "Ответьте на сообщение командой /duel или напишите /duel @username", parse_mode=None)
            return

        target_id = resolve_username(parts[1].strip())
        target_name = "Соперник"

        if not target_id:
            bot.reply_to(message, "Пользователь не найден. Он должен сначала написать что-нибудь в чат.", parse_mode=None)
            return

    _start_duel(message, target_id, target_name)


@bot.message_handler(func=lambda m: bool(m.text) and m.text.lower().startswith("дуэль"))
def cmd_duel_ru(message):
    ensure_user(message.from_user.id, message.from_user)

    if message.reply_to_message and message.reply_to_message.from_user:
        target_id = message.reply_to_message.from_user.id
        target_name = user_label_from_tg(message.reply_to_message.from_user)
        ensure_user(target_id, message.reply_to_message.from_user)
    else:
        parts = (message.text or "").split(maxsplit=1)
        if len(parts) < 2:
            bot.reply_to(message, "Ответьте на сообщение словом «дуэль» или напишите дуэль @username", parse_mode=None)
            return

        target_id = resolve_username(parts[1].strip())
        target_name = "Соперник"

        if not target_id:
            bot.reply_to(message, "Пользователь не найден.", parse_mode=None)
            return

    _start_duel(message, target_id, target_name)


def _start_duel(message, target_id, target_name):
    initiator = message.from_user.id

    if target_id == initiator:
        bot.reply_to(message, "Нельзя вызвать самого себя.", parse_mode=None)
        return

    if _user_in_duel(initiator):
        bot.reply_to(message, "У вас уже есть активная дуэль.", parse_mode=None)
        return

    if _user_in_duel(target_id):
        bot.reply_to(message, "У соперника уже есть активная дуэль.", parse_mode=None)
        return

    st = _new_duel_state(message.chat.id, initiator, target_id)
    st["initiator_name"] = user_label_from_tg(message.from_user)
    st["target_name"] = target_name

    bot.send_message(
        message.chat.id,
        f"⚔️ Дуэль!\n{st['initiator_name']} вызывает {st['target_name']}.\nВыберите режим:",
        reply_markup=kb_choose_mode(st["id"]),
        parse_mode=None
    )


def _rps_winner(a, b):
    if a == b:
        return 0
    win = {"R": "S", "S": "P", "P": "R"}
    return 1 if win.get(a) == b else -1


def _rps_name(x):
    return {"R": "Камень", "S": "Ножницы", "P": "Бумага"}.get(x, "?")


def _rps_panel(st):
    r = st["rps"]["round"]
    a = st["initiator"]
    b = st["target"]
    sa = st["rps"]["scores"][a]
    sb = st["rps"]["scores"][b]
    return f"🪨✂️📄 Раунд {r}/3\nСчёт: {_pname(st, a)} {sa} — {sb} {_pname(st, b)}\nВыберите жест:"


def _rps_start_round(st):
    st["rps"]["choices"] = {}
    msg = bot.send_message(st["chat_id"], _rps_panel(st), reply_markup=kb_rps(st["id"]), parse_mode=None)
    st["rps"]["panel_msg_id"] = msg.message_id


def _click_start(st):
    st["click"]["end_at"] = time.time() + 15

    msg = bot.send_message(
        st["chat_id"],
        f"👆 Кликер начался! 15 секунд.\n{_pname(st, st['initiator'])}: 0\n{_pname(st, st['target'])}: 0",
        reply_markup=kb_click(st["id"]),
        parse_mode=None
    )

    st["click"]["panel_msg_id"] = msg.message_id

    def finish():
        with st["lock"]:
            if st.get("status") != "click_active":
                return

            a = st["initiator"]
            b = st["target"]
            ca = st["click"]["counts"][a]
            cb = st["click"]["counts"][b]

            text = f"🏁 Итог кликера:\n{_pname(st, a)}: {ca}\n{_pname(st, b)}: {cb}\n"

            if ca > cb:
                text += f"🏆 Победитель: {_pname(st, a)}"
                ensure_user(a)["duel_wins"] = _to_int(ensure_user(a).get("duel_wins", 0), 0) + 1
            elif cb > ca:
                text += f"🏆 Победитель: {_pname(st, b)}"
                ensure_user(b)["duel_wins"] = _to_int(ensure_user(b).get("duel_wins", 0), 0) + 1
            else:
                text += "🤝 Ничья!"

            save_data()

        bot.send_message(st["chat_id"], text, parse_mode=None)

        try:
            bot.edit_message_reply_markup(st["chat_id"], st["click"]["panel_msg_id"], reply_markup=None)
        except Exception:
            pass

        _cleanup_duel(st)

    threading.Timer(15.2, finish).start()


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("duel:"))
def cb_duel(call):
    parts = call.data.split(":")
    action = parts[1]
    did = parts[2] if len(parts) > 2 else None
    st = DUELS.get(did)

    if not st:
        bot.answer_callback_query(call.id, "Дуэль не найдена или завершена.")
        return

    uid = call.from_user.id

    if action == "cancel":
        if uid != st["initiator"]:
            bot.answer_callback_query(call.id, "Отменить может только инициатор.")
            return

        _cleanup_duel(st)

        try:
            bot.edit_message_text("❌ Дуэль отменена.", call.message.chat.id, call.message.message_id, parse_mode=None)
        except Exception:
            bot.send_message(call.message.chat.id, "❌ Дуэль отменена.", parse_mode=None)

        bot.answer_callback_query(call.id, "Отменено")
        return

    if action == "mode":
        if uid != st["initiator"]:
            bot.answer_callback_query(call.id, "Режим выбирает инициатор.")
            return

        mode = parts[3] if len(parts) > 3 else ""
        if mode not in ("rps", "clicker"):
            bot.answer_callback_query(call.id, "Неизвестный режим.")
            return

        st["mode"] = mode
        st["status"] = "await_confirm"

        mode_name = "КНБ" if mode == "rps" else "Кликер"

        try:
            bot.edit_message_text(f"⚔️ Режим выбран: {mode_name}. Ждём подтверждения соперника.", call.message.chat.id, call.message.message_id, parse_mode=None)
        except Exception:
            pass

        bot.send_message(
            st["chat_id"],
            f"{_pname(st, st['target'])}, принять дуэль против {_pname(st, st['initiator'])}?",
            reply_markup=kb_confirm(did),
            parse_mode=None
        )

        bot.answer_callback_query(call.id, "Режим выбран")
        return

    if action == "accept":
        if uid != st["target"]:
            bot.answer_callback_query(call.id, "Принять может только соперник.")
            return

        if st["status"] != "await_confirm":
            bot.answer_callback_query(call.id, "Неверное состояние дуэли.")
            return

        if st["mode"] == "rps":
            st["status"] = "rps_active"
            bot.answer_callback_query(call.id, "Принято")
            bot.send_message(st["chat_id"], "✅ Дуэль принята. Начинаем КНБ!", parse_mode=None)
            _rps_start_round(st)
        else:
            st["status"] = "click_active"
            bot.answer_callback_query(call.id, "Принято")
            bot.send_message(st["chat_id"], "✅ Дуэль принята. Начинаем кликер!", parse_mode=None)
            _click_start(st)
        return

    if action == "decline":
        if uid not in (st["initiator"], st["target"]):
            bot.answer_callback_query(call.id, "Вы не участник дуэли.")
            return

        _cleanup_duel(st)
        bot.answer_callback_query(call.id, "Отклонено")
        bot.send_message(call.message.chat.id, "❌ Дуэль отклонена.", parse_mode=None)
        return

    if action == "rps":
        if st["status"] != "rps_active":
            bot.answer_callback_query(call.id, "Сейчас не идёт КНБ.")
            return

        if uid not in (st["initiator"], st["target"]):
            bot.answer_callback_query(call.id, "Вы не участник.")
            return

        choice = parts[3] if len(parts) > 3 else ""

        if choice not in ("R", "S", "P"):
            bot.answer_callback_query(call.id, "Неверный выбор.")
            return

        with st["lock"]:
            choices = st["rps"]["choices"]

            if uid in choices:
                bot.answer_callback_query(call.id, "Вы уже выбрали.")
                return

            choices[uid] = choice
            bot.answer_callback_query(call.id, "Выбор принят.")

            if len(choices) < 2:
                return

            a = st["initiator"]
            b = st["target"]
            ca = choices[a]
            cb = choices[b]
            res = _rps_winner(ca, cb)

            round_text = (
                f"📣 Раунд {st['rps']['round']}:\n"
                f"{_pname(st, a)} — {_rps_name(ca)}\n"
                f"{_pname(st, b)} — {_rps_name(cb)}\n"
            )

            if res == 1:
                st["rps"]["scores"][a] += 1
                round_text += f"Победил в раунде: {_pname(st, a)}"
            elif res == -1:
                st["rps"]["scores"][b] += 1
                round_text += f"Победил в раунде: {_pname(st, b)}"
            else:
                round_text += "Ничья в раунде."

            bot.send_message(st["chat_id"], round_text, parse_mode=None)

            if st["rps"]["round"] < 3:
                st["rps"]["round"] += 1
                _rps_start_round(st)
            else:
                sa = st["rps"]["scores"][a]
                sb = st["rps"]["scores"][b]
                final = f"🏁 Итог КНБ:\n{_pname(st, a)} {sa} — {sb} {_pname(st, b)}\n"

                if sa > sb:
                    final += f"🏆 Победитель: {_pname(st, a)}"
                    ua = ensure_user(a)
                    ua["duel_wins"] = _to_int(ua.get("duel_wins", 0), 0) + 1
                elif sb > sa:
                    final += f"🏆 Победитель: {_pname(st, b)}"
                    ub = ensure_user(b)
                    ub["duel_wins"] = _to_int(ub.get("duel_wins", 0), 0) + 1
                else:
                    final += "🤝 Ничья!"

                save_data()
                bot.send_message(st["chat_id"], final, parse_mode=None)
                _cleanup_duel(st)

        return

    if action == "click":
        if st["status"] != "click_active":
            bot.answer_callback_query(call.id, "Сейчас не идёт кликер.")
            return

        if uid not in (st["initiator"], st["target"]):
            bot.answer_callback_query(call.id, "Вы не участник.")
            return

        if time.time() > st["click"]["end_at"]:
            bot.answer_callback_query(call.id, "Время вышло.")
            return

        with st["lock"]:
            st["click"]["counts"][uid] += 1
            a = st["initiator"]
            b = st["target"]
            ca = st["click"]["counts"][a]
            cb = st["click"]["counts"][b]
            left = max(0, int(st["click"]["end_at"] - time.time()))

        bot.answer_callback_query(call.id, f"Ты кликнул! Осталось {left} сек.")

        try:
            bot.edit_message_text(
                f"👆 Кликер — осталось {left} сек.\n{_pname(st, a)}: {ca}\n{_pname(st, b)}: {cb}",
                st["chat_id"],
                st["click"]["panel_msg_id"],
                reply_markup=kb_click(st["id"]),
                parse_mode=None
            )
        except Exception:
            pass

        return


def _wd_display_name(user):
    return user_label_from_tg(user)


def _wd_kb_accept(sid):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("✅ Принять дуэль", callback_data=f"wd:accept:{sid}"))
    return kb


def _wd_kb_choose(sid):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(DUEL_MODES["clicker"], callback_data=f"wd:mode:{sid}:clicker"))
    kb.add(InlineKeyboardButton(DUEL_MODES["rps"], callback_data=f"wd:mode:{sid}:rps"))
    kb.add(InlineKeyboardButton("❌ Отмена", callback_data=f"wd:cancel:{sid}"))
    return kb


def _wd_publish_search(message):
    sid = uuid.uuid4().hex[:8]
    name = _wd_display_name(message.from_user)

    sent = bot.send_message(message.chat.id, f"{name} ищет дуэль!", reply_markup=_wd_kb_accept(sid), parse_mode=None)

    WHO_DUEL[sid] = {
        "sid": sid,
        "chat_id": message.chat.id,
        "msg_id": sent.message_id,
        "initiator_id": message.from_user.id,
        "initiator_name": name,
        "created_at": time.time(),
        "accepted_by": None,
        "chooser_id": None,
        "opponent_id": None,
        "choose_msg_id": None,
    }


@bot.message_handler(commands=["who_duel"])
def cmd_who_duel(message):
    ensure_user(message.from_user.id, message.from_user)
    _wd_publish_search(message)


def _wd_text_trigger(m):
    return bool(m.text) and re.match(r"^\s*кто\s+дуэ[лль]([яеи])?\s*[\?\!]*\s*$", m.text.strip(), flags=re.I)


@bot.message_handler(func=_wd_text_trigger)
def txt_who_duel(message):
    ensure_user(message.from_user.id, message.from_user)
    _wd_publish_search(message)


@bot.callback_query_handler(func=lambda c: c.data and c.data.startswith("wd:"))
def cb_who_duel(call):
    parts = call.data.split(":")
    action = parts[1]
    sid = parts[2]
    st = WHO_DUEL.get(sid)

    if not st:
        bot.answer_callback_query(call.id, "Поиск устарел.")
        return

    if time.time() - st["created_at"] > WHO_DUEL_TTL:
        WHO_DUEL.pop(sid, None)
        bot.answer_callback_query(call.id, "Время вышло.")
        return

    if action == "accept":
        if call.from_user.id == st["initiator_id"]:
            bot.answer_callback_query(call.id, "Нельзя принять свой поиск.")
            return

        if st.get("accepted_by"):
            bot.answer_callback_query(call.id, "Уже принят.")
            return

        st["accepted_by"] = call.from_user.id
        st["chooser_id"] = call.from_user.id
        st["opponent_id"] = st["initiator_id"]

        name = user_label_from_tg(call.from_user)

        try:
            bot.edit_message_text(
                f"{st['initiator_name']} ищет дуэль!\nПринял: {name}",
                st["chat_id"],
                st["msg_id"],
                parse_mode=None
            )
        except Exception:
            pass

        sent = bot.send_message(
            st["chat_id"],
            f"{name}, выберите режим дуэли против {st['initiator_name']}:",
            reply_markup=_wd_kb_choose(sid),
            parse_mode=None
        )

        st["choose_msg_id"] = sent.message_id
        bot.answer_callback_query(call.id, "Выберите режим.")
        return

    if action == "mode":
        if call.from_user.id != st.get("chooser_id"):
            bot.answer_callback_query(call.id, "Режим выбирает принявший.")
            return

        mode = parts[3] if len(parts) > 3 else ""

        if mode not in ("rps", "clicker"):
            bot.answer_callback_query(call.id, "Неизвестный режим.")
            return

        player1 = st["chooser_id"]
        player2 = st["opponent_id"]

        if _user_in_duel(player1) or _user_in_duel(player2):
            bot.answer_callback_query(call.id, "Кто-то уже в дуэли.")
            return

        duel = _new_duel_state(st["chat_id"], player1, player2)
        duel["initiator_name"] = user_label_from_tg(call.from_user)
        duel["target_name"] = st["initiator_name"]
        duel["mode"] = mode

        WHO_DUEL.pop(sid, None)

        try:
            bot.edit_message_text("✅ Режим выбран.", st["chat_id"], st.get("choose_msg_id"), parse_mode=None)
        except Exception:
            pass

        if mode == "rps":
            duel["status"] = "rps_active"
            bot.send_message(st["chat_id"], "⚔️ Дуэль началась! Режим: КНБ", parse_mode=None)
            _rps_start_round(duel)
        else:
            duel["status"] = "click_active"
            bot.send_message(st["chat_id"], "⚔️ Дуэль началась! Режим: Кликер", parse_mode=None)
            _click_start(duel)

        bot.answer_callback_query(call.id, "Дуэль началась.")
        return

    if action == "cancel":
        if call.from_user.id not in (st.get("initiator_id"), st.get("chooser_id")):
            bot.answer_callback_query(call.id, "Нет прав отменить.")
            return

        WHO_DUEL.pop(sid, None)
        bot.answer_callback_query(call.id, "Отменено.")

        try:
            bot.edit_message_text("❌ Поиск дуэли отменён.", st["chat_id"], st.get("choose_msg_id") or st["msg_id"], parse_mode=None)
        except Exception:
            bot.send_message(st["chat_id"], "❌ Поиск дуэли отменён.", parse_mode=None)

        return

@bot.message_handler(commands=["weather"])
def cmd_weather(message):
    city = _weather_get_city_from_message(message)

    if not city:
        bot.reply_to(
            message,
            "❌ Укажи город.\n\n"
            "Примеры:\n"
            "/weather Липецк\n"
            "Погода Липецк",
            parse_mode=None
        )
        return

    weather_data, error = _weather_fetch_open_meteo(city)

    if error or not weather_data:
        bot.reply_to(
            message,
            f"❌ Не удалось получить погоду для города: {city}\n\n"
            f"Причина: {error or 'неизвестная ошибка'}",
            parse_mode=None
        )
        return

    text = _weather_format_open_meteo(city, weather_data)

    if not text:
        bot.reply_to(
            message,
            f"❌ Не удалось разобрать погоду для города: {city}",
            parse_mode=None
        )
        return

    bot.reply_to(message, text, parse_mode=None)


@bot.message_handler(func=lambda m: bool(m.text) and m.text.strip().lower().startswith("погода"))
def txt_weather(message):
    return cmd_weather(message)

@bot.message_handler(commands=["give_money"])
def cmd_give_money(message):
    if ADMIN_ID and message.from_user.id not in ADMIN_ID:
        return

    amount = _parse_money_amount(message)

    if amount is None:
        bot.reply_to(
            message,
            "❌ Укажи сумму.\n\n"
            "Примеры:\n"
            "/give_money 1000 — выдать себе\n"
            "Ответом на сообщение: /give_money 1000 — выдать человеку",
            parse_mode=None
        )
        return

    target_id, target_user = _get_money_target(message)

    u = ensure_user(target_id, target_user)
    old_balance = _to_int(u.get("balance", 0), 0)
    new_balance = old_balance + amount

    u["balance"] = new_balance
    save_data()

    bot.reply_to(
        message,
        f"✅ Валюта выдана\n\n"
        f"👤 Пользователь: {_wr_get_name(target_id)}\n"
        f"➕ Выдано: {amount}\n"
        f"💰 Было: {old_balance}\n"
        f"💰 Стало: {new_balance}\n"
        f"👮 Админ: {_wr_get_name(message.from_user.id)}",
        parse_mode=None
    )


@bot.message_handler(commands=["take_money"])
def cmd_take_money(message):
    if ADMIN_ID and message.from_user.id not in ADMIN_ID:
        return

    amount = _parse_money_amount(message)

    if amount is None:
        bot.reply_to(
            message,
            "❌ Укажи сумму.\n\n"
            "Примеры:\n"
            "/take_money 1000 — забрать у себя\n"
            "Ответом на сообщение: /take_money 1000 — забрать у человека",
            parse_mode=None
        )
        return

    target_id, target_user = _get_money_target(message)

    u = ensure_user(target_id, target_user)
    old_balance = _to_int(u.get("balance", 0), 0)

    taken = min(old_balance, amount)
    new_balance = old_balance - taken

    u["balance"] = new_balance
    save_data()

    if taken < amount:
        note = f"\n⚠️ У пользователя было меньше валюты, поэтому забрано только: {taken}"
    else:
        note = ""

    bot.reply_to(
        message,
        f"✅ Валюта забрана\n\n"
        f"👤 Пользователь: {_wr_get_name(target_id)}\n"
        f"➖ Запрошено снять: {amount}\n"
        f"💸 Фактически снято: {taken}\n"
        f"💰 Было: {old_balance}\n"
        f"💰 Стало: {new_balance}\n"
        f"👮 Админ: {_wr_get_name(message.from_user.id)}"
        f"{note}",
        parse_mode=None
    )

@bot.message_handler(commands=["fill_users"])
def cmd_fill_users(message):
    if ADMIN_ID and message.from_user.id not in ADMIN_ID:
        bot.reply_to(message, "❌ У тебя нет доступа к этой команде.", parse_mode=None)
        return

    if not is_group(message.chat):
        bot.reply_to(message, "❌ Команда работает только в группе.", parse_mode=None)
        return

    chat_id = message.chat.id

    found_ids = set()
    saved = 0
    skipped = 0
    errors = 0
    admins_count = 0

    # Добавляем самого отправителя команды
    try:
        save_tg_user_to_data(message.from_user, chat_id=chat_id)
        found_ids.add(int(message.from_user.id))
        saved += 1
    except Exception:
        errors += 1

    # Получаем и сохраняем администраторов чата
    try:
        admins = bot.get_chat_administrators(chat_id)

        for admin in admins:
            try:
                tg_user = admin.user

                found_ids.add(int(tg_user.id))

                status = getattr(admin, "status", None)
                custom_title = getattr(admin, "custom_title", None)

                if save_tg_user_to_data(
                    tg_user,
                    chat_id=chat_id,
                    status=status,
                    custom_title=custom_title
                ):
                    saved += 1
                    admins_count += 1
                else:
                    skipped += 1

            except Exception:
                errors += 1

    except Exception:
        errors += 1

    # Берём пользователей, которые уже есть в статистике этого чата
    known_ids = collect_known_user_ids_from_chat(chat_id)

    for uid in known_ids:
        if uid in found_ids:
            continue

        try:
            member = bot.get_chat_member(chat_id, uid)

            status = getattr(member, "status", None)

            if status in ("left", "kicked"):
                skipped += 1
                continue

            tg_user = member.user
            custom_title = getattr(member, "custom_title", None)

            if save_tg_user_to_data(
                tg_user,
                chat_id=chat_id,
                status=status,
                custom_title=custom_title
            ):
                saved += 1
                found_ids.add(int(uid))
            else:
                skipped += 1

        except Exception:
            errors += 1

    save_data()

    bot.reply_to(
        message,
        f"✅ Заполнение пользователей завершено.\n\n"
        f"👮 Админов найдено: {admins_count}\n"
        f"👥 Всего сохранено/обновлено: {saved}\n"
        f"⏭️ Пропущено: {skipped}\n"
        f"⚠️ Ошибок: {errors}\n\n"
        f"Важно: Telegram Bot API не позволяет получить всех участников чата сразу. "
        f"Добавлены админы и пользователи, которые уже есть в статистике/базе бота.",
        parse_mode=None
    )

@bot.message_handler(func=lambda m: bool(m.text) and m.text.strip().lower() == "бан")
def cmd_ban(message):
    target_id, target_user, duration, reason = _pun_parse_target_duration_reason(message)

    if not _pun_check_common(message, target_id):
        return

    if target_user:
        _pun_save_user_minimal(target_user, chat_id=message.chat.id)

    until_date = _pun_until_date(duration)

    try:
        if until_date:
            bot.ban_chat_member(
                message.chat.id,
                target_id,
                until_date=until_date,
                revoke_messages=False
            )
        else:
            bot.ban_chat_member(
                message.chat.id,
                target_id,
                revoke_messages=False
            )

        _pun_add_log(
            chat_id=message.chat.id,
            action="ban",
            moderator_id=message.from_user.id,
            target_id=target_id,
            duration=duration,
            reason=reason
        )

        text = (
            f"🔨 Пользователь забанен\n\n"
            f"👤 Нарушитель: {_pun_get_name_by_id(target_id)}\n"
            f"👮 Модератор: {_pun_get_name_by_id(message.from_user.id)}\n"
            f"⏳ Срок: {_pun_format_duration(duration)}\n"
            f"📝 Причина: {reason or 'не указана'}"
        )

        bot.reply_to(message, text, parse_mode=None)

    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Не удалось забанить пользователя.\n\n"
            f"Причина: {e}\n\n"
            f"Проверь, что бот является администратором и имеет право банить пользователей.",
            parse_mode=None
        )


@bot.message_handler(commands=["ban"])
def cmd_ban(message):
    target_id, target_user, duration, reason = _pun_parse_target_duration_reason(message)

    if not _pun_check_common(message, target_id):
        return

    if target_user:
        _pun_save_user_minimal(target_user, chat_id=message.chat.id)

    until_date = _pun_until_date(duration)

    try:
        if until_date:
            bot.ban_chat_member(
                message.chat.id,
                target_id,
                until_date=until_date,
                revoke_messages=False
            )
        else:
            bot.ban_chat_member(
                message.chat.id,
                target_id,
                revoke_messages=False
            )

        _pun_add_log(
            chat_id=message.chat.id,
            action="ban",
            moderator_id=message.from_user.id,
            target_id=target_id,
            duration=duration,
            reason=reason
        )

        text = (
            f"🔨 Пользователь забанен\n\n"
            f"👤 Нарушитель: {_pun_get_name_by_id(target_id)}\n"
            f"👮 Модератор: {_pun_get_name_by_id(message.from_user.id)}\n"
            f"⏳ Срок: {_pun_format_duration(duration)}\n"
            f"📝 Причина: {reason or 'не указана'}"
        )

        bot.reply_to(message, text, parse_mode=None)

    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Не удалось забанить пользователя.\n\n"
            f"Причина: {e}\n\n"
            f"Проверь, что бот является администратором и имеет право банить пользователей.",
            parse_mode=None
        )

@bot.message_handler(func=lambda m: bool(m.text) and m.text.strip().lower() == "разбан")
def cmd_unban(message):
    target_id, target_user, duration, reason = _pun_parse_target_duration_reason(message)

    if not _pun_is_group(message):
        bot.reply_to(message, "❌ Эта команда работает только в группе.", parse_mode=None)
        return

    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "🚫 У тебя нет прав администратора.", parse_mode=None)
        return

    if not target_id:
        bot.reply_to(
            message,
            "❌ Не найден пользователь.\n\n"
            "Используй:\n"
            "/unban ID\n"
            "или ответом на сообщение пользователя.",
            parse_mode=None
        )
        return

    try:
        bot.unban_chat_member(message.chat.id, target_id, only_if_banned=True)

        _pun_add_log(
            chat_id=message.chat.id,
            action="unban",
            moderator_id=message.from_user.id,
            target_id=target_id,
            reason=reason
        )

        bot.reply_to(
            message,
            f"✅ Пользователь разбанен\n\n"
            f"👤 Пользователь: {_pun_get_name_by_id(target_id)}\n"
            f"👮 Модератор: {_pun_get_name_by_id(message.from_user.id)}",
            parse_mode=None
        )

    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Не удалось разбанить пользователя.\n\n"
            f"Причина: {e}",
            parse_mode=None
        )

@bot.message_handler(commands=["unban"])
def cmd_unban(message):
    target_id, target_user, duration, reason = _pun_parse_target_duration_reason(message)

    if not _pun_is_group(message):
        bot.reply_to(message, "❌ Эта команда работает только в группе.", parse_mode=None)
        return

    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "🚫 У тебя нет прав администратора.", parse_mode=None)
        return

    if not target_id:
        bot.reply_to(
            message,
            "❌ Не найден пользователь.\n\n"
            "Используй:\n"
            "/unban ID\n"
            "или ответом на сообщение пользователя.",
            parse_mode=None
        )
        return

    try:
        bot.unban_chat_member(message.chat.id, target_id, only_if_banned=True)

        _pun_add_log(
            chat_id=message.chat.id,
            action="unban",
            moderator_id=message.from_user.id,
            target_id=target_id,
            reason=reason
        )

        bot.reply_to(
            message,
            f"✅ Пользователь разбанен\n\n"
            f"👤 Пользователь: {_pun_get_name_by_id(target_id)}\n"
            f"👮 Модератор: {_pun_get_name_by_id(message.from_user.id)}",
            parse_mode=None
        )

    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Не удалось разбанить пользователя.\n\n"
            f"Причина: {e}",
            parse_mode=None
        )
@bot.message_handler(func=lambda m: bool(m.text) and m.text.strip().lower() == "мут")
def cmd_mute(message):
    target_id, target_user, duration, reason = _pun_parse_target_duration_reason(message)

    if duration is None:
        duration = 60 * 60

    if not _pun_check_common(message, target_id):
        return

    if target_user:
        _pun_save_user_minimal(target_user, chat_id=message.chat.id)

    until_date = _pun_until_date(duration)

    try:
        if types:
            permissions = types.ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_manage_topics=False
            )
        else:
            permissions = None

        if until_date:
            bot.restrict_chat_member(
                message.chat.id,
                target_id,
                permissions=permissions,
                until_date=until_date
            )
        else:
            bot.restrict_chat_member(
                message.chat.id,
                target_id,
                permissions=permissions
            )

        _pun_add_log(
            chat_id=message.chat.id,
            action="mute",
            moderator_id=message.from_user.id,
            target_id=target_id,
            duration=duration,
            reason=reason
        )

        bot.reply_to(
            message,
            f"🔇 Пользователь получил мут\n\n"
            f"👤 Нарушитель: {_pun_get_name_by_id(target_id)}\n"
            f"👮 Модератор: {_pun_get_name_by_id(message.from_user.id)}\n"
            f"⏳ Срок: {_pun_format_duration(duration)}\n"
            f"📝 Причина: {reason or 'не указана'}",
            parse_mode=None
        )

    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Не удалось выдать мут.\n\n"
            f"Причина: {e}\n\n"
            f"Проверь, что бот является администратором и имеет право ограничивать пользователей.",
            parse_mode=None
        )

@bot.message_handler(commands=["mute"])
def cmd_mute(message):
    target_id, target_user, duration, reason = _pun_parse_target_duration_reason(message)

    if duration is None:
        duration = 60 * 60

    if not _pun_check_common(message, target_id):
        return

    if target_user:
        _pun_save_user_minimal(target_user, chat_id=message.chat.id)

    until_date = _pun_until_date(duration)

    try:
        if types:
            permissions = types.ChatPermissions(
                can_send_messages=False,
                can_send_audios=False,
                can_send_documents=False,
                can_send_photos=False,
                can_send_videos=False,
                can_send_video_notes=False,
                can_send_voice_notes=False,
                can_send_polls=False,
                can_send_other_messages=False,
                can_add_web_page_previews=False,
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_manage_topics=False
            )
        else:
            permissions = None

        if until_date:
            bot.restrict_chat_member(
                message.chat.id,
                target_id,
                permissions=permissions,
                until_date=until_date
            )
        else:
            bot.restrict_chat_member(
                message.chat.id,
                target_id,
                permissions=permissions
            )

        _pun_add_log(
            chat_id=message.chat.id,
            action="mute",
            moderator_id=message.from_user.id,
            target_id=target_id,
            duration=duration,
            reason=reason
        )

        bot.reply_to(
            message,
            f"🔇 Пользователь получил мут\n\n"
            f"👤 Нарушитель: {_pun_get_name_by_id(target_id)}\n"
            f"👮 Модератор: {_pun_get_name_by_id(message.from_user.id)}\n"
            f"⏳ Срок: {_pun_format_duration(duration)}\n"
            f"📝 Причина: {reason or 'не указана'}",
            parse_mode=None
        )

    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Не удалось выдать мут.\n\n"
            f"Причина: {e}\n\n"
            f"Проверь, что бот является администратором и имеет право ограничивать пользователей.",
            parse_mode=None
        )

@bot.message_handler(func=lambda m: bool(m.text) and m.text.strip().lower() == "размут")
def cmd_unmute(message):
    target_id, target_user, duration, reason = _pun_parse_target_duration_reason(message)

    if not _pun_is_group(message):
        bot.reply_to(message, "❌ Эта команда работает только в группе.", parse_mode=None)
        return

    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "🚫 У тебя нет прав администратора.", parse_mode=None)
        return

    if not target_id:
        bot.reply_to(
            message,
            "❌ Не найден пользователь.\n\n"
            "Используй команду ответом на сообщение или так:\n"
            "/unmute @username",
            parse_mode=None
        )
        return

    try:
        if types:
            permissions = types.ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_invite_users=True
            )
        else:
            permissions = None

        bot.restrict_chat_member(
            message.chat.id,
            target_id,
            permissions=permissions
        )

        _pun_add_log(
            chat_id=message.chat.id,
            action="unmute",
            moderator_id=message.from_user.id,
            target_id=target_id,
            reason=reason
        )

        bot.reply_to(
            message,
            f"🔊 Пользователь размучен\n\n"
            f"👤 Пользователь: {_pun_get_name_by_id(target_id)}\n"
            f"👮 Модератор: {_pun_get_name_by_id(message.from_user.id)}",
            parse_mode=None
        )

    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Не удалось снять мут.\n\n"
            f"Причина: {e}",
            parse_mode=None
        )

@bot.message_handler(commands=["unmute"])
def cmd_unmute(message):
    target_id, target_user, duration, reason = _pun_parse_target_duration_reason(message)

    if not _pun_is_group(message):
        bot.reply_to(message, "❌ Эта команда работает только в группе.", parse_mode=None)
        return

    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "🚫 У тебя нет прав администратора.", parse_mode=None)
        return

    if not target_id:
        bot.reply_to(
            message,
            "❌ Не найден пользователь.\n\n"
            "Используй команду ответом на сообщение или так:\n"
            "/unmute @username",
            parse_mode=None
        )
        return

    try:
        if types:
            permissions = types.ChatPermissions(
                can_send_messages=True,
                can_send_audios=True,
                can_send_documents=True,
                can_send_photos=True,
                can_send_videos=True,
                can_send_video_notes=True,
                can_send_voice_notes=True,
                can_send_polls=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_invite_users=True
            )
        else:
            permissions = None

        bot.restrict_chat_member(
            message.chat.id,
            target_id,
            permissions=permissions
        )

        _pun_add_log(
            chat_id=message.chat.id,
            action="unmute",
            moderator_id=message.from_user.id,
            target_id=target_id,
            reason=reason
        )

        bot.reply_to(
            message,
            f"🔊 Пользователь размучен\n\n"
            f"👤 Пользователь: {_pun_get_name_by_id(target_id)}\n"
            f"👮 Модератор: {_pun_get_name_by_id(message.from_user.id)}",
            parse_mode=None
        )

    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Не удалось снять мут.\n\n"
            f"Причина: {e}",
            parse_mode=None
        )

@bot.message_handler(func=lambda m: bool(m.text) and m.text.strip().lower() == "варн")
def cmd_warn_system(message):
    cmd, args_text = _wr_get_cmd_and_args(message)

    if not _wr_check_admin_command(message):
        return

    _wr_cleanup_expired_warns(message.chat.id)
    _wr_save_user(message.from_user, chat_id=message.chat.id)

    target_id, target_user, duration, reason = _wr_parse_warn_target_duration_reason(message, args_text)

    if not _wr_check_target(message, target_id):
        return

    if target_user:
        _wr_save_user(target_user, chat_id=message.chat.id)

    if not reason:
        reason = "не указана"

    warn_id = _wr_add_warn(
        chat_id=message.chat.id,
        target_id=target_id,
        moderator_id=message.from_user.id,
        reason=reason,
        duration=duration,
        message_id=message.message_id
    )

    active_warns = _wr_get_active_warns(message.chat.id, target_id)
    expires_text = "никогда ♾️"

    if duration is not None and int(duration) > 0:
        expires_text = _wr_format_time(_wr_now() + int(duration))

    bot.reply_to(
        message,
        f"⚠️ Пользователь получил предупреждение\n\n"
        f"👤 Пользователь: {_wr_get_name(target_id)}\n"
        f"👮 Админ: {_wr_get_name(message.from_user.id)}\n"
        f"📝 Причина: {reason}\n"
        f"⏳ Срок: {_wr_format_duration(duration)}\n"
        f"🕒 Пропадёт: {expires_text}\n"
        f"📊 Всего активных варнов: {len(active_warns)}\n"
        f"🆔 ID варна: {warn_id}",
        parse_mode=None
    )


def _wr_parse_unwarn_target(message, args_text):
    args = args_text.split() if args_text else []

    target_id = None
    target_user = None
    remove_all = False
    reason = ""

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        target_id = int(target_user.id)

        if args and args[0].lower() in ("all", "все", "всё"):
            remove_all = True
            reason = " ".join(args[1:]).strip()
        else:
            reason = " ".join(args).strip()

        return target_id, target_user, remove_all, reason

    if not args:
        return None, None, False, ""

    target_id = _wr_find_user_id_by_arg(args[0])
    rest = args[1:]

    if rest and rest[0].lower() in ("all", "все", "всё"):
        remove_all = True
        reason = " ".join(rest[1:]).strip()
    else:
        reason = " ".join(rest).strip()

    return target_id, target_user, remove_all, reason


@bot.message_handler(func=lambda message: _wr_get_cmd_and_args(message)[0] == "warn")
def cmd_warn_system(message):
    cmd, args_text = _wr_get_cmd_and_args(message)

    if not _wr_check_admin_command(message):
        return

    _wr_cleanup_expired_warns(message.chat.id)
    _wr_save_user(message.from_user, chat_id=message.chat.id)

    target_id, target_user, duration, reason = _wr_parse_warn_target_duration_reason(message, args_text)

    if not _wr_check_target(message, target_id):
        return

    if target_user:
        _wr_save_user(target_user, chat_id=message.chat.id)

    if not reason:
        reason = "не указана"

    warn_id = _wr_add_warn(
        chat_id=message.chat.id,
        target_id=target_id,
        moderator_id=message.from_user.id,
        reason=reason,
        duration=duration,
        message_id=message.message_id
    )

    active_warns = _wr_get_active_warns(message.chat.id, target_id)
    expires_text = "никогда ♾️"

    if duration is not None and int(duration) > 0:
        expires_text = _wr_format_time(_wr_now() + int(duration))

    bot.reply_to(
        message,
        f"⚠️ Пользователь получил предупреждение\n\n"
        f"👤 Пользователь: {_wr_get_name(target_id)}\n"
        f"👮 Админ: {_wr_get_name(message.from_user.id)}\n"
        f"📝 Причина: {reason}\n"
        f"⏳ Срок: {_wr_format_duration(duration)}\n"
        f"🕒 Пропадёт: {expires_text}\n"
        f"📊 Всего активных варнов: {len(active_warns)}\n"
        f"🆔 ID варна: {warn_id}",
        parse_mode=None
    )


def _wr_parse_unwarn_target(message, args_text):
    args = args_text.split() if args_text else []

    target_id = None
    target_user = None
    remove_all = False
    reason = ""

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        target_id = int(target_user.id)

        if args and args[0].lower() in ("all", "все", "всё"):
            remove_all = True
            reason = " ".join(args[1:]).strip()
        else:
            reason = " ".join(args).strip()

        return target_id, target_user, remove_all, reason

    if not args:
        return None, None, False, ""

    target_id = _wr_find_user_id_by_arg(args[0])
    rest = args[1:]

    if rest and rest[0].lower() in ("all", "все", "всё"):
        remove_all = True
        reason = " ".join(rest[1:]).strip()
    else:
        reason = " ".join(rest).strip()

    return target_id, target_user, remove_all, reason

@bot.message_handler(func=lambda m: _wr_text_starts_with_any(m, ("разварн", "-варн", "снять варн", "анварн")))
def cmd_unwarn_system(message):
    cmd, args_text = _wr_get_cmd_and_args(message)

    if not _wr_check_admin_command(message):
        return

    _wr_cleanup_expired_warns(message.chat.id)
    _wr_save_user(message.from_user, chat_id=message.chat.id)

    target_id, target_user, remove_all, reason = _wr_parse_unwarn_target(message, args_text)

    if not target_id:
        bot.reply_to(
            message,
            "❌ Пользователь не найден.\n\n"
            "Используй команду ответом на сообщение или так:\n"
            "/unwarn @username\n"
            "-варн @username",
            parse_mode=None
        )
        return

    if target_user:
        _wr_save_user(target_user, chat_id=message.chat.id)

    chat_warns = _wr_warns_storage(message.chat.id)
    user_warns = chat_warns.setdefault(str(target_id), [])

    active_warns = _wr_get_active_warns(message.chat.id, target_id)

    if not active_warns:
        bot.reply_to(
            message,
            f"✅ У пользователя нет активных варнов.\n\n"
            f"👤 Пользователь: {_wr_get_name(target_id)}",
            parse_mode=None
        )
        return

    removed_count = 0

    if remove_all:
        remove_ids = set(w.get("id") for w in active_warns)
    else:
        latest_warn = sorted(active_warns, key=lambda w: int(w.get("time", 0)), reverse=True)[0]
        remove_ids = {latest_warn.get("id")}

    new_warns = []

    for w in user_warns:
        if isinstance(w, dict) and w.get("id") in remove_ids:
            removed_count += 1
            continue

        new_warns.append(w)

    chat_warns[str(target_id)] = new_warns

    _wr_save()

    left_warns = _wr_get_active_warns(message.chat.id, target_id)

    bot.reply_to(
        message,
        f"✅ Варн снят\n\n"
        f"👤 Пользователь: {_wr_get_name(target_id)}\n"
        f"👮 Админ: {_wr_get_name(message.from_user.id)}\n"
        f"🗑️ Снято варнов: {removed_count}\n"
        f"📊 Осталось активных варнов: {len(left_warns)}\n"
        f"📝 Причина снятия: {reason or 'не указана'}",
        parse_mode=None
    )

@bot.message_handler(func=_wr_is_unwarn_cmd)
def cmd_unwarn_system(message):
    cmd, args_text = _wr_get_cmd_and_args(message)

    if not _wr_check_admin_command(message):
        return

    _wr_cleanup_expired_warns(message.chat.id)
    _wr_save_user(message.from_user, chat_id=message.chat.id)

    target_id, target_user, remove_all, reason = _wr_parse_unwarn_target(message, args_text)

    if not target_id:
        bot.reply_to(
            message,
            "❌ Пользователь не найден.\n\n"
            "Используй команду ответом на сообщение или так:\n"
            "/unwarn @username\n"
            "-варн @username",
            parse_mode=None
        )
        return

    if target_user:
        _wr_save_user(target_user, chat_id=message.chat.id)

    chat_warns = _wr_warns_storage(message.chat.id)
    user_warns = chat_warns.setdefault(str(target_id), [])

    active_warns = _wr_get_active_warns(message.chat.id, target_id)

    if not active_warns:
        bot.reply_to(
            message,
            f"✅ У пользователя нет активных варнов.\n\n"
            f"👤 Пользователь: {_wr_get_name(target_id)}",
            parse_mode=None
        )
        return

    removed_count = 0

    if remove_all:
        remove_ids = set(w.get("id") for w in active_warns)
    else:
        latest_warn = sorted(active_warns, key=lambda w: int(w.get("time", 0)), reverse=True)[0]
        remove_ids = {latest_warn.get("id")}

    new_warns = []

    for w in user_warns:
        if isinstance(w, dict) and w.get("id") in remove_ids:
            removed_count += 1
            continue

        new_warns.append(w)

    chat_warns[str(target_id)] = new_warns

    _wr_save()

    left_warns = _wr_get_active_warns(message.chat.id, target_id)

    bot.reply_to(
        message,
        f"✅ Варн снят\n\n"
        f"👤 Пользователь: {_wr_get_name(target_id)}\n"
        f"👮 Админ: {_wr_get_name(message.from_user.id)}\n"
        f"🗑️ Снято варнов: {removed_count}\n"
        f"📊 Осталось активных варнов: {len(left_warns)}\n"
        f"📝 Причина снятия: {reason or 'не указана'}",
        parse_mode=None
    )


def _wr_reports_storage(chat_id):
    reports = data.setdefault("reports", {})
    return reports.setdefault(str(chat_id), [])


def _wr_report_cooldowns_storage(chat_id):
    cooldowns = data.setdefault("report_cooldowns", {})
    return cooldowns.setdefault(str(chat_id), {})


def _wr_parse_report_target_reason(message, args_text):
    args = args_text.split() if args_text else []

    target_id = None
    target_user = None
    reason = ""

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user = message.reply_to_message.from_user
        target_id = int(target_user.id)
        reason = args_text.strip()
        return target_id, target_user, reason

    if not args:
        return None, None, ""

    target_id = _wr_find_user_id_by_arg(args[0])
    reason = " ".join(args[1:]).strip()

    return target_id, target_user, reason

@bot.message_handler(func=lambda m: _wr_text_starts_with_any(m, ("репорт", "+репорт", "зарепортить")))
def cmd_report_system(message):
    cmd, args_text = _wr_get_cmd_and_args(message)

    if not _wr_is_group(message):
        bot.reply_to(message, "❌ Репорты работают только в группе.", parse_mode=None)
        return

    _wr_cleanup_expired_warns(message.chat.id)
    _wr_save_user(message.from_user, chat_id=message.chat.id)

    cooldowns = _wr_report_cooldowns_storage(message.chat.id)
    reporter_id = str(message.from_user.id)
    now = _wr_now()
    last_report = int(cooldowns.get(reporter_id, 0) or 0)

    if now - last_report < 120:
        wait = 120 - (now - last_report)
        bot.reply_to(
            message,
            f"⏳ Не так быстро!\n\n"
            f"📨 Репорт можно отправлять раз в 2 минуты.\n"
            f"🕒 Подожди ещё: {wait} сек.",
            parse_mode=None
        )
        return

    target_id, target_user, reason = _wr_parse_report_target_reason(message, args_text)

    if not target_id:
        bot.reply_to(
            message,
            "❌ Пользователь не найден.\n\n"
            "Используй репорт ответом на сообщение:\n"
            "/report причина\n\n"
            "Или так:\n"
            "/report @username причина",
            parse_mode=None
        )
        return

    if int(target_id) == int(message.from_user.id):
        bot.reply_to(message, "🤨 Нельзя пожаловаться на самого себя.", parse_mode=None)
        return

    if target_user:
        _wr_save_user(target_user, chat_id=message.chat.id)

    if not reason:
        bot.reply_to(
            message,
            "❌ Укажи причину репорта.\n\n"
            "Пример:\n"
            "/report оскорбления\n"
            "или:\n"
            "репорт флуд",
            parse_mode=None
        )
        return

    if message.reply_to_message:
        reported_message_id = message.reply_to_message.message_id
    else:
        reported_message_id = message.message_id

    report_link = _wr_message_link(message.chat, reported_message_id)

    reports = _wr_reports_storage(message.chat.id)

    report_id = int(time.time() * 1000)

    reports.append({
        "id": report_id,
        "chat_id": int(message.chat.id),
        "target_id": int(target_id),
        "reporter_id": int(message.from_user.id),
        "reason": reason,
        "time": now,
        "message_id": int(reported_message_id),
        "command_message_id": int(message.message_id),
        "link": report_link or "",
    })

    cooldowns[reporter_id] = now

    _wr_save()

    bot.reply_to(
        message,
        f"📨 Репорт отправлен админам\n\n"
        f"👤 Жалоба на: {_wr_get_name(target_id)}\n"
        f"🙋 Отправил: {_wr_get_name(message.from_user.id)}\n"
        f"📝 Причина: {reason}\n"
        f"🕒 Время: {_wr_format_time(now)}\n"
        f"🆔 ID репорта: {report_id}",
        parse_mode=None
    )


@bot.message_handler(func=_wr_is_report_cmd)
def cmd_report_system(message):
    cmd, args_text = _wr_get_cmd_and_args(message)

    if not _wr_is_group(message):
        bot.reply_to(message, "❌ Репорты работают только в группе.", parse_mode=None)
        return

    _wr_cleanup_expired_warns(message.chat.id)
    _wr_save_user(message.from_user, chat_id=message.chat.id)

    cooldowns = _wr_report_cooldowns_storage(message.chat.id)
    reporter_id = str(message.from_user.id)
    now = _wr_now()
    last_report = int(cooldowns.get(reporter_id, 0) or 0)

    if now - last_report < 120:
        wait = 120 - (now - last_report)
        bot.reply_to(
            message,
            f"⏳ Не так быстро!\n\n"
            f"📨 Репорт можно отправлять раз в 2 минуты.\n"
            f"🕒 Подожди ещё: {wait} сек.",
            parse_mode=None
        )
        return

    target_id, target_user, reason = _wr_parse_report_target_reason(message, args_text)

    if not target_id:
        bot.reply_to(
            message,
            "❌ Пользователь не найден.\n\n"
            "Используй репорт ответом на сообщение:\n"
            "/report причина\n\n"
            "Или так:\n"
            "/report @username причина",
            parse_mode=None
        )
        return

    if int(target_id) == int(message.from_user.id):
        bot.reply_to(message, "🤨 Нельзя пожаловаться на самого себя.", parse_mode=None)
        return

    if target_user:
        _wr_save_user(target_user, chat_id=message.chat.id)

    if not reason:
        bot.reply_to(
            message,
            "❌ Укажи причину репорта.\n\n"
            "Пример:\n"
            "/report оскорбления\n"
            "или:\n"
            "репорт флуд",
            parse_mode=None
        )
        return

    if message.reply_to_message:
        reported_message_id = message.reply_to_message.message_id
    else:
        reported_message_id = message.message_id

    report_link = _wr_message_link(message.chat, reported_message_id)

    reports = _wr_reports_storage(message.chat.id)

    report_id = int(time.time() * 1000)

    reports.append({
        "id": report_id,
        "chat_id": int(message.chat.id),
        "target_id": int(target_id),
        "reporter_id": int(message.from_user.id),
        "reason": reason,
        "time": now,
        "message_id": int(reported_message_id),
        "command_message_id": int(message.message_id),
        "link": report_link or "",
    })

    cooldowns[reporter_id] = now

    _wr_save()

    bot.reply_to(
        message,
        f"📨 Репорт отправлен админам\n\n"
        f"👤 Жалоба на: {_wr_get_name(target_id)}\n"
        f"🙋 Отправил: {_wr_get_name(message.from_user.id)}\n"
        f"📝 Причина: {reason}\n"
        f"🕒 Время: {_wr_format_time(now)}\n"
        f"🆔 ID репорта: {report_id}",
        parse_mode=None
    )


def _wr_split_text(text, limit=3800):
    chunks = []
    current = ""

    for line in text.splitlines(True):
        if len(current) + len(line) > limit:
            if current:
                chunks.append(current)
            current = line
        else:
            current += line

    if current:
        chunks.append(current)

    return chunks

@bot.message_handler(func=lambda m: bool(getattr(m, "text", None)) and _rp_get_command(m.text) is not None)
def cmd_rp_action(message):
    command = _rp_get_command(message.text)

    if not command:
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        bot.reply_to(
            message,
            f"❌ Используй команду ответом на сообщение.\n\n"
            f"Пример: ответь на сообщение и напиши «{command}»",
            parse_mode=None
        )
        return

    cooldown_left = _rp_get_cooldown_left(message.from_user.id)

    if cooldown_left > 0:
        bot.reply_to(
            message,
            f"⏳ Подожди ещё {cooldown_left} сек.",
            parse_mode=None
        )
        return

    actor = message.from_user
    target = message.reply_to_message.from_user

    if getattr(target, "is_bot", False):
        bot.reply_to(
            message,
            "🤖 Ботов трогать нельзя.",
            parse_mode=None
        )
        return

    action = RP_ACTIONS[command]

    actor_link = _rp_get_user_link(actor)
    target_link = _rp_get_user_link(target)

    verb = action["verb"]

    text = f"{action['emoji']} {actor_link} {verb} {target_link}"

    _rp_set_cooldown(actor.id)

    bot.reply_to(
        message,
        text,
        parse_mode="HTML",
        disable_web_page_preview=True
    )

@bot.message_handler(commands=["voice_id"])
def cmd_voice_id(message):
    if not _is_admin_id(message.from_user.id):
        return

    if not message.reply_to_message or not message.reply_to_message.voice:
        bot.reply_to(message, "Ответь командой /voice_id на голосовое сообщение.", parse_mode=None)
        return

    bot.reply_to(
        message,
        f"file_id голосового:\n{message.reply_to_message.voice.file_id}",
        parse_mode=None
    )

@bot.message_handler(commands=["clear_report"])
def cmd_clear_report(message):
    if not _wr_check_admin_command(message):
        return

    parts = (message.text or "").split(maxsplit=1)

    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(
            message,
            "❌ Укажи ID репорта.\n\n"
            "Использование:\n"
            "/clear_report 123456789",
            parse_mode=None
        )
        return

    report_id_arg = parts[1].strip()

    if not report_id_arg.isdigit():
        bot.reply_to(
            message,
            "❌ ID репорта должен быть числом.\n\n"
            "Пример:\n"
            "/clear_report 123456789",
            parse_mode=None
        )
        return

    report_id = int(report_id_arg)

    reports = _wr_reports_storage(message.chat.id)

    if not reports:
        bot.reply_to(message, "📭 В этом чате пока нет репортов.", parse_mode=None)
        return

    removed_report = None
    new_reports = []

    for r in reports:
        if isinstance(r, dict) and int(r.get("id", 0) or 0) == report_id:
            removed_report = r
            continue

        new_reports.append(r)

    if removed_report is None:
        bot.reply_to(
            message,
            f"❌ Репорт с ID {report_id} не найден в этом чате.",
            parse_mode=None
        )
        return

    data.setdefault("reports", {})[str(message.chat.id)] = new_reports
    _wr_save()

    target_id = removed_report.get("target_id")
    reporter_id = removed_report.get("reporter_id")
    reason = removed_report.get("reason") or "не указана"
    created_at = removed_report.get("time")

    bot.reply_to(
        message,
        f"✅ Репорт удалён\n\n"
        f"🆔 ID репорта: {report_id}\n"
        f"👤 Жалоба была на: {_wr_get_name(target_id)}\n"
        f"🙋 Отправил: {_wr_get_name(reporter_id)}\n"
        f"📝 Причина: {reason}\n"
        f"🕒 Был создан: {_wr_format_time(created_at)}\n"
        f"👮 Удалил: {_wr_get_name(message.from_user.id)}",
        parse_mode=None
    )

@bot.message_handler(commands=["warn_list"])
def cmd_warn_list(message):
    if not _wr_check_admin_command(message):
        return

    _wr_cleanup_expired_warns(message.chat.id)

    chat_warns = _wr_warns_storage(message.chat.id)

    rows = []

    for uid_str, warns in chat_warns.items():
        if not isinstance(warns, list):
            continue

        active_warns = _wr_get_active_warns(message.chat.id, uid_str)

        for warn in active_warns:
            if not isinstance(warn, dict):
                continue

            rows.append((uid_str, warn))

    if not rows:
        bot.reply_to(message, "✅ В этом чате нет активных варнов.", parse_mode=None)
        return

    rows.sort(key=lambda x: _safe_int(x[1].get("time", 0), 0), reverse=True)

    text = f"⚠️ Активные варны чата\nВсего: {len(rows)}\n\n"

    for index, item in enumerate(rows, start=1):
        uid = item[0]
        warn = item[1]

        reason = warn.get("reason") or "не указана"
        moderator_id = warn.get("moderator_id")
        created_at = warn.get("time")
        expires_at = warn.get("expires_at")
        warn_id = warn.get("id", "без id")

        if expires_at:
            expires_text = _wr_format_time(expires_at)
        else:
            expires_text = "никогда ♾️"

        text += (
            f"#{index}\n"
            f"🆔 ID варна: {warn_id}\n"
            f"👤 Пользователь: {_wr_get_name(uid)}\n"
            f"👮 Выдал: {_wr_get_name(moderator_id)}\n"
            f"📝 Причина: {reason}\n"
            f"🕒 Выдан: {_wr_format_time(created_at)}\n"
            f"⏳ Истекает: {expires_text}\n\n"
        )

    _list_split_send(message.chat.id, text, reply_to_message_id=message.message_id)


@bot.message_handler(commands=["mute_list"])
def cmd_mute_list(message):
    if not _wr_check_admin_command(message):
        return

    records = _pun_get_active_records(message.chat.id, "mute")

    if not records:
        bot.reply_to(message, "✅ В этом чате нет активных мутов.", parse_mode=None)
        return

    text = f"🔇 Активные муты чата\nВсего: {len(records)}\n\n"

    for index, record in enumerate(records, start=1):
        target_id = record.get("target_id")
        moderator_id = record.get("moderator_id")
        reason = record.get("reason") or "не указана"
        duration = record.get("duration")
        created_at = record.get("time")
        expires_at = _pun_expires_at(record)

        if expires_at:
            expires_text = _wr_format_time(expires_at)
        else:
            expires_text = "никогда ♾️"

        text += (
            f"#{index}\n"
            f"👤 Пользователь: {_pun_get_name_by_id(target_id)}\n"
            f"👮 Модератор: {_pun_get_name_by_id(moderator_id)}\n"
            f"⏳ Срок: {_pun_format_duration(duration)}\n"
            f"📝 Причина: {reason}\n"
            f"🕒 Выдан: {_wr_format_time(created_at)}\n"
            f"⏰ Истекает: {expires_text}\n\n"
        )

    _list_split_send(message.chat.id, text, reply_to_message_id=message.message_id)


@bot.message_handler(commands=["ban_list"])
def cmd_ban_list(message):
    if not _wr_check_admin_command(message):
        return

    records = _pun_get_active_records(message.chat.id, "ban")

    if not records:
        bot.reply_to(message, "✅ В этом чате нет активных банов.", parse_mode=None)
        return

    text = f"🔨 Активные баны чата\nВсего: {len(records)}\n\n"

    for index, record in enumerate(records, start=1):
        target_id = record.get("target_id")
        moderator_id = record.get("moderator_id")
        reason = record.get("reason") or "не указана"
        duration = record.get("duration")
        created_at = record.get("time")
        expires_at = _pun_expires_at(record)

        if expires_at:
            expires_text = _wr_format_time(expires_at)
        else:
            expires_text = "никогда ♾️"

        text += (
            f"#{index}\n"
            f"👤 Пользователь: {_pun_get_name_by_id(target_id)}\n"
            f"👮 Модератор: {_pun_get_name_by_id(moderator_id)}\n"
            f"⏳ Срок: {_pun_format_duration(duration)}\n"
            f"📝 Причина: {reason}\n"
            f"🕒 Выдан: {_wr_format_time(created_at)}\n"
            f"⏰ Истекает: {expires_text}\n\n"
        )

    _list_split_send(message.chat.id, text, reply_to_message_id=message.message_id)

@bot.message_handler(func=lambda m: _wr_text_starts_with_any(m, ("репорты", "репортыы", "все репорты")))
def cmd_reports_system(message):
    cmd, args_text = _wr_get_cmd_and_args(message)

    if not _wr_check_admin_command(message):
        return

    reports = _wr_reports_storage(message.chat.id)

    if not reports:
        bot.reply_to(message, "📭 В этом чате пока нет репортов.", parse_mode=None)
        return

    text = f"📋 Репорты чата\n📨 Всего: {len(reports)}\n\n"

    for i, r in enumerate(reports, start=1):
        if not isinstance(r, dict):
            continue

        target_id = r.get("target_id")
        reporter_id = r.get("reporter_id")
        reason = r.get("reason") or "не указана"
        created_at = r.get("time")
        link = r.get("link") or ""

        if not link and r.get("message_id"):
            link = _wr_message_link(message.chat, r.get("message_id")) or ""

        text += (
            f"#{i} 🆔 {r.get('id', 'без id')}\n"
            f"👤 Жалоба на: {_wr_get_name(target_id)}\n"
            f"🙋 Отправил: {_wr_get_name(reporter_id)}\n"
            f"📝 Причина: {reason}\n"
            f"🕒 Когда: {_wr_format_time(created_at)}\n"
        )

        if link:
            text += f"🔗 Сообщение: {link}\n\n"
        else:
            text += f"🔗 Сообщение: ссылка недоступна\n\n"

    chunks = _wr_split_text(text)

    for chunk in chunks:
        bot.send_message(message.chat.id, chunk, parse_mode=None)

@bot.message_handler(func=_wr_is_reports_cmd)
def cmd_reports_system(message):
    cmd, args_text = _wr_get_cmd_and_args(message)

    if not _wr_check_admin_command(message):
        return

    reports = _wr_reports_storage(message.chat.id)

    if not reports:
        bot.reply_to(message, "📭 В этом чате пока нет репортов.", parse_mode=None)
        return

    text = f"📋 Репорты чата\n📨 Всего: {len(reports)}\n\n"

    for i, r in enumerate(reports, start=1):
        if not isinstance(r, dict):
            continue

        target_id = r.get("target_id")
        reporter_id = r.get("reporter_id")
        reason = r.get("reason") or "не указана"
        created_at = r.get("time")
        link = r.get("link") or ""

        if not link and r.get("message_id"):
            link = _wr_message_link(message.chat, r.get("message_id")) or ""

        text += (
            f"#{i} 🆔 {r.get('id', 'без id')}\n"
            f"👤 Жалоба на: {_wr_get_name(target_id)}\n"
            f"🙋 Отправил: {_wr_get_name(reporter_id)}\n"
            f"📝 Причина: {reason}\n"
            f"🕒 Когда: {_wr_format_time(created_at)}\n"
        )

        if link:
            text += f"🔗 Сообщение: {link}\n\n"
        else:
            text += f"🔗 Сообщение: ссылка недоступна\n\n"

    chunks = _wr_split_text(text)

    for chunk in chunks:
        bot.send_message(message.chat.id, chunk, parse_mode=None)

@bot.message_handler(commands=["import_iris_top2", "iris_import2"])
def cmd_import_iris_top2(message):
    if not is_group(message.chat):
        bot.reply_to(message, "❌ Импорт доступен только в группе.", parse_mode=None)
        return

    if ADMIN_ID and message.from_user.id not in ADMIN_ID:
        bot.reply_to(message, "❌ Импортировать топ может только администратор чата.", parse_mode=None)
        return

    if not message.reply_to_message:
        bot.reply_to(
            message,
            "❌ Ответьте этой командой на сообщение Iris с топом.\n\n"
            "Пример:\n"
            "1. Напишите Iris: топ\n"
            "2. Ответьте на сообщение Iris: /import_iris_top\n\n"
            "Для топа за всё время:\n"
            "1. Напишите Iris: топ вся\n"
            "2. Ответьте на сообщение Iris: /import_iris_top",
            parse_mode=None
        )
        return

    reply_msg = message.reply_to_message
    iris_text = getattr(reply_msg, "text", None) or getattr(reply_msg, "caption", None) or ""

    if not iris_text:
        bot.reply_to(message, "❌ В сообщении Iris нет текста для импорта.", parse_mode=None)
        return

    parts = (message.text or "").split(maxsplit=1)
    forced_type = None

    if len(parts) > 1:
        arg = parts[1].strip().lower()

        if arg in ("today", "day", "день", "сегодня", "top", "топ"):
            forced_type = "today"

        elif arg in ("all", "вся", "все", "всё", "top_all", "alltime", "топвся"):
            forced_type = "all"

    top_type = forced_type or _detect_iris_top_type(iris_text)

    if top_type is None:
        bot.reply_to(
            message,
            "❌ Не смог понять, это топ за сегодня или за всё время.\n\n"
            "Ответьте на сообщение Iris так:\n"
            "/import_iris_top today — импорт топа за сегодня\n"
            "/import_iris_top all — импорт топа за всё время",
            parse_mode=None
        )
        return

    rows = parse_iris_top_message(reply_msg)

    if not rows:
        debug_entities = getattr(reply_msg, "entities", None) or getattr(reply_msg, "caption_entities", None) or []

        bot.reply_to(
            message,
            "❌ Не удалось найти пользователей и количество сообщений в топе Iris.\n\n"
            f"Найдено entities в сообщении: {len(debug_entities)}\n\n"
            "Что можно сделать:\n"
            "1. Ответьте именно на сообщение Iris с топом, не пересылайте его.\n"
            "2. Попробуйте команду явно:\n"
            "/import_iris_top today\n"
            "или\n"
            "/import_iris_top all\n"
            "3. Если в топе Iris нет кликабельных пользователей и нет @username, мой бот сможет найти только тех, кто уже писал в чат и есть в базе.",
            parse_mode=None
        )
        return

    chat = ensure_chat(message.chat.id)

    imported = 0
    skipped = 0

    if top_type == "today":
        day = _today()
        daily = chat.setdefault("msg_count_daily", {}).setdefault(day, {})

        for uid, count in rows:
            if uid <= 0 or count <= 0:
                skipped += 1
                continue

            daily[str(uid)] = int(count)

            try:
                u = ensure_user(uid)
                u["msg_day"] = day
                u["msg_today"] = int(count)
            except Exception:
                pass

            imported += 1

        save_data()

        bot.reply_to(
            message,
            f"✅ Импорт топа Iris за сегодня завершён.\n"
            f"📥 Импортировано строк: {imported}\n"
            f"⏭️ Пропущено: {skipped}\n\n"
            f"Теперь /top будет показывать статистику этого чата.",
            parse_mode=None
        )
        return

    if top_type == "all":
        all_counts = chat.setdefault("msg_count_all", {})

        for uid, count in rows:
            if uid <= 0 or count <= 0:
                skipped += 1
                continue

            all_counts[str(uid)] = int(count)

            try:
                u = ensure_user(uid)
                u["msg_total"] = max(_to_int(u.get("msg_total", 0), 0), int(count))
            except Exception:
                pass

            imported += 1

        save_data()

        bot.reply_to(
            message,
            f"✅ Импорт топа Iris за всё время завершён.\n"
            f"📥 Импортировано строк: {imported}\n"
            f"⏭️ Пропущено: {skipped}\n\n"
            f"Теперь /top_all будет показывать статистику этого чата.",
            parse_mode=None
        )
        return

@bot.message_handler(commands=["import_iris_top", "iris_import"])
def cmd_import_iris_top(message):
    if not is_group(message.chat):
        bot.reply_to(message, "❌ Импорт доступен только в группе.", parse_mode=None)
        return

    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "❌ Импортировать топ может только администратор чата.", parse_mode=None)
        return

    if not message.reply_to_message:
        bot.reply_to(
            message,
            "❌ Ответьте этой командой на сообщение Iris с топом.\n\n"
            "Пример:\n"
            "1. Напишите Iris: топ\n"
            "2. Ответьте на сообщение Iris: /import_iris_top\n\n"
            "Для топа за всё время:\n"
            "1. Напишите Iris: топ вся\n"
            "2. Ответьте на сообщение Iris: /import_iris_top",
            parse_mode=None
        )
        return

    reply_msg = message.reply_to_message
    iris_text = getattr(reply_msg, "text", None) or getattr(reply_msg, "caption", None) or ""

    if not iris_text:
        bot.reply_to(message, "❌ В сообщении Iris нет текста для импорта.", parse_mode=None)
        return

    parts = (message.text or "").split(maxsplit=1)
    forced_type = None

    if len(parts) > 1:
        arg = parts[1].strip().lower()

        if arg in ("today", "day", "день", "сегодня", "top", "топ"):
            forced_type = "today"

        elif arg in ("all", "вся", "все", "всё", "top_all", "alltime", "топвся"):
            forced_type = "all"

    top_type = forced_type or _detect_iris_top_type(iris_text)

    if top_type is None:
        bot.reply_to(
            message,
            "❌ Не смог понять, это топ за сегодня или за всё время.\n\n"
            "Ответьте на сообщение Iris так:\n"
            "/import_iris_top today — импорт топа за сегодня\n"
            "/import_iris_top all — импорт топа за всё время",
            parse_mode=None
        )
        return

    rows = parse_iris_top_message(reply_msg)

    if not rows:
        debug_entities = getattr(reply_msg, "entities", None) or getattr(reply_msg, "caption_entities", None) or []

        bot.reply_to(
            message,
            "❌ Не удалось найти пользователей и количество сообщений в топе Iris.\n\n"
            f"Найдено entities в сообщении: {len(debug_entities)}\n\n"
            "Что можно сделать:\n"
            "1. Ответьте именно на сообщение Iris с топом, не пересылайте его.\n"
            "2. Попробуйте команду явно:\n"
            "/import_iris_top today\n"
            "или\n"
            "/import_iris_top all\n"
            "3. Если в топе Iris нет кликабельных пользователей и нет @username, мой бот сможет найти только тех, кто уже писал в чат и есть в базе.",
            parse_mode=None
        )
        return

    chat = ensure_chat(message.chat.id)

    imported = 0
    skipped = 0

    if top_type == "today":
        day = _today()
        daily = chat.setdefault("msg_count_daily", {}).setdefault(day, {})

        for uid, count in rows:
            if uid <= 0 or count <= 0:
                skipped += 1
                continue

            daily[str(uid)] = int(count)

            try:
                u = ensure_user(uid)
                u["msg_day"] = day
                u["msg_today"] = int(count)
            except Exception:
                pass

            imported += 1

        save_data()

        bot.reply_to(
            message,
            f"✅ Импорт топа Iris за сегодня завершён.\n"
            f"📥 Импортировано строк: {imported}\n"
            f"⏭️ Пропущено: {skipped}\n\n"
            f"Теперь /top будет показывать статистику этого чата.",
            parse_mode=None
        )
        return

    if top_type == "all":
        all_counts = chat.setdefault("msg_count_all", {})

        for uid, count in rows:
            if uid <= 0 or count <= 0:
                skipped += 1
                continue

            all_counts[str(uid)] = int(count)

            try:
                u = ensure_user(uid)
                u["msg_total"] = max(_to_int(u.get("msg_total", 0), 0), int(count))
            except Exception:
                pass

            imported += 1

        save_data()

        bot.reply_to(
            message,
            f"✅ Импорт топа Iris за всё время завершён.\n"
            f"📥 Импортировано строк: {imported}\n"
            f"⏭️ Пропущено: {skipped}\n\n"
            f"Теперь /top_all будет показывать статистику этого чата.",
            parse_mode=None
        )
        return


@bot.message_handler(commands=["award"])
def cmd_award(message):
    if not is_group(message.chat):
        bot.reply_to(message, "Команда доступна только в группе.", parse_mode=None)
        return

    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "Награды могут выдавать только администраторы.", parse_mode=None)
        return

    if not message.reply_to_message or not message.reply_to_message.from_user:
        bot.reply_to(message, "Ответьте на сообщение пользователя командой /award 🏆 Название | заметка", parse_mode=None)
        return

    target = message.reply_to_message.from_user
    ensure_user(target.id, target)

    text = (message.text or "").split(maxsplit=1)
    if len(text) < 2:
        bot.reply_to(message, "Укажите награду: /award 🏆 Чемпион | за победу", parse_mode=None)
        return

    raw = text[1].strip()
    note = ""

    if "|" in raw:
        raw, note = raw.split("|", 1)
        raw = raw.strip()
        note = note.strip()

    parts = raw.split(maxsplit=1)
    icon = ""
    title = raw

    if len(parts) == 2 and any(ord(ch) > 127 for ch in parts[0]) and len(parts[0]) <= 4:
        icon = parts[0]
        title = parts[1]

    if not title:
        bot.reply_to(message, "Название награды пустое.", parse_mode=None)
        return

    u = ensure_user(target.id)
    awards = u.setdefault("awards_by_chat", {}).setdefault(str(message.chat.id), [])
    awards.append({
        "id": uuid.uuid4().hex[:8],
        "icon": icon,
        "title": title[:100],
        "note": note[:200],
        "given_by": message.from_user.id,
        "given_at": int(time.time()),
    })

    save_data()
    bot.reply_to(message, f"✅ Награда выдана: {icon + ' ' if icon else ''}{tg_escape_html(title)}")


@bot.message_handler(commands=["awards"])
def cmd_awards(message):
    if message.reply_to_message and message.reply_to_message.from_user:
        uid = message.reply_to_message.from_user.id
        ensure_user(uid, message.reply_to_message.from_user)
    else:
        uid = message.from_user.id
        ensure_user(uid, message.from_user)

    text = award_text(message.chat.id, uid)

    if not text:
        bot.reply_to(message, "Наград нет.", parse_mode=None)
    else:
        bot.reply_to(message, text)


@bot.message_handler(commands=["off_chat"])
def cmd_off_chat(message):
    if not is_group(message.chat):
        bot.reply_to(message, "Команда доступна только в группе.", parse_mode=None)
        return

    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "Команда доступна только администраторам.", parse_mode=None)
        return

    if not bot_can_manage(message.chat.id):
        bot.reply_to(message, "Мне нужны права администратора с возможностью ограничивать участников.", parse_mode=None)
        return

    try:
        bot.set_chat_permissions(message.chat.id, make_closed_permissions())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", parse_mode=None)
        return

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🔓 Открыть чат", callback_data=OPEN_CHAT_CB))
    bot.reply_to(message, "🔒 Чат закрыт.", reply_markup=kb, parse_mode=None)


@bot.message_handler(commands=["on_chat"])
def cmd_on_chat(message):
    if not is_group(message.chat):
        bot.reply_to(message, "Команда доступна только в группе.", parse_mode=None)
        return

    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "Команда доступна только администраторам.", parse_mode=None)
        return

    if not bot_can_manage(message.chat.id):
        bot.reply_to(message, "Мне нужны права администратора.", parse_mode=None)
        return

    try:
        bot.set_chat_permissions(message.chat.id, make_open_permissions())
    except Exception as e:
        bot.reply_to(message, f"Ошибка: {e}", parse_mode=None)
        return

    bot.reply_to(message, "🔓 Чат открыт.", parse_mode=None)


@bot.callback_query_handler(func=lambda c: c.data == OPEN_CHAT_CB)
def cb_open_chat(call):
    if not is_admin(call.message.chat.id, call.from_user.id):
        bot.answer_callback_query(call.id, "Только администраторы.")
        return

    if not bot_can_manage(call.message.chat.id):
        bot.answer_callback_query(call.id, "Нет прав у бота.", show_alert=True)
        return

    try:
        bot.set_chat_permissions(call.message.chat.id, make_open_permissions())
    except Exception as e:
        bot.answer_callback_query(call.id, f"Ошибка: {e}", show_alert=True)
        return

    try:
        bot.edit_message_text("🔓 Чат открыт.", call.message.chat.id, call.message.message_id, parse_mode=None)
    except Exception:
        bot.send_message(call.message.chat.id, "🔓 Чат открыт.", parse_mode=None)

    bot.answer_callback_query(call.id, "Готово")


@bot.message_handler(func=lambda m: bool(m.text) and (m.text.lower().startswith("-смс") or m.text.lower().startswith("смс ")))
def cmd_delete_messages(message):
    if not is_group(message.chat):
        bot.reply_to(message, "Команда доступна только в группе.", parse_mode=None)
        return

    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "Удалять сообщения могут только администраторы.", parse_mode=None)
        return

    parts = (message.text or "").split()

    if len(parts) < 2:
        bot.reply_to(message, "Использование: -смс 10", parse_mode=None)
        return

    count = _to_int(parts[1], -1)

    if count <= 0:
        bot.reply_to(message, "Количество должно быть положительным.", parse_mode=None)
        return

    c = ensure_chat(message.chat.id)
    hist = list(c.get("history", []))

    if hist and hist[-1] == message.message_id:
        hist.pop()

    deleted = 0

    for mid in reversed(hist[-count:]):
        try:
            bot.delete_message(message.chat.id, mid)
            deleted += 1
        except Exception:
            pass

    try:
        bot.delete_message(message.chat.id, message.message_id)
    except Exception:
        pass

    bot.send_message(message.chat.id, f"Удалено сообщений: {deleted}.", parse_mode=None)

@bot.message_handler(commands=["call_everyone"])
def cmd_call_all(message):
    if not is_group(message.chat):
        bot.reply_to(message, "Команда доступна только в группе.", parse_mode=None)
        return

    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "Команда доступна только администраторам.", parse_mode=None)
        return

    c = ensure_chat(message.chat.id)
    users = c.get("known_users", [])

    if not users:
        bot.reply_to(message, "Я пока не знаю участников.", parse_mode=None)
        return

    mentions = []
    for uid in users:
        u = data.get("users", {}).get(str(uid), {})
        mentions.append(mention_by_id(uid, user_display_from_data(u)))

    text = "Призыв всех:\n" + " ".join(mentions)
    send_long_message(message.chat.id, text)


@bot.message_handler(func=lambda m: bool(m.text) and m.text.strip().lower() == "призвать всех")
def cmd_call_all(message):
    if not is_group(message.chat):
        bot.reply_to(message, "Команда доступна только в группе.", parse_mode=None)
        return

    if not is_admin(message.chat.id, message.from_user.id):
        bot.reply_to(message, "Команда доступна только администраторам.", parse_mode=None)
        return

    c = ensure_chat(message.chat.id)
    users = c.get("known_users", [])

    if not users:
        bot.reply_to(message, "Я пока не знаю участников.", parse_mode=None)
        return

    mentions = []
    for uid in users:
        u = data.get("users", {}).get(str(uid), {})
        mentions.append(mention_by_id(uid, user_display_from_data(u)))

    text = "Призыв всех:\n" + " ".join(mentions)
    send_long_message(message.chat.id, text)

def _warning_get_recipients_all():
    recipients = set()

    try:
        for uid in data.get("users", {}).keys():
            uid_str = str(uid)

            if uid_str.lstrip("-").isdigit():
                recipients.add(int(uid_str))
    except Exception:
        pass

    try:
        for chat_id in data.get("chats", {}).keys():
            chat_id_str = str(chat_id)

            if chat_id_str.lstrip("-").isdigit():
                recipients.add(int(chat_id_str))
    except Exception:
        pass

    return sorted(recipients)


def _warning_get_recipients_all():
    recipients = set()

    try:
        for uid in data.get("users", {}).keys():
            uid_str = str(uid)

            if uid_str.lstrip("-").isdigit():
                recipients.add(int(uid_str))
    except Exception:
        pass

    try:
        for chat_id in data.get("chats", {}).keys():
            chat_id_str = str(chat_id)

            if chat_id_str.lstrip("-").isdigit():
                recipients.add(int(chat_id_str))
    except Exception:
        pass

    return sorted(recipients)



def _upd_get_recipients_all():
    recipients = set()

    try:
        for uid in data.get("users", {}).keys():
            uid_str = str(uid)

            if uid_str.lstrip("-").isdigit():
                recipients.add(int(uid_str))
    except Exception:
        pass

    try:
        for chat_id in data.get("chats", {}).keys():
            chat_id_str = str(chat_id)

            if chat_id_str.lstrip("-").isdigit():
                recipients.add(int(chat_id_str))
    except Exception:
        pass

    return sorted(recipients)


def _upd_files_exist():
    if not UPD_VOICE_FILES:
        return False, "Список UPD_VOICE_FILES пустой."

    if len(UPD_VOICE_FILES) < 2:
        return False, "Нужно указать 2 голосовых файла."

    for file_path in UPD_VOICE_FILES[:2]:
        if not file_path:
            return False, "Один из путей к файлу пустой."

        if not os.path.exists(file_path):
            return False, f"Файл не найден: {file_path}"

        if not os.path.isfile(file_path):
            return False, f"Это не файл: {file_path}"

    return True, ""


def _send_upd_voices_to_chat(chat_id):
    for file_path in UPD_VOICE_FILES[:2]:
        with open(file_path, "rb") as voice_file:
            bot.send_voice(
                chat_id,
                voice_file,
                parse_mode=None
            )

        time.sleep(UPD_SLEEP)


@bot.message_handler(commands=["upd"])
def cmd_upd(message):
    if not _is_admin_id(message.from_user.id):
        return

    ok_files, file_error = _upd_files_exist()

    if not ok_files:
        bot.reply_to(
            message,
            f"❌ Голосовые файлы для /upd не настроены.\n\n{file_error}\n\n"
            f"Положи файлы в папку проекта:\n"
            f"1. upd1.ogg\n"
            f"2. upd2.ogg",
            parse_mode=None
        )
        return

    parts = (message.text or "").split(maxsplit=1)
    mode = ""

    if len(parts) > 1:
        mode = parts[1].strip().lower()

    if mode == "all":
        recipients = _upd_get_recipients_all()

        if not recipients:
            bot.reply_to(
                message,
                "❌ Нет пользователей или чатов для рассылки.",
                parse_mode=None
            )
            return

        bot.reply_to(
            message,
            f"⚠️ Рассылка /upd all запущена.\n"
            f"Получателей: {len(recipients)}",
            parse_mode=None
        )

        ok = 0
        fail = 0

        for index, recipient_id in enumerate(recipients, start=1):
            try:
                _send_upd_voices_to_chat(recipient_id)
                ok += 1
            except Exception as e:
                fail += 1
                print(f"upd send error to {recipient_id}: {e}")

            if index % UPD_PROGRESS_EVERY == 0:
                try:
                    bot.send_message(
                        message.chat.id,
                        f"⚠️ Прогресс upd: {index}/{len(recipients)}\n"
                        f"✅ Успешно: {ok}\n"
                        f"❌ Ошибок: {fail}",
                        parse_mode=None
                    )
                except Exception:
                    pass

            time.sleep(UPD_SLEEP)

        bot.send_message(
            message.chat.id,
            f"✅ Рассылка /upd all завершена.\n\n"
            f"Получателей: {len(recipients)}\n"
            f"✅ Успешно: {ok}\n"
            f"❌ Ошибок: {fail}",
            parse_mode=None
        )

        return

    try:
        _send_upd_voices_to_chat(message.chat.id)


    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Не удалось отправить UPD в этот чат.\n\n"
            f"Ошибка: {e}",
            parse_mode=None
        )

@bot.message_handler(func=lambda m: bool(getattr(m, "text", None)) and m.text.strip().lower() == "-маты")
def cmd_disable_mats(message):
    if not _mat_can_manage(message):
        return

    _mat_set_enabled(message.chat.id, False)

    bot.reply_to(
        message,
        "✅ Антимат выключен.\nБот больше не будет реагировать на маты в этом чате.",
        parse_mode=None
    )


@bot.message_handler(func=lambda m: bool(getattr(m, "text", None)) and m.text.strip().lower() == "+маты")
def cmd_enable_mats(message):
    if not _mat_can_manage(message):
        return

    keyboard = types.InlineKeyboardMarkup(row_width=1)

    keyboard.add(
        types.InlineKeyboardButton(
            "⚠️ Варнить за маты",
            callback_data=f"mat_action:warn:{message.chat.id}"
        ),
        types.InlineKeyboardButton(
            "🔇 Мутить за маты",
            callback_data=f"mat_action:mute:{message.chat.id}"
        ),
        types.InlineKeyboardButton(
            "⛔ Банить за маты",
            callback_data=f"mat_action:ban:{message.chat.id}"
        ),
        types.InlineKeyboardButton(
            "❌ Отмена",
            callback_data=f"mat_action:cancel:{message.chat.id}"
        ),
    )

    bot.reply_to(
        message,
        "Выбери, что делать с пользователями за маты:",
        reply_markup=keyboard,
        parse_mode=None
    )


@bot.callback_query_handler(func=lambda call: call.data.startswith("mat_action:"))
def callback_mat_action(call):
    if not _mat_can_manage_callback(call):
        bot.answer_callback_query(
            call.id,
            "У тебя нет прав.",
            show_alert=True
        )
        return

    try:
        _, action, chat_id = call.data.split(":")
        chat_id = int(chat_id)
    except Exception:
        bot.answer_callback_query(
            call.id,
            "Ошибка данных кнопки.",
            show_alert=True
        )
        return

    if action == "cancel":
        bot.answer_callback_query(call.id, "Отменено.")

        try:
            bot.edit_message_text(
                "❌ Настройка антимата отменена.",
                call.message.chat.id,
                call.message.message_id,
                parse_mode=None
            )
        except Exception:
            pass

        return

    if action not in MAT_ACTION_NAMES:
        bot.answer_callback_query(
            call.id,
            "Неизвестное действие.",
            show_alert=True
        )
        return

    _mat_set_action(chat_id, action)

    bot.answer_callback_query(
        call.id,
        "Антимат включён."
    )

    try:
        bot.edit_message_text(
            f"✅ Антимат включён.\n"
            f"Действие за маты: {MAT_ACTION_NAMES[action]}.",
            call.message.chat.id,
            call.message.message_id,
            parse_mode=None
        )
    except Exception:
        pass


@bot.message_handler(func=lambda m: bool(getattr(m, "text", None)) and _mat_is_enabled(m.chat.id) and _mat_contains_bad_word(m.text))
def mat_filter_handler(message):
    if not message.from_user:
        return

    if _is_admin_id(message.from_user.id):
        return

    if message.chat.type in ["group", "supergroup"]:
        if _mat_is_chat_admin(message.chat.id, message.from_user.id):
            return

    settings = _mat_get_chat_settings(message.chat.id)
    action = settings.get("action", MAT_DEFAULT_ACTION)

    if action == "warn":
        _mat_warn_user(message)
        return

    if action == "mute":
        _mat_mute_user(message)
        return

    if action == "ban":
        _mat_ban_user(message)
        return

    _mat_warn_user(message)

def _warning_files_exist():
    if not WARNING_VOICE_FILES:
        return False, "Список WARNING_VOICE_FILES пустой."

    if len(WARNING_VOICE_FILES) < 2:
        return False, "Нужно указать 2 голосовых файла."

    for file_path in WARNING_VOICE_FILES[:2]:
        if not file_path:
            return False, "Один из путей к файлу пустой."

        if not os.path.exists(file_path):
            return False, f"Файл не найден: {file_path}"

        if not os.path.isfile(file_path):
            return False, f"Это не файл: {file_path}"

    return True, ""


def _send_warning_voices_to_chat(chat_id):
    for file_path in WARNING_VOICE_FILES[:2]:
        with open(file_path, "rb") as voice_file:
            bot.send_voice(
                chat_id,
                voice_file,
                parse_mode=None
            )

        time.sleep(WARNING_SLEEP)


@bot.message_handler(commands=["warning"])
def cmd_warning(message):
    if not _is_admin_id(message.from_user.id):
        return

    ok_files, file_error = _warning_files_exist()

    if not ok_files:
        bot.reply_to(
            message,
            f"❌ Голосовые файлы не настроены.\n\n{file_error}\n\n"
            f"Положи файлы в папку проекта:\n"
            f"1. warning1.ogg\n"
            f"2. warning2.ogg",
            parse_mode=None
        )
        return

    parts = (message.text or "").split(maxsplit=1)
    mode = ""

    if len(parts) > 1:
        mode = parts[1].strip().lower()

    if mode == "all":
        recipients = _warning_get_recipients_all()

        if not recipients:
            bot.reply_to(
                message,
                "❌ Нет пользователей или чатов для рассылки.",
                parse_mode=None
            )
            return

        bot.reply_to(
            message,
            f"⚠️ Рассылка /warning all запущена.\n"
            f"Получателей: {len(recipients)}",
            parse_mode=None
        )

        ok = 0
        fail = 0

        for index, recipient_id in enumerate(recipients, start=1):
            try:
                _send_warning_voices_to_chat(recipient_id)
                ok += 1
            except Exception as e:
                fail += 1
                print(f"warning send error to {recipient_id}: {e}")

            if index % WARNING_PROGRESS_EVERY == 0:
                try:
                    bot.send_message(
                        message.chat.id,
                        f"⚠️ Прогресс warning: {index}/{len(recipients)}\n"
                        f"✅ Успешно: {ok}\n"
                        f"❌ Ошибок: {fail}",
                        parse_mode=None
                    )
                except Exception:
                    pass

            time.sleep(WARNING_SLEEP)

        bot.send_message(
            message.chat.id,
            f"✅ Рассылка /warning all завершена.\n\n"
            f"Получателей: {len(recipients)}\n"
            f"✅ Успешно: {ok}\n"
            f"❌ Ошибок: {fail}",
            parse_mode=None
        )

        return

    try:
        _send_warning_voices_to_chat(message.chat.id)

    except Exception as e:
        bot.reply_to(
            message,
            f"❌ Не удалось отправить warning в этот чат.\n\n"
            f"Ошибка: {e}",
            parse_mode=None
        )

@bot.message_handler(commands=["broadcast"])
def cmd_broadcast(message):
    if ADMIN_ID and message.from_user.id not in ADMIN_ID:
        bot.reply_to(message, "Команда доступна только администратору.", parse_mode=None)
        return

    parts = (message.text or "").split(maxsplit=2)
    scope = "all"
    text = None

    if len(parts) >= 2 and parts[1].lower() in ("users", "chats", "all"):
        scope = parts[1].lower()
        text = parts[2] if len(parts) >= 3 else None
    elif len(parts) >= 2:
        text = parts[1] if len(parts) == 2 else parts[1] + " " + parts[2]

    reply = message.reply_to_message

    if not reply and not text:
        bot.reply_to(message, "Использование: /broadcast текст или /broadcast users текст", parse_mode=None)
        return

    users = [int(x) for x in data.get("users", {}).keys() if str(x).lstrip("-").isdigit()]
    chats = [int(x) for x in data.get("chats", {}).keys() if str(x).lstrip("-").isdigit()]

    if scope == "users":
        recipients = sorted(set(users))
    elif scope == "chats":
        recipients = sorted(set(chats))
    else:
        recipients = sorted(set(users) | set(chats))

    ok = 0
    fail = 0

    bot.reply_to(message, f"Рассылка запущена. Получателей: {len(recipients)}", parse_mode=None)

    for i, rid in enumerate(recipients, start=1):
        try:
            if reply:
                bot.copy_message(rid, message.chat.id, reply.message_id)
            else:
                bot.send_message(rid, text, parse_mode=None)
            ok += 1
        except Exception:
            fail += 1

        if i % BROADCAST_PROGRESS_EVERY == 0:
            try:
                bot.send_message(message.chat.id, f"Прогресс {i}/{len(recipients)}. ОК: {ok}, ошибок: {fail}", parse_mode=None)
            except Exception:
                pass

        time.sleep(BROADCAST_SLEEP)

    bot.send_message(message.chat.id, f"✅ Готово. ОК: {ok}, ошибок: {fail}", parse_mode=None)


@bot.message_handler(func=lambda m: bool(m.text) and m.text.strip().lower() == "приветствие")
def cmd_show_greeting(message):
    greeting = _get_chat_greeting(message.chat.id)

    if not greeting:
        bot.reply_to(
            message,
            "ℹ️ В этом чате приветствие ещё не установлено.\n\n"
            "Админ может установить его так:\n"
            "+приветствие\n"
            "Добро пожаловать, {user}!",
            parse_mode=None
        )
        return

    bot.reply_to(
        message,
        f"👋 Текущее приветствие в этом чате:\n\n{greeting}",
        parse_mode=None
    )


@bot.message_handler(func=lambda m: bool(m.text) and m.text.strip().lower().startswith("+приветствие"))
def cmd_set_greeting(message):
    if not _is_chat_admin(message):
        bot.reply_to(
            message,
            "❌ Устанавливать приветствие могут только админы чата.",
            parse_mode=None
        )
        return

    text = message.text or ""

    if "\n" not in text:
        bot.reply_to(
            message,
            "❌ Напиши текст приветствия с новой строки.\n\n"
            "Пример:\n"
            "+приветствие\n"
            "Добро пожаловать, {user}!",
            parse_mode=None
        )
        return

    greeting = text.split("\n", 1)[1].strip()

    if not greeting:
        bot.reply_to(
            message,
            "❌ Текст приветствия не может быть пустым.\n\n"
            "Пример:\n"
            "+приветствие\n"
            "Добро пожаловать, {user}!",
            parse_mode=None
        )
        return

    _set_chat_greeting(message.chat.id, greeting)

    bot.reply_to(
        message,
        "✅ Приветствие установлено.\n\n"
        "Доступные переменные:\n"
        "{user} — ссылка на пользователя\n"
        "{name} — имя пользователя\n"
        "{full_name} — полное имя\n"
        "{id} — ID пользователя\n"
        "{chat} — название чата",
        parse_mode=None
    )

@bot.message_handler(commands=["add_greetings"])
def cmd_set_greeting(message):
    if not _is_chat_admin(message):
        bot.reply_to(
            message,
            "❌ Устанавливать приветствие могут только админы чата.",
            parse_mode=None
        )
        return

    text = message.text or ""

    if "\n" not in text:
        bot.reply_to(
            message,
            "❌ Напиши текст приветствия с новой строки.\n\n"
            "Пример:\n"
            "+приветствие\n"
            "Добро пожаловать, {user}!",
            parse_mode=None
        )
        return

    greeting = text.split("\n", 1)[1].strip()

    if not greeting:
        bot.reply_to(
            message,
            "❌ Текст приветствия не может быть пустым.\n\n"
            "Пример:\n"
            "+приветствие\n"
            "Добро пожаловать, {user}!",
            parse_mode=None
        )
        return

    _set_chat_greeting(message.chat.id, greeting)

    bot.reply_to(
        message,
        "✅ Приветствие установлено.\n\n"
        "Доступные переменные:\n"
        "{user} — ссылка на пользователя\n"
        "{name} — имя пользователя\n"
        "{full_name} — полное имя\n"
        "{id} — ID пользователя\n"
        "{chat} — название чата",
        parse_mode=None
    )

@bot.message_handler(content_types=["new_chat_members"])
def welcome_new_members(message):
    greeting = _get_chat_greeting(message.chat.id)

    if not greeting:
        return

    for user in message.new_chat_members:
        text = _format_greeting(greeting, user, message.chat)

        bot.send_message(
            message.chat.id,
            text,
            parse_mode="HTML",
            disable_web_page_preview=True
        )

@bot.message_handler(content_types=[
    "text",
    "photo",
    "video",
    "animation",
    "sticker",
    "voice",
    "video_note",
    "audio",
    "document",
    "poll",
    "contact",
    "location",
    "venue"
])
def track_all_messages(message):
    add_message_to_stats(message)

    if ContinueHandling:
        return ContinueHandling()


def handle_all_messages(message):
    try:
        if message.from_user:
            ensure_user(message.from_user.id, message.from_user)
    except Exception as e:
        print("ensure_user in handle_all error:", e)

    try:
        if is_group(message.chat) and message.from_user:
            add_known_user(message.chat.id, message.from_user.id)
            push_message_history(message.chat.id, message.message_id)

            if is_countable_text_message(message):
                count_user_message_global(message)
                inc_msg_counters(message.chat.id, message.from_user.id)
    except Exception as e:
        print("handle_all error:", e)

def _message_stats_is_countable(message):
    if not message:
        return False

    if not getattr(message, "chat", None):
        return False

    if not getattr(message, "from_user", None):
        return False

    user = message.from_user

    if getattr(user, "is_bot", False):
        return False

    content_type = getattr(message, "content_type", None)

    allowed_types = {
        "text",
        "photo",
        "video",
        "animation",
        "sticker",
        "voice",
        "video_note",
        "audio",
        "document",
        "poll",
        "contact",
        "location",
        "venue",
    }

    if content_type not in allowed_types:
        return False

    if content_type == "text":
        text = (getattr(message, "text", None) or "").strip()

        if not text:
            return False

        if text.startswith("/"):
            return False

        try:
            normalized = normalize_plain_cmd(text)
            if normalized in ("top_today", "top_all", "rules", "balance"):
                return False
        except Exception:
            pass

    return True


def _clean_stats_name(name):
    name = str(name or "").replace("\n", " ").strip()
    return name or "Без имени"


def _ensure_message_stats_chat(chat_id):
    chat_key = get_chat_key(chat_id)

    if chat_key not in message_stats or not isinstance(message_stats.get(chat_key), dict):
        message_stats[chat_key] = {}

    chat_stats = message_stats[chat_key]

    chat_stats.setdefault("total_messages", 0)
    chat_stats.setdefault("users", {})
    chat_stats.setdefault("daily", {})

    if not isinstance(chat_stats["users"], dict):
        chat_stats["users"] = {}

    if not isinstance(chat_stats["daily"], dict):
        chat_stats["daily"] = {}

    return chat_stats


def _ensure_message_stats_day(chat_stats, day):
    daily = chat_stats.setdefault("daily", {})

    if day not in daily or not isinstance(daily.get(day), dict):
        daily[day] = {
            "total_messages": 0,
            "users": {}
        }

    day_stats = daily[day]

    day_stats.setdefault("total_messages", 0)
    day_stats.setdefault("users", {})

    if not isinstance(day_stats["users"], dict):
        day_stats["users"] = {}

    return day_stats


def add_message_to_stats(message):
    if getattr(message, "_message_stats_counted", False):
        return

    if not _message_stats_is_countable(message):
        return

    try:
        setattr(message, "_message_stats_counted", True)
    except Exception:
        pass

    user = message.from_user
    chat_id = message.chat.id
    user_id = user.id

    user_key = get_user_key(user_id)
    now = int(time.time())
    today = _today()

    name = _clean_stats_name(get_user_name(user))
    username = user.username if getattr(user, "username", None) else None

    with MESSAGE_STATS_LOCK:
        chat_stats = _ensure_message_stats_chat(chat_id)

        users = chat_stats["users"]

        if user_key not in users or not isinstance(users.get(user_key), dict):
            users[user_key] = {
                "id": int(user_id),
                "name": name,
                "username": username,
                "messages": 0,
                "first_seen": now,
                "last_seen": now
            }

        users[user_key]["id"] = int(user_id)
        users[user_key]["name"] = name
        users[user_key]["username"] = username or users[user_key].get("username")
        users[user_key]["messages"] = int(users[user_key].get("messages", 0)) + 1
        users[user_key]["last_seen"] = now

        chat_stats["total_messages"] = int(chat_stats.get("total_messages", 0)) + 1

        day_stats = _ensure_message_stats_day(chat_stats, today)
        day_users = day_stats["users"]

        if user_key not in day_users or not isinstance(day_users.get(user_key), dict):
            day_users[user_key] = {
                "id": int(user_id),
                "name": name,
                "username": username,
                "messages": 0,
                "first_seen": now,
                "last_seen": now
            }

        day_users[user_key]["id"] = int(user_id)
        day_users[user_key]["name"] = name
        day_users[user_key]["username"] = username or day_users[user_key].get("username")
        day_users[user_key]["messages"] = int(day_users[user_key].get("messages", 0)) + 1
        day_users[user_key]["last_seen"] = now

        day_stats["total_messages"] = int(day_stats.get("total_messages", 0)) + 1

        save_message_stats()


def get_chat_top_data(chat_id, mode="today"):
    chat_key = get_chat_key(chat_id)

    with MESSAGE_STATS_LOCK:
        chat_stats = message_stats.get(chat_key)

        if not isinstance(chat_stats, dict):
            return [], 0

        if mode == "all":
            users = chat_stats.get("users", {})
            total_messages = int(chat_stats.get("total_messages", 0))
        else:
            day = _today()
            day_stats = chat_stats.get("daily", {}).get(day, {})
            users = day_stats.get("users", {})
            total_messages = int(day_stats.get("total_messages", 0))

        if not isinstance(users, dict):
            return [], 0

        top_users = []

        for user_id, user_data in users.items():
            if not isinstance(user_data, dict):
                continue

            count = int(user_data.get("messages", 0))

            if count <= 0:
                continue

            name = (
                user_data.get("name")
                or user_data.get("username")
                or f"ID {user_id}"
            )

            name = _clean_stats_name(name)

            top_users.append((name, count))

        top_users.sort(key=lambda x: x[1], reverse=True)

        return top_users, total_messages


def format_top_message(top_users, total_messages, title):
    lines = [
        title,
        ""
    ]

    for index, item in enumerate(top_users, start=1):
        name = item[0]
        count = item[1]

        lines.append(f"{index}. {name} — {format_count_number(count)}")

    lines.append("")
    lines.append(f"Всего сообщений: {format_count_number(total_messages)}")

    return "\n".join(lines)


def cmd_top(message):
    top_users, total_messages = get_chat_top_data(message.chat.id, mode="today")

    if not top_users:
        bot.reply_to(
            message,
            "Статистика за сегодня пустая. Напишите несколько сообщений в чат.",
            parse_mode=None
        )
        return

    top_users = top_users[:TOP_LIMIT]

    text = format_top_message(
        top_users,
        total_messages,
        "🏆 Топ сообщений за сегодня"
    )

    bot.reply_to(
        message,
        text,
        parse_mode=None
    )


def cmd_top_all(message):
    top_users, total_messages = get_chat_top_data(message.chat.id, mode="all")

    if not top_users:
        bot.reply_to(
            message,
            "Общая статистика пустая. Напишите несколько сообщений в чат.",
            parse_mode=None
        )
        return

    text = format_top_message(
        top_users,
        total_messages,
        "🏆 Топ сообщений за всё время"
    )

    send_long_message(
        message.chat.id,
        text,
        reply_to_message_id=message.message_id
    )


def cmd_top_today(message):
    return cmd_top(message)


def _track_message_before_handlers(message):
    if not message:
        return

    try:
        add_message_to_stats(message)
    except Exception as e:
        print("add_message_to_stats error:", e)

    try:
        if getattr(message, "_handle_all_messages_done", False):
            return

        setattr(message, "_handle_all_messages_done", True)

        handle_all_messages(message)

    except Exception as e:
        print("handle_all_messages global tracker error:", e)


def install_global_message_tracker():
    if getattr(bot, "_global_message_tracker_installed", False):
        return

    original_process_new_updates = bot.process_new_updates

    def patched_process_new_updates(updates):
        try:
            for update in updates:
                message = None

                if getattr(update, "message", None):
                    message = update.message

                elif getattr(update, "edited_message", None):
                    message = update.edited_message

                if message:
                    _track_message_before_handlers(message)

        except Exception as e:
            print("global message tracker error:", e)

        return original_process_new_updates(updates)

    bot.process_new_updates = patched_process_new_updates
    bot._global_message_tracker_installed = True

    print("Глобальный трекер сообщений установлен")


if __name__ == "__main__":
    if botik_token == "ВСТАВЬ_СЮДА_НОВЫЙ_ТОКЕН":
        print("ОШИБКА: вставь новый токен в BOT_TOKEN или задай перемную окружения BOT_TOKEN")
    else:
        install_global_message_tracker()

        print("Бот запущен")
        print("Глобальный трекер сообщений включён:", getattr(bot, "_global_message_tracker_installed", False))

        bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)