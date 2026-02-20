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
    
    # Parse the data
    message = "📱 Available SMS Ranges\n\n"
    
    # Handle different possible JSON structures
    ranges = []
    has_more = False
    
    if isinstance(data, dict):
        if 'results' in data:
            ranges = data['results']
            has_more = data.get('pagination', {}).get('more', False)
        elif 'data' in data:
            ranges = data['data']
            has_more = page * 10 < data.get('total', 0)
        elif 'aaData' in data:
            ranges = data['aaData']
        else:
            ranges = [data]
    elif isinstance(data, list):
        ranges = data
    
    if not ranges:
        message += "No SMS ranges available.\n"
    else:
        for i, item in enumerate(ranges, 1):
            message += f"{(page-1)*10 + i}. "
            if isinstance(item, dict):
                # Format dict items
                for key, value in item.items():
                    message += f"{key}: {value}  "
                message += "\n"
            elif isinstance(item, list):
                message += " | ".join(str(x) for x in item) + "\n"
            else:
                message += str(item) + "\n"
    
    # Create pagination keyboard
    keyboard = []
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
    if not db_user.is_admin:
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
    if not db_user.is_admin:
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
    if not db_user.is_admin:
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
    if not db_user.is_admin:
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
    if not db_user.is_admin:
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
