"""Telegram bot for ARGSMS - SMS range management system."""

import os
import json
import logging
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
    User
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

# Constants for button text formatting
MAX_BUTTON_TEXT_LENGTH = 60
MAX_TITLE_LENGTH = 50

# Initialize database session factory
SessionFactory = init_db()


def get_db_session():
    """Get a new database session."""
    return SessionFactory()


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle the /start command."""
    user = update.effective_user
    db = get_db_session()
    
    try:
        # Get or create user in database
        db_user = get_or_create_user(db, user.id, user.username)
        log_access(db, db_user, "start_command")
        
        # Create main menu
        keyboard = [
            [InlineKeyboardButton("📱 View SMS Ranges", callback_data="view_sms_ranges")],
            [InlineKeyboardButton("ℹ️ About", callback_data="about")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        welcome_message = (
            f"👋 Welcome to ARGSMS Bot, {user.first_name}!\n\n"
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
        
        callback_data = query.data
        
        # Main menu callbacks
        if callback_data == "view_sms_ranges":
            await view_sms_ranges_callback(query, context, db, db_user)
        elif callback_data == "about":
            await about_callback(query, context, db, db_user)
        elif callback_data == "back_to_main":
            await back_to_main_callback(query, context, db, db_user)
        
        # Admin panel callbacks
        elif callback_data == "admin_list_users":
            await admin_list_users_callback(query, context, db, db_user)
        elif callback_data == "admin_manage_admins":
            await admin_manage_admins_callback(query, context, db, db_user)
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
            parts = callback_data.split("_")
            range_id = parts[2]
            start = int(parts[3]) if len(parts) > 3 else 0
            await view_sms_numbers_callback(query, context, db, db_user, range_id, start)
        
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
            escaped_value = str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            message += f"<b>{formatted_key}</b>: {escaped_value}\n"
    elif isinstance(range_data, list):
        message += " | ".join(str(x) for x in range_data)
    else:
        message += str(range_data)
    
    # Add buttons for actions and navigation
    keyboard = [
        [InlineKeyboardButton("📞 View Numbers", callback_data=f"view_numbers_{range_id}_0")],
        [InlineKeyboardButton("⬅️ Back to Ranges", callback_data="view_sms_ranges")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(message, reply_markup=reply_markup, parse_mode='HTML')


async def view_sms_numbers_callback(query, context, db, db_user, range_id, start=0):
    """Show SMS numbers for a specific range."""
    log_access(db, db_user, f"view_sms_numbers_{range_id}_start_{start}")
    
    # Get scrapper session and fetch numbers
    scrapper = get_scrapper_session()
    length = 10  # Numbers per page
    
    # Safety check
    if length <= 0:
        length = 10
    
    data = scrapper.get_sms_numbers(range_id, start=start, length=length)
    
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
        total_records = data.get('iTotalRecords', 0)
    
    # Calculate page info
    current_page = (start // length) + 1
    total_pages = (total_records + length - 1) // length if total_records > 0 else 1
    
    # Format message
    message = f"📞 <b>SMS Numbers - Range {range_id}</b>\n"
    message += f"<i>Page {current_page}/{total_pages} ({len(numbers)} numbers)</i>\n\n"
    
    if not numbers:
        message += "No SMS numbers found in this range."
    else:
        for i, number in enumerate(numbers, 1):
            if isinstance(number, list) and len(number) > 0:
                # Format list data - typically: [number, status, date, etc.]
                number_str = number[0] if len(number) > 0 else "N/A"
                status = number[1] if len(number) > 1 else "N/A"
                message += f"{start + i}. <code>{number_str}</code>"
                if status:
                    message += f" - {status}"
                message += "\n"
            elif isinstance(number, dict):
                # Format dict data
                number_str = number.get('number', number.get('phone', 'N/A'))
                status = number.get('status', '')
                message += f"{start + i}. <code>{number_str}</code>"
                if status:
                    message += f" - {status}"
                message += "\n"
            else:
                message += f"{start + i}. {number}\n"
    
    # Create navigation keyboard
    keyboard = []
    
    # Pagination buttons
    nav_buttons = []
    if start > 0:
        prev_start = max(0, start - length)
        nav_buttons.append(InlineKeyboardButton("⬅️ Previous", callback_data=f"view_numbers_{range_id}_{prev_start}"))
    
    if start + length < total_records:
        next_start = start + length
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"view_numbers_{range_id}_{next_start}"))
    
    if nav_buttons:
        keyboard.append(nav_buttons)
    
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
        [InlineKeyboardButton("ℹ️ About", callback_data="about")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_message = (
        f"👋 Welcome to ARGSMS Bot!\n\n"
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
        username_str = f"@{user.username}" if user.username else "N/A"
        message += f"{admin_badge} ID: {user.telegram_id} | {username_str}\n"
        message += f"   Joined: {user.created_at.strftime('%Y-%m-%d %H:%M')}\n\n"
    
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
    total_users = db.query(User).count()
    admin_users = db.query(User).filter_by(is_admin=True).count()
    
    from sqlalchemy import func
    from database import AccessLog
    
    today = datetime.utcnow().date()
    today_logs = db.query(AccessLog).filter(
        func.date(AccessLog.timestamp) == today
    ).count()
    
    message = (
        "📊 Bot Statistics\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🔑 Admin Users: {admin_users}\n"
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
        [InlineKeyboardButton("📊 View Stats", callback_data="admin_view_stats")],
        [InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="back_to_main")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    admin_message = (
        "🔐 Admin Panel\n\n"
        "Welcome to the admin panel. Select an option:"
    )
    
    await query.edit_message_text(admin_message, reply_markup=reply_markup)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    logger.error(f"Update {update} caused error {context.error}")


def main():
    """Start the bot."""
    # Create the Application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("admin", admin_command))
    
    # Register callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Register error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Starting ARGSMS Telegram Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
