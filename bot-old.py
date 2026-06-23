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

import telebot
from telebot import types
from telebot.types import ChatPermissions, InlineKeyboardMarkup, InlineKeyboardButton
from telebot.apihelper import ApiTelegramException


TOKEN = os.getenv("BOT_TOKEN", "ВСТАВЬ_СЮДА_НОВЫЙ_ТОКЕН")
DATA_FILE = "data.json"

ADMIN_ID = {6301107206}

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

TOP_LIMIT = 50

EMO_TROPHY = "🏆"
EMO_TODAY = "📅"
EMO_MSG = "💬"
EMO_FIRST = "🥇"
EMO_SECOND = "🥈"
EMO_THIRD = "🥉"

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

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
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


def _today() -> str:
    return date.today().isoformat()


def rank_emoji(pos: int) -> str:
    if pos == 0:
        return EMO_FIRST
    if pos == 1:
        return EMO_SECOND
    if pos == 2:
        return EMO_THIRD
    return f"{pos + 1}."


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
        lines.append(f"{i}. {icon + ' ' if icon else ''}{title}{' — ' + note if note else ''}")

    return "\n".join(lines)


@bot.message_handler(commands=["ping"])
def cmd_ping(message):
    bot.reply_to(message, "pong", parse_mode=None)


@bot.message_handler(commands=["start", "help"])
def cmd_start(message):
    ensure_user(message.from_user.id, message.from_user)
    text = (
        "Привет! Я админ-бот с экономикой, кланами, топом сообщений и дуэлями.\n\n"
        "Команды:\n"
        "• /earn — заработать валюту\n"
        "• /balance — баланс\n"
        "• /profile — профиль\n"
        "• /shop — магазин\n"
        "• /top — топ сообщений за сегодня\n"
        "• /top_all — топ сообщений за всё время\n"
        "• /clan_create название — создать клан\n"
        "• /clan_join название — вступить в клан\n"
        "• /clans — список кланов\n"
        "• /clan_info — информация о клане\n"
        "• /clan_deposit сумма — пополнить казну\n"
        "• /clan_withdraw сумма — забрать из казны\n"
        "• /duel — дуэль, лучше ответом на сообщение\n"
        "• /who_duel — найти соперника\n"
        "• /rules — правила чата\n\n"
        "Админ-команды:\n"
        "• -смс число — удалить сообщения\n"
        "• призвать всех — упомянуть известных участников\n"
        "• /off_chat — закрыть чат\n"
        "• /on_chat — открыть чат\n"
        "• /award — выдать награду ответом на сообщение\n"
        "• +правила текст — установить правила"
    )
    bot.reply_to(message, text, parse_mode=None)


@bot.message_handler(commands=["balance"])
def cmd_balance(message):
    u = ensure_user(message.from_user.id, message.from_user)
    balance = _to_int(u.get("balance", 0), 0)
    prime = "есть" if _to_int(u.get("prime", 0), 0) else "нет"
    bot.reply_to(message, f"💰 Баланс: {balance}\n✨ Прайм: {prime}", parse_mode=None)


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
    kb.add(InlineKeyboardButton(f"✨ Купить Прайм ({PRIME_COST})", callback_data="shop:prime"))

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
        "👤 Профиль\n\n"
        f"🪪 Имя: {tg_escape_html(name)}\n"
        f"🆔 ID: {target_id}\n"
        f"🔗 Username: {tg_escape_html(username)}\n"
        f"💰 Баланс: {_to_int(u.get('balance', 0), 0)}\n"
        f"✨ Прайм: {'есть' if _to_int(u.get('prime', 0), 0) else 'нет'}\n"
        f"🛡️ Клан: {tg_escape_html(clan)}\n"
        f"🏆 Победы в дуэлях: {_to_int(u.get('duel_wins', 0), 0)}\n"
        f"💬 Сообщений всего: {_to_int(u.get('msg_total', 0), 0)}\n"
        f"📅 Сообщений сегодня: {_to_int(u.get('msg_today', 0), 0) if u.get('msg_day') == _today() else 0}\n"
        f"📌 Регистрация: {_fmt_dt(u.get('created_at'))}"
    )

    awards = award_text(message.chat.id, target_id)
    if awards:
        text += "\n\n" + awards

    bot.reply_to(message, text)


@bot.message_handler(commands=["top"])
def cmd_top_today(message):
    ranked = _sorted_users_today_positive(data.get("users", {}))[:TOP_LIMIT]

    if not ranked:
        bot.reply_to(message, "Нет пользователей с сообщениями за сегодня.", parse_mode=None)
        return

    lines = []
    for i, (val, u) in enumerate(ranked):
        lines.append(f"{rank_emoji(i)} {user_display_from_data(u)} — {val} {EMO_MSG}")

    bot.reply_to(message, f"{EMO_TODAY} Топ по сообщениям за сегодня:\n" + "\n".join(lines), parse_mode=None)


@bot.message_handler(commands=["top_all"])
def cmd_top_all(message):
    ranked = _sorted_users_by_key_positive(data.get("users", {}), "msg_total")[:TOP_LIMIT]

    if not ranked:
        bot.reply_to(message, "Нет пользователей с сообщениями за всё время.", parse_mode=None)
        return

    lines = []
    for i, (val, u) in enumerate(ranked):
        lines.append(f"{rank_emoji(i)} {user_display_from_data(u)} — {val} {EMO_MSG}")

    bot.reply_to(message, f"{EMO_TROPHY} Топ по сообщениям за всё время:\n" + "\n".join(lines), parse_mode=None)


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


@bot.message_handler(content_types=["new_chat_members"])
def on_new_members(message):
    if not is_group(message.chat):
        return

    for user in message.new_chat_members:
        ensure_user(user.id, user)
        add_known_user(message.chat.id, user.id)

    push_message_history(message.chat.id, message.message_id)


@bot.message_handler(content_types=["text"], func=lambda m: normalize_plain_cmd(m.text) is not None)
def handle_plain_commands(message):
    cmd = normalize_plain_cmd(message.text)

    if cmd == "top_today":
        return cmd_top_today(message)

    if cmd == "top_all":
        return cmd_top_all(message)

    if cmd == "rules":
        return cmd_rules(message)

    if cmd == "balance":
        return cmd_balance(message)


@bot.message_handler(content_types=[
    "text", "audio", "document", "photo", "sticker",
    "video", "video_note", "voice", "location", "contact",
    "left_chat_member"
])
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


if __name__ == "__main__":
    if TOKEN == "ВСТАВЬ_СЮДА_НОВЫЙ_ТОКЕН":
        print("ОШИБКА: вставь новый токен в BOT_TOKEN или задай переменную окружения BOT_TOKEN")
    else:
        print("Бот запущен")
        bot.infinity_polling(skip_pending=True, timeout=20, long_polling_timeout=20)