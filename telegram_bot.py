# -*- coding: utf-8 -*-
"""
بوت تلجرام لمراقبة AjayXGlory (اختياري).
- يقرأ التوكن من متغير البيئة TELEGRAM_BOT_TOKEN، أو من ملف telegram_token.txt بجانب المشروع.
- الأوامر: /start /help /status /glory /log
- عند حفظ معرف محادثة (أول رسالة ترسلها للبوت) يخزنها محلياً ليبلغك بحالة التشغيل.
"""
import asyncio
import json
import os
import time

import httpx

import account_generator
from dashboard_server import bot_state

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_token():
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if tok:
        return tok
    try:
        with open(os.path.join(_BASE_DIR, "telegram_token.txt"), encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return ""


def _load_chats():
    try:
        with open(os.path.join(_BASE_DIR, "telegram_chats.json"), encoding="utf-8") as f:
            return list(json.load(f))
    except Exception:
        return []


def _save_chat(chat_id):
    chats = _load_chats()
    if chat_id not in chats:
        chats.append(chat_id)
        try:
            with open(os.path.join(_BASE_DIR, "telegram_chats.json"), "w", encoding="utf-8") as f:
                json.dump(chats, f)
        except Exception:
            pass


TOKEN = _load_token()
API = f"https://api.telegram.org/bot{TOKEN}" if TOKEN else ""
_offset = 0

HELP_TEXT = (
    "🤖 بوت AjayXGlory للتحكم والمراقبة\n\n"
    "/status — حالة البوت الحالية\n"
    "/glory — مجد الجيلد المباشر\n"
    "/region — فحص منطقة الحسابات الجديدة\n"
    "/log — آخر سطور السجل\n"
    "/help — عرض هذه المساعدة"
)


async def _call(method, **payload):
    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            r = await client.post(f"{API}/{method}", json=payload)
            return r.json()
    except Exception:
        return {}


def _status_text():
    accounts = list(bot_state.accounts.values())
    online = sum(1 for a in accounts if a.get("status") in ("ONLINE", "IN_MATCH"))
    uptime = max(1, int(time.time() - bot_state.start_time))
    h, m = uptime // 3600, uptime % 3600 // 60
    lines = [
        "📊 حالة AjayXGlory",
        f"⏱ مدة التشغيل: {h}س {m}د",
        f"👥 الحسابات: {len(accounts)} (متصل {online})",
        f"🎮 مباريات جارية: {sum(a.get('active_matches', 0) for a in accounts)}",
        f"🏁 مباريات مكتملة: {bot_state.total_matches}",
        f"⭐ خبرة مكتسبة: {bot_state.total_gained_exp}",
        f"🚀 المجد: {'يعمل' if bot_state.glory_started else 'متوقف'}",
    ]
    return "\n".join(lines)


async def send_message(chat_id, text):
    await _call("sendMessage", chat_id=chat_id, text=str(text)[:4000])


async def broadcast(text):
    """إرسال رسالة لكل المحادثات المحفوظة + TELEGRAM_CHAT_ID إن وُجد."""
    chats = set(_load_chats())
    env_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if env_chat:
        chats.add(env_chat)
    for c in chats:
        await send_message(c, text)


async def _handle_update(update):
    global _offset
    _offset = max(_offset, update.get("update_id", 0) + 1)
    msg = update.get("message") or update.get("edited_message") or {}
    text = (msg.get("text") or "").strip()
    chat = (msg.get("chat") or {}).get("id")
    if not chat or not text.startswith("/"):
        return
    _save_chat(chat)
    cmd = text.split()[0].lower().split("@")[0]
    if cmd in ("/start", "/help"):
        reply = HELP_TEXT
    elif cmd == "/status":
        reply = _status_text()
    elif cmd == "/glory":
        gl = bot_state.guild_live or {}
        if gl.get("glory"):
            reply = (
                f"🛡 {gl.get('name') or 'الجيلد'}\n"
                f"🏆 مجد الآن: {gl.get('glory')}\n"
                f"📈 مكسب الجلسة: {gl.get('gained_session', 0)}\n"
                f"⚡ السرعة/ساعة: {gl.get('per_hour', 0)}\n"
                f"👥 أعضاء متصلون: {gl.get('members_online', '—')} / {gl.get('total_members', '—')}"
            )
        else:
            reply = "لا يوجد مجد مباشر بعد — ابدأ المجد من لوحة التحكم أولاً."
    elif cmd == "/region":
        await send_message(chat, "🔎 جاري فحص المنطقة — إنشاء حساب اختباري لمعرفة المنطقة المُقفلة…")
        gc = bot_state.guild_config or {}
        region = str(gc.get("region") or "ME").upper()
        try:
            probe = await asyncio.to_thread(account_generator.probe_region, region, None)
        except Exception as e:
            await send_message(chat, f"❌ فشل الفحص: {e}")
            return
        if not probe.get("ok"):
            await send_message(chat, f"❌ فشل الفحص: {probe.get('error')}")
            return
        lock = str(probe.get("lock_region") or "؟").upper()
        match = lock == region
        reply = (
            f"🌍 فحص المنطقة (المطلوب: {region})\n"
            f"📍 بلد الـ IP: {probe.get('country_code') or '؟'}\n"
            f"🔒 المنطقة المُقفلة على الحساب: {lock}\n\n"
            + ("✅ متطابقة — الحسابات ستدخل الجيلد بلا مشاكل."
               if match else
               f"⚠️ غير متطابقة! الانضمام لجيلد {region} سيفشل (BR_CLAN_NOT_SAME_REGION).\n"
               f"الحل: شغّل الأداة من شبكة داخل منطقة {region} أو استخدم بروكسي من نفس المنطقة من لوحة التحكم.")
        )
    elif cmd == "/log":
        logs = bot_state.logs[-10:]
        reply = "\n".join(f"[{l.get('level', 'info')}] {l.get('message', '')}" for l in logs) or "السجل فارغ."
    else:
        reply = "أمر غير معروف — أرسل /help لعرض الأوامر."
    await send_message(chat, reply)


async def _poll_loop():
    global _offset
    await broadcast("✅ بوت AjayXGlory يعمل الآن")
    while True:
        try:
            data = await _call("getUpdates", offset=_offset, timeout=25)
            for u in (data.get("result") or []):
                try:
                    await _handle_update(u)
                except Exception:
                    pass
        except Exception:
            await asyncio.sleep(5)
        await asyncio.sleep(0.5)


def start():
    """يبدأ بوت تلجرام كخلفية إذا وجد توكن؛ وإلا يتجاهل بصمت."""
    if not TOKEN:
        print("[TELEGRAM] لا يوجد توكن — تخطي بوت تلجرام (أضف TELEGRAM_BOT_TOKEN أو ملف telegram_token.txt)")
        return None
    try:
        print("[TELEGRAM] بدء بوت تلجرام...")
        return asyncio.create_task(_poll_loop())
    except Exception as e:
        print(f"[TELEGRAM] فشل البدء: {e}")
        return None
