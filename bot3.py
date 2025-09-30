import os
import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import sqlite3
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardRemove
import secrets
from datetime import datetime
from telegram import ReplyKeyboardRemove
import asyncio  # Add this line with other imports


# Configuration
BOT_TOKEN = "8053732489:AAGAVSAvK4u1Gxy_rbAPDMpTIFE-ciXImq0"  # Replace with actual token
ADMIN_ID = 5397131005  # Replace with your user ID

# New configuration variables
MIN_WITHDRAWAL = 35 # Minimum withdrawal amount
ADMIN_USERNAME = "@Adey_support"  # Replace with actual admin username

REQUIRED_CHANNELS = [
    {"username": "@Yemesahft_Alem", "name": "የመጻሕፍት ዓለም"},
    {"username": "@history_ethiopian", "name": "አስገራሚ ታሪኮች"},
]

CHANNEL_JOIN_REWARD = 0.2
REFERRAL_REWARD = 1

# New configuration variables for advertising system
COST_PER_SUBSCRIBER = 0.5  # $0.10 per subscriber
JOIN_CHANNEL_REWARD = 0.2  # $5 reward for joining a channel


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Database setup
def init_db():
    conn = sqlite3.connect('referral_bot.db')
    cursor = conn.cursor()
    
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            phone_number TEXT,
            referral_code TEXT UNIQUE,
            balance INTEGER DEFAULT 0,
            total_referrals INTEGER DEFAULT 0,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value REAL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referred_id INTEGER UNIQUE,
            earned_amount INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (referrer_id) REFERENCES users (user_id),
            FOREIGN KEY (referred_id) REFERENCES users (user_id)
        )
    ''')
    
    # New tables for advertising system
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS advertisements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            advertiser_id INTEGER,
            type TEXT,
            channel_link TEXT,
            channel_username TEXT,
            desired_subscribers INTEGER,
            current_subscribers INTEGER DEFAULT 0,
            cost REAL,
            is_active BOOLEAN DEFAULT 1,
            is_bot_admin BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (advertiser_id) REFERENCES users (user_id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS channel_joins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            advertisement_id INTEGER,
            user_id INTEGER,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reward_given BOOLEAN DEFAULT 0,
            FOREIGN KEY (advertisement_id) REFERENCES advertisements (id),
            FOREIGN KEY (user_id) REFERENCES users (user_id),
            UNIQUE(advertisement_id, user_id)
        )
    ''')
    
    # New table for withdrawal requests
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS withdrawal_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            amount REAL,
            phone_number TEXT,
            status TEXT DEFAULT 'pending', -- pending, approved, cancelled, completed
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            admin_approved_at TIMESTAMP,
            screenshot_sent BOOLEAN DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')

    # New table for required channels
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS required_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert default required channels if they don't exist
    default_channels = [
        {"username": "@Yemesahft_Alem", "name": "የመጻሕፍት ዓለም"},
        {"username": "@history_ethiopian", "name": "አስገራሚ ታሪኮች"},
    ]
    
    for channel in default_channels:
        cursor.execute('''
            INSERT OR IGNORE INTO required_channels (username, name)
            VALUES (?, ?)
        ''', (channel["username"], channel["name"]))
    
    conn.commit()
    conn.close()
    load_bot_settings()
    load_required_channels()  # Load channels from database

def load_required_channels():
    """Load required channels from database into global variable"""
    global REQUIRED_CHANNELS
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT username, name FROM required_channels ORDER BY created_at')
    channels = cursor.fetchall()
    conn.close()
    
    REQUIRED_CHANNELS = [{"username": row[0], "name": row[1]} for row in channels]

def get_db_connection():
    return sqlite3.connect('referral_bot.db')

def generate_referral_code(user_id):
    return f"REF{user_id}{secrets.token_hex(3).upper()}"


def load_bot_settings():
    """Load bot settings from database into global variables"""
    global MIN_WITHDRAWAL, COST_PER_SUBSCRIBER, JOIN_CHANNEL_REWARD, REFERRAL_REWARD
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT key, value FROM bot_settings')
    settings = cursor.fetchall()
    conn.close()
    
    for key, value in settings:
        if key == 'MIN_WITHDRAWAL':
            MIN_WITHDRAWAL = value
        elif key == 'COST_PER_SUBSCRIBER':
            COST_PER_SUBSCRIBER = value
        elif key == 'JOIN_CHANNEL_REWARD':
            JOIN_CHANNEL_REWARD = value
        elif key == 'REFERRAL_REWARD':
            REFERRAL_REWARD = value

def update_bot_setting(key: str, value: float):
    """Update a bot setting in the database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO bot_settings (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
    ''', (key, value))
    
    conn.commit()
    conn.close()
    
    # Reload settings to update global variables
    load_bot_settings()

async def set_min_withdrawal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set minimum withdrawal amount"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "Usage: /set_min_withdrawal <amount>\n\n"
            "Example: <code>/set_min_withdrawal 25</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        global MIN_WITHDRAWAL
        MIN_WITHDRAWAL = float(context.args[0])
        await update.message.reply_text(f"✅ Minimum withdrawal amount set to {MIN_WITHDRAWAL} ብር")
        
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number.")

async def set_cost_per_subscriber(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set cost per subscriber for advertising"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "Usage: /set_cost_per_subscriber <amount>\n\n"
            "Example: <code>/set_cost_per_subscriber 0.75</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        global COST_PER_SUBSCRIBER
        COST_PER_SUBSCRIBER = float(context.args[0])
        await update.message.reply_text(f"✅ Cost per subscriber set to {COST_PER_SUBSCRIBER} ብር")
        
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number.")

async def set_join_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set channel join reward amount"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "Usage: /set_join_reward <amount>\n\n"
            "Example: <code>/set_join_reward 0.3</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        global JOIN_CHANNEL_REWARD
        JOIN_CHANNEL_REWARD = float(context.args[0])
        await update.message.reply_text(f"✅ Channel join reward set to {JOIN_CHANNEL_REWARD} ብር")
        
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number.")

async def set_referral_reward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set referral reward amount"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "Usage: /set_referral_reward <amount>\n\n"
            "Example: <code>/set_referral_reward 1.5</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        global REFERRAL_REWARD
        REFERRAL_REWARD = float(context.args[0])
        await update.message.reply_text(f"✅ Referral reward set to {REFERRAL_REWARD} ብር")
        
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid number.")

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current bot settings"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    text = (
        "⚙️ <b>Current Bot Settings</b>\n\n"
        f"💰 <b>Minimum Withdrawal:</b> {MIN_WITHDRAWAL} ብር\n"
        f"📢 <b>Cost Per Subscriber:</b> {COST_PER_SUBSCRIBER} ብር\n"
        f"🎯 <b>Channel Join Reward:</b> {JOIN_CHANNEL_REWARD} ብር\n"
        f"👥 <b>Referral Reward:</b> {REFERRAL_REWARD} ብር\n\n"
        "<b>Commands to change:</b>\n"
        "<code>/set_min_withdrawal &lt;amount&gt;</code>\n"
        "<code>/set_cost_per_subscriber &lt;amount&gt;</code>\n"
        "<code>/set_join_reward &lt;amount&gt;</code>\n"
        "<code>/set_referral_reward &lt;amount&gt;</code>\n\n"
        "<i>Note: Changes will reset when bot restarts</i>"
    )
    
    await update.message.reply_text(text, parse_mode="HTML")

async def pending_withdrawals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show all pending withdrawal requests with copyable phone numbers"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT wr.id, wr.amount, wr.phone_number, u.username, u.first_name, wr.created_at
        FROM withdrawal_requests wr
        JOIN users u ON wr.user_id = u.user_id
        WHERE wr.status = 'pending'
        ORDER BY wr.created_at DESC
    ''')
    pending_requests = cursor.fetchall()
    conn.close()
    
    if not pending_requests:
        await update.message.reply_text("✅ No pending withdrawal requests.")
        return
    
    # Send each request as a separate message for easy copying
    for req in pending_requests:
        req_id, amount, phone, username, first_name, created = req
        user_display = f"@{username}" if username else (first_name or f"User")
        created_date = created[:16] if created else "Unknown"
        
        # Format phone number in code block for easy copying
        phone_formatted = f"<code>{phone}</code>"
        
        message_text = (
            f"⏳ <b>Pending Withdrawal #{req_id}</b>\n\n"
            f"👤 User: {user_display}\n"
            f"💰 Amount: {amount} birr\n"
            f"📱 Phone: {phone_formatted}\n"
            f"🕒 Created: {created_date}\n\n"
            f"<i>Tap and hold the phone number to copy</i>"
        )
        
        await update.message.reply_text(
            message_text,
            parse_mode="HTML"
        )
    
    # Send summary
    await update.message.reply_text(
        f"📊 <b>Summary</b>\n\n"
        f"Total pending withdrawals: {len(pending_requests)}\n"
        f"Total amount: {sum(req[1] for req in pending_requests)} birr",
        parse_mode="HTML"
    )

async def check_channel_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    for channel in REQUIRED_CHANNELS:
        try:
            member = await context.bot.get_chat_member(channel["username"], user_id)
            if member.status in ['left', 'kicked']:
                return False, channel
        except Exception as e:
            logging.error(f"Error checking channel {channel['username']}: {e}")
            return False, channel
    
    return True, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    referral_code = None
    
    if context.args:
        referral_code = context.args[0]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user.id,))
    user_exists = cursor.fetchone()
    
    if not user_exists:
        referral_code_new = generate_referral_code(user.id)
        cursor.execute('''
            INSERT INTO users (user_id, username, first_name, last_name, referral_code)
            VALUES (?, ?, ?, ?, ?)
        ''', (user.id, user.username, user.first_name, user.last_name, referral_code_new))
        
        # Save referral info, but don't reward yet
        if referral_code:
            cursor.execute('SELECT user_id FROM users WHERE referral_code = ?', (referral_code,))
            referrer = cursor.fetchone()
            
            if referrer:
                referrer_id = referrer[0]
                # Save referral with earned_amount = 0 (not yet rewarded)
                cursor.execute('''
                    INSERT OR IGNORE INTO referrals (referrer_id, referred_id, earned_amount)
                    VALUES (?, ?, 0)
                ''', (referrer_id, user.id))

    conn.commit()
    conn.close()
    
    is_member, channel = await check_channel_membership(update, context)
    
    if not is_member:
        await show_channel_requirements(update, context)
        return
    
    await show_main_menu(update, context)



async def approve_advertisement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    # Example: Just respond with a message (you can expand this logic)
    await update.message.reply_text("✅ Advertisement approved (placeholder function).")

async def change_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET phone_number = NULL WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(
        "📱 Your registered phone number has been cleared.\n\n"
        "Please share your new phone number using the contact button:",
    )
    
    # Reuse your phone number sharing logic
    contact_button = KeyboardButton("📱 Share Phone Number", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "Click the button below to send your new phone number:",
        reply_markup=reply_markup
    )

async def edit_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Allow user to edit their own phone number"""
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT phone_number FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    
    if result and result[0]:
        old_phone = result[0]
        await update.message.reply_text(
            f"📱 Your current phone number is: <code>{old_phone}</code>\n\n"
            f"To change it, click the button below to share your new phone number:",
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            "You don't have a phone number saved yet.\n\n"
            "Please share your phone number using the button below:"
        )
    
    # Show contact sharing button
    contact_button = KeyboardButton("📱 Share Phone Number", request_contact=True)
    reply_markup = ReplyKeyboardMarkup([[contact_button]], resize_keyboard=True, one_time_keyboard=True)
    await update.message.reply_text(
        "Click the button below to send your phone number:",
        reply_markup=reply_markup
    )

async def add_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only allow the admin to use this command
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /add_money <user_id OR @username> <amount>\n\n"
            "Examples:\n"
            "<code>/add_money 123456789 50</code>\n"
            "<code>/add_money @username 100</code>",
            parse_mode="HTML"
        )
        return
    
    user_identifier = context.args[0]
    
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid amount.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if input is username (starts with @) or user ID
    if user_identifier.startswith('@'):
        # Search by username (remove the @)
        username = user_identifier[1:]
        cursor.execute("SELECT user_id, username FROM users WHERE username = ?", (username,))
    else:
        # Search by user ID
        try:
            user_id = int(user_identifier)
            cursor.execute("SELECT user_id, username FROM users WHERE user_id = ?", (user_id,))
        except ValueError:
            await update.message.reply_text("❌ Please provide a valid user ID or @username.")
            conn.close()
            return

    user = cursor.fetchone()

    if not user:
        await update.message.reply_text(f"❌ No user found with identifier: {user_identifier}")
        conn.close()
        return

    user_id, username = user

    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    
    if cursor.rowcount == 0:
        await update.message.reply_text(f"❌ Error updating balance for user {user_identifier}.")
    else:
        conn.commit()
        await update.message.reply_text(f"✅ Added {amount} ብር to @{username if username else 'N/A'} (ID: {user_id})'s balance.")
        try:
            await context.bot.send_message(user_id, f"💰 አድሚን {amount} ያህል ብር ወደ balance አስገብቶሎታል")
        except:
            pass  # Ignore if we can't message the user
    
    conn.close()

async def remove_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only allow the admin to use this command
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /remove_money <user_id OR @username> <amount>\n\n"
            "Examples:\n"
            "<code>/remove_money 123456789 20</code>\n"
            "<code>/remove_money @username 50</code>",
            parse_mode="HTML"
        )
        return
    
    user_identifier = context.args[0]
    
    try:
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid user_id/username and amount.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if input is username (starts with @) or user ID
    if user_identifier.startswith('@'):
        # Search by username (remove the @)
        username = user_identifier[1:]
        cursor.execute("SELECT user_id, username, balance FROM users WHERE username = ?", (username,))
    else:
        # Search by user ID
        try:
            user_id = int(user_identifier)
            cursor.execute("SELECT user_id, username, balance FROM users WHERE user_id = ?", (user_id,))
        except ValueError:
            await update.message.reply_text("❌ Please provide a valid user ID or @username.")
            conn.close()
            return

    result = cursor.fetchone()

    if not result:
        await update.message.reply_text(f"❌ No user found with identifier: {user_identifier}.")
        conn.close()
        return

    user_id, username, current_balance = result

    if current_balance < amount:
        await update.message.reply_text(
            f"❌ Cannot remove {amount} ብር. @{username if username else 'N/A'} only has {current_balance} ብር."
        )
        conn.close()
        return

    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ Removed {amount} ብር from @{username if username else 'N/A'} (ID: {user_id})'s balance.")
    try:
        await context.bot.send_message(user_id, f"⚠️ {amount} ብር ከአካውንቶ በአድሚን ተቀንሷል.")
    except:
        pass


async def show_channel_requirements(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    
    for req_channel in REQUIRED_CHANNELS:
        keyboard.append([InlineKeyboardButton(
            f"Join {req_channel['name']}", 
            url=f"https://t.me/{req_channel['username'][1:]}"
        )])
    
    keyboard.append([InlineKeyboardButton("✅ I've Joined All Channels", callback_data="check_membership")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "📢 ይህንን ቦት ለመጠቀም እባክዎ መጀመርያ ከታች ያሉትን ቻናሎች ይቀላቀሉ:\n\n" +
        "\n".join([f"• {ch['name']} ({ch['username']})" for ch in REQUIRED_CHANNELS]) +
        "\n\nከተቀላቀሉ በኋላ ✅ I've Joined All Channels የሚለውን ይጫኑ ",
        reply_markup=reply_markup
    )

async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    is_member, channel = await check_channel_membership(update, context)
    
    if not is_member:
        await query.edit_message_text(
            f"❌ ሁሉንም ቻናል አልተቀላቀሉም። እባክዎ ለመቀላቀል /start ብለው ይላኩ።"
        )
        return
    
    user_id = query.from_user.id
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if this user was referred by someone
    cursor.execute('SELECT referrer_id, earned_amount FROM referrals WHERE referred_id = ?', (user_id,))
    referral = cursor.fetchone()
    
    if referral:
        referrer_id, earned_amount = referral
        # Only give reward if not already given
        if earned_amount == 0:
            cursor.execute('UPDATE referrals SET earned_amount = ? WHERE referred_id = ?', (REFERRAL_REWARD, user_id))
            cursor.execute('UPDATE users SET balance = balance + ?, total_referrals = total_referrals + 1 WHERE user_id = ?', (REFERRAL_REWARD, referrer_id))
            
            try:
                await context.bot.send_message(
                    referrer_id,
                    f"🎉 እንኳን ደስ አሎት፣ {REFERRAL_REWARD} ብር ከ referral አግኝተዋል!"
                )
            except Exception as e:
                logging.error(f"Could not notify referrer: {e}")
    
    conn.commit()
    conn.close()
    
    await query.edit_message_text("✅ Great! You've joined all required channels.")
    await show_main_menu_from_callback(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT balance, total_referrals, referral_code FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        balance, referrals, ref_code = user_data
        referral_link = f"https://t.me/{context.bot.username}?start={ref_code}"
        
        # Updated reply keyboard with new buttons
        keyboard = [
            ["➕ Join Channel", "👥 My Referrals"],
            ["💰 My Balance","🏆 Leaderboard","📢 Advertise"],
            ["ℹ️ Help","📤 Share Referral Link"]  # Added Leaderboard button
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        text = f"""
                  <b>🎉 እንኳን ወደ Adey Earning Bot በሰላም መጡ።</b>

ይህ ቦት ቀላል ስራዎችን በመስራት ብር እንዲያገኙ ያስችልዎታል።

📢 Join Channels - ቻቶችን በመቀላቀል በእያንዳንዱ ቻናል {JOIN_CHANNEL_REWARD} ብር ያገኛሉ
👨‍🦰 ሰውን በመጋበዝ - ሰዎችን በመጋበዝ በአንድ ሰው {REFERRAL_REWARD} ብር ያገኛሉ

💰 <b>ያሎት ገንዘብ:</b> {balance} ብር
👥 <b>የጋበዙት ሰው ብዛት:</b> {referrals}

🔗 <b>የእርሶ የመጋበዣ link:</b>
<code>{referral_link}</code>
                     
                        """
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="HTML")

async def show_main_menu_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT balance, total_referrals, referral_code FROM users WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    
    if user_data:
        balance, referrals, ref_code = user_data
        referral_link = f"https://t.me/{context.bot.username}?start={ref_code}"
        
        # Updated reply keyboard with new buttons
        keyboard = [
            ["➕ Join Channel", "👥 My Referrals"],
            ["💰 My Balance","🏆 Leaderboard","📢 Advertise"],
            ["ℹ️ Help","📤 Share Referral Link"] 
        ]
        
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        text = f"""
<b>🎉 እንኳን ወደ Adey Earning Bot በሰላም መጡ።</b>

ይህ ቦት ቀላል ስራዎችን በመስራት ብር እንዲያገኙ ያስችልዎታል።

📢 Join Channels - ቻቶችን በመቀላቀል በእያንዳንዱ ቻናል {JOIN_CHANNEL_REWARD} ብር ያገኛሉ
👨‍🦰 ሰውን በመጋበዝ - ሰዎችን በመጋበዝ በአንድ ሰው {REFERRAL_REWARD} ብር ያገኛሉ

💰 <b>ያሎት ገንዘብ:</b> {balance} ብር
👥 <b>የጋበዙት ሰው ብዛት:</b> {referrals}

🔗 <b>የእርሶ የመጋበዣ link:</b>
<code>{referral_link}</code>
        """
        
        await context.bot.send_message(user_id, text, reply_markup=reply_markup, parse_mode="HTML")

# Handle reply button presses
async def handle_reply_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if not await check_membership_decorator(update, context):
        return

    if text == "📤 Share Referral Link":
        await share_referral_link(update, context)
    
    elif text == "💰 My Balance":
        await show_balance(update, context)
    
    elif text == "👥 My Referrals":
        await show_referrals(update, context)
    
    elif text == "ℹ️ Help":
        await show_help(update, context)
    
    elif text == "🏆 Leaderboard":  # Added Leaderboard handler
        await show_leaderboard(update, context)
    
    elif text == "📢 Advertise":
        await start_advertisement(update, context)
    
    elif text == "➕ Join Channel":
        await show_joinable_channels(update, context)  # Updated to use new function
    
    else:
        await show_main_menu(update, context)

async def check_membership_decorator(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check channel membership before proceeding with any command"""
    user_id = update.effective_user.id
    
    # Skip check for admin
    if user_id == ADMIN_ID:
        return True
        
    is_member, channel = await check_channel_membership(update, context)
    
    if not is_member:
        await show_channel_requirements(update, context)
        return False
        
    return True

# Balance and withdrawal system functions
async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_membership_decorator(update, context):
        return
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT balance, phone_number FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        await update.message.reply_text("❌ User not found in database.")
        return
    
    balance, phone_number = result
    
    # If user doesn't have a phone number, ask for it using contact sharing
    if not phone_number:
        # Create a keyboard with a button that requests contact sharing
        contact_button = KeyboardButton("📱 Share Phone Number", request_contact=True)
        keyboard = [[contact_button]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        # Fixed message - removed problematic Markdown
        message_text = (
            "📱 እባክዎን 'Share Phone Number' የሚለውን በመጫን ስልክ ቁጥሮን ያጋሩን። \n\n"
            "በሚልኩልን ስልክ ቁጥር ነው ክፍያዎን የምናስተላልፍሎት."
        )
        
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup
            # Removed parse_mode parameter
        )
        return
    
    # User has phone number, show balance options
    keyboard = [
        ["💳 Withdraw", "💰 Deposit"],
        ["📊 Main Menu"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    # Fixed message for balance display
    message_text = (
        f"💰 ያሎት ገንዘብ: {balance} ብር\n\n"
        f"የተመዘገበው ስልክቁጥር: {phone_number}\n"
        f"ገንዘብ ማውጣት የሚችሉት በዚህ የቴሌብር ቁጥር ብቻ ነው\n\n"
        f"ቁጥሮን ለመቀየር ከፈለጉ ያናግሩን {ADMIN_USERNAME}"
    )
    
    await update.message.reply_text(
        message_text,
        reply_markup=reply_markup
        # Removed parse_mode parameter
    )

async def handle_phone_number_sharing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    # Check if user has contact sharing
    if update.message.contact:
        phone_number = update.message.contact.phone_number
        
        # Check if phone number already exists for another user
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM users WHERE phone_number = ? AND user_id != ?', (phone_number, user_id))
        existing_user = cursor.fetchone()
        
        if existing_user:
            await update.message.reply_text(
                "❌ This phone number is already registered to another user. "
                "Please contact admin if this is an error.",
                reply_markup=ReplyKeyboardRemove()
            )
            conn.close()
            return
        
        # Get current balance before saving phone number
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        current_balance = result[0] if result else 0
        
        # Save phone number to database
        cursor.execute('UPDATE users SET phone_number = ? WHERE user_id = ?', (phone_number, user_id))
        conn.commit()
        conn.close()
        
        # Show balance information after saving phone number
        keyboard = [
            ["💳 Withdraw", "💰 Deposit"],
            ["📊 Main Menu"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        # FIXED: Use HTML formatting and parse_mode
        message_text = (
            f"✅ ስልክቁጥሮት ተመዝግቧል!\n\n"
            f"💰 <b>ያሎት ገንዘብ:</b> {current_balance} ብር\n"
            f"<b>የተመዘገበው ስልክቁጥር:</b> {phone_number}\n"
            f"<i>በዚህ የቴሌብር ስልክቁጥር ብቻ ነው ገንዘብ ማውጣት የሚችሉት</i>\n\n"
            f"<i>ስልክቁጥሮን መቀየር ከፈለጉ ያናግሩን</i> {ADMIN_USERNAME}\n\n"
            f"Choose an option:"
        )
        
        await update.message.reply_text(
            message_text,
            parse_mode='HTML',  # Changed to HTML
            reply_markup=reply_markup
        )
    else:
        # User clicked the button but didn't share contact
        await update.message.reply_text(
            "እባክዎን 'Share Phone Number' የሚለውን በመጫን ስልክቁጥሮን ያጋሩን። በዚህ ስልክ ቁጥር ነው ክፍያዎን የምናስተላልፍሎት."
        )

async def show_balance_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    conn.close()
    
    keyboard = [
        ["💳 Withdraw", "💰 Deposit"],
        ["📊 Main Menu"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"💰 <b>ያሎት ገንዘብ:</b> {balance} ብር\n\n"
        "Choose an option:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def show_balance_options_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    conn.close()
    
    keyboard = [
        ["💳 Withdraw", "💰 Deposit"],
        ["📊 Main Menu"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await context.bot.send_message(
        user_id,
        f"💰 <b>ያሎት ገንዘብ:</b> {balance} ብር\n\n"
        "Choose an option:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def handle_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    conn.close()
    
    if balance < MIN_WITHDRAWAL:
        await update.message.reply_text(
            f"❌ ትንሹ ማውጣት የሚቻለው {MIN_WITHDRAWAL} birr\n\n"
            f"Your current balance: {balance} birr\n"
            f"You need {MIN_WITHDRAWAL - balance} birr more to withdraw.",
            parse_mode="HTML"
        )
        return
    
    keyboard = [
        ["💵 Withdraw All", "🔢 Enter Amount"],
        ["❌ Cancel"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        f"💳 <b>Withdrawal Options</b>\n\n"
        f"ያሎት ገንዘብ: {balance} ብር\n"
        f"ትንሹ ማውጣት የሚችሉት: {MIN_WITHDRAWAL} ብር\n\n"
        f"ቀጥሎ ምረጡ:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    context.user_data['awaiting_withdrawal_amount'] = True

async def handle_withdrawal_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('awaiting_withdrawal_amount'):
        return
    
    text = update.message.text
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    balance = cursor.fetchone()[0]
    conn.close()
    
    if text == "❌ Cancel":
        context.user_data.clear()
        await update.message.reply_text("Withdrawal cancelled.", reply_markup=ReplyKeyboardRemove())
        await show_balance_options(update, context)
        return
    
    if text == "💵 Withdraw All":
        amount = balance
    elif text == "🔢 Enter Amount":
        # Ask user to enter the amount
        await update.message.reply_text(
            "💵 እባክዎ ማውጣት የሚፈልጉትን የገንዘብ መጠን ይጻፉ (20 ፣ 30 ):",
            reply_markup=ReplyKeyboardRemove()
        )
        context.user_data['awaiting_specific_amount'] = True
        return
    else:
        # Check if we're waiting for a specific amount input
        if context.user_data.get('awaiting_specific_amount'):
            try:
                amount = float(text)
                if amount < MIN_WITHDRAWAL:
                    await update.message.reply_text(f"❌ ትንሹ ማውጣት የሚቻለው ገንዘብ {MIN_WITHDRAWAL} ብር ነው።")
                    return
                if amount > balance:
                    await update.message.reply_text(f"❌ Insufficient balance. Your balance is {balance} birr.")
                    return
                # Clear the flag
                context.user_data['awaiting_specific_amount'] = False
            except ValueError:
                await update.message.reply_text("❌ እባክዎ ትክክለኛ ቁጥር ያስገቡ (ምሳሌ :- 20,30)")
                return
        else:
            # If it's not a recognized command, show withdrawal options again
            await handle_withdraw(update, context)
            return
    
    # If we get here, we have a valid amount
    context.user_data['withdrawal_amount'] = amount
    context.user_data['awaiting_withdrawal_amount'] = False
    
    # Ask for confirmation with inline buttons
    keyboard = [
        [InlineKeyboardButton("✅ Confirm Withdrawal", callback_data=f"confirm_withdraw_{amount}")],
        [InlineKeyboardButton("❌ Cancel Withdrawal", callback_data="cancel_withdraw")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"⚠️ <b>Withdrawal Confirmation</b>\n\n"
        f"ማውጥት የሚፈልጉት የገንዘብ መጠን: {amount} ብር\n"
        f"ካወጡ በኋላ የሚቀሮት ገንዘብ: {balance - amount} ብር\n\n"
        f"እርግጠኛ ኖት {amount}ብር ማውጣት ይፈልጋሉ?",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def handle_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"💰 <b>Deposit Money</b>\n\n"
        f"ገንዘብ ወደ ሂሳቦ ለማስገባት ያናግሩን 👉<b>{ADMIN_USERNAME}</b>\n\n"
        f"የፈለጉትን ያህል እናስገባሎታለን",
        parse_mode="HTML"
    )


async def handle_withdrawal_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data.startswith("confirm_withdraw_"):
        amount = float(query.data.replace("confirm_withdraw_", ""))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check balance again
        cursor.execute('SELECT balance, phone_number FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if not result or result[0] < amount:
            await query.edit_message_text("❌ Withdrawal failed. Insufficient balance.")
            conn.close()
            return
        
        balance, phone_number = result
        
        # Create withdrawal request instead of deducting immediately
        cursor.execute('''
            INSERT INTO withdrawal_requests (user_id, amount, phone_number, status)
            VALUES (?, ?, ?, 'pending')
        ''', (user_id, amount, phone_number))
        
        request_id = cursor.lastrowid
        
        # Notify admin with inline buttons
        keyboard = [
            [InlineKeyboardButton("✅ Confirm Request", callback_data=f"admin_confirm_withdraw_{request_id}")],
            [InlineKeyboardButton("❌ Cancel Request", callback_data=f"admin_cancel_withdraw_{request_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"💳 <b>New Withdrawal Request</b>\n\n"
                f"• User: {query.from_user.mention_html()}\n"
                f"• Amount: {amount} birr\n"
                f"📱 Phone: <code>{phone_number}</code>\n"
                f"• User ID: {user_id}\n"
                f"• Request ID: {request_id}\n\n"
                f"Please confirm or cancel this withdrawal request:",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        except Exception as e:
            logging.error(f"Could not notify admin: {e}")
        
        conn.commit()
        conn.close()
        
        await query.edit_message_text(
            f"✅ Withdrawal request submitted!\n\n"
            f"• የገንዘብ መጠን: {amount}  ብር\n"
            f"• የቴሌብር ቁጥር: {phone_number}\n"
            f"• የአሁን የገንዘብ መጠን: {balance} birr\n\n"
            f"⏳ <b>ይህ አሰራር እስከ 24 ሰአት ሊወስድ ይችላል.</b>\n\n"
            f"ገንዘብ ለማውጣት ያቀረቡት ጥያቄ ለadmin ተልኳል።"
            f"ገንዘቦን በ24 ሰአት ይቀበላሉ.\n\n"
            f"ገንዘቦ ሲላክሎት የምናሳውቆት ይሆንናል ፣ እናመሰግናለን !",
            parse_mode="HTML"
        )
        
    elif query.data == "cancel_withdraw":
        await query.edit_message_text("❌ ገንዘብ የማውጣት ሂደቱ ተቋርጣል")
    
    # Show balance options
    await show_balance_options_from_callback(update, context)

# Admin withdrawal handling
async def handle_admin_withdrawal_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("admin_confirm_withdraw_"):
        request_id = int(query.data.replace("admin_confirm_withdraw_", ""))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get withdrawal request details
        cursor.execute('''
            SELECT wr.user_id, wr.amount, u.username, u.phone_number, u.balance 
            FROM withdrawal_requests wr
            JOIN users u ON wr.user_id = u.user_id
            WHERE wr.id = ?
        ''', (request_id,))
        result = cursor.fetchone()
        
        if not result:
            await query.edit_message_text("❌ Withdrawal request not found.")
            conn.close()
            return
        
        user_id, amount, username, phone_number, user_balance = result
        
        # Check if user still has sufficient balance
        if user_balance < amount:
            await query.edit_message_text(
                f"❌ Withdrawal failed. User now has insufficient balance.\n\n"
                f"• Requested: {amount} birr\n"
                f"• Current balance: {user_balance} birr"
            )
            conn.close()
            return
        
        # Update withdrawal request status
        cursor.execute('''
            UPDATE withdrawal_requests 
            SET status = 'approved', admin_approved_at = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (request_id,))
        
        # Deduct the amount from user's balance
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user_id))
        
        conn.commit()
        conn.close()
        
        # Ask admin to send screenshot
        keyboard = [
            [InlineKeyboardButton("📸 Send Payment Screenshot", callback_data=f"admin_send_screenshot_{request_id}")],
            [InlineKeyboardButton("❌ Decline Sending", callback_data=f"admin_decline_screenshot_{request_id}")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ Withdrawal request #{request_id} approved!\n\n"
            f"• User: @{username if username else 'N/A'} (ID: {user_id})\n"
            f"• Amount: {amount} ብር\n"
            f"• የቴሌብር ስልክቁጥር: {phone_number}\n"
            f"• አዲሱ የገንዘብ መጠን: {user_balance - amount} ብር\n\n"
            f"Please send the payment screenshot to the user:",
            reply_markup=reply_markup
        )
        
    elif query.data.startswith("admin_cancel_withdraw_"):
        request_id = int(query.data.replace("admin_cancel_withdraw_", ""))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get withdrawal request details
        cursor.execute('''
            SELECT wr.user_id, wr.amount, u.username 
            FROM withdrawal_requests wr
            JOIN users u ON wr.user_id = u.user_id
            WHERE wr.id = ?
        ''', (request_id,))
        result = cursor.fetchone()
        
        if result:
            user_id, amount, username = result
            
            # Update withdrawal request status
            cursor.execute("UPDATE withdrawal_requests SET status = 'cancelled' WHERE id = ?", (request_id,))
            conn.commit()
            
            # Notify user
            try:
                await context.bot.send_message(
                    user_id,
                    f"❌ Your withdrawal request of {amount} birr has been cancelled by admin.\n\n"
                    f"If you believe this is an error, please contact {ADMIN_USERNAME}."
                )
            except Exception as e:
                logging.error(f"Could not notify user: {e}")
        
        conn.close()
        
        await query.edit_message_text(f"❌ Withdrawal request #{request_id} has been cancelled.")

async def handle_admin_screenshot_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("admin_send_screenshot_"):
        request_id = int(query.data.replace("admin_send_screenshot_", ""))
        
        # Store the request ID in context for the next message
        context.user_data['awaiting_screenshot'] = True
        context.user_data['screenshot_request_id'] = request_id
        
        await query.edit_message_text(
            f"📸 Please send the payment screenshot now.\n\n"
            f"Make sure it includes:\n"
            f"• Amount sent\n"
            f"• Date and time\n"
            f"• Recipient phone number\n"
            f"• Transaction ID (if available)"
        )
        
    elif query.data.startswith("admin_decline_screenshot_"):
        request_id = int(query.data.replace("admin_decline_screenshot_", ""))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get withdrawal request details
        cursor.execute('''
            SELECT wr.user_id, wr.amount, u.username 
            FROM withdrawal_requests wr
            JOIN users u ON wr.user_id = u.user_id
            WHERE wr.id = ?
        ''', (request_id,))
        result = cursor.fetchone()
        
        if result:
            user_id, amount, username = result
            
            # Update withdrawal request status
            cursor.execute("UPDATE withdrawal_requests SET status = 'completed', screenshot_sent = 0 WHERE id = ?", (request_id,))
            conn.commit()
            
            # Notify user that payment was sent but no screenshot
            try:
                await context.bot.send_message(
                    user_id,
                    f"✅ ያመለከቱት የ{amount} ብር ወጪ ተሳክቷል!\n\n"
                    f"💰 የጠየቁት የብር መጠን በቴሌብር አካውንቶ ተልኳል።\n"
                    f"📱 በደቂቃዎች ውስጥ የሚደርሶት ይሆናል\n\n"
                    f"እኛን ስለመረጡ እናመሰግናለን !"
                )
            except Exception as e:
                logging.error(f"Could not notify user: {e}")
        
        conn.close()
        
        await query.edit_message_text(f"✅ Payment processed for request #{request_id} (no screenshot sent).")

async def clear_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only allow the admin to use this command
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /clear_balance <user_id OR @username>\n\n"
            "Examples:\n"
            "<code>/clear_balance 123456789</code>\n"
            "<code>/clear_balance @username</code>",
            parse_mode="HTML"
        )
        return

    user_identifier = context.args[0]

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if input is username (starts with @) or user ID
    if user_identifier.startswith('@'):
        # Search by username (remove the @)
        username = user_identifier[1:]
        cursor.execute("SELECT user_id, username, balance FROM users WHERE username = ?", (username,))
    else:
        # Search by user ID
        try:
            user_id = int(user_identifier)
            cursor.execute("SELECT user_id, username, balance FROM users WHERE user_id = ?", (user_id,))
        except ValueError:
            await update.message.reply_text("❌ Please provide a valid user ID or @username.")
            conn.close()
            return

    result = cursor.fetchone()

    if not result:
        await update.message.reply_text(f"❌ No user found with identifier: {user_identifier}.")
        conn.close()
        return

    user_id, username, old_balance = result

    if old_balance == 0:
        await update.message.reply_text(f"ℹ️ @{username if username else 'N/A'} already has 0 ብር balance.")
        conn.close()
        return

    cursor.execute("UPDATE users SET balance = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(f"✅ Cleared @{username if username else 'N/A'} (ID: {user_id})'s balance (removed {old_balance} ብር).")

    # Notify user (optional)
    try:
        await context.bot.send_message(
            user_id,
            f"⚠️ ገንዘቦ በadmin ወደ 0 ብር ተቀይሯል \nPrevious balance: {old_balance} ብር"
        )
    except:
        pass  # Ignore if the bot can't DM the user


# Handle admin sending screenshot
async def handle_admin_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    
    if not context.user_data.get('awaiting_screenshot'):
        return
    
    request_id = context.user_data.get('screenshot_request_id')
    
    if not request_id:
        await update.message.reply_text("❌ No active screenshot request found.")
        return
    
    # Check if it's a photo
    if not update.message.photo:
        await update.message.reply_text("❌ Please send a valid photo/screenshot.")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get withdrawal request details
    cursor.execute('''
        SELECT wr.user_id, wr.amount, u.username, u.phone_number
        FROM withdrawal_requests wr
        JOIN users u ON wr.user_id = u.user_id
        WHERE wr.id = ?
    ''', (request_id,))
    result = cursor.fetchone()
    
    if not result:
        await update.message.reply_text("❌ Withdrawal request not found.")
        conn.close()
        return
    
    user_id, amount, username, phone_number = result
    
    # Get the photo file ID (use the largest version)
    photo_file_id = update.message.photo[-1].file_id
    
    # Create confirmation keyboard for admin
    keyboard = [
        [InlineKeyboardButton("✅ Send to User", callback_data=f"confirm_send_screenshot_{request_id}")],
        [InlineKeyboardButton("❌ Don't Send", callback_data=f"cancel_send_screenshot_{request_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Store the photo file ID in context for later use
    context.user_data['screenshot_file_id'] = photo_file_id
    
    await update.message.reply_text(
        f"📸 Screenshot received!\n\n"
        f"• User: @{username if username else 'N/A'} (ID: {user_id})\n"
        f"• Amount: {amount} birr\n"
        f"• Phone: {phone_number}\n\n"
        f"Send this screenshot to the user?",
        reply_markup=reply_markup
    )
    
    # Clear the awaiting state
    context.user_data['awaiting_screenshot'] = False
    conn.close()

async def user_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ይህንን ለመጠቀም ስልጣን የሎትም")
        return

    if len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /user_stats <user_id OR @username>\n\n"
            "Examples:\n"
            "<code>/user_stats 123456789</code>\n"
            "<code>/user_stats @username</code>",
            parse_mode="HTML"
        )
        return

    user_identifier = context.args[0]
    
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if input is username (starts with @) or user ID
    if user_identifier.startswith('@'):
        # Search by username (remove the @)
        username = user_identifier[1:]
        cursor.execute("""
            SELECT user_id, username, first_name, last_name, phone_number, balance, total_referrals, referral_code, joined_at
            FROM users WHERE username = ?
        """, (username,))
    else:
        # Search by user ID
        try:
            user_id = int(user_identifier)
            cursor.execute("""
                SELECT user_id, username, first_name, last_name, phone_number, balance, total_referrals, referral_code, joined_at
                FROM users WHERE user_id = ?
            """, (user_id,))
        except ValueError:
            await update.message.reply_text("❌ Please provide a valid user ID or @username.")
            conn.close()
            return

    user = cursor.fetchone()

    if not user:
        await update.message.reply_text(f"❌ No user found with identifier: {user_identifier}")
        conn.close()
        return

    user_id, username, first_name, last_name, phone_number, balance, total_referrals, referral_code, joined_at = user

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(earned_amount), 0) FROM referrals WHERE referrer_id = ?", (user_id,))
    referral_count, total_earned = cursor.fetchone()

    cursor.execute("SELECT COUNT(*), COALESCE(SUM(cost), 0) FROM advertisements WHERE advertiser_id = ?", (user_id,))
    ad_count, total_spent = cursor.fetchone()

    cursor.execute("""
        SELECT status, COUNT(*), COALESCE(SUM(amount), 0)
        FROM withdrawal_requests 
        WHERE user_id = ? 
        GROUP BY status
    """, (user_id,))
    withdrawal_stats = cursor.fetchall()
    withdrawal_summary = "\n".join(
        [f"• {status}: {count} (Total: {total:.2f} birr)" for status, count, total in withdrawal_stats]
    ) or "None"

    total_withdrawn = sum(total for status, _, total in withdrawal_stats if status == "completed")
    conn.close()

    text = (
        f"📊 <b>User Statistics</b>\n\n"
        f"👤 <b>Name:</b> {first_name or ''} {last_name or ''}\n"
        f"🔗 <b>Username:</b> @{username if username else 'N/A'}\n"
        f"🆔 <b>User ID:</b> {user_id}\n"
        f"📱 <b>Phone:</b> {phone_number or 'Not set'}\n"
        f"🪪 <b>Referral Code:</b> <code>{referral_code}</code>\n"
        f"📅 <b>Joined:</b> {joined_at}\n\n"
        f"💰 <b>Balance:</b> {balance:.2f} birr\n"
        f"👥 <b>Referrals:</b> {total_referrals} (actual: {referral_count})\n"
        f"💵 <b>Total Earned from Referrals:</b> {total_earned:.2f} birr\n"
        f"📢 <b>Advertisements:</b> {ad_count}\n"
        f"💸 <b>Total Spent on Ads:</b> {total_spent:.2f} birr\n\n"
        f"💳 <b>Withdrawal Requests:</b>\n{withdrawal_summary}\n\n"
        f"✅ <b>Total Withdrawn:</b> {total_withdrawn:.2f} birr"
    )

    await update.message.reply_text(text, parse_mode="HTML")

async def ads_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ ይህንን ለመጠቀም ስልጣን የሎትም ")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Running ads
    cursor.execute("""
        SELECT id, channel_username, desired_subscribers, current_subscribers, cost, created_at
        FROM advertisements
        WHERE is_active = 1
        ORDER BY created_at DESC
    """)
    running_ads = cursor.fetchall()

    # Expired ads count
    cursor.execute("SELECT COUNT(*) FROM advertisements WHERE is_active = 0")
    expired_ads = cursor.fetchone()[0]

    # Total ads count
    cursor.execute("SELECT COUNT(*) FROM advertisements")
    total_ads = cursor.fetchone()[0]

    conn.close()

    # Build response
    if running_ads:
        ads_list = "\n\n".join(
            [
                f"🆔 <b>Ad ID:</b> {ad[0]}\n"
                f"📢 <b>Channel:</b> @{ad[1]}\n"
                f"👥 <b>Subscribers:</b> {ad[3]}/{ad[2]}\n"
                f"💵 <b>Cost:</b> {ad[4]:.2f} birr\n"
                f"📅 <b>Created:</b> {ad[5][:10]}"
                for ad in running_ads
            ]
        )
    else:
        ads_list = "No running ads found."

    text = (
        "📊 <b>Advertisement Stats</b>\n\n"
        f"✅ Running Ads: {len(running_ads)}\n"
        f"❌ Expired Ads: {expired_ads}\n"
        f"📢 Total Ads: {total_ads}\n\n"
        f"<b>Running Ads Details:</b>\n\n{ads_list}"
    )

    await update.message.reply_text(text, parse_mode="HTML")

async def remove_ad(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if len(context.args) < 1:
        await update.message.reply_text(
            "Usage: /remove_ad <ad_id>\n\nExample: <code>/remove_ad 5</code>",
            parse_mode="HTML"
        )
        return

    try:
        ad_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Please provide a valid advertisement ID.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Check if ad exists
    cursor.execute("SELECT channel_username, is_active FROM advertisements WHERE id = ?", (ad_id,))
    ad = cursor.fetchone()
    if not ad:
        await update.message.reply_text("❌ No advertisement found with this ID.")
        conn.close()
        return

    username, is_active = ad

    # Mark as inactive
    cursor.execute("UPDATE advertisements SET is_active = 0 WHERE id = ?", (ad_id,))
    conn.commit()
    conn.close()

    await update.message.reply_text(
        f"🗑 Advertisement for @{username} (ID: {ad_id}) has been removed from join channels."
    )

async def handle_screenshot_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("confirm_send_screenshot_"):
        request_id = int(query.data.replace("confirm_send_screenshot_", ""))
        photo_file_id = context.user_data.get('screenshot_file_id')
        
        if not photo_file_id:
            await query.edit_message_text("❌ No screenshot found to send.")
            return
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get withdrawal request details
        cursor.execute('''
            SELECT wr.user_id, wr.amount, u.username, u.phone_number
            FROM withdrawal_requests wr
            JOIN users u ON wr.user_id = u.user_id
            WHERE wr.id = ?
        ''', (request_id,))
        result = cursor.fetchone()
        
        if not result:
            await query.edit_message_text("❌ Withdrawal request not found.")
            conn.close()
            return
        
        user_id, amount, username, phone_number = result
        
        # Update withdrawal request
        cursor.execute("UPDATE withdrawal_requests SET status = 'completed', screenshot_sent = 1 WHERE id = ?", (request_id,))
        conn.commit()
        conn.close()
        
        # Send screenshot to user
        try:
            await context.bot.send_photo(
                user_id,
                photo=photo_file_id,
                caption=f"✅ ያመለከቱት የ{amount} ብር ወጪ ተሳክቷል!\n\n"
                        f"📸 <b>Payment Confirmation</b>\n"
                        f"• የገንዘብ መጠን: {amount} ብር\n"
                        f"• የቴሌብር ቁጥር: {phone_number}\n"
                        f"• Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
                        f"💰 💰 የጠየቁት የብር መጠን በቴሌብር አካውንቶ ተልኳል።\n"
                        f"📱 በደቂቃዎች ውስጥ የሚደርሶት ይሆናል\n\n"
                        f"እኛን ስለመረጡ እናመሰግናለን !",
                parse_mode="HTML"
            )
            
            await query.edit_message_text("✅ Screenshot sent to user successfully!")
        except Exception as e:
            logging.error(f"Could not send screenshot to user: {e}")
            await query.edit_message_text("❌ Failed to send screenshot to user.")
    
    elif query.data.startswith("cancel_send_screenshot_"):
        request_id = int(query.data.replace("cancel_send_screenshot_", ""))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Update withdrawal request (completed but no screenshot sent)
        cursor.execute("UPDATE withdrawal_requests SET status = 'completed', screenshot_sent = 0 WHERE id = ?", (request_id,))
        conn.commit()
        conn.close()
        
        await query.edit_message_text("❌ Screenshot not sent to user.")

# Handle callback queries
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    
    # Check membership for main menu actions (skip for channel joining flows)
    if (user_id != ADMIN_ID and 
        not query.data.startswith("verify_join_") and 
        not query.data.startswith("join_channel_") and
        query.data != "check_membership"):
        
        if not await check_membership_decorator(update, context):
            return
    
    if query.data == "check_membership":
        await check_membership(update, context)
    elif query.data.startswith("join_channel_"):
        await handle_join_channel(update, context)
    elif query.data in ["confirm_broadcast", "cancel_broadcast"]:
        await handle_broadcast_confirmation(update, context)
    elif query.data.startswith("verify_join_"):
        await verify_channel_join(update, context)
    elif query.data == "main_menu":
        await show_main_menu_from_callback(update, context)
    elif query.data == "cancel_join_channels" or query.data == "cancel_join":
        await cancel_join_channels(update, context)
    elif query.data == "show_next_channel":  # ADD THIS LINE
        await show_next_channel(update, context)
    elif query.data == "refresh_leaderboard":  # Added leaderboard refresh handler
        await refresh_leaderboard(update, context)
    elif query.data in ["confirm_ad", "cancel_ad"]:
        await handle_advertisement_confirmation(update, context)
    elif query.data.startswith("confirm_withdraw_") or query.data == "cancel_withdraw":
        await handle_withdrawal_confirmation(update, context)
    elif query.data.startswith("admin_confirm_withdraw_") or query.data.startswith("admin_cancel_withdraw_"):
        await handle_admin_withdrawal_action(update, context)
    elif query.data.startswith("admin_send_screenshot_") or query.data.startswith("admin_decline_screenshot_"):
        await handle_admin_screenshot_action(update, context)
    elif query.data.startswith("confirm_send_screenshot_") or query.data.startswith("cancel_send_screenshot_"):
        await handle_screenshot_confirmation(update, context)

# Handle text messages for all flows - FIXED VERSION
async def handle_text_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if (user_id != ADMIN_ID and 
        not context.user_data.get('awaiting_admin_confirmation') and
        not context.user_data.get('awaiting_link') and
        text not in ["❌ Cancel"]):
        
        if not await check_membership_decorator(update, context):
            return
    
    # First, check if it's one of the main menu buttons
    # Update this line in handle_text_messages function:
    main_menu_buttons = ["📤 Share Referral Link", "💰 My Balance", "👥 My Referrals", "📢 Advertise", "➕ Join Channel", "🏆 Leaderboard", "ℹ️ Help"]
    
    if text in main_menu_buttons:
        # Clear any ongoing flows
        if user_id != ADMIN_ID:
            context.user_data.clear()
        
        # Handle the main menu button
        await handle_reply_buttons(update, context)
        return
        
    # Handle cancellation first
    if text == "❌ Cancel":
        context.user_data.clear()
        await show_main_menu(update, context)
        return
        
    # Handle balance options
    if text in ["💳 Withdraw", "💰 Deposit", "💵 Withdraw All", "🔢 Enter Amount", "❌ Cancel", "📊 Main Menu"]:
        if text == "💳 Withdraw":
            await handle_withdraw(update, context)
        elif text == "💰 Deposit":
            await handle_deposit(update, context)
        elif text == "📊 Main Menu":
            context.user_data.clear()
            await show_main_menu(update, context)
        elif text in ["💵 Withdraw All", "🔢 Enter Amount", "❌ Cancel"]:
            await handle_withdrawal_amount(update, context)
        return
    
    # Handle specific amount input for withdrawal
    if context.user_data.get('awaiting_specific_amount'):
        await handle_withdrawal_amount(update, context)
        return
    
    # Handle advertisement flow states
    if context.user_data.get('awaiting_ad_type'):
        if text in ["📺 Channel"]:
            ad_type = text.replace("📺 ", "").lower()
            context.user_data['ad_type'] = ad_type
            context.user_data['awaiting_ad_type'] = False
            
            type_names = {
                "channel": "Telegram Channel"
            }
            
            keyboard = [["❌ Cancel"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            
            await update.message.reply_text(
                f"✅ የመረጡት: <b>{type_names[ad_type]}</b>\n\n"
                f"በመጀመሪያ ማስተዋወቅ የሚፈልጉት {type_names[ad_type].lower()} ላይ ይህን Bot Admin ያድርጉ።\n\n🔗 ከዛ የቻነሉን Link/Username ያስገቡ:",
                parse_mode="HTML",
                reply_markup=reply_markup
            )
            
            context.user_data['awaiting_link'] = True
            return
        elif text == "❌ Cancel":
            context.user_data.clear()
            await show_main_menu(update, context)
            return
        else:
            await update.message.reply_text("Please select one of the options above:")
            return
    
    if context.user_data.get('awaiting_admin_confirmation'):
        if text == "✅ I've Made Bot Admin":
            await check_bot_admin_status(update, context)
            return
        elif text == "❌ Cancel":
            context.user_data.clear()
            await show_main_menu(update, context)
            return
        else:
            await update.message.reply_text("Please confirm you've made the bot admin or cancel:")

    # Handle advertisement link input
    if context.user_data.get('awaiting_link'):
        await handle_advertisement_link(update, context)
        return
    
    # Handle subscriber count input
    if context.user_data.get('awaiting_subscribers'):
        await handle_desired_subscribers(update, context)
        return
    
    # Handle withdrawal amount input
    if context.user_data.get('awaiting_withdrawal_amount'):
        await handle_withdrawal_amount(update, context)
        return
    
    # If it's not a recognized command, show the main menu
    await show_main_menu(update, context)

async def share_referral_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_membership_decorator(update, context):
        return
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT referral_code FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        await update.message.reply_text("❌ User not found in database.")
        return
    
    ref_code = result[0]
    referral_link = f"https://t.me/{context.bot.username}?start={ref_code}"
    
    keyboard = [[InlineKeyboardButton("📤 Share Message", 
                 url=f"https://t.me/share/url?url={referral_link}&text=Join%20this%20awesome%20bot!")]]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"<b>የእርሶ የመጋበዣ link:</b>\n<code>{referral_link}</code>\n\nClick below to share:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def show_referrals(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_membership_decorator(update, context):
        return
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.first_name, u.username, r.created_at 
        FROM referrals r 
        JOIN users u ON r.referred_id = u.user_id 
        WHERE r.referrer_id = ?
    ''', (user_id,))
    referrals = cursor.fetchall()
    
    cursor.execute('SELECT total_referrals FROM users WHERE user_id = ?', (user_id,))
    total_refs = cursor.fetchone()[0]
    conn.close()
    
    if referrals:
        ref_list = []
        for ref in referrals:
            first_name = ref[0] or "Unknown"
            username = ref[1] or "no_username"
            date = ref[2][:10] if ref[2] else "Unknown date"
            
            ref_list.append(f"• {first_name} (@{username}) - {date}")
        
        text = f"👥 <b>የጋበዟቸው ሰዎች (Total: {total_refs}):</b>\n\n" + "\n".join(ref_list)
    else:
        text = "እስካሁን ማንንም አልጋበዙም ፣ ሲጋብዙ እዚህ ጋር የሚያሳይ ይሆናል!"
    
    await update.message.reply_text(text, parse_mode="HTML")

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_membership_decorator(update, context):
        return
    help_text = f"""
        🤖 <b>ይህንን ቦት እንዴት መጠቀም እንደሚችሉ:</b>

1. <b>የመጋበዣ link በማጋራት</b>: የራሶት ልዩ የሆነውን የመጋበዛ ሊንክ ለሰዎች ሲያጋሩ በእያንዳንዱ ሰው 1 ብር ያገኛሉ ። ብዙ ባጋሩ ቁጥር ብዙ ገንዘብ ያገኛሉ
2. <b>ቻናሎችን በመቀላቀል</b>: ቻናሎችን በመቀላቀል {CHANNEL_JOIN_REWARD} ብር ከአንድ ቻናል ያገኛሉ 
3. <b>Advertise</b>:እዚህ ቦት ላይ ቻናሎትን ማስተዋወቅ ይችላሉ
        
       እርዳታ ይፈልጋሉ? 👉 {ADMIN_USERNAME}
       ቻናላችንን ይቀላቀሉ 👉 @AdeyChannel
       ግሩፓችንንም ይቀላቀሉ 👉 @AdeyGroup1
    """
    
    await update.message.reply_text(help_text, parse_mode="HTML")

async def channel_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get all channel advertisements
    cursor.execute('''
        SELECT a.id, a.channel_username, a.desired_subscribers, a.current_subscribers, 
               a.cost, a.is_active, u.username, a.created_at
        FROM advertisements a
        LEFT JOIN users u ON a.advertiser_id = u.user_id
        WHERE a.type = 'channel'
        ORDER BY a.created_at DESC
    ''')
    channels = cursor.fetchall()

    # Get total joins and rewards given
    cursor.execute('SELECT COUNT(*) FROM channel_joins')
    total_joins = cursor.fetchone()[0]

    cursor.execute('SELECT COUNT(*) FROM channel_joins WHERE reward_given = 1')
    rewards_given = cursor.fetchone()[0]

    total_rewards = rewards_given * CHANNEL_JOIN_REWARD

    conn.close()

    if not channels:
        await update.message.reply_text("📊 <b>Channel Statistics</b>\n\nNo channel advertisements found.", parse_mode="HTML")
        return

    stats_text = f"📊 <b>Channel Statistics</b>\n\n"
    stats_text += f"<b>Overall:</b>\n"
    stats_text += f"• Total Joins: {total_joins}\n"
    stats_text += f"• Rewards Given: {rewards_given}\n"
    stats_text += f"• Total Rewards: {total_rewards} birr\n\n"

    stats_text += f"<b>Channels:</b>\n"
    for channel in channels:
        ad_id, username, desired, current, cost, is_active, advertiser, created = channel
        status = "✅ Active" if is_active else "❌ Completed"
        progress = f"{current}/{desired}"
        
        stats_text += f"\n<b>@{username}</b> ({status})\n"
        stats_text += f"• Progress: {progress}\n"
        stats_text += f"• Advertiser: @{advertiser or 'N/A'}\n"
        stats_text += f"• Cost: {cost} birr\n"
        stats_text += f"• Created: {created[:10]}\n"

    await update.message.reply_text(stats_text, parse_mode="HTML")


async def start_advertisement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_membership_decorator(update, context):
        return
    keyboard = [
        ["📺 Channel"],
        ["❌ Cancel"]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        "📢 <b>Advertisement System</b>\n\n"
        "ምንድን ነው ማስትተዋወቅ የሚፍልጉት?\n\n"
        "• 📺 <b>Channel</b> - ቻናሎትን ለማስተዋወቅ\n\n"
        "እባክዎ ይምረጡ:",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    context.user_data['awaiting_ad_type'] = True

async def handle_advertisement_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Advertisement link handling - to be implemented")

async def check_bot_admin_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bot admin status check - to be implemented")

async def handle_desired_subscribers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Desired subscribers handling - to be implemented")



def get_next_available_channel(user_id):
    """Get the next available channel that the user hasn't joined yet"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get active advertisements that are channels and haven't reached their goal
    # AND that the user hasn't joined yet
    cursor.execute('''
        SELECT a.id, a.channel_username, a.channel_link, a.desired_subscribers, a.current_subscribers 
        FROM advertisements a
        WHERE a.type = 'channel' 
          AND a.is_active = 1 
          AND a.current_subscribers < a.desired_subscribers
          AND a.id NOT IN (
              SELECT advertisement_id 
              FROM channel_joins 
              WHERE user_id = ?
          )
        LIMIT 1
    ''', (user_id,))
    
    channel = cursor.fetchone()
    conn.close()
    
    return channel


async def show_joinable_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_membership_decorator(update, context):
        return

    user_id = update.effective_user.id

    # Get the correct message object (works for both message + callback_query)
    message = update.message or (update.callback_query and update.callback_query.message)

    # Get the next available channel that user hasn't joined
    channel = get_next_available_channel(user_id)

    if not channel:
        if message:
            await message.reply_text(
                "<b>⛔️አሁን ላይ ምንም ስራ የለም።</b>\n\n"
                "<b>እባክዎ ትንሽ ቆይተው ይሞክሩ። ⏰</b>\n\n",
                parse_mode="HTML"
            )
        return

    ad_id, username, link, desired, current = channel

    keyboard = [
        [InlineKeyboardButton(f"📢 Join @{username}", url=link)],
        [InlineKeyboardButton("✅ I've Joined", callback_data=f"verify_join_{ad_id}")]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    if message:
        await message.reply_text(
            f"📢 <b>ቻናል በመቀላቀል {CHANNEL_JOIN_REWARD} ብር ያግኙ !</b>\n\n"
            f"<b>Channel:</b> @{username}\n"
            f"<b>Reward:</b> {CHANNEL_JOIN_REWARD} ብር\n\n",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )


async def show_next_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    # Get the next available channel
    channel = get_next_available_channel(user_id)
    
    if not channel:
        await query.edit_message_text(
            "🎉 <b>You've joined all available channels!</b>\n\n"
            "There are no more channels available to join at the moment.\n"
            "Check back later for new campaigns!",
            parse_mode="HTML"
        )
        return
    
    ad_id, username, link, desired, current = channel
    
    # Create inline keyboard for this single channel
    keyboard = [
        [InlineKeyboardButton(f"📢 Join @{username}", callback_data=f"join_channel_{ad_id}")],
        [InlineKeyboardButton("➡️ Next Channel", callback_data="show_next_channel")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📢 <b>Join Channel & Earn {CHANNEL_JOIN_REWARD} birr!</b>\n\n"
        f"<b>Channel:</b> @{username}\n"
        f"<b>Progress:</b> {current}/{desired} subscribers\n"
        f"<b>Reward:</b> {CHANNEL_JOIN_REWARD} birr\n\n"
        f"Click the button below to join this channel and earn {CHANNEL_JOIN_REWARD} birr!",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

# Add this function to handle channel joining
async def handle_join_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    ad_id = int(query.data.replace("join_channel_", ""))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get channel details
    cursor.execute('''
        SELECT channel_username, channel_link, desired_subscribers, current_subscribers 
        FROM advertisements 
        WHERE id = ?
    ''', (ad_id,))
    channel = cursor.fetchone()
    
    if not channel:
        await query.edit_message_text("❌ Channel not found or no longer available.")
        conn.close()
        return
    
    username, link, desired, current = channel
    
    # Check if user has already joined this channel
    cursor.execute('''
        SELECT * FROM channel_joins 
        WHERE advertisement_id = ? AND user_id = ?
    ''', (ad_id, query.from_user.id))
    
    already_joined = cursor.fetchone()
    
    if already_joined:
        await query.edit_message_text(
            f"✅ <b>You've already joined this channel!</b>\n\n"
            f"Channel: @{username}\n"
            f"Reward: {CHANNEL_JOIN_REWARD} birr (already claimed)\n\n"
            f"You can check other available channels.",
            parse_mode="HTML"
        )
        conn.close()
        return
    
    # Create join verification keyboard
    keyboard = [
        [InlineKeyboardButton(f"📢 Join @{username}", url=link)],
        [InlineKeyboardButton("✅ I've Joined", callback_data=f"verify_join_{ad_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_join")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        f"📢 <b>መመርያ</b>\n\n"
        f"<b>Channel:</b> @{username}\n"
        f"<b>የሚገኘው የገንዘብ መጠን:</b> {CHANNEL_JOIN_REWARD} ብር\n\n"
        f"<b>አካሄድ:</b>\n"
        f"1. ከታች join @{username} የሚለውን ይጫኑ\n"
        f"2. ቻናሉን join ያድርጉ\n"
        f"3. ሲጨርሱ i've joined የሚለውን ይጫኑ\n\n",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    conn.close()

# Add this function to verify channel joining
# async def verify_channel_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     """Handle 'I've Joined' button press with simple message feedback"""
#     query = update.callback_query
#     await query.answer()
    
#     try:
#         ad_id = int(query.data.replace("verify_join_", ""))
#         user_id = query.from_user.id

#         conn = get_db_connection()
#         cursor = conn.cursor()

#         # Get channel info
#         cursor.execute("SELECT channel_username, channel_link, desired_subscribers, current_subscribers FROM advertisements WHERE id = ?", (ad_id,))
#         ad = cursor.fetchone()

#         if not ad:
#             await query.edit_message_text("❌ Channel not found. It might have expired.")
#             conn.close()
#             return

#         username, link, desired, current = ad

#         # ✅ FIRST: Check if user was already rewarded
#         cursor.execute("SELECT 1 FROM channel_joins WHERE advertisement_id = ? AND user_id = ?", (ad_id, user_id))
#         already_joined = cursor.fetchone()

#         if already_joined:
#             # Send a simple message instead of popup
#             await context.bot.send_message(
#                 user_id,
#                 f"ℹ️ You have already been rewarded for joining @{username}."
#             )
#             conn.close()
#             await show_next_channel(update, context)
#             return

#         # ✅ SECOND: Try to check membership
#         try:
#             member = await context.bot.get_chat_member(f"@{username}", user_id)
            
#             if member.status in ["left", "kicked"]:
#                 # User hasn't joined - send warning message
#                 await context.bot.send_message(
#                     user_id,
#                     f"❌ You haven't joined @{username} yet!\n\n"
#                     f"Please click the 'Join @{username}' button to join the channel first, "
#                     f"then come back and click 'I've Joined' to get your reward."
#                 )
#                 conn.close()
#                 return
                
#             # User HAS joined - proceed with reward
#             user_has_joined = True
            
#         except Exception as e:
#             # If we can't verify membership, assume user needs to join
#             logging.error(f"Error checking membership for @{username}: {e}")
#             await context.bot.send_message(
#                 user_id,
#                 f"⚠️ Could not verify if you joined @{username}.\n\n"
#                 f"Please make sure:\n"
#                 f"1. You've joined the channel\n"
#                 f"2. The channel is public\n"
#                 f"3. Try clicking 'I've Joined' again\n\n"
#                 f"If the problem continues, contact {ADMIN_USERNAME}"
#             )
#             conn.close()
#             return

#         # ✅ THIRD: Reward the user (only if they've joined)
#         try:
#             # Insert join record
#             cursor.execute("""
#                 INSERT INTO channel_joins (advertisement_id, user_id, reward_given)
#                 VALUES (?, ?, 1)
#             """, (ad_id, user_id))

#             # Update ad progress
#             cursor.execute("""
#                 UPDATE advertisements
#                 SET current_subscribers = current_subscribers + 1
#                 WHERE id = ?
#             """, (ad_id,))

#             # Reward user
#             cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (CHANNEL_JOIN_REWARD, user_id))
#             conn.commit()

#             # ✅ SUCCESS - Send success message
#             await context.bot.send_message(
#                 user_id,
#                 f"✅ Success! You earned {CHANNEL_JOIN_REWARD} Birr for joining @{username} 🎉"
#             )
            
#             # Update the original message to show success
#             await query.edit_message_text(
#                 f"✅ <b>Channel Joined Successfully!</b>\n\n"
#                 f"📢 Channel: @{username}\n"
#                 f"💰 Reward Earned: {CHANNEL_JOIN_REWARD} Birr\n\n"
#                 f"<i>Loading next channel...</i>",
#                 parse_mode="HTML"
#             )
            
#         except Exception as e:
#             logging.error(f"Error rewarding user: {e}")
#             await context.bot.send_message(
#                 user_id,
#                 "❌ Error processing your reward. Please contact admin."
#             )
#         finally:
#             conn.close()

#         # ✅ FOURTH: Show next channel
#         await asyncio.sleep(1)  # Small delay for better UX
#         await show_next_channel(update, context)

#     except ValueError:
#         await context.bot.send_message(
#             query.from_user.id,
#             "❌ Invalid channel. Please try again."
#         )
#     except Exception as e:
#         logging.error(f"Error in verify_channel_join: {e}")
#         await context.bot.send_message(
#             query.from_user.id,
#             "❌ An error occurred. Please try again."
#         )

async def verify_channel_join(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    ad_id = int(query.data.replace("verify_join_", ""))

    conn = get_db_connection()
    cursor = conn.cursor()

    # Get channel info
    cursor.execute("SELECT channel_username, channel_link FROM advertisements WHERE id = ?", (ad_id,))
    ad = cursor.fetchone()
    if not ad:
        await query.edit_message_text("❌ Channel not found or no longer active.")
        conn.close()
        return

    username, link = ad

    # Check if user is actually a member
    try:
        member = await context.bot.get_chat_member(f"@{username}", user_id)
        if member.status in ["left", "kicked"]:
            await query.answer("❌ You must join the channel first!", show_alert=True)
            conn.close()
            return
    except Exception:
        await query.answer("⚠️ Could not verify channel join.", show_alert=True)
        conn.close()
        return

    # Insert join record if not already rewarded
    cursor.execute("SELECT id FROM channel_joins WHERE advertisement_id = ? AND user_id = ?", (ad_id, user_id))
    if cursor.fetchone():
        await query.answer("✅ Already rewarded for this channel.", show_alert=True)
        conn.close()
        return

    cursor.execute(
        "INSERT INTO channel_joins (advertisement_id, user_id, reward_given) VALUES (?, ?, 1)",
        (ad_id, user_id),
    )
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (CHANNEL_JOIN_REWARD, user_id),
    )
    cursor.execute(
        "UPDATE advertisements SET current_subscribers = current_subscribers + 1 WHERE id = ?",
        (ad_id,),
    )

    conn.commit()
    conn.close()

    # Success message
    await query.edit_message_text(
        f"🎉 ስራውን በትክክል ሰርተዋል ፣ {CHANNEL_JOIN_REWARD} ብር ወደሂሳቦት ገብቷል።"
    )

    # Show next channel
    await show_joinable_channels(update, context)


# Add this function to handle join cancellation
async def cancel_join_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text("❌ Channel joining cancelled.")
    await show_main_menu_from_callback(update, context)


async def global_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only admin can use this command
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    conn = get_db_connection()
    cursor = conn.cursor()

    # Total users
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    # Total referrals
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(earned_amount), 0) FROM referrals")
    total_referrals, total_referral_earned = cursor.fetchone()

    # Total balance across all users
    cursor.execute("SELECT COALESCE(SUM(balance), 0) FROM users")
    total_balance = cursor.fetchone()[0]

    # Total ads created + total spent
    cursor.execute("SELECT COUNT(*), COALESCE(SUM(cost), 0) FROM advertisements")
    total_ads, total_spent = cursor.fetchone()

    # Total withdrawals by status
    cursor.execute("SELECT status, COUNT(*), COALESCE(SUM(amount), 0) FROM withdrawal_requests GROUP BY status")
    withdrawal_stats = cursor.fetchall()

    withdrawal_summary = "\n".join(
        [f"• {status}: {count} (Total: {total:.2f} birr)" for status, count, total in withdrawal_stats]
    ) or "None"

    total_withdrawn = sum(total for status, _, total in withdrawal_stats if status == "completed")

    conn.close()

    text = (
        f"📊 <b>Global Bot Statistics</b>\n\n"
        f"👥 <b>Total Users:</b> {total_users}\n"
        f"🔗 <b>Total Referrals:</b> {total_referrals}\n"
        f"💵 <b>Total Earned from Referrals:</b> ${total_referral_earned:.2f}\n\n"
        f"💰 <b>Total Balance in System:</b> ${total_balance:.2f}\n"
        f"📢 <b>Total Ads:</b> {total_ads}\n"
        f"💸 <b>Total Spent on Ads:</b> ${total_spent:.2f}\n\n"
        f"💳 <b>Withdrawal Requests:</b>\n{withdrawal_summary}\n\n"
        f"✅ <b>Total Completed Withdrawals:</b> ${total_withdrawn:.2f}"
    )

    await update.message.reply_text(text, parse_mode="HTML")

async def handle_advertisement_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    # Validate URL format
    if not (text.startswith('https://t.me/') or text.startswith('@')):
        await update.message.reply_text(
            "❌እባክዎን ትክክለኛ የቴሌግራም ቻናሎትን ሊንክ ያስገቡ.\n\n"
            "ለምሳሌ:\n"
            "• https://t.me/channel_username\n"
            "• @channel_username\n\n"
        )
        return
    
    # Extract channel username
    if text.startswith('https://t.me/'):
        channel_username = text.replace('https://t.me/', '')
        if channel_username.startswith('+'):
            channel_username = channel_username[1:]
    else:
        channel_username = text.replace('@', '')
    
    # Store channel info in context
    context.user_data['ad_channel_link'] = text
    context.user_data['ad_channel_username'] = channel_username
    context.user_data['awaiting_link'] = False
    
    # Check if bot is admin in the channel
    try:
        chat = await context.bot.get_chat(f"@{channel_username}")
        
        # Check if bot is admin in the channel
        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        
        if bot_member.status not in ['administrator', 'creator']:
            # Bot is not admin, ask user to make bot admin
            keyboard = [
                ["✅ I've Made Bot Admin", "❌ Cancel"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            
            await update.message.reply_text(
                f"🔧 <b>Admin Required</b>\n\n"
                f"To advertise your channel, you need to make me an admin in:\n"
                f"<b>{chat.title}</b> (@{channel_username})\n\n"
                f"<b>Required permissions:</b>\n"
                f"• ❌ <b>Add members permission is MUST</b>\n"
                f"• ✅ Post messages (optional)\n"
                f"• ✅ Delete messages (optional)\n\n"
                f"After making me admin, click the button below:",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            
            context.user_data['awaiting_admin_confirmation'] = True
            return
        else:
            # Bot is already admin, proceed to ask for subscribers
            context.user_data['is_bot_admin'] = True
            await ask_for_subscribers(update, context, chat.title)
            
    except Exception as e:
        logging.error(f"Error checking channel: {e}")
        await update.message.reply_text(
            f"❌ Cannot access the channel @{channel_username}. Please ensure:\n\n"
            f"1. The channel exists\n"
            f"2. The channel is public\n"
            f"3. You are an admin in the channel\n\n"
            f"Please send a valid channel link:"
        )

async def check_bot_admin_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    channel_username = context.user_data.get('ad_channel_username')
    
    if not channel_username:
        await update.message.reply_text("❌ Channel information missing. Please start over.")
        context.user_data.clear()
        await show_main_menu(update, context)
        return
    
    try:
        chat = await context.bot.get_chat(f"@{channel_username}")
        bot_member = await context.bot.get_chat_member(chat.id, context.bot.id)
        
        if bot_member.status in ['administrator', 'creator']:
            # Bot is now admin, proceed
            context.user_data['is_bot_admin'] = True
            context.user_data['awaiting_admin_confirmation'] = False
            
            keyboard = [["❌ Cancel"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
            
            await update.message.reply_text(
                f"✅ Great! I'm now admin in <b>{chat.title}</b>\n\n"
                f"Now, how many subscribers do you want to get for your channel?\n\n"
                f"<b>Cost:</b> {COST_PER_SUBSCRIBER} birr per subscriber\n\n"
                f"Enter the number of subscribers:",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            
            context.user_data['awaiting_subscribers'] = True
        else:
            # Bot is still not admin
            await update.message.reply_text(
                f"❌ I'm still not an admin in <b>{chat.title}</b>\n\n"
                f"Please make me an admin with <b>add members permission</b> and click the button again.",
                parse_mode="HTML"
            )
            
    except Exception as e:
        logging.error(f"Error re-checking channel: {e}")
        await update.message.reply_text(
            f"❌ Error checking channel status. Please try again or contact {ADMIN_USERNAME} for help."
        )

async def ask_for_subscribers(update: Update, context: ContextTypes.DEFAULT_TYPE, channel_title=None):
    if not channel_title:
        channel_username = context.user_data.get('ad_channel_username')
        try:
            chat = await context.bot.get_chat(f"@{channel_username}")
            channel_title = chat.title
        except:
            channel_title = f"@{channel_username}"
    
    keyboard = [["❌ Cancel"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    
    await update.message.reply_text(
        f"📈 <b>Subscriber Goal</b>\n\n"
        f"Channel: <b>{channel_title}</b>\n"
        f"Cost: <b>{COST_PER_SUBSCRIBER} ብር per subscriber</b>\n\n"
        f"💸 ምን ያህል ሰው እንዲቀላቀሉ ይፈልጋሉ?\n\n"
        f"ዝቅተኛ ማዘዝ የሚቻለው 10 ሰው ነው።\n\n",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )
    
    context.user_data['awaiting_subscribers'] = True

async def handle_desired_subscribers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = update.effective_user.id
    
    try:
        desired_subscribers = int(text)
        
        if desired_subscribers < 10:
            await update.message.reply_text("❌ Minimum subscribers required is 10. Please enter a higher number:")
            return
        
        # Calculate total cost
        total_cost = desired_subscribers * COST_PER_SUBSCRIBER
        
        # Check user balance
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            await update.message.reply_text("❌ User not found in database.")
            context.user_data.clear()
            await show_main_menu(update, context)
            return
        
        user_balance = result[0]
        
        if user_balance < total_cost:
            # Insufficient balance
            needed_amount = total_cost - user_balance
            
            keyboard = [["💰 Deposit", "❌ Cancel"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            await update.message.reply_text(
                f"❌ <b>Insufficient Balance</b>\n\n"
                f"<b>Requested:</b> {desired_subscribers} subscribers\n"
                f"<b>Total Cost:</b> {total_cost:.2f} birr\n"
                f"<b>Your Balance:</b> {user_balance:.2f} birr\n"
                f"<b>Needed:</b> {needed_amount:.2f} birr\n\n"
                f"Please deposit at least {needed_amount:.2f} birr and try again.\n\n"
                f"Contact {ADMIN_USERNAME} for deposit assistance.",
                reply_markup=reply_markup,
                parse_mode="HTML"
            )
            
            context.user_data.clear()
            return
        
        # Sufficient balance, ask for confirmation
        context.user_data['desired_subscribers'] = desired_subscribers
        context.user_data['total_cost'] = total_cost
        context.user_data['awaiting_subscribers'] = False
        
        channel_username = context.user_data.get('ad_channel_username')
        try:
            chat = await context.bot.get_chat(f"@{channel_username}")
            channel_title = chat.title
        except:
            channel_title = f"@{channel_username}"
        
        # Create confirmation inline keyboard
        keyboard = [
            [InlineKeyboardButton("✅ Confirm Advertisement", callback_data="confirm_ad")],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_ad")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"📢 <b>Advertisement Confirmation</b>\n\n"
            f"<b>Channel:</b> {channel_title}\n"
            f"<b>Subscribers Requested:</b> {desired_subscribers}\n"
            f"<b>Cost per Subscriber:</b> {COST_PER_SUBSCRIBER} ብር\n"
            f"<b>ጠቅላላ ክፍያ:</b> {total_cost:.2f} ብር\n"
            f"<b>የአሁን የገንዘብ መጠን:</b> {user_balance:.2f} ብር\n"
            f"<b>ካስተዋወቁ በኋላ የሚቀር:</b> {user_balance - total_cost:.2f} ብር\n\n"
            f"Please confirm your advertisement:",
            reply_markup=reply_markup,
            parse_mode="HTML"
        )
        
    except ValueError:
        await update.message.reply_text("❌ Please enter a valid number (e.g., 100):")

async def handle_advertisement_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if query.data == "confirm_ad":
        # Get advertisement details from context
        ad_type = "channel"  # Currently only supporting channels
        channel_link = context.user_data.get('ad_channel_link')
        channel_username = context.user_data.get('ad_channel_username')
        desired_subscribers = context.user_data.get('desired_subscribers')
        total_cost = context.user_data.get('total_cost')
        
        if not all([channel_link, channel_username, desired_subscribers, total_cost]):
            await query.edit_message_text("❌ Advertisement data missing. Please start over.")
            context.user_data.clear()
            return
        
        # Get channel title
        try:
            chat = await context.bot.get_chat(f"@{channel_username}")
            channel_title = chat.title
        except:
            channel_title = f"@{channel_username}"
        
        # Check user balance again before proceeding
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        
        if not result:
            await query.edit_message_text("❌ User not found in database.")
            conn.close()
            context.user_data.clear()
            return
        
        user_balance = result[0]
        
        if user_balance < total_cost:
            await query.edit_message_text(
                f"❌ <b>Insufficient Balance</b>\n\n"
                f"Your balance is now {user_balance:.2f} birr, but you need {total_cost:.2f} birr.\n\n"
                f"Please deposit more funds and try again.",
                parse_mode="HTML"
            )
            conn.close()
            context.user_data.clear()
            return
        
        # DEDUCT THE COST FROM USER'S BALANCE
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', 
                      (total_cost, user_id))
        
        # Save advertisement to database
        cursor.execute('''
            INSERT INTO advertisements (advertiser_id, type, channel_link, channel_username, 
                                     desired_subscribers, cost, is_bot_admin)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, ad_type, channel_link, channel_username, desired_subscribers, total_cost, True))
        
        ad_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        # Notify admin
        await context.bot.send_message(
            ADMIN_ID,
            f"📢 New channel advertisement created!\n\n"
            f"Advertiser: (ID: {user_id})\n"
            f"Channel: @{channel_username}\n"
            f"Target Subscribers: {desired_subscribers}\n"
            f"Cost: {total_cost} ብር\n"
            f"Paid from balance: ✅"
        )
        
        await query.edit_message_text(
            f"✅ <b>Advertisement Submitted!</b>\n\n"
            f"የጠየቁት የቻናል ማስታውቂያ ጥያቄ ተሳክቷል\n\n"
            f"<b>ማብራሪያ:</b>\n"
            f"• ቻናል: {channel_title}\n"
            f"• የሰው ብዛት: {desired_subscribers}\n"
            f"• ክፍያ: {total_cost:.2f} ብር\n"
            f"• አዲሱ የገንዘብ መጠን: {user_balance - total_cost:.2f} ብር\n\n"
            f"እኛን ስለመረጡ እናመሰግናለን",
            parse_mode="HTML"
        )
        
        # Clear context data
        context.user_data.clear()
        
    elif query.data == "cancel_ad":
        await query.edit_message_text("❌ Advertisement cancelled.")
        context.user_data.clear()
        await show_main_menu_from_callback(update, context)
        
    elif query.data == "cancel_ad":
        await query.edit_message_text("❌ Advertisement cancelled.")
        context.user_data.clear()
        await show_main_menu_from_callback(update, context)


async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send broadcast message to all users (Admin only)"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if not context.args:
        await update.message.reply_text(
            "📢 <b>Broadcast Message</b>\n\n"
            "Usage: <code>/broadcast your message here</code>\n\n"
            "Example:\n"
            "<code>/broadcast Hello everyone! New update available.</code>\n\n"
            "You can also use HTML formatting.",
            parse_mode="HTML"
        )
        return

    message_text = " ".join(context.args)
    
    # Create confirmation keyboard
    keyboard = [
        [InlineKeyboardButton("✅ Send Broadcast", callback_data=f"confirm_broadcast")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Store message in context for confirmation
    context.user_data['broadcast_message'] = message_text
    
    await update.message.reply_text(
        f"📢 <b>Broadcast Preview</b>\n\n"
        f"{message_text}\n\n"
        f"<b>This message will be sent to all users.</b>\n"
        f"Are you sure you want to proceed?",
        reply_markup=reply_markup,
        parse_mode="HTML"
    )

async def send_broadcast_to_users(context: ContextTypes.DEFAULT_TYPE, message_text: str):
    """Send broadcast message to all users in database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get all user IDs
    cursor.execute('SELECT user_id FROM users')
    users = cursor.fetchall()
    conn.close()
    
    total_users = len(users)
    successful_sends = 0
    failed_sends = 0
    
    # Send message to each user
    for user_tuple in users:
        user_id = user_tuple[0]
        try:
            await context.bot.send_message(
                user_id,
                f"📢 <b>Announcement</b>\n\n{message_text}",
                parse_mode="HTML"
            )
            successful_sends += 1
        except Exception as e:
            logging.error(f"Failed to send broadcast to user {user_id}: {e}")
            failed_sends += 1
        # Small delay to avoid rate limiting
        await asyncio.sleep(0.1)  # This requires asyncio import
    
    return total_users, successful_sends, failed_sends

async def handle_broadcast_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle broadcast confirmation from admin"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_broadcast":
        message_text = context.user_data.get('broadcast_message')
        
        if not message_text:
            await query.edit_message_text("❌ Broadcast message not found.")
            return
        
        # Show sending progress
        await query.edit_message_text("🔄 <b>Sending broadcast to all users...</b>", parse_mode="HTML")
        
        # Send broadcast
        total_users, successful_sends, failed_sends = await send_broadcast_to_users(context, message_text)
        
        # Send results to admin
        result_text = (
            f"✅ <b>Broadcast Completed</b>\n\n"
            f"📊 <b>Results:</b>\n"
            f"• Total Users: {total_users}\n"
            f"• Successful: {successful_sends}\n"
            f"• Failed: {failed_sends}\n\n"
            f"💬 <b>Message Sent:</b>\n{message_text}"
        )
        
        await context.bot.send_message(
            ADMIN_ID,
            result_text,
            parse_mode="HTML"
        )
        
        # Update the original message
        await query.edit_message_text(
            f"✅ <b>Broadcast Sent Successfully!</b>\n\n"
            f"• Total Users: {total_users}\n"
            f"• Successful: {successful_sends}\n"
            f"• Failed: {failed_sends}",
            parse_mode="HTML"
        )
        
        # Clear the stored message
        context.user_data.pop('broadcast_message', None)
        
    elif query.data == "cancel_broadcast":
        await query.edit_message_text("❌ Broadcast cancelled.")
        context.user_data.pop('broadcast_message', None)


async def edit_user_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to edit any user's phone number"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /edit_user_phone <user_id OR @username> <new_phone_number>\n\n"
            "Examples:\n"
            "<code>/edit_user_phone 123456789 +251912345678</code>\n"
            "<code>/edit_user_phone @username +251912345678</code>\n\n"
            "Note: Phone number should be in international format (with +)",
            parse_mode="HTML"
        )
        return
    
    user_identifier = context.args[0]
    new_phone_number = " ".join(context.args[1:])
    
    # Basic phone number validation
    if not new_phone_number.startswith('+'):
        await update.message.reply_text(
            "❌ Phone number must be in international format starting with +\n"
            "Example: +251912345678"
        )
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if phone number already exists for another user
    cursor.execute('SELECT user_id, username FROM users WHERE phone_number = ?', (new_phone_number,))
    existing_user = cursor.fetchone()
    
    if existing_user:
        existing_user_id, existing_username = existing_user
        if str(existing_user_id) != user_identifier and (not user_identifier.startswith('@') or existing_username != user_identifier[1:]):
            await update.message.reply_text(
                f"❌ This phone number is already registered to another user:\n"
                f"User ID: {existing_user_id}\n"
                f"Username: @{existing_username if existing_username else 'N/A'}\n\n"
                f"Please use a different phone number."
            )
            conn.close()
            return
    
    # Find the user
    if user_identifier.startswith('@'):
        # Search by username
        username = user_identifier[1:]
        cursor.execute('SELECT user_id, username, phone_number FROM users WHERE username = ?', (username,))
    else:
        # Search by user ID
        try:
            user_id = int(user_identifier)
            cursor.execute('SELECT user_id, username, phone_number FROM users WHERE user_id = ?', (user_id,))
        except ValueError:
            await update.message.reply_text("❌ Please provide a valid user ID or @username.")
            conn.close()
            return
    
    user = cursor.fetchone()
    
    if not user:
        await update.message.reply_text(f"❌ No user found with identifier: {user_identifier}")
        conn.close()
        return
    
    user_id, username, old_phone = user
    
    # Update the phone number
    cursor.execute('UPDATE users SET phone_number = ? WHERE user_id = ?', (new_phone_number, user_id))
    
    if cursor.rowcount == 0:
        await update.message.reply_text(f"❌ Error updating phone number for user {user_identifier}.")
    else:
        conn.commit()
        
        # Format the response
        user_display = f"@{username}" if username else f"User {user_id}"
        old_phone_display = old_phone if old_phone else "Not set"
        
        await update.message.reply_text(
            f"✅ Phone number updated successfully!\n\n"
            f"👤 User: {user_display}\n"
            f"🆔 User ID: {user_id}\n"
            f"📱 Old Phone: {old_phone_display}\n"
            f"📱 New Phone: {new_phone_number}\n\n"
            f"The user's withdrawal phone number has been updated."
        )
        
        # Notify the user
        try:
            await context.bot.send_message(
                user_id,
                f"📱 <b>ስልክ ቁጥሮ በተሳካ ሁኔታ ተቀይሯል</b>\n\n"
                f"የተመዘገቡበት ስልክቁጥር አሁን በአድሚን ተቀይሯል:\n\n"
                f"<b>የድሮ ቁጥር:</b> {old_phone_display}\n"
                f"<b>አዲሱ ቁጥር:</b> {new_phone_number}\n\n"
                f"ለወደፊቱ ወጪ ሲያደርጉ ገንዘቦ የሚገባሎት በዚህ ስልክ ቁጥር ይሆናል\n"
                f"ይህ ነገር እርሶ ያዘዙት ካልሆነ አሁኑኑ እኛን ያናግሩን @Adey_Support",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Could not notify user {user_id}: {e}")
            await update.message.reply_text(
                f"⚠️ Could not send notification to user (they may have blocked the bot)."
            )
    
    conn.close()


# Admin advertisement approval handler
async def handle_admin_ad_approval(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith("admin_approve_ad_"):
        ad_id = int(query.data.replace("admin_approve_ad_", ""))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get advertisement details - FIXED COLUMN INDEXES
        cursor.execute('''
            SELECT a.*, u.user_id, u.username, u.balance 
            FROM advertisements a 
            JOIN users u ON a.advertiser_id = u.user_id 
            WHERE a.id = ?
        ''', (ad_id,))
        ad = cursor.fetchone()
        
        if not ad:
            await query.edit_message_text("❌ Advertisement not found.")
            return
        
        # Debug: Print the ad tuple to see the structure
        print(f"Advertisement tuple: {ad}")
        
        # FIXED: Correct column indexes based on the SELECT query
        # a.* columns: id, advertiser_id, type, channel_link, channel_username, 
        #              desired_subscribers, current_subscribers, cost, is_active, 
        #              is_bot_admin, created_at (11 columns total)
        # Then u.user_id, u.username, u.balance (3 more columns)
        # Total: 14 columns, index 0-13
        
        # Cost is at index 7 (8th column)
        total_cost = float(ad[7]) if ad[7] is not None else 0.0
        
        # Balance is at index 13 (14th column) - the last one
        user_balance = float(ad[13]) if ad[13] is not None else 0.0
        
        # advertiser_id is at index 1 (2nd column)
        advertiser_id = ad[1]
        
        # desired_subscribers is at index 5 (6th column)
        desired_subscribers = ad[5]
        
        # channel_username is at index 4 (5th column)
        channel_username = ad[4]
        
        if user_balance < total_cost:
            await query.edit_message_text(
                f"❌ Cannot approve. User now has insufficient balance.\n\n"
                f"Required: {total_cost:.2f} birr\n"
                f"Available: {user_balance:.2f} birr"
            )
            conn.close()
            return
        
        # Deduct balance and activate advertisement
        cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', 
                      (total_cost, advertiser_id))
        
        cursor.execute('UPDATE advertisements SET is_active = 1 WHERE id = ?', (ad_id,))
        conn.commit()
        
        # Get channel info for display
        try:
            chat = await context.bot.get_chat(f"@{channel_username}")
            channel_title = chat.title
        except:
            channel_title = f"@{channel_username}"
        
        # Notify user
        try:
            await context.bot.send_message(
                advertiser_id,
                f"✅ <b>Your Advertisement is Approved!</b>\n\n"
                f"<b>Channel:</b> {channel_title}\n"
                f"<b>Subscribers Requested:</b> {desired_subscribers}\n"
                f"<b>Total Cost:</b> {total_cost:.2f} birr\n"
                f"<b>New Balance:</b> {user_balance - total_cost:.2f} birr\n\n"
                f"Your channel is now being promoted to users. "
                f"You will be notified when the target is reached.\n\n"
                f"Thank you for advertising with us!",
                parse_mode="HTML"
            )
        except Exception as e:
            logging.error(f"Could not notify user: {e}")
        
        await query.edit_message_text(
            f"✅ Advertisement #{ad_id} approved!\n\n"
            f"• Channel: {channel_title}\n"
            f"• Subscribers: {desired_subscribers}\n"
            f"• Amount deducted: {total_cost:.2f} birr\n"
            f"• Channel is now available for users to join."
        )
        
        conn.close()
        
    elif query.data.startswith("admin_reject_ad_"):
        ad_id = int(query.data.replace("admin_reject_ad_", ""))
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get advertisement details to notify user
        cursor.execute('SELECT advertiser_id, channel_username FROM advertisements WHERE id = ?', (ad_id,))
        ad = cursor.fetchone()
        
        if ad:
            advertiser_id, channel_username = ad
            
            # Delete the advertisement
            cursor.execute('DELETE FROM advertisements WHERE id = ?', (ad_id,))
            conn.commit()
            
            # Notify user
            try:
                await context.bot.send_message(
                    advertiser_id,
                    f"❌ <b>Your Advertisement was Rejected</b>\n\n"
                    f"Your advertisement for @{channel_username} has been rejected by admin.\n\n"
                    f"If you believe this is an error, please contact {ADMIN_USERNAME}.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"Could not notify user: {e}")
        
        conn.close()
        
        await query.edit_message_text(f"❌ Advertisement #{ad_id} has been rejected.")


async def show_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get top 10 users by balance (total earnings)
    cursor.execute('''
        SELECT user_id, username, first_name, balance 
        FROM users 
        WHERE balance > 0 
        ORDER BY balance DESC 
        LIMIT 10
    ''')
    top_users = cursor.fetchall()
    conn.close()
    
    if not top_users:
        await update.message.reply_text(
            "🏆 <b>Leaderboard</b>\n\n"
            "No users with earnings yet. Be the first to earn!",
            parse_mode="HTML"
        )
        return
    
    # Get current user's rank
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) + 1 as rank 
        FROM users 
        WHERE balance > (SELECT balance FROM users WHERE user_id = ?)
    ''', (user_id,))
    user_rank_result = cursor.fetchone()
    user_rank = user_rank_result[0] if user_rank_result else "Not ranked"
    
    # Get current user's balance
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    user_balance_result = cursor.fetchone()
    user_balance = user_balance_result[0] if user_balance_result else 0
    conn.close()
    
    # Build leaderboard text
    leaderboard_text = "🏆 <b>ከፍተኛ ገንዘብ ያገኙ</b>\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (user_id, username, first_name, balance) in enumerate(top_users):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = f"@{username}" if username else (first_name or f"User {user_id}")
        leaderboard_text += f"{medal} {name}: <b>{balance} ብር</b>\n"
    
    leaderboard_text += f"\n📊 <b>እርሶ:</b> #{user_rank}ኛ ኖት\n"
    leaderboard_text += f"💰 <b>ያሎት ገንዘብ:</b> {user_balance} ብር\n\n"
    
    if user_rank > 10:
        leaderboard_text += f"ከ10ሮቹ ውስጥ ለመግባት ትንሽ ነው የቀሮት 💪"
    else:
        leaderboard_text += f"🎉 እንኳን ደስ አሎት ፣ እርሶ {user_rank}ኛ ላይ ኖት!"
    
    # Removed inline buttons - just send the message without reply_markup
    await update.message.reply_text(
        leaderboard_text,
        parse_mode="HTML"
    )

async def add_required_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add a new required channel"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /add_required_channel <@username> <channel_name>\n\n"
            "Example: <code>/add_required_channel @MyChannel \"My Channel Name\"</code>\n\n"
            "Note: Channel username must start with @",
            parse_mode="HTML"
        )
        return
    
    username = context.args[0]
    channel_name = " ".join(context.args[1:])
    
    # Validate username format
    if not username.startswith('@'):
        await update.message.reply_text("❌ Channel username must start with @")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute('''
            INSERT INTO required_channels (username, name)
            VALUES (?, ?)
        ''', (username, channel_name))
        
        conn.commit()
        
        # Reload channels
        load_required_channels()
        
        await update.message.reply_text(
            f"✅ Channel added successfully!\n\n"
            f"📢 <b>Channel:</b> {channel_name}\n"
            f"🔗 <b>Username:</b> {username}\n\n"
            f"Total required channels: {len(REQUIRED_CHANNELS)}",
            parse_mode="HTML"
        )
        
    except sqlite3.IntegrityError:
        await update.message.reply_text(f"❌ Channel {username} already exists in required channels.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error adding channel: {str(e)}")
    finally:
        conn.close()

async def remove_required_channel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Remove a required channel"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if len(context.args) != 1:
        await update.message.reply_text(
            "Usage: /remove_required_channel <@username>\n\n"
            "Example: <code>/remove_required_channel @MyChannel</code>\n\n"
            "Use /list_required_channels to see current channels",
            parse_mode="HTML"
        )
        return
    
    username = context.args[0]
    
    if not username.startswith('@'):
        await update.message.reply_text("❌ Channel username must start with @")
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT name FROM required_channels WHERE username = ?', (username,))
    channel = cursor.fetchone()
    
    if not channel:
        await update.message.reply_text(f"❌ Channel {username} not found in required channels.")
        conn.close()
        return
    
    channel_name = channel[0]
    
    cursor.execute('DELETE FROM required_channels WHERE username = ?', (username,))
    conn.commit()
    conn.close()
    
    # Reload channels
    load_required_channels()
    
    await update.message.reply_text(
        f"✅ Channel removed successfully!\n\n"
        f"📢 <b>Removed:</b> {channel_name}\n"
        f"🔗 <b>Username:</b> {username}\n\n"
        f"Total required channels: {len(REQUIRED_CHANNELS)}",
        parse_mode="HTML"
    )

async def list_required_channels(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all required channels"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    
    if not REQUIRED_CHANNELS:
        await update.message.reply_text("📭 No required channels set.")
        return
    
    channels_text = "📋 <b>Required Channels</b>\n\n"
    
    for i, channel in enumerate(REQUIRED_CHANNELS, 1):
        channels_text += f"{i}. <b>{channel['name']}</b>\n"
        channels_text += f"   🔗 {channel['username']}\n\n"
    
    channels_text += f"Total: {len(REQUIRED_CHANNELS)} channels"
    
    await update.message.reply_text(channels_text, parse_mode="HTML")


# Add this function to handle leaderboard refresh (updated without buttons)
async def refresh_leaderboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_membership_decorator(update, context):
        return
    query = update.callback_query
    await query.answer()
    
    # Edit the message to remove the buttons and show updated leaderboard
    user_id = query.from_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get top 10 users by balance
    cursor.execute('''
        SELECT user_id, username, first_name, balance 
        FROM users 
        WHERE balance > 0 
        ORDER BY balance DESC 
        LIMIT 10
    ''')
    top_users = cursor.fetchall()
    conn.close()
    
    if not top_users:
        await query.edit_message_text(
            "🏆 <b>Leaderboard</b>\n\n"
            "No users with earnings yet. Be the first to earn!",
            parse_mode="HTML"
        )
        return
    
    # Get current user's rank
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) + 1 as rank 
        FROM users 
        WHERE balance > (SELECT balance FROM users WHERE user_id = ?)
    ''', (user_id,))
    user_rank_result = cursor.fetchone()
    user_rank = user_rank_result[0] if user_rank_result else "Not ranked"
    
    # Get current user's balance
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    user_balance_result = cursor.fetchone()
    user_balance = user_balance_result[0] if user_balance_result else 0
    conn.close()
    
    # Build leaderboard text
    leaderboard_text = "🏆 <b>ከፍተኛ ገንዘብ ያገኙ</b>\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (user_id, username, first_name, balance) in enumerate(top_users):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = f"@{username}" if username else (first_name or f"User {user_id}")
        leaderboard_text += f"{medal} {name}: <b>{balance} birr</b>\n"
    
    leaderboard_text += f"\n📊 <b>እርሶ:</b> #{user_rank}ኛ ኖት\n"
    leaderboard_text += f"💰 <b>ያሎት ገንዘብ:</b> {user_balance} ብር\n\n"
    
    if user_rank > 10:
        leaderboard_text += f"💪 ከ10ሮቹ ውስጥ ለመግባት ትንሽ ነው የቀሮት 💪"
    else:
        leaderboard_text += f"🎉 እንኳን ደስ አሎት ፣ እርሶ {user_rank}ኛ ላይ ኖት!"
    
    await query.edit_message_text(
        leaderboard_text,
        parse_mode="HTML"
    )

# Add this function to show leaderboard from callback (updated without buttons)
async def show_leaderboard_from_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get top 10 users by balance
    cursor.execute('''
        SELECT user_id, username, first_name, balance 
        FROM users 
        WHERE balance > 0 
        ORDER BY balance DESC 
        LIMIT 10
    ''')
    top_users = cursor.fetchall()
    conn.close()
    
    if not top_users:
        await query.edit_message_text(
            "🏆 <b>Leaderboard</b>\n\n"
            "No users with earnings yet. Be the first to earn!",
            parse_mode="HTML"
        )
        return
    
    # Get current user's rank
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT COUNT(*) + 1 as rank 
        FROM users 
        WHERE balance > (SELECT balance FROM users WHERE user_id = ?)
    ''', (user_id,))
    user_rank_result = cursor.fetchone()
    user_rank = user_rank_result[0] if user_rank_result else "Not ranked"
    
    # Get current user's balance
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    user_balance_result = cursor.fetchone()
    user_balance = user_balance_result[0] if user_balance_result else 0
    conn.close()
    
    # Build leaderboard text
    leaderboard_text = "🏆 <b>ከፍተኛ ገንዘብ ያገኙ</b>\n\n"
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, (user_id, username, first_name, balance) in enumerate(top_users):
        medal = medals[i] if i < len(medals) else f"{i+1}."
        name = f"@{username}" if username else (first_name or f"User {user_id}")
        leaderboard_text += f"{medal} {name}: <b>{balance} birr</b>\n"
    
    leaderboard_text += f"\n📊 <b>እርሶ:</b> #{user_rank}ኛ ኖት\n"
    leaderboard_text += f"💰 <b>ያሎት ገንዘብ:</b> {user_balance} ብር\n\n"
    
    if user_rank > 10:
        leaderboard_text += f"ከ10ሮቹ ውስጥ ለመግባት ትንሽ ነው የቀሮት 💪"
    else:
        leaderboard_text += f"🎉 እንኳን ደስ አሎት ፣ እርሶ {user_rank}ኛ ላይ ኖት!"
    
    # Removed inline buttons - just send the message without reply_markup
    await update.message.reply_text(
        leaderboard_text,
        parse_mode="HTML"
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Only allow the admin to use this
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    text = (
        "🛠 <b>Admin Panel</b>\n\n"
        "Here are all available admin commands:\n\n"
        "👥 <b>User Management</b>\n"
        "<code>/user_stats &lt;user_id&gt;</code> – View full stats of a user.\n"
        "<code>/ads_stats </code> – View full ad stats.\n"
        "<code>/remove_ad &lt;ad_id&gt;</code> – to remove ad from join channel.\n"
        "<code>/add_money &lt;user_id&gt; &lt;amount&gt;</code> – Add money to user.\n"
        "<code>/remove_money &lt;user_id&gt; &lt;amount&gt;</code> – Remove money from user.\n"
        "<code>/clear_balance &lt;user_id&gt;</code> – Reset user balance to $0.\n\n"
        "<code>/edit_user_phone &lt;user_id&gt; &lt;phone&gt;</code> – Edit user's phone number.\n\n"
         "📢 <b>Channel Management</b>\n"
        "<code>/add_required_channel &lt;@username&gt; &lt;name&gt;</code> – Add required channel.\n"
        "<code>/remove_required_channel &lt;@username&gt;</code> – Remove required channel.\n"
        "<code>/list_required_channels</code> – List all required channels.\n\n"
         "⚙️ <b>Bot Settings</b>\n"
        "<code>/settings</code> – View current bot settings.\n"
        "<code>/set_min_withdrawal &lt;amount&gt;</code> – Set minimum withdrawal amount.\n"
        "<code>/set_cost_per_subscriber &lt;amount&gt;</code> – Set cost per subscriber for ads.\n"
        "<code>/set_join_reward &lt;amount&gt;</code> – Set channel join reward.\n" 
        "<code>/set_referral_reward &lt;amount&gt;</code> – Set referral reward.\n\n"
        "📢 <b>Broadcast</b>\n"
        "<code>/broadcast &lt;message&gt;</code> – Send message to all users.\n\n"
        "📊 <b>Bot Statistics</b>\n"
        "<code>/stats</code> – View global bot statistics.\n\n"
        "📱 <b>Phone Management</b>\n"
        "<code>/change_phone</code> – Clear and reset your own phone number.\n"
        "<code>/edit_phone</code> – View & update your phone number.\n\n"
        "💡 <b>Tip:</b> Only you (the admin) can use these commands."
    )

    await update.message.reply_text(text, parse_mode="HTML")


def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("clear_balance", clear_balance))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", global_stats))
    application.add_handler(CommandHandler("user_stats", user_stats))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CommandHandler("change_phone", change_phone))
    application.add_handler(CommandHandler("channel_stats", channel_stats)) 
    application.add_handler(CommandHandler("edit_user_phone", edit_user_phone))
    application.add_handler(CommandHandler("edit_phone", edit_phone))  # New command
    application.add_handler(CommandHandler("set_min_withdrawal", set_min_withdrawal))
    application.add_handler(CommandHandler("set_cost_per_subscriber", set_cost_per_subscriber))
    application.add_handler(CommandHandler("set_join_reward", set_join_reward))
    application.add_handler(CommandHandler("set_referral_reward", set_referral_reward))
    application.add_handler(CommandHandler("settings", show_settings))
    application.add_handler(CommandHandler("add_money", add_money))
    application.add_handler(CommandHandler("ads_stats", ads_stats))
    application.add_handler(CommandHandler("remove_ad", remove_ad))
    application.add_handler(CommandHandler("remove_money", remove_money))
    application.add_handler(CommandHandler("add_required_channel", add_required_channel))
    application.add_handler(CommandHandler("remove_required_channel", remove_required_channel))
    application.add_handler(CommandHandler("list_required_channels", list_required_channels))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.CONTACT, handle_phone_number_sharing))
    application.add_handler(MessageHandler(filters.PHOTO, handle_admin_screenshot))  # New handler for admin screenshots
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_messages))
    
    
    print("Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()