"""Telegram bot for ARGSMS - SMS range management system."""

import os
import json
import logging
import random
import re
import traceback
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)

from database import (
    init_db,
    get_or_create_user,
    log_access,
    is_user_admin,
    is_user_banned,
    get_user_balance,
    add_user_balance,
    deduct_user_balance,
    get_price_for_range,
    create_number_holds,
    mark_number_permanent,
    get_held_numbers,
    is_number_held,
    cleanup_expired_holds,
    update_first_retry_time,
    User,
    NumberHold,
    PriceRange,
    Transaction,
    RechargeRequest
)
from scrapper_wrapper import get_scrapper_session

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get bot token from environment
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN must be set in .env file")

# Get force join channel ID
FORCE_JOIN_CHANNEL_ID = os.getenv("FORCE_JOIN_CHANNEL_ID", "")

# Constants for button text formatting
MAX_BUTTON_TEXT_LENGTH = 60
MAX_TITLE_LENGTH = 50

# Constants for SMS number fetching
SMS_FETCH_COUNT = 100  # How many numbers to fetch from API
SMS_DISPLAY_COUNT = 20  # How many random numbers to display

# Constants for SMS message display
MAX_TELEGRAM_MESSAGE_LENGTH = 3500  # Leave room for additional text

# Initialize database session factory
SessionFactory = init_db()


def get_db_session():
    """Get a new database session."""
    return SessionFactory()


def escape_html(text):
    """Escape HTML special characters for safe display in Telegram messages."""
    if text is None:
        return ""
    return str(text).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


def strip_html_tags(html_str):
    """
    Strip HTML tags from string and decode HTML entities.
    
    Args:
        html_str: String potentially containing HTML tags
    
    Returns:
        Clean text without HTML tags
    """
    if not html_str or not isinstance(html_str, str):
        return str(html_str) if html_str else ""
    
    # Use a simple regex to remove HTML tags
    import re
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', html_str)
    # Decode common HTML entities
    text = text.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&')
    text = text.replace('&quot;', '"').replace('&#039;', "'").replace('&nbsp;', ' ')
    # Clean up whitespace
    text = ' '.join(text.split())
    return text.strip()


async def check_channel_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Check if user is a member of the required channel.
    Returns True if user is a member or no channel is configured, False otherwise.
    If False, sends a message to the user with a join button.
    """
    # If no channel is configured, skip check
    if not FORCE_JOIN_CHANNEL_ID:
        return True
    
    user_id = update.effective_user.id
    
    try:
        # Check if user is a member of the channel
        member = await context.bot.get_chat_member(FORCE_JOIN_CHANNEL_ID, user_id)
        
        # Check if user has left or is kicked
        if member.status in ['left', 'kicked']:
            # User is not a member, send join prompt
            keyboard = [[InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{FORCE_JOIN_CHANNEL_ID.lstrip('@')}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            message_text = (
                "🔒 <b>Channel Membership Required</b>\n\n"
                "To use this bot, you must join our channel first.\n"
                "Click the button below to join, then try again."
            )
            
            # Send or edit message depending on context
            if update.callback_query:
                await update.callback_query.answer("❌ Please join our channel first", show_alert=True)
                await update.callback_query.edit_message_text(
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            else:
                await update.message.reply_text(
                    message_text,
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
            return False
        
        # User is a member (status: creator, administrator, member, restricted)
        return True
        
    except Exception as e:
        logger.error(f"Error checking channel membership: {e}")
        # On error, allow access (fail open)
        return True


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    user = update.effective_user
    db = get_db_session()
    
    try:
        # Get or create user in database
        db_user = get_or_create_user(db, user.id, user.username)
        
        # Check if user is banned
        if db_user.is_banned:
            await update.message.reply_text(
                "🚫 You have been banned from using this bot.\n"
                "Please contact an administrator if you believe this is an error."
            )
            return
        
        # Check channel membership
        if not await check_channel_membership(update, context):
            return
        
        log_access(db, db_user, "start_command")
        
        # Create main menu
        keyboard = [
            [InlineKeyboardButton("📱 View SMS Ranges", callback_data="view_sms_ranges")],
            [InlineKeyboardButton("👤 My Profile", callback_data="user_profile")],
            [InlineKeyboardButton("💰 Recharge Balance", callback_data="recharge_request")],
            [InlineKeyboardButton("ℹ️ About", callback_data="about")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_message = (
            f"👋 Welcome to ARGSMS Bot, {user.first_name}!\n\n"
            f"💰 Balance: ${db_user.balance:.2f}\n\n"
            "This bot allows you to view available SMS ranges.\n"
            "Use the menu below to navigate:"
        )
        
        await update.message.reply_text(welcome_message, reply_markup=reply_markup)
    finally:
        db.close()


async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /admin command for admin panel."""
    user = update.effective_user
    db = get_db_session()
    
    try:
        # Check if user is admin
        if not is_user_admin(db, user.id):
            await update.message.reply_text("❌ You don't have admin privileges.")
            return
        
        db_user = get_or_create_user(db, user.id, user.username)
        log_access(db, db_user, "admin_panel_access")
        
        # Create admin panel keyboard
        keyboard = [
            [InlineKeyboardButton("👥 List Users", callback_data="admin_list_users")],
            [InlineKeyboardButton("🔑 Manage Admins", callback_data="admin_manage_admins")],
            [InlineKeyboardButton("🚫 Ban/Unban Users", callback_data="admin_manage_bans")],
            [InlineKeyboardButton("💰 Manage Balance", callback_data="admin_manage_balance")],
            [InlineKeyboardButton("💳 Recharge Requests", callback_data="admin_recharge_requests")],
            [InlineKeyboardButton("💵 Set Price Ranges", callback_data="admin_price_ranges")],
            [InlineKeyboardButton("📊 View Stats", callback_data="admin_view_stats")],
            [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        admin_message = (
            "🔐 Admin Panel\n\n"
            "Welcome to the admin panel. Select an option:"
        )
        
        await update.message.reply_text(admin_message, reply_markup=reply_markup)
    finally:
        db.close()


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button callbacks from inline keyboards."""
    query = update.callback_query
    user = query.from_user
    
    # Answer the callback query to remove loading state
    await query.answer()
    
    db = get_db_session()
    try:
        # Get or create user
        db_user = get_or_create_user(db, user.id, user.username)
        
        # Check if user is banned (except for back_to_main)
        callback_data = query.data
        if callback_data != "back_to_main" and db_user.is_banned:
            await query.answer("🚫 You have been banned from using this bot.", show_alert=True)
            return
        
        # Check channel membership for non-admin actions
        if not callback_data.startswith("admin_") and callback_data != "back_to_main":
            if not await check_channel_membership(update, context):
                return
        
        # Main menu callbacks
        if callback_data == "view_sms_ranges":
            await view_sms_ranges_callback(query, context, db, db_user)
        elif callback_data == "user_profile":
            await user_profile_callback(query, context, db, db_user)
        elif callback_data == "recharge_request":
            await recharge_request_callback(query, context, db, db_user)
        elif callback_data == "about":
            await about_callback(query, context, db, db_user)
        elif callback_data == "back_to_main":
            await back_to_main_callback(query, context, db, db_user)
        
        # Admin panel callbacks
        elif callback_data == "admin_list_users":
            await admin_list_users_callback(query, context, db, db_user)
        elif callback_data == "admin_manage_admins":
            await admin_manage_admins_callback(query, context, db, db_user)
        elif callback_data == "admin_manage_bans":
            await admin_manage_bans_callback(query, context, db, db_user)
        elif callback_data == "admin_manage_balance":
            await admin_manage_balance_callback(query, context, db, db_user)
        elif callback_data == "admin_recharge_requests":
            await admin_recharge_requests_callback(query, context, db, db_user)
        elif callback_data == "admin_price_ranges":
            await admin_price_ranges_callback(query, context, db, db_user)
        elif callback_data == "admin_view_stats":
            await admin_view_stats_callback(query, context, db, db_user)
        elif callback_data == "admin_back":
            await admin_back_callback(query, context, db, db_user)
        
        # SMS range detail view
        elif callback_data.startswith("sms_range_"):
            range_id = callback_data.replace("sms_range_", "")
            await view_sms_range_detail_callback(query, context, db, db_user, range_id)
        
        # View SMS numbers for a range
        elif callback_data.startswith("view_numbers_"):
            range_id = callback_data[len("view_numbers_"):]
            await view_sms_numbers_callback(query, context, db, db_user, range_id)
        
        # Pagination callbacks
        elif callback_data.startswith("sms_page_"):
            page = int(callback_data.split("_")[2])
            await view_sms_ranges_callback(query, context, db, db_user, page=page)
        
        # Make user admin callback
        elif callback_data.startswith("make_admin_"):
            user_id = int(callback_data.split("_")[2])
            await make_admin_callback(query, context, db, db_user, user_id)
        
        # Remove admin callback
        elif callback_data.startswith("remove_admin_"):
            user_id = int(callback_data.split("_")[2])
            await remove_admin_callback(query, context, db, db_user, user_id)
        
        # Ban user callback
        elif callback_data.startswith("ban_user_"):
            user_id = int(callback_data.split("_")[2])
            await ban_user_callback(query, context, db, db_user, user_id)
        
        # Unban user callback
        elif callback_data.startswith("unban_user_"):
            user_id = int(callback_data.split("_")[2])
            await unban_user_callback(query, context, db, db_user, user_id)
        
        # Add balance callback
        elif callback_data.startswith("add_balance_"):
            user_id = int(callback_data.split("_")[2])
            await add_balance_prompt_callback(query, context, db, db_user, user_id)
        
        # Deduct balance callback
        elif callback_data.startswith("deduct_balance_"):
            user_id = int(callback_data.split("_")[2])
            await deduct_balance_prompt_callback(query, context, db, db_user, user_id)
        
        # Approve recharge callback
        elif callback_data.startswith("approve_recharge_"):
            request_id = int(callback_data.split("_")[2])
            await approve_recharge_callback(query, context, db, db_user, request_id)
        
        # Reject recharge callback
        elif callback_data.startswith("reject_recharge_"):
            request_id = int(callback_data.split("_")[2])
            await reject_recharge_callback(query, context, db, db_user, request_id)
        
        # Retry SMS search callback
        elif callback_data.startswith("retry_sms_"):
            await retry_sms_callback(query, context, db, db_user)
    finally:
        db.close()


async def view_sms_ranges_callback(query, context, db, db_user, page=1):
    """Show SMS ranges to the user."""
    log_access(db, db_user, f"view_sms_ranges_page_{page}")
    
    # Get scrapper session and fetch data
    scrapper = get_scrapper_session()
    data = scrapper.get_sms_ranges(max_results=10, page=page)
    
    if not data:
        await query.edit_message_text(
            "❌ Failed to retrieve SMS ranges. Please try again later."
        )
        return
    
    # Handle different possible JSON structures
    ranges = []
    has_more = False
    total_items = None
    
    if isinstance(data, dict):
        if 'results' in data:
            ranges = data['results']
            has_more = data.get('pagination', {}).get('more', False)
        elif 'data' in data:
            ranges = data['data']
            total_items = data.get('total', None)
            has_more = page * 10 < total_items if total_items else len(ranges) == 10
        elif 'aaData' in data:
            ranges = data['aaData']
        else:
            ranges = [data]
    elif isinstance(data, list):
        ranges = data
    
    # Create message header with page info
    page_info = f"Page {page}"
    if total_items:
        total_pages = (total_items + 9) // 10  # Round up
        page_info = f"Page {page}/{total_pages}"
    
    message = f"📱 Available SMS Ranges ({page_info})\n\n"
    
    if not ranges:
        message += "No SMS ranges available."
    else:
        message += f"Select a range to view details ({len(ranges)} ranges):"
    
    # Create keyboard with one button per range
    keyboard = []
    
    for i, item in enumerate(ranges, 1):
        # Format button text based on item structure
        button_text = ""
        range_id = None
        
        if isinstance(item, dict):
            # Extract id and title if available
            range_id = item.get('id') or item.get('range_id') or str((page-1)*10 + i)
            title = item.get('title', '')
            
            # Create concise button text
            if title:
                # Truncate title if too long
                button_text = f"{range_id}: {title[:MAX_TITLE_LENGTH]}" if len(title) > MAX_TITLE_LENGTH else f"{range_id}: {title}"
            else:
                # If no title, show all key-value pairs truncated
                info = " - ".join(f"{k}: {v}" for k, v in list(item.items())[:3])
                button_text = info[:MAX_BUTTON_TEXT_LENGTH]
        elif isinstance(item, list):
            range_id = str((page-1)*10 + i)
            info = " | ".join(str(x) for x in item[:3])
            button_text = info[:MAX_BUTTON_TEXT_LENGTH]
        else:
            range_id = str((page-1)*10 + i)
            button_text = str(item)[:MAX_BUTTON_TEXT_LENGTH]
        
        # Store the full item data in chat_data for later retrieval
        if 'sms_ranges' not in context.chat_data:
            context.chat_data['sms_ranges'] = {}
        context.chat_data['sms_ranges'][str(range_id)] = item
        
        # Add button for this range
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"sms_range_{range_id}")])
    
    # Add pagination controls
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"sms_page_{page-1}"))
    
    if has_more or len(ranges) == 10:
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"sms_page_{page+1}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup)


async def view_sms_range_detail_callback(query, context, db, db_user, range_id):
    """Show detailed information about a specific SMS range."""
    log_access(db, db_user, f"view_sms_range_detail_{range_id}")
    
    # Try to retrieve the range data from chat_data
    range_data = None
    if 'sms_ranges' in context.chat_data:
        range_data = context.chat_data['sms_ranges'].get(str(range_id))
    
    if not range_data:
        await query.answer("❌ Range data not found. Please go back and try again.")
        return
    
    # Format the detailed message with HTML
    message = "📱 <b>SMS Range Details</b>\n\n"
    
    if isinstance(range_data, dict):
        for key, value in range_data.items():
            # Format key to be more readable
            formatted_key = key.replace('_', ' ').title()
            # Escape HTML special characters in value
            escaped_value = escape_html(value)
            message += f"<b>{formatted_key}</b>: {escaped_value}\n"
    elif isinstance(range_data, list):
        message += " | ".join(str(x) for x in range_data)
    else:
        message += str(range_data)
    
    # Add buttons for actions and navigation
    keyboard = [
        [InlineKeyboardButton("📞 View Numbers", callback_data=f"view_numbers_{range_id}")],
        [InlineKeyboardButton("⬅️ Back to Ranges", callback_data="view_sms_ranges")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def view_sms_numbers_callback(query, context, db, db_user, range_id):
    """Show SMS numbers for a specific range."""
    log_access(db, db_user, f"view_sms_numbers_{range_id}")
    
    # Clean up expired holds
    cleanup_expired_holds(db)
    
    # Get price for this range
    price = get_price_for_range(db, range_id)
    
    # Check if user has sufficient balance
    if db_user.balance < price:
        await query.edit_message_text(
            f"❌ Insufficient balance!\n\n"
            f"💰 Your Balance: ${db_user.balance:.2f}\n"
            f"💵 Required: ${price:.2f}\n\n"
            "Please recharge your balance to continue.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("💰 Recharge", callback_data="recharge_request"),
                InlineKeyboardButton("⬅️ Back", callback_data=f"sms_range_{range_id}")
            ]])
        )
        return
    
    # Get scrapper session and fetch numbers
    scrapper = get_scrapper_session()
    
    # Fetch a larger batch to randomly select from
    data = scrapper.get_sms_numbers(range_id, start=0, length=SMS_FETCH_COUNT)
    
    if not data:
        await query.edit_message_text(
            "❌ Failed to retrieve SMS numbers. Please try again later.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data=f"sms_range_{range_id}")
            ]])
        )
        return
    
    # Parse DataTables response
    numbers = []
    total_records = 0
    
    if isinstance(data, dict):
        numbers = data.get('aaData', [])
        # iTotalRecords might be a string, convert to int
        total_records_raw = data.get('iTotalRecords', 0)
        try:
            total_records = int(total_records_raw) if total_records_raw else 0
        except (ValueError, TypeError):
            total_records = 0
    
    # Filter out numbers that are already held
    available_numbers = []
    for number in numbers:
        if isinstance(number, list) and len(number) >= 4:
            phone_number = number[3] if len(number) > 3 else None
            if phone_number and not is_number_held(db, phone_number):
                available_numbers.append(number)
    
    # Check if we have enough available numbers
    if len(available_numbers) < SMS_DISPLAY_COUNT:
        await query.edit_message_text(
            f"❌ Not enough available numbers in this range!\n\n"
            f"Available: {len(available_numbers)} numbers\n"
            f"Required: {SMS_DISPLAY_COUNT} numbers\n\n"
            "Please try another range or try again later.",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("⬅️ Back", callback_data=f"sms_range_{range_id}")
            ]])
        )
        return
    
    # Randomly select SMS_DISPLAY_COUNT numbers from available
    selected_numbers = random.sample(available_numbers, SMS_DISPLAY_COUNT)
    
    # Extract phone numbers for holding
    phone_numbers = []
    for number in selected_numbers:
        if isinstance(number, list) and len(number) >= 4:
            phone_number = number[3] if len(number) > 3 else "N/A"
            phone_numbers.append(phone_number)
    
    # Create holds for selected numbers
    create_number_holds(db, db_user, phone_numbers, range_id)
    
    # Format message (escape range_id for HTML)
    range_id_escaped = escape_html(range_id)
    message = f"📞 <b>SMS Numbers - Range {range_id_escaped}</b>\n\n"
    message += f"💵 Price per SMS: ${price:.2f}\n"
    message += f"💰 Your Balance: ${db_user.balance:.2f}\n\n"
    message += f"🔒 These {len(phone_numbers)} numbers are now held for you.\n"
    message += "They will be released after 5 minutes from your first retry.\n\n"
    
    # Format all numbers in a single code block
    numbers_text = '\n'.join([f'{phone}' for phone in phone_numbers])
    message += f"<pre>{numbers_text}</pre>"
    
    # Create navigation keyboard (no pagination, only back buttons)
    keyboard = []
    
    # Back buttons
    keyboard.append([InlineKeyboardButton("⬅️ Back to Range Details", callback_data=f"sms_range_{range_id}")])
    keyboard.append([InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def about_callback(query, context, db, db_user):
    """Show about information."""
    log_access(db, db_user, "about")
    
    message = (
        "ℹ️ About ARGSMS Bot\n\n"
        "This bot provides access to SMS range information.\n"
        "You can view available SMS ranges and navigate through pages.\n\n"
        "Commands:\n"
        "/start - Show main menu\n"
        "/admin - Admin panel (admin only)\n"
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup)


async def back_to_main_callback(query, context, db, db_user):
    """Return to main menu."""
    keyboard = [
        [InlineKeyboardButton("📱 View SMS Ranges", callback_data="view_sms_ranges")],
        [InlineKeyboardButton("👤 My Profile", callback_data="user_profile")],
        [InlineKeyboardButton("💰 Recharge Balance", callback_data="recharge_request")],
        [InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        f"👋 Welcome to ARGSMS Bot!\n\n"
        f"💰 Balance: ${db_user.balance:.2f}\n\n"
        "This bot allows you to view available SMS ranges.\n"
        "Use the menu below to navigate:"
    )
    
    await query.edit_message_text(welcome_message, reply_markup=reply_markup)


async def admin_list_users_callback(query, context, db, db_user):
    """List all users (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    log_access(db, db_user, "admin_list_users")
    
    # Get all users
    users = db.query(User).order_by(User.created_at.desc()).limit(20).all()
    
    message = "👥 User List (Last 20)\n\n"
    for user in users:
        admin_badge = "🔑" if user.is_admin else "👤"
        ban_badge = "🚫" if user.is_banned else ""
        username_str = f"@{user.username}" if user.username else "N/A"
        message += f"{admin_badge}{ban_badge} ID: {user.telegram_id} | {username_str}\n"
        message += f"   Balance: ${user.balance:.2f} | Joined: {user.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("🔑 Manage Admins", callback_data="admin_manage_admins")],
        [InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup)


async def admin_manage_admins_callback(query, context, db, db_user):
    """Manage admin users (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    log_access(db, db_user, "admin_manage_admins")
    
    # Get all users
    users = db.query(User).order_by(User.created_at.desc()).limit(10).all()
    
    message = "🔑 Manage Admins\n\n"
    message += "Select a user to toggle admin status:\n\n"
    
    keyboard = []
    for user in users:
        admin_badge = "🔑" if user.is_admin else "👤"
        username_str = f"@{user.username}" if user.username else f"ID:{user.telegram_id}"
        button_text = f"{admin_badge} {username_str}"
        
        if user.is_admin:
            callback = f"remove_admin_{user.id}"
        else:
            callback = f"make_admin_{user.id}"
        
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback)])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup)


async def admin_view_stats_callback(query, context, db, db_user):
    """View statistics (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    log_access(db, db_user, "admin_view_stats")
    
    # Get statistics
    from sqlalchemy import func
    
    total_users = db.query(User).count()
    admin_users = db.query(User).filter_by(is_admin=True).count()
    banned_users = db.query(User).filter_by(is_banned=True).count()
    
    # Calculate total balance in system
    total_balance = db.query(func.sum(User.balance)).scalar() or 0.0
    total_spent = db.query(func.sum(User.total_spent)).scalar() or 0.0
    total_sms = db.query(func.sum(User.total_sms_received)).scalar() or 0
    
    # Number holds stats
    total_holds = db.query(NumberHold).count()
    permanent_holds = db.query(NumberHold).filter_by(is_permanent=True).count()
    
    today = datetime.utcnow().date()
    today_logs = db.query(AccessLog).filter(
        func.date(AccessLog.timestamp) == today
    ).count()
    
    message = (
        "📊 Bot Statistics\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🔑 Admin Users: {admin_users}\n"
        f"🚫 Banned Users: {banned_users}\n\n"
        f"💰 Total Balance in System: ${total_balance:.2f}\n"
        f"💸 Total Spent: ${total_spent:.2f}\n"
        f"📨 Total SMS Received: {total_sms}\n\n"
        f"🔒 Number Holds: {total_holds}\n"
        f"🔐 Permanent Holds: {permanent_holds}\n\n"
        f"📈 Today's Actions: {today_logs}\n"
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup)


async def make_admin_callback(query, context, db, db_user, target_user_id):
    """Make a user admin (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    target_user = db.query(User).filter_by(id=target_user_id).first()
    if target_user:
        target_user.is_admin = True
        db.commit()
        log_access(db, db_user, f"make_admin_{target_user.telegram_id}")
        await query.answer(f"✅ User {target_user.telegram_id} is now an admin")
    else:
        await query.answer("❌ User not found")
    
    # Refresh the manage admins view
    await admin_manage_admins_callback(query, context, db, db_user)


async def remove_admin_callback(query, context, db, db_user, target_user_id):
    """Remove admin status from a user (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    # Prevent removing own admin status
    if target_user_id == db_user.id:
        await query.answer("❌ You cannot remove your own admin status")
        return
    
    target_user = db.query(User).filter_by(id=target_user_id).first()
    if target_user:
        target_user.is_admin = False
        db.commit()
        log_access(db, db_user, f"remove_admin_{target_user.telegram_id}")
        await query.answer(f"✅ Removed admin status from user {target_user.telegram_id}")
    else:
        await query.answer("❌ User not found")
    
    # Refresh the manage admins view
    await admin_manage_admins_callback(query, context, db, db_user)


async def admin_back_callback(query, context, db, db_user):
    """Return to admin panel."""
    user = query.from_user
    
    # Check if user is admin
    if not is_user_admin(db, user.id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton("👥 List Users", callback_data="admin_list_users")],
        [InlineKeyboardButton("🔑 Manage Admins", callback_data="admin_manage_admins")],
        [InlineKeyboardButton("🚫 Ban/Unban Users", callback_data="admin_manage_bans")],
        [InlineKeyboardButton("💰 Manage Balance", callback_data="admin_manage_balance")],
        [InlineKeyboardButton("💳 Recharge Requests", callback_data="admin_recharge_requests")],
        [InlineKeyboardButton("💵 Set Price Ranges", callback_data="admin_price_ranges")],
        [InlineKeyboardButton("📊 View Stats", callback_data="admin_view_stats")],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_message = (
        "🔐 Admin Panel\n\n"
        "Welcome to the admin panel. Select an option:"
    )
    
    await query.edit_message_text(admin_message, reply_markup=reply_markup)


async def user_profile_callback(query, context, db, db_user):
    """Show user profile with stats."""
    log_access(db, db_user, "view_profile")
    
    # Get user's held numbers count
    held_numbers = db.query(NumberHold).filter_by(user_id=db_user.id).count()
    permanent_holds = db.query(NumberHold).filter_by(user_id=db_user.id, is_permanent=True).count()
    
    message = (
        "👤 <b>Your Profile</b>\n\n"
        f"🆔 <b>User ID:</b> <code>{db_user.telegram_id}</code>\n"
        f"👤 <b>Username:</b> @{db_user.username if db_user.username else 'N/A'}\n"
        f"💰 <b>Balance:</b> ${db_user.balance:.2f}\n"
        f"💸 <b>Total Spent:</b> ${db_user.total_spent:.2f}\n"
        f"📨 <b>Total SMS Received:</b> {db_user.total_sms_received}\n"
        f"🔒 <b>Numbers Held:</b> {held_numbers} ({permanent_holds} permanent)\n"
        f"📅 <b>Joined:</b> {db_user.created_at.strftime('%Y-%m-%d %H:%M')}\n"
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def recharge_request_callback(query, context, db, db_user):
    """Handle recharge request from user."""
    log_access(db, db_user, "recharge_request")
    
    message = (
        "💰 <b>Recharge Balance</b>\n\n"
        "To recharge your balance, please contact an administrator.\n\n"
        "📞 Send a message to the admin with:\n"
        "• Your User ID\n"
        "• Amount you want to recharge\n"
        "• Payment proof (if required)\n\n"
        f"Your User ID: <code>{db_user.telegram_id}</code>\n"
    )
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def admin_manage_bans_callback(query, context, db, db_user):
    """Manage banned users (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    log_access(db, db_user, "admin_manage_bans")
    
    # Get all users
    users = db.query(User).order_by(User.created_at.desc()).limit(10).all()
    
    message = "🚫 Ban/Unban Users\n\n"
    message += "Select a user to toggle ban status:\n\n"
    
    keyboard = []
    for user in users:
        ban_badge = "🚫" if user.is_banned else "✅"
        username_str = f"@{user.username}" if user.username else f"ID:{user.telegram_id}"
        button_text = f"{ban_badge} {username_str}"
        
        if user.is_banned:
            callback = f"unban_user_{user.id}"
        else:
            callback = f"ban_user_{user.id}"
        
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback)])
    
    keyboard.append([InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup)


async def ban_user_callback(query, context, db, db_user, target_user_id):
    """Ban a user (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    target_user = db.query(User).filter_by(id=target_user_id).first()
    if target_user:
        # Don't allow banning admins
        if target_user.is_admin:
            await query.answer("❌ Cannot ban an admin user", show_alert=True)
            return
        
        target_user.is_banned = True
        db.commit()
        log_access(db, db_user, f"ban_user_{target_user.telegram_id}")
        await query.answer(f"✅ User {target_user.telegram_id} has been banned")
    else:
        await query.answer("❌ User not found")
    
    # Refresh the manage bans view
    await admin_manage_bans_callback(query, context, db, db_user)


async def unban_user_callback(query, context, db, db_user, target_user_id):
    """Unban a user (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    target_user = db.query(User).filter_by(id=target_user_id).first()
    if target_user:
        target_user.is_banned = False
        db.commit()
        log_access(db, db_user, f"unban_user_{target_user.telegram_id}")
        await query.answer(f"✅ User {target_user.telegram_id} has been unbanned")
    else:
        await query.answer("❌ User not found")
    
    # Refresh the manage bans view
    await admin_manage_bans_callback(query, context, db, db_user)


async def admin_manage_balance_callback(query, context, db, db_user):
    """Manage user balances (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    log_access(db, db_user, "admin_manage_balance")
    
    # Get all users
    users = db.query(User).order_by(User.created_at.desc()).limit(10).all()
    
    message = "💰 Manage User Balance\n\n"
    message += "Select a user to manage their balance:\n\n"
    
    for user in users:
        username_str = f"@{user.username}" if user.username else f"ID:{user.telegram_id}"
        message += f"👤 {username_str} - Balance: ${user.balance:.2f}\n"
    
    message += "\n💡 Tip: Use /addbalance <user_id> <amount> or /deductbalance <user_id> <amount> commands"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup)


async def add_balance_prompt_callback(query, context, db, db_user, target_user_id):
    """Prompt for balance addition (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    # This is a placeholder - actual implementation requires message handler
    await query.answer("💡 Use /addbalance <user_id> <amount> command", show_alert=True)


async def deduct_balance_prompt_callback(query, context, db, db_user, target_user_id):
    """Prompt for balance deduction (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    # This is a placeholder - actual implementation requires message handler
    await query.answer("💡 Use /deductbalance <user_id> <amount> command", show_alert=True)


async def admin_recharge_requests_callback(query, context, db, db_user):
    """View and manage recharge requests (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    log_access(db, db_user, "admin_recharge_requests")
    
    # Get pending recharge requests
    pending_requests = db.query(RechargeRequest).filter_by(status='pending').order_by(RechargeRequest.created_at.desc()).limit(10).all()
    
    message = "💳 <b>Recharge Requests</b>\n\n"
    
    if not pending_requests:
        message += "No pending recharge requests.\n"
        keyboard = [[InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_back")]]
    else:
        message += f"Pending requests: {len(pending_requests)}\n\n"
        
        keyboard = []
        for req in pending_requests:
            req_user = db.query(User).filter_by(id=req.user_id).first()
            username_str = f"@{req_user.username}" if req_user.username else f"ID:{req_user.telegram_id}"
            button_text = f"{username_str} - ${req.amount:.2f}"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=f"view_recharge_{req.id}")])
        
        message += "💡 Tip: Use /approverecharge <request_id> or /rejectrecharge <request_id> commands"
        keyboard.append([InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_back")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def approve_recharge_callback(query, context, db, db_user, request_id):
    """Approve a recharge request (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    # This is handled via command
    await query.answer("💡 Use /approverecharge <request_id> command", show_alert=True)


async def reject_recharge_callback(query, context, db, db_user, request_id):
    """Reject a recharge request (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    # This is handled via command
    await query.answer("💡 Use /rejectrecharge <request_id> command", show_alert=True)


async def admin_price_ranges_callback(query, context, db, db_user):
    """Manage price ranges (admin only)."""
    if not is_user_admin(db, db_user.telegram_id):
        await query.answer("❌ Admin access required", show_alert=True)
        return
    
    log_access(db, db_user, "admin_price_ranges")
    
    # Get all price ranges
    price_ranges = db.query(PriceRange).order_by(PriceRange.created_at.desc()).limit(10).all()
    
    message = "💵 <b>SMS Price Ranges</b>\n\n"
    
    if not price_ranges:
        message += "No price ranges configured.\n\n"
    else:
        for pr in price_ranges:
            message += f"📍 Pattern: <code>{pr.range_pattern}</code>\n"
            message += f"   Price: ${pr.price:.2f}\n\n"
    
    message += "💡 Use /setprice <pattern> <price> to set a price range\n"
    message += "Example: /setprice russia 2.5"
    
    keyboard = [[InlineKeyboardButton("⬅️ Back to Admin Panel", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


def is_phone_number(text):
    """Check if the text is a valid phone number."""
    # Remove any whitespace or special characters
    cleaned = re.sub(r'[^\d+]', '', text)
    
    # Check if it's a valid phone number (at least 10 digits, optionally starting with +)
    # Pattern: optional +, then 10-15 digits
    pattern = r'^\+?\d{10,15}$'
    return bool(re.match(pattern, cleaned))


def is_stats_row(row):
    """
    Check if a row from the SMS messages API is a statistics row rather than an actual message.
    
    Stats rows typically have comma-separated values with percentages in the first field,
    e.g., "0.01,0,0,0,0,0,0.01,0,0,100%,NAN%,NAN%,1"
    
    Args:
        row: A list representing a row from the aaData array
        
    Returns:
        True if the row is a stats row, False if it's an actual SMS message
    """
    if not isinstance(row, list) or len(row) < 1:
        return False
    
    first_field = row[0]
    if not isinstance(first_field, str):
        return False
    
    # Stats rows have comma-separated values with percentage signs
    return ',' in first_field and '%' in first_field


async def handle_phone_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle phone number search when user sends a phone number."""
    message = update.message
    if not message or not message.text:
        return
    
    text = message.text.strip()
    
    # Check if the message is a phone number
    if not is_phone_number(text):
        return
    
    # Extract clean phone number
    phone_number = re.sub(r'[^\d+]', '', text)
    
    # Get database session
    db = get_db_session()
    try:
        # Get or create user
        user = get_or_create_user(
            db,
            telegram_id=message.from_user.id,
            username=message.from_user.username or message.from_user.first_name
        )
        
        # Check if user is banned
        if user.is_banned:
            await message.reply_text(
                "🚫 You have been banned from using this bot.\n"
                "Please contact an administrator if you believe this is an error."
            )
            return
        
        # Check channel membership
        if not await check_channel_membership(update, context):
            return
        
        # Check if this number is held by the user
        held_number = db.query(NumberHold).filter_by(
            user_id=user.id,
            phone_number=phone_number
        ).first()
        
        if not held_number:
            await message.reply_text(
                "❌ This number is not held by you.\n"
                "Please request numbers from a range first."
            )
            return
        
        # Update first retry time if not set
        if not held_number.first_retry_time:
            update_first_retry_time(db, user, phone_number)
        
        # Log the search
        log_access(db, user, f"SMS search: {phone_number}")
        
        # Send "searching" message
        searching_msg = await message.reply_text(
            f"🔍 Searching SMS messages for <code>{escape_html(phone_number)}</code>...",
            parse_mode='HTML'
        )
        
        try:
            # Get scrapper session
            scrapper = get_scrapper_session()
            
            # Search for SMS messages
            data = scrapper.get_sms_messages(phone_number)
            
            if not data:
                await searching_msg.edit_text(
                    "❌ Failed to retrieve SMS messages. Please try again later."
                )
                return
            
            # Parse response
            total_records = data.get('iTotalRecords', '0')
            if isinstance(total_records, str):
                total_records = int(total_records) if total_records.isdigit() else 0
            
            messages = data.get('aaData', [])
            
            # Filter out the stats row using helper function
            actual_messages = []
            for msg in messages:
                if isinstance(msg, list) and len(msg) >= 6:
                    if not is_stats_row(msg):
                        actual_messages.append(msg)
            
            if not actual_messages:
                # Create keyboard with retry button
                keyboard = [
                    [
                        InlineKeyboardButton("🔄 Retry", callback_data=f"retry_sms_{phone_number}"),
                        InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")
                    ]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await searching_msg.edit_text(
                    f"📭 No SMS messages found for <code>{escape_html(phone_number)}</code>",
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
                return
            
            # SMS found! Mark as permanent and deduct balance
            if not held_number.is_permanent:
                # Get price for this range
                price = get_price_for_range(db, held_number.range_id)
                
                # Deduct balance
                new_balance = deduct_user_balance(
                    db, user, price, 
                    transaction_type='sms_charge',
                    description=f"SMS received on {phone_number}"
                )
                
                if new_balance is None:
                    await searching_msg.edit_text(
                        "❌ Insufficient balance to complete this transaction."
                    )
                    return
                
                # Mark as permanent hold
                mark_number_permanent(db, user, phone_number)
            
            # Format messages
            message_text = f"📱 <b>SMS Messages for {escape_html(phone_number)}</b>\n"
            message_text += f"Found {len(actual_messages)} message(s)\n"
            
            # Show balance deduction info if it was just deducted
            if not held_number.is_permanent:
                message_text += f"\n💸 Balance deducted: ${price:.2f}\n"
                message_text += f"💰 New balance: ${user.balance:.2f}\n"
            
            message_text += "\n"
            
            for i, msg_data in enumerate(actual_messages, 1):
                time = msg_data[0] if len(msg_data) > 0 else "N/A"
                sender_id = msg_data[3] if len(msg_data) > 3 else "N/A"
                sms_body = msg_data[5] if len(msg_data) > 5 else "N/A"
                
                # Clean up None values
                if sender_id is None:
                    sender_id = "Unknown"
                if sms_body is None:
                    sms_body = "(empty)"
                
                # Escape HTML in the content
                time_escaped = escape_html(str(time))
                sender_escaped = escape_html(str(sender_id))
                body_escaped = escape_html(str(sms_body))
                
                message_text += f"<b>Message {i}:</b>\n"
                message_text += f"🕒 <b>Time:</b> {time_escaped}\n"
                message_text += f"📨 <b>Sender:</b> {sender_escaped}\n"
                message_text += f"💬 <b>Message:</b>\n<pre>{body_escaped}</pre>\n\n"
                
                # Telegram has a message length limit, so split if needed
                if len(message_text) > MAX_TELEGRAM_MESSAGE_LENGTH:
                    message_text += f"<i>... and {len(actual_messages) - i} more message(s)</i>"
                    break
            
            # Create keyboard with back button
            keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await searching_msg.edit_text(
                message_text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            logger.error(f"Error in phone search: {e}")
            await searching_msg.edit_text(
                "❌ An error occurred while searching for SMS messages. Please try again later."
            )
    finally:
        db.close()


async def retry_sms_callback(query, context, db, db_user):
    """Handle retry button for SMS search."""
    # Extract phone number from callback data (format: retry_sms_PHONENUMBER)
    phone_number = query.data.replace("retry_sms_", "")
    
    # Check if this number is held by the user
    held_number = db.query(NumberHold).filter_by(
        user_id=db_user.id,
        phone_number=phone_number
    ).first()
    
    if not held_number:
        await query.answer("❌ This number is not held by you.", show_alert=True)
        return
    
    # Update first retry time if not set
    if not held_number.first_retry_time:
        update_first_retry_time(db, db_user, phone_number)
    
    # Log the retry
    log_access(db, db_user, f"SMS search retry: {phone_number}")
    
    # Show searching message
    await query.edit_message_text(
        f"🔍 Searching SMS messages for <code>{escape_html(phone_number)}</code>...",
        parse_mode='HTML'
    )
    
    try:
        # Get scrapper session
        scrapper = get_scrapper_session()
        
        # Search for SMS messages
        data = scrapper.get_sms_messages(phone_number)
        
        if not data:
            # Create keyboard with retry button
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Retry", callback_data=f"retry_sms_{phone_number}"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "❌ Failed to retrieve SMS messages. Please try again.",
                reply_markup=reply_markup
            )
            return
        
        # Parse response
        total_records = data.get('iTotalRecords', '0')
        if isinstance(total_records, str):
            total_records = int(total_records) if total_records.isdigit() else 0
        
        messages = data.get('aaData', [])
        
        # Filter out the stats row
        actual_messages = []
        for msg in messages:
            if isinstance(msg, list) and len(msg) >= 6:
                if not is_stats_row(msg):
                    actual_messages.append(msg)
        
        if not actual_messages:
            # Create keyboard with retry button
            keyboard = [
                [
                    InlineKeyboardButton("🔄 Retry", callback_data=f"retry_sms_{phone_number}"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"📭 No SMS messages found for <code>{escape_html(phone_number)}</code>",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            return
        
        # SMS found! Mark as permanent and deduct balance
        if not held_number.is_permanent:
            # Get price for this range
            price = get_price_for_range(db, held_number.range_id)
            
            # Deduct balance
            new_balance = deduct_user_balance(
                db, db_user, price, 
                transaction_type='sms_charge',
                description=f"SMS received on {phone_number}"
            )
            
            if new_balance is None:
                await query.edit_message_text(
                    "❌ Insufficient balance to complete this transaction."
                )
                return
            
            # Mark as permanent hold
            mark_number_permanent(db, db_user, phone_number)
        
        # Format messages
        message_text = f"📱 <b>SMS Messages for {escape_html(phone_number)}</b>\n"
        message_text += f"Found {len(actual_messages)} message(s)\n"
        
        # Show balance deduction info if it was just deducted
        if not held_number.is_permanent:
            message_text += f"\n💸 Balance deducted: ${price:.2f}\n"
            message_text += f"💰 New balance: ${db_user.balance:.2f}\n"
        
        message_text += "\n"
        
        for i, msg_data in enumerate(actual_messages, 1):
            time = msg_data[0] if len(msg_data) > 0 else "N/A"
            sender_id = msg_data[3] if len(msg_data) > 3 else "N/A"
            sms_body = msg_data[5] if len(msg_data) > 5 else "N/A"
            
            # Clean up None values
            if sender_id is None:
                sender_id = "Unknown"
            if sms_body is None:
                sms_body = "(empty)"
            
            # Escape HTML in the content
            time_escaped = escape_html(str(time))
            sender_escaped = escape_html(str(sender_id))
            body_escaped = escape_html(str(sms_body))
            
            message_text += f"<b>Message {i}:</b>\n"
            message_text += f"🕒 <b>Time:</b> {time_escaped}\n"
            message_text += f"📨 <b>Sender:</b> {sender_escaped}\n"
            message_text += f"💬 <b>Message:</b>\n<pre>{body_escaped}</pre>\n\n"
            
            # Telegram has a message length limit
            if len(message_text) > MAX_TELEGRAM_MESSAGE_LENGTH:
                message_text += f"<i>... and {len(actual_messages) - i} more message(s)</i>"
                break
        
        # Create keyboard with back button
        keyboard = [[InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            message_text,
            parse_mode='HTML',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error in SMS retry: {e}")
        
        # Create keyboard with retry button
        keyboard = [
            [
                InlineKeyboardButton("🔄 Retry", callback_data=f"retry_sms_{phone_number}"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="back_to_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "❌ An error occurred while searching for SMS messages. Please try again.",
            reply_markup=reply_markup
        )


async def addbalance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /addbalance command (admin only)."""
    user = update.effective_user
    db = get_db_session()
    
    try:
        # Check if user is admin
        if not is_user_admin(db, user.id):
            await update.message.reply_text("❌ You don't have admin privileges.")
            return
        
        # Parse command arguments
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Usage: /addbalance <user_id> <amount>\n"
                "Example: /addbalance 123456789 10.50"
            )
            return
        
        try:
            target_telegram_id = int(context.args[0])
            amount = float(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID or amount.")
            return
        
        if amount <= 0:
            await update.message.reply_text("❌ Amount must be positive.")
            return
        
        # Find target user
        target_user = db.query(User).filter_by(telegram_id=target_telegram_id).first()
        if not target_user:
            await update.message.reply_text(f"❌ User with ID {target_telegram_id} not found.")
            return
        
        # Add balance
        admin_user = get_or_create_user(db, user.id, user.username)
        new_balance = add_user_balance(
            db, target_user, amount, 
            transaction_type='admin_add',
            description=f"Admin added by {user.id}"
        )
        
        log_access(db, admin_user, f"add_balance_{target_telegram_id}_{amount}")
        
        await update.message.reply_text(
            f"✅ Successfully added ${amount:.2f} to user {target_telegram_id}\n"
            f"New balance: ${new_balance:.2f}"
        )
    finally:
        db.close()


async def deductbalance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /deductbalance command (admin only)."""
    user = update.effective_user
    db = get_db_session()
    
    try:
        # Check if user is admin
        if not is_user_admin(db, user.id):
            await update.message.reply_text("❌ You don't have admin privileges.")
            return
        
        # Parse command arguments
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Usage: /deductbalance <user_id> <amount>\n"
                "Example: /deductbalance 123456789 5.50"
            )
            return
        
        try:
            target_telegram_id = int(context.args[0])
            amount = float(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID or amount.")
            return
        
        if amount <= 0:
            await update.message.reply_text("❌ Amount must be positive.")
            return
        
        # Find target user
        target_user = db.query(User).filter_by(telegram_id=target_telegram_id).first()
        if not target_user:
            await update.message.reply_text(f"❌ User with ID {target_telegram_id} not found.")
            return
        
        # Check if user has sufficient balance
        if target_user.balance < amount:
            await update.message.reply_text(
                f"❌ User has insufficient balance.\n"
                f"Current balance: ${target_user.balance:.2f}\n"
                f"Requested deduction: ${amount:.2f}"
            )
            return
        
        # Deduct balance
        admin_user = get_or_create_user(db, user.id, user.username)
        new_balance = deduct_user_balance(
            db, target_user, amount, 
            transaction_type='admin_deduct',
            description=f"Admin deducted by {user.id}"
        )
        
        log_access(db, admin_user, f"deduct_balance_{target_telegram_id}_{amount}")
        
        await update.message.reply_text(
            f"✅ Successfully deducted ${amount:.2f} from user {target_telegram_id}\n"
            f"New balance: ${new_balance:.2f}"
        )
    finally:
        db.close()


async def setprice_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /setprice command (admin only)."""
    user = update.effective_user
    db = get_db_session()
    
    try:
        # Check if user is admin
        if not is_user_admin(db, user.id):
            await update.message.reply_text("❌ You don't have admin privileges.")
            return
        
        # Parse command arguments
        if len(context.args) < 2:
            await update.message.reply_text(
                "❌ Usage: /setprice <pattern> <price>\n"
                "Example: /setprice russia 2.5"
            )
            return
        
        pattern = context.args[0].lower()
        try:
            price = float(context.args[1])
        except ValueError:
            await update.message.reply_text("❌ Invalid price.")
            return
        
        if price < 0:
            await update.message.reply_text("❌ Price must be non-negative.")
            return
        
        # Check if pattern already exists
        existing = db.query(PriceRange).filter_by(range_pattern=pattern).first()
        
        admin_user = get_or_create_user(db, user.id, user.username)
        
        if existing:
            # Update existing price
            existing.price = price
            db.commit()
            action = "updated"
        else:
            # Create new price range
            price_range = PriceRange(
                range_pattern=pattern,
                price=price,
                created_by=admin_user.id
            )
            db.add(price_range)
            db.commit()
            action = "created"
        
        log_access(db, admin_user, f"set_price_{pattern}_{price}")
        
        await update.message.reply_text(
            f"✅ Price range {action} successfully!\n"
            f"Pattern: {pattern}\n"
            f"Price: ${price:.2f}"
        )
    finally:
        db.close()


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors in a clean and informative way."""
    # Extract useful information from update
    update_info = "No update information"
    if update:
        try:
            if update.effective_user:
                user_id = update.effective_user.id
                username = update.effective_user.username or "N/A"
                update_info = f"User {user_id} (@{username})"
            
            if update.effective_chat:
                chat_id = update.effective_chat.id
                update_info += f", Chat {chat_id}"
            
            if update.message and update.message.text:
                text = update.message.text[:100]  # Truncate long messages
                update_info += f", Text: '{text}'"
            elif update.callback_query:
                data = update.callback_query.data
                update_info += f", Callback: '{data}'"
        except Exception as e:
            update_info += f" (Error extracting info: {e})"
    
    # Log the error with clean information
    error_msg = f"Error occurred: {context.error.__class__.__name__}: {str(context.error)}"
    logger.error(f"{update_info} - {error_msg}")
    
    # Log full traceback at debug level
    if context.error:
        tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
        tb_string = ''.join(tb_list)
        logger.debug(f"Full traceback:\n{tb_string}")


def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command))
    application.add_handler(CommandHandler("addbalance", addbalance_command))
    application.add_handler(CommandHandler("deductbalance", deductbalance_command))
    application.add_handler(CommandHandler("setprice", setprice_command))
    
    # Register message handler for phone number search
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone_search))
    
    # Register callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Starting ARGSMS Telegram Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
