import requests
import re
import json
import time
import logging
from datetime import datetime
import os
import asyncio
import threading
import random
import sys
from flask import Flask
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
IVASMS_EMAIL = os.getenv("IVASMS_EMAIL")
IVASMS_PASSWORD = os.getenv("IVASMS_PASSWORD")

if not all([BOT_TOKEN, CHAT_ID, IVASMS_EMAIL, IVASMS_PASSWORD]):
    logger.error("Missing required environment variables!")
    sys.exit(1)

# Flask app for health checks
app = Flask(__name__)

@app.route('/')
def health():
    return "IVASMS Bot is running! ✅", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)

# Start Flask in background thread
threading.Thread(target=run_flask, daemon=True).start()
logger.info("Flask health server started")

# Bot constants
ADMIN_IDS = [7562165596]
BANNER_URL = "https://files.catbox.moe/koc535.jpg"

def get_inline_keyboard():
    keyboard = [
        [InlineKeyboardButton("𝐍ᴜᴍʙᴇʀ 𝐂ʜᴀɴɴᴇʟ", url="https://t.me/mrafrixtech")],
        [InlineKeyboardButton("𝐎ᴛᴘ 𝐆𝐫𝐨𝐮𝐩", url="https://t.me/afrixotpgc")],
        [InlineKeyboardButton("𝐑ᴇɴᴛ sᴄʀɪᴘᴛ", url="https://t.me/KnKudo")],
    ]
    return InlineKeyboardMarkup(keyboard)

def get_powered_by_caption():
    return f"©ᴘᴏᴡᴇʀᴇᴅ ʙʏ 𝐀ᴜʀᴏʀᴀ𝐈ɪɴᴄ {datetime.now().year}"

def is_admin(user_id):
    return user_id in ADMIN_IDS

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
]

def get_random_headers():
    return {
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }

class IVASMSBot:
    def __init__(self):
        self.email = IVASMS_EMAIL
        self.password = IVASMS_PASSWORD
        self.bot_token = BOT_TOKEN
        self.chat_id = CHAT_ID
        self.session = requests.Session()
        self.consecutive_failures = 0
        self.last_sms = {}
        self.logged_in = False

    def login(self):
        """Login using requests (Selenium removed for Render compatibility)"""
        try:
            logger.info("Logging in with requests...")
            # Warm up
            for attempt in range(3):
                try:
                    self.session.get("https://www.ivasms.com/", headers=get_random_headers(), timeout=15)
                    break
                except:
                    time.sleep(2)
            
            time.sleep(2)
            
            login_data = {"email": self.email, "password": self.password}
            response = self.session.post(
                "https://www.ivasms.com/login",
                data=login_data,
                headers=get_random_headers(),
                timeout=20,
                allow_redirects=True
            )
            
            if response.status_code == 200:
                if "dashboard" in response.url or "home" in response.url or "logout" in response.text.lower():
                    logger.info("✅ Login successful")
                    self.consecutive_failures = 0
                    self.logged_in = True
                    return True
            logger.warning(f"Login failed: {response.status_code}")
            self.consecutive_failures += 1
            return False
        except Exception as e:
            logger.error(f"Login error: {e}")
            self.consecutive_failures += 1
            return False

    def check_sms(self):
        """Check for new SMS messages via API"""
        if not self.logged_in:
            if not self.login():
                return []
        try:
            response = self.session.get(
                "https://www.ivasms.com/api/sms",
                headers=get_random_headers(),
                timeout=15
            )
            if response.status_code == 200:
                try:
                    sms_data = response.json()
                    new_messages = []
                    if isinstance(sms_data, list):
                        for sms in sms_data:
                            sms_id = sms.get("id", str(random.random()))
                            if sms_id not in self.last_sms:
                                new_messages.append(sms)
                                self.last_sms[sms_id] = True
                    if new_messages:
                        logger.info(f"Found {len(new_messages)} new SMS")
                    return new_messages
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON response")
            else:
                logger.warning(f"API error {response.status_code}")
                self.logged_in = False  # Force re-login
            return []
        except Exception as e:
            logger.error(f"Check SMS error: {e}")
            return []

    async def send_sms_notification(self, bot, sms):
        """Send notification with banner and buttons"""
        try:
            message = f"""
<b>📱 New SMS Received</b>

<b>From:</b> {sms.get('sender', 'Unknown')}
<b>Message:</b> {sms.get('message', 'No content')}
<b>Time:</b> {sms.get('timestamp', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}

{get_powered_by_caption()}
"""
            await bot.send_photo(
                chat_id=self.chat_id,
                photo=BANNER_URL,
                caption=message,
                parse_mode="HTML",
                reply_markup=get_inline_keyboard()
            )
            logger.info("SMS notification sent")
        except Exception as e:
            logger.error(f"Send notification error: {e}")

    async def handle_command(self, update, context):
        user_id = update.effective_user.id
        command = update.message.text.split()[0].lower()
        
        if command == "/start":
            await update.message.reply_text(
                "👋 Welcome to IVASMS Bot!\n\n"
                "🤖 I monitor your ivasms.com account and notify you about incoming SMS.\n\n"
                "📝 Commands:\n"
                "/status - Check bot status\n"
                "/help - Show this message\n",
                reply_markup=get_inline_keyboard()
            )
        elif command == "/help":
            await update.message.reply_text(
                "📖 Available Commands:\n\n"
                "/start - Welcome message\n"
                "/status - Bot status\n"
                "/help - This message\n",
                reply_markup=get_inline_keyboard()
            )
        elif command == "/status":
            status = "🟢 Online and monitoring" if self.logged_in else "🔴 Not logged in"
            await update.message.reply_text(
                f"Bot Status: {status}\n"
                f"Messages tracked: {len(self.last_sms)}\n\n"
                f"{get_powered_by_caption()}",
                reply_markup=get_inline_keyboard()
            )
        elif command == "/stats" and is_admin(user_id):
            await update.message.reply_text(
                f"📊 Admin Stats:\n"
                f"Messages tracked: {len(self.last_sms)}\n"
                f"Consecutive failures: {self.consecutive_failures}\n"
                f"Last check: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"{get_powered_by_caption()}",
                reply_markup=get_inline_keyboard()
            )
        elif command == "/broadcast" and is_admin(user_id):
            if len(context.args) > 0:
                msg = " ".join(context.args)
                await context.bot.send_message(chat_id=self.chat_id, text=msg, reply_markup=get_inline_keyboard())
                await update.message.reply_text("✓ Broadcast sent!")
            else:
                await update.message.reply_text("Usage: /broadcast <message>")
        elif command == "/restart" and is_admin(user_id):
            await update.message.reply_text("🔄 Restarting bot...")
            self.consecutive_failures = 0
            self.logged_in = False
            logger.info("Bot restarted by admin")

async def main():
    # Initialize bot
    bot = Bot(token=BOT_TOKEN)
    application = Application.builder().token(BOT_TOKEN).build()
    
    ivasms = IVASMSBot()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", ivasms.handle_command))
    application.add_handler(CommandHandler("help", ivasms.handle_command))
    application.add_handler(CommandHandler("status", ivasms.handle_command))
    application.add_handler(CommandHandler("stats", ivasms.handle_command))
    application.add_handler(CommandHandler("broadcast", ivasms.handle_command))
    application.add_handler(CommandHandler("restart", ivasms.handle_command))
    
    await application.initialize()
    await application.start()
    
    # Initial login
    if not ivasms.login():
        logger.error("Initial login failed - check credentials")
        await application.stop()
        return
    
    logger.info("Bot started successfully - monitoring for SMS...")
    
    # Monitoring loop
    try:
        while True:
            sms_messages = ivasms.check_sms()
            if sms_messages:
                for sms in sms_messages:
                    await ivasms.send_sms_notification(bot, sms)
            wait_time = random.uniform(30, 60)
            logger.info(f"Next check in {wait_time:.1f}s")
            await asyncio.sleep(wait_time)
    except asyncio.CancelledError:
        pass
    finally:
        await application.stop()

if __name__ == "__main__":
    asyncio.run(main())
