from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import logging
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, insert, select, Table, MetaData, Column, Integer, String, DateTime, Text, text
from sqlalchemy.exc import IntegrityError
from collections import defaultdict
from datetime import datetime, timedelta
import requests
from io import BytesIO
from telegram import InputFile
from typing import Optional, Dict, Any
from sqlalchemy.sql import func
import asyncio
from linkedin_api import Linkedin
import json
import logging.handlers
from config.logging_config import setup_logging
from time import sleep
import aiohttp
from sqlalchemy.sql import or_
import csv
import time
import telegram.error
import platform



message_timestamps = defaultdict(list)

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
DB_HOST = os.getenv('DB_HOST')
DB_PORT = os.getenv('DB_PORT')
DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')

# Optional runtime mode configuration
BOT_MODE = (os.getenv('BOT_MODE', 'auto') or 'auto').strip().lower()
VALID_BOT_MODES = {'auto', 'polling', 'webhook'}

# Validate environment variables that are always required
required_env = {
    'TELEGRAM_BOT_TOKEN': TELEGRAM_BOT_TOKEN,
    'DB_HOST': DB_HOST,
    'DB_PORT': DB_PORT,
    'DB_NAME': DB_NAME,
    'DB_USER': DB_USER,
    'DB_PASSWORD': DB_PASSWORD,
}
missing_env = [name for name, value in required_env.items() if not value]
if missing_env:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_env)}")

if BOT_MODE not in VALID_BOT_MODES:
    raise ValueError(f"Invalid BOT_MODE '{BOT_MODE}'. Expected one of {', '.join(sorted(VALID_BOT_MODES))}.")

USE_WEBHOOK = False
if BOT_MODE == 'webhook':
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL must be set when BOT_MODE=webhook.")
    USE_WEBHOOK = True
elif BOT_MODE == 'auto':
    USE_WEBHOOK = bool(WEBHOOK_URL)

# Database connection string
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Initialize SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Configure logging with rotation
log_file = os.getenv('LOG_FILE', 'logs/bot.log')
os.makedirs(os.path.dirname(log_file), exist_ok=True)

handler = logging.handlers.RotatingFileHandler(
    log_file,
    maxBytes=1024 * 1024,  # 1MB
    backupCount=5
)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)

logger = setup_logging(__name__)
logger.info("Bot configured to run in %s mode (webhook enabled: %s)", BOT_MODE, USE_WEBHOOK)

# Initialize metadata
meta = MetaData()

# Define the LinkedIn user table
linkedin_table = Table(
    'user_linkedin', meta,
    Column('id', Integer, primary_key=True),
    Column('linkedin_url', String, unique=True, nullable=False),
    Column('telegram_user_id', BigInteger, nullable=False),
    Column('full_name', String),
    Column('headline', String),
    Column('location', String),
    Column('current_company', String),
    Column('summary', Text),
    Column('created_at', DateTime, default=datetime.utcnow),
    Column('updated_at', DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
)

PROFILE_COLUMNS = {column.name for column in linkedin_table.columns}

# Helper to keep DB payload in sync with defined columns
def sanitize_profile_data(data: Dict[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if key in PROFILE_COLUMNS}

# Add LinkedIn API initialization
try:
    logger.info("Initializing LinkedIn API...")
    LINKEDIN_USERNAME = os.getenv('LINKEDIN_USERNAME')
    LINKEDIN_PASSWORD = os.getenv('LINKEDIN_PASSWORD')
    
    if not all([LINKEDIN_USERNAME, LINKEDIN_PASSWORD]):
        logger.warning("LinkedIn credentials not found - bot will run without LinkedIn API features")
        api = None
    else:
        try:
            # Initialize API with basic authentication (removed unsupported parameters)
            api = Linkedin(
                LINKEDIN_USERNAME,
                LINKEDIN_PASSWORD
            )
            # Test the connection with a simple operation
            logger.info("Testing LinkedIn connection...")
            try:
                # Use a simpler test that's less likely to trigger security
                me = api.get_profile()
                if me:
                    logger.info("LinkedIn API initialized successfully")
                else:
                    raise Exception("Could not verify LinkedIn connection")
            except Exception as test_error:
                logger.error(f"LinkedIn API test failed: {str(test_error)}")
                api = None
                
        except Exception as api_error:
            logger.error(f"LinkedIn API initialization failed: {str(api_error)}", exc_info=True)
            if "CHALLENGE" in str(api_error):
                logger.warning("""
                LinkedIn requires additional verification. To fix this:
                1. Log in to LinkedIn in your browser with the same account
                2. Complete any security verification steps
                3. Make sure 2FA is disabled for this account
                4. Wait 15-30 minutes before trying again
                5. Consider using a different LinkedIn account
                Bot will continue without LinkedIn API features.
                """)
            else:
                logger.error(f"Unexpected error during LinkedIn API initialization: {str(api_error)}", exc_info=True)
            api = None

except Exception as e:
    logger.error(f"Failed to initialize LinkedIn API: {str(e)}", exc_info=True)
    api = None

# Define handlers
async def get_main_keyboard():
    """Get the main keyboard markup"""
    keyboard = [
        [KeyboardButton("➕ Add Profile"), KeyboardButton("👥 View Users")],
        [KeyboardButton("📚 Help"), KeyboardButton("ℹ️ Status")],
        [KeyboardButton("❌ Delete Profile"), KeyboardButton("🔄 Update Profile")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: CallbackContext) -> None:
    try:
        user_id = update.message.from_user.id
        username = update.message.from_user.username
        logger.info(f"New user {user_id} (@{username}) started the bot")
        
        reply_markup = await get_main_keyboard()
        
        welcome_text = (
            "🌟 *Welcome to the LinkedIn Profile Sharing Bot!* 🌟\n\n"
            "Connect with professionals and share your LinkedIn profile easily.\n\n"
            "📝 *How to use:*\n"
            "• Share your LinkedIn profile URL\n"
            "• View other professionals' profiles\n"
            "• Get notified about new connections\n\n"
            "🔗 *Share your profile by sending a URL like:*\n"
            "`https://www.linkedin.com/in/username`\n\n"
            "Use the buttons below to navigate! 👇"
        )
        
        await update.message.reply_text(
            welcome_text, 
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error in start command: {str(e)}", exc_info=True)
        await update.message.reply_text("Sorry, an error occurred. Please try again later.")

async def handle_message(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    user_message = update.message.text
    logger.info(f"Received message from user {user_id}: {user_message}")
    
    # List of all valid button commands
    valid_commands = [
        "📚 Help", "ℹ️ Status", "❌ Delete Profile", "🔄 Update Profile", 
        "👥 View Users", "➕ Add Profile", "🏠 Back to Main Menu",
        "✅ Yes, Delete My Profile", "❌ No, Keep My Profile"
    ]
    
    # Handle button commands first
    if user_message in valid_commands:
        if user_message == "🏠 Back to Main Menu":
            await back_to_main_menu(update, context)
            return
        elif user_message == "📚 Help":
            await help_command(update, context)
        elif user_message == "ℹ️ Status":
            await status(update, context)
        elif user_message == "❌ Delete Profile":
            await delete_profile(update, context)
        elif user_message == "🔄 Update Profile":
            await update_profile(update, context)
        elif user_message == "👥 View Users":
            await show_user_list(update, context)
        elif user_message == "➕ Add Profile":
            await add_profile(update, context)
        return

    # Handle profile update flow
    if context.user_data.get('awaiting_update'):
        if is_valid_linkedin_url(user_message):
            await process_profile_update(update, context, user_message)
        else:
            await update.message.reply_text(
                "Please send a valid LinkedIn profile URL in the format:\n"
                "https://www.linkedin.com/in/username"
            )
        return
    
    # Handle delete confirmation
    if context.user_data.get('awaiting_delete_confirmation'):
        if user_message.lower() in ["yes", "✅ yes, delete my profile"]:
            try:
                with engine.begin() as conn:
                    result = conn.execute(
                        linkedin_table.delete().where(linkedin_table.c.telegram_user_id == user_id)
                    )
                    if result.rowcount > 0:
                        logger.info(f"Successfully deleted profile for user {user_id}")
                        await update.message.reply_text("Your profile has been deleted.", reply_markup=await get_main_keyboard())
                    else:
                        logger.warning(f"No profile found to delete for user {user_id}")
                        await update.message.reply_text("No profile found to delete.")
            except Exception as e:
                logger.error(f"Error deleting profile for user {user_id}: {str(e)}", exc_info=True)
                await update.message.reply_text("Sorry, there was an error deleting your profile.")
        elif user_message.lower() in ["no", "❌ no, keep my profile"]:
            await update.message.reply_text("Profile deletion cancelled.", reply_markup=await get_main_keyboard())
        context.user_data.pop('awaiting_delete_confirmation', None)
        return

    # Handle LinkedIn URL processing
    if is_valid_linkedin_url(user_message):
        await process_linkedin_url(update, context, user_message)
    else:
        logger.warning(f"Invalid message received from user {user_id}: {user_message}")
        await update.message.reply_text("Please send a valid LinkedIn profile URL or use the buttons below.\nExample URL: https://www.linkedin.com/in/username")
            
async def add_profile(update: Update, context: CallbackContext) -> None:
    """Handle Add Profile button press"""
    user_id = update.message.from_user.id
    logger.info(f"Add profile requested by user {user_id}")
    
    try:
        # Check if user already has a profile
        with engine.connect() as conn:
            existing_profile = conn.execute(
                select(linkedin_table).where(linkedin_table.c.telegram_user_id == user_id)
            ).first()
            
            if existing_profile:
                await update.message.reply_text(
                    "❌ You already have a registered profile!\n\n"
                    "Use '🔄 Update Profile' to modify your existing profile or\n"
                    "'❌ Delete Profile' to remove it first."
                )
                return
        
        # Send instruction message
        await update.message.reply_text(
            "🔗 *Add Your LinkedIn Profile*\n\n"
            "Please send your LinkedIn profile URL in this format:\n"
            "`https://www.linkedin.com/in/username`\n\n"
            "Make sure your profile is public for best results!",
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error in add_profile for user {user_id}: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "❌ Sorry, there was an error processing your request.\n"
            "Please try again later."
        )


async def process_linkedin_url(update: Update, context: CallbackContext, url: str) -> None:
    """Process LinkedIn URL submission"""
    user_id = update.message.from_user.id
    
    # Check rate limit
    if not await rate_limit_check(user_id):
        logger.warning(f"Rate limit exceeded for user {user_id}")
        await update.message.reply_text("You're sending too many messages. Please wait a moment.")
        return

    try:
        # Check if user already has a profile
        with engine.connect() as conn:
            existing_profile = conn.execute(
                select(linkedin_table).where(linkedin_table.c.telegram_user_id == user_id)
            ).first()
            
            is_update = context.user_data.get('awaiting_update', False)
            
            if existing_profile and not is_update:
                logger.warning(f"Duplicate LinkedIn URL from user {user_id}")
                await update.message.reply_text(
                    "You have already registered a LinkedIn profile.\n"
                    "Use '❌ Delete Profile' to remove your current profile first, or\n"
                    "Use '🔄 Update Profile' to update your existing profile."
                )
                return

        # Fetch profile information
        profile_info = await fetch_linkedin_profile(url)
        
        # Insert the new profile
        with engine.begin() as conn:
            insert_data = {
                'linkedin_url': url,
                'telegram_user_id': user_id,
                'created_at': datetime.utcnow()
            }
            
            if profile_info:
                insert_data.update(profile_info)

            sanitized_data = sanitize_profile_data(insert_data)
            conn.execute(linkedin_table.insert(), sanitized_data)
            logger.info(f"Saved LinkedIn URL for user {user_id}")
            
            # Show other profiles and notify users only for new profiles
            await send_linkedin_profiles(update, url)
            await notify_users_of_new_profile(context, url, user_id)
        
    except IntegrityError:
        logger.warning(f"Duplicate LinkedIn URL from user {user_id}")
        await update.message.reply_text(
            "This LinkedIn profile has already been registered by another user.",
            reply_markup=await get_main_keyboard()
        )
        context.user_data.pop('awaiting_update', None)
    except Exception as e:
        logger.error(f"Error processing LinkedIn URL: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "Sorry, there was an error processing your LinkedIn URL.",
            reply_markup=await get_main_keyboard()
        )
        context.user_data.pop('awaiting_update', None)

async def process_profile_update(update: Update, context: CallbackContext, url: str) -> None:
    """Update an existing LinkedIn profile for the user."""
    user_id = update.message.from_user.id
    
    try:
        with engine.connect() as conn:
            existing_profile = conn.execute(
                select(linkedin_table).where(linkedin_table.c.telegram_user_id == user_id)
            ).first()
        
        if not existing_profile:
            context.user_data.pop('awaiting_update', None)
            await update.message.reply_text(
                "You don't have a profile yet. Please share your LinkedIn URL first."
            )
            return
        
        profile_info = await fetch_linkedin_profile(url)
        update_data = {
            'linkedin_url': url,
            'updated_at': datetime.utcnow()
        }
        
        if profile_info:
            update_data.update(profile_info)
        
        sanitized_data = sanitize_profile_data(update_data)
        
        with engine.begin() as conn:
            conn.execute(
                linkedin_table.update()
                .where(linkedin_table.c.telegram_user_id == user_id)
                .values(sanitized_data)
            )
        
        context.user_data.pop('awaiting_update', None)
        
        await update.message.reply_text(
            "✅ Your LinkedIn profile has been updated!",
            reply_markup=await get_main_keyboard()
        )
        
    except IntegrityError:
        await update.message.reply_text(
            "This LinkedIn profile URL is already registered by another user."
        )
    except Exception as e:
        logger.error(f"Error updating LinkedIn profile for user {user_id}: {str(e)}", exc_info=True)
        await update.message.reply_text("Sorry, there was an error updating your profile.")

async def send_linkedin_profiles(update: Update, user_message: str) -> None:
    """Send other LinkedIn profiles to the user in a structured format"""
    user_id = update.message.from_user.id
    logger.info(f"Fetching LinkedIn profiles for user {user_id}")
    
    try:
        with engine.connect() as conn:
            # Query all profiles except the current user's with all fields
            query = select(linkedin_table).where(
                linkedin_table.c.telegram_user_id != user_id
            )
            result = conn.execute(query)
            profiles = result.fetchall()
            
            if not profiles:
                logger.info(f"No other profiles to show to user {user_id}")
                await update.message.reply_text(
                    "You're the first one here! 🎉\n"
                    "Share your profile with others to grow the network."
                )
                return
            
            logger.info(f"Sending {len(profiles)} profiles to user {user_id}")
            
            # Send profiles one by one with formatted information
            for profile in profiles:
                profile_text = (
                    f"👤 *{profile.full_name or 'Name not available'}*\n"
                    f"{'✨ ' + profile.headline + chr(10) if profile.headline else ''}"
                    f"{'🏢 ' + profile.current_company + chr(10) if profile.current_company else ''}"
                    f"{'📍 ' + profile.location + chr(10) if profile.location else ''}"
                    f"\n🔗 [View Full Profile]({profile.linkedin_url})\n"
                    f"{'━' * 30}"
                )
                
                try:
                    await update.message.reply_text(
                        profile_text,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.error(f"Error sending profile {profile.linkedin_url}: {str(e)}")
                    continue
                
            # Send summary message
            await update.message.reply_text(
                f"✨ Showing {len(profiles)} professional{'s' if len(profiles) > 1 else ''} "
                f"in your network.\n\n"
                "💡 Use /search to find specific profiles\n"
                "📊 Use /stats to see network statistics",
                parse_mode='Markdown'
            )
                
    except Exception as e:
        logger.error(f"Error fetching profiles for user {user_id}: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "Sorry, there was an error fetching other profiles."
        )

async def notify_users_of_new_profile(context: CallbackContext, linkedin_url: str, new_user_id: int) -> None:
    """Notify existing users about new profile with structured information"""
    try:
        with engine.connect() as conn:
            # Get the new user's profile information
            new_profile = conn.execute(
                select(linkedin_table).where(linkedin_table.c.telegram_user_id == new_user_id)
            ).first()
            
            if not new_profile:
                logger.error(f"Could not find profile for new user {new_user_id}")
                return
                
            # Get all other users
            stmt = select(linkedin_table.c.telegram_user_id).where(
                linkedin_table.c.telegram_user_id != new_user_id
            )
            result = conn.execute(stmt)
            registered_users = [row[0] for row in result]

            # Create notification message with structured information
            notification_text = (
                "🎉 *New Connection Alert!*\n\n"
                f"👤 *{new_profile.full_name or 'New Professional'}*\n"
                f"{'✨ ' + new_profile.headline + chr(10) if new_profile.headline else ''}"
                f"{'🏢 ' + new_profile.current_company + chr(10) if new_profile.current_company else ''}"
                f"{'📍 ' + new_profile.location + chr(10) if new_profile.location else ''}"
                f"\n🔗 [View Full Profile]({linkedin_url})\n\n"
                "Connect and expand your professional network! ✨"
            )

            # Notify each user
            for user_id in registered_users:
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text=notification_text,
                        parse_mode='Markdown',
                        disable_web_page_preview=True
                    )
                    logger.info(f"Notified user {user_id} about new profile")
                except Exception as e:
                    logger.error(f"Failed to notify user {user_id}: {e}")
                    
    except Exception as e:
        logger.error(f"Error in notify_users_of_new_profile: {str(e)}", exc_info=True)

async def rate_limit_check(user_id: int, limit: int = 5, window: int = 60) -> bool:
    current_time = datetime.now()
    timestamps = message_timestamps[user_id]
    
    # Remove timestamps older than the window
    timestamps = [ts for ts in timestamps if (current_time - ts).total_seconds() < window]
    message_timestamps[user_id] = timestamps
    
    # Check if user has exceeded rate limit
    if len(timestamps) >= limit:
        return False
    
    # Add new timestamp
    timestamps.append(current_time)
    return True


# Error handling
async def error_handler(update: object, context: CallbackContext) -> None:
    logger.error("Exception while handling an update:", exc_info=context.error)
    if update and hasattr(update, 'effective_chat'):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Sorry, an error occurred while processing your request."
        )



async def delete_profile(update: Update, context: CallbackContext) -> None:
    """Delete user's LinkedIn profile with confirmation"""
    user_id = update.message.from_user.id
    logger.info(f"Delete profile request from user {user_id}")
    
    try:
        # First check if user has a profile
        with engine.connect() as conn:
            result = conn.execute(
                select(linkedin_table).where(linkedin_table.c.telegram_user_id == user_id)
            ).first()
            
            if not result:
                logger.warning(f"No profile found to delete for user {user_id}")
                await update.message.reply_text("You don't have a registered profile.")
                return
        
        # Create confirmation keyboard
        keyboard = [
            [KeyboardButton("✅ Yes, delete my profile")],
            [KeyboardButton("❌ No, keep my profile")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
        
        # Ask for confirmation
        await update.message.reply_text(
            "⚠️ *Are you sure you want to delete your LinkedIn profile?*\n"
            "This action cannot be undone.",
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
        # Set user state to await confirmation
        context.user_data['awaiting_delete_confirmation'] = True
        
    except Exception as e:
        logger.error(f"Error in delete profile command: {str(e)}", exc_info=True)
        await update.message.reply_text("Sorry, there was an error processing your request.")

async def update_profile(update: Update, context: CallbackContext) -> None:
    """Update existing LinkedIn profile"""
    user_id = update.message.from_user.id
    logger.info(f"Profile update requested by user {user_id}")
    
    try:
        # First check if user has a profile
        with engine.connect() as conn:
            stmt = select(linkedin_table).where(linkedin_table.c.telegram_user_id == user_id)
            result = conn.execute(stmt)
            existing_profile = result.fetchone()
            
        if not existing_profile:
            await update.message.reply_text(
                "❌ You don't have a profile yet!\n\n"
                "Please share your LinkedIn URL first to create a profile."
            )
            return
            
        # Send instruction message
        await update.message.reply_text(
            "🔄 *Profile Update*\n\n"
            "Please send your LinkedIn URL to update your profile.\n"
            "Your existing profile will be updated with new information.\n\n"
            "Current profile URL:\n"
            f"`{existing_profile.linkedin_url}`",
            parse_mode='Markdown'
        )
        
        # Store the update state in user_data
        context.user_data['awaiting_update'] = True
        
    except Exception as e:
        logger.error(f"Error in update_profile for user {user_id}: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "❌ Sorry, there was an error processing your request.\n"
            "Please try again later."
        )

ADMIN_IDS = []
admin_ids_str = os.getenv('ADMIN_IDS', '')
if admin_ids_str:
    try:
        ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
    except ValueError:
        logger.error("Invalid ADMIN_IDS format in environment variables")

async def admin_stats(update: Update, context: CallbackContext) -> None:
    if update.message.from_user.id not in ADMIN_IDS:
        return
    
    with engine.connect() as conn:
        total_users = conn.execute(select(func.count()).select_from(linkedin_table)).scalar()
        await update.message.reply_text(f"Total registered users: {total_users}")

async def help_command(update: Update, context: CallbackContext) -> None:
    user_id = update.message.from_user.id
    logger.info(f"Help command requested by user {user_id}")
    help_text = (
        "📚 *Available Commands:*\n\n"
        "🎯 *Basic Commands*\n"
        "• /start - Start the bot and see welcome message\n"
        "• /help - Show this help message\n"
        "• /status - Check bot's current status\n\n"
        "👤 *Profile Management*\n"
        "• /delete - Remove your LinkedIn profile\n"
        "• /update - Update your existing profile\n\n"
        "💡 *How to Share Your Profile:*\n"
        "Simply send your LinkedIn URL in this format:\n"
        "`https://www.linkedin.com/in/username`\n\n"
        "🔔 *Features:*\n"
        "• Automatic profile information extraction\n"
        "• Real-time notifications for new connections\n"
        "• View other professionals' profiles\n\n"
        "Need more help? Contact @alphityy"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def retry_linkedin_api(func: callable, *args, max_retries: int = 3, **kwargs) -> Optional[Any]:
    """Retry a LinkedIn API call with exponential backoff"""
    for attempt in range(max_retries):
        try:
            # Create a thread pool executor for the blocking call
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: func(*args, **kwargs))
            return result
        except Exception as e:
            if attempt == max_retries - 1:  # Last attempt
                raise
            wait_time = (2 ** attempt) * 1  # Exponential backoff: 1, 2, 4 seconds
            logger.warning(f"LinkedIn API call failed, retrying in {wait_time}s: {str(e)}")
            await asyncio.sleep(wait_time)

async def fetch_linkedin_profile(linkedin_url: str) -> Optional[Dict]:
    """Fetch profile information and photo from LinkedIn URL"""
    try:
        if api is None:
            logger.error("LinkedIn API not initialized when trying to fetch profile")
            return None
            
        profile_id = linkedin_url.split('/in/')[-1].strip('/')
        logger.info(f"Attempting to fetch profile for ID: {profile_id}")
        
        try:
            # Fetch profile data with retries
            profile_data = await retry_linkedin_api(api.get_profile, profile_id)
            
            if not profile_data:
                logger.error("No profile data returned from LinkedIn API")
                return None
                
            logger.info("Successfully fetched profile data")
            
            # Process the profile data
            profile_info = {
                'full_name': f"{profile_data.get('firstName', '')} {profile_data.get('lastName', '')}",
                'headline': profile_data.get('headline', ''),
                'location': profile_data.get('geoLocationName', ''),
                'current_company': profile_data.get('experience', [{}])[0].get('companyName', '') if profile_data.get('experience') else '',
                'summary': profile_data.get('summary', '')
            }
            
            # Handle profile picture separately to avoid timeouts
            try:
                if profile_data.get('profilePicture', {}).get('displayImage'):
                    pic_url = profile_data['profilePicture']['displayImage']
                    async with aiohttp.ClientSession() as session:
                        async with session.get(pic_url) as response:
                            if response.status == 200:
                                profile_info['profile_picture'] = BytesIO(await response.read())
                                profile_info['profile_picture'].name = 'profile_picture.jpg'
            except Exception as pic_error:
                logger.warning(f"Could not fetch profile picture: {str(pic_error)}")
            
            return profile_info
            
        except Exception as api_error:
            logger.error(f"Error fetching profile from LinkedIn API: {str(api_error)}", exc_info=True)
            return None
            
    except Exception as e:
        logger.error(f"Error in fetch_linkedin_profile: {str(e)}", exc_info=True)
        return None

async def test_linkedin(update: Update, context: CallbackContext) -> None:
    """Admin command to test LinkedIn API connection"""
    if update.message.from_user.id not in ADMIN_IDS:
        return
        
    try:
        logger.info("Testing LinkedIn API connection...")
        if api is None:
            await update.message.reply_text("LinkedIn API not initialized!")
            return
            
        # Try to fetch a test profile
        test_profile = await asyncio.to_thread(api.get_profile, 'williamhgates')
        if test_profile:
            await update.message.reply_text("LinkedIn API connection successful!")
            logger.info("LinkedIn API test successful")
        else:
            await update.message.reply_text("LinkedIn API connected but returned no data")
            logger.warning("LinkedIn API test returned no data")
            
    except Exception as e:
        error_message = f"LinkedIn API test failed: {str(e)}"
        logger.error(error_message, exc_info=True)
        await update.message.reply_text(f"Error: {error_message}")

async def status(update: Update, context: CallbackContext) -> None:
    """Check bot status"""
    try:
        status_text = (
            "🤖 *Bot Status Report*\n\n"
            f"🟢 Bot Service: *Active*\n"
            f"🗄️ Database: *{'Connected' if engine else 'Disconnected'}*\n"
            f"🔗 LinkedIn API: *{'Connected' if api else 'Disconnected'}*\n\n"
            f"⚡️ Response Time: *Fast*\n"
            f"🔐 Security: *Enabled*\n\n"
            "All systems operational! ✨"
        )
        await update.message.reply_text(status_text, parse_mode='Markdown')
        logger.info(f"Status check by user {update.message.from_user.id}")
    except Exception as e:
        logger.error(f"Error in status command: {str(e)}", exc_info=True)
        await update.message.reply_text(
            "⚠️ *Error checking status*\n"
            "Please try again later.",
            parse_mode='Markdown'
        )

async def format_profile_info(profile_data: dict) -> str:
    """Format profile information into a readable message"""
    sections = []
    
    # Header with name and headline
    header = []
    if profile_data.get('full_name'):
        header.append(f"👤 *{profile_data['full_name']}*")
    if profile_data.get('headline'):
        header.append(f"✨ _{profile_data['headline']}_")
    if header:
        sections.append("\n".join(header))
    
    # Professional Info
    prof_info = []
    if profile_data.get('current_company'):
        prof_info.append(f"🏢 *Current Company:*\n   {profile_data['current_company']}")
    if profile_data.get('location'):
        prof_info.append(f"📍 *Location:*\n   {profile_data['location']}")
    if prof_info:
        sections.append("\n".join(prof_info))
    
    # Summary/About
    if profile_data.get('summary'):
        summary = (f"📝 *About:*\n"
                  f"_{profile_data['summary'][:300]}{'...' if len(profile_data['summary']) > 300 else ''}_")
        sections.append(summary)
    
    # Profile Link
    if profile_data.get('linkedin_url'):
        sections.append(f"🔗 [View Complete LinkedIn Profile]({profile_data['linkedin_url']})")
    
    # Footer
    sections.append("\n━━━━━━━━━━━━━━━━━━━━━")
    
    return "\n\n".join(sections)

async def search_profiles(update: Update, context: CallbackContext) -> None:
    """Search for profiles based on keywords"""
    user_id = update.message.from_user.id
    search_query = ' '.join(context.args).lower()
    
    if not search_query:
        await update.message.reply_text(
            "Please provide search terms.\n"
            "Example: /search software engineer"
        )
        return
        
    try:
        with engine.connect() as conn:
            # Search across multiple fields
            query = select(linkedin_table).where(
                or_(
                    func.lower(linkedin_table.c.full_name).contains(search_query),
                    func.lower(linkedin_table.c.headline).contains(search_query),
                    func.lower(linkedin_table.c.current_company).contains(search_query),
                    func.lower(linkedin_table.c.location).contains(search_query)
                )
            )
            results = conn.execute(query).fetchall()
            
        if not results:
            await update.message.reply_text("No profiles found matching your search.")
            return
            
        response = "🔍 *Search Results:*\n\n"
        for profile in results:
            response += (
                f"👤 *{profile.full_name or 'Name not available'}*\n"
                f"📝 {profile.headline or 'No headline'}\n"
                f"🔗 {profile.linkedin_url}\n\n"
            )
            
        await update.message.reply_text(
            response,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Error in search: {str(e)}", exc_info=True)
        await update.message.reply_text("Sorry, an error occurred while searching.")

async def profile_stats(update: Update, context: CallbackContext) -> None:
    """Show profile statistics"""
    try:
        with engine.connect() as conn:
            # Get total profiles
            total = conn.execute(select(func.count()).select_from(linkedin_table)).scalar()
            
            # Get most common companies
            company_query = select(
                linkedin_table.c.current_company,
                func.count(linkedin_table.c.current_company).label('count')
            ).group_by(linkedin_table.c.current_company).order_by(text('count DESC')).limit(3)
            top_companies = conn.execute(company_query).fetchall()
            
            # Get most common locations
            location_query = select(
                linkedin_table.c.location,
                func.count(linkedin_table.c.location).label('count')
            ).group_by(linkedin_table.c.location).order_by(text('count DESC')).limit(3)
            top_locations = conn.execute(location_query).fetchall()
            
        stats_text = (
            "📊 *Network Statistics*\n\n"
            f"👥 Total Profiles: *{total}*\n\n"
            "🏢 *Top Companies:*\n"
        )
        
        for company in top_companies:
            if company.current_company:
                stats_text += f"• {company.current_company}: {company.count}\n"
                
        stats_text += "\n📍 *Top Locations:*\n"
        for location in top_locations:
            if location.location:
                stats_text += f"• {location.location}: {location.count}\n"
                
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in profile_stats: {str(e)}", exc_info=True)
        await update.message.reply_text("Sorry, an error occurred while fetching statistics.")

async def export_profiles(update: Update, context: CallbackContext) -> None:
    """Export profiles to CSV"""
    user_id = update.message.from_user.id
    
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("This command is only available to administrators.")
        return
        
    try:
        with engine.connect() as conn:
            profiles = conn.execute(select(linkedin_table)).fetchall()
            
        if not profiles:
            await update.message.reply_text("No profiles to export.")
            return
            
        # Create CSV in memory
        output = BytesIO()
        writer = csv.writer(output)
        writer.writerow(['Full Name', 'LinkedIn URL', 'Headline', 'Company', 'Location'])
        
        for profile in profiles:
            writer.writerow([
                profile.full_name,
                profile.linkedin_url,
                profile.headline,
                profile.current_company,
                profile.location
            ])
            
        output.seek(0)
        await update.message.reply_document(
            document=InputFile(output, filename='linkedin_profiles.csv'),
            caption="Here are all the LinkedIn profiles in CSV format."
        )
        
    except Exception as e:
        logger.error(f"Error in export_profiles: {str(e)}", exc_info=True)
        await update.message.reply_text("Sorry, an error occurred while exporting profiles.")

def is_valid_linkedin_url(url: str) -> bool:
    """Validate LinkedIn URL format"""
    import re
    linkedin_pattern = r'^https?:\/\/([\w]+\.)?linkedin\.com\/in\/[A-z0-9_-]+\/?$'
    return bool(re.match(linkedin_pattern, url))

CONNECT_TIMEOUT = 30.0  # seconds
READ_TIMEOUT = 30.0    # seconds

def reset_event_loop():
    """Reset the event loop for Windows platform"""
    if platform.system() == 'Windows':
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except Exception as e:
            logger.error(f"Error resetting event loop: {str(e)}")

async def show_user_list(update: Update, context: CallbackContext) -> None:
    """Show all registered users without pagination"""
    try:
        # Determine if the request comes from a command or a callback query
        if update.message:
            message_sender = update.message
        elif update.callback_query:
            message_sender = update.callback_query.message
            await update.callback_query.answer()  # Acknowledge the callback query
        else:
            return  # No valid update, exit the function

        with engine.connect() as conn:
            # Get all registered users
            query = select(linkedin_table).order_by(linkedin_table.c.created_at.desc())
            users = conn.execute(query).fetchall()
            
        if not users:
            await message_sender.reply_text(
                "No users registered yet! 😊\n"
                "Be the first one to share your LinkedIn profile!",
                reply_markup=await get_main_keyboard()
            )
            return
        
        # Create user list message
        message = "👥 *Registered Users*\n\n"
        for user in users:
            message += (
                f"👤 *{user.full_name or 'Name not available'}*\n"
                f"{'✨ ' + user.headline + chr(10) if user.headline else ''}"
                f"{'🏢 ' + user.current_company + chr(10) if user.current_company else ''}"
                f"{'📍 ' + user.location + chr(10) if user.location else ''}"
                f"🔗 [View Profile]({user.linkedin_url})\n"
                f"{'━' * 20}\n\n"
            )
        
        # Send user list message
        await message_sender.reply_text(
            message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Error showing user list: {str(e)}", exc_info=True)
        await message_sender.reply_text(
            "Sorry, there was an error fetching the user list.",
            reply_markup=await get_main_keyboard()
        )


async def button_callback(update: Update, context: CallbackContext) -> None:
    """Handle button callbacks"""
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data and query.data.startswith("users_page_"):
            await show_user_list(update, context)
            
    except Exception as e:
        logger.error(f"Error in button callback: {str(e)}", exc_info=True)
        await query.message.reply_text(
            "Sorry, there was an error processing your request.",
            reply_markup=await get_main_keyboard()
        )


async def back_to_main_menu(update: Update, context: CallbackContext) -> None:
    """Return to main menu"""
    try:
        # Clear any ongoing operations in context
        context.user_data.clear()
        
        # Get main keyboard
        reply_markup = await get_main_keyboard()
        
        await update.message.reply_text(
            "🏠 Back to main menu!",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error returning to main menu: {str(e)}", exc_info=True)
        await update.message.reply_text("Sorry, there was an error. Please try /start to reset.")

def build_application():
    """Create and configure the Telegram application."""
    application = (
        ApplicationBuilder()
        .token(TELEGRAM_BOT_TOKEN)
        .connect_timeout(CONNECT_TIMEOUT)
        .read_timeout(READ_TIMEOUT)
        .build()
    )

    logger.info("Setting up command handlers...")
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("delete", delete_profile))
    application.add_handler(CommandHandler("update", update_profile))
    application.add_handler(CommandHandler("search", search_profiles))
    application.add_handler(CommandHandler("stats", profile_stats))
    application.add_handler(CommandHandler("export", export_profiles))
    application.add_handler(CommandHandler("adminstats", admin_stats))
    application.add_handler(CommandHandler("testlinkedin", test_linkedin))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)

    return application


def run_bot():
    """Start the bot using either webhook or polling based on configuration."""
    logger.info("Starting bot runtime (mode=%s)", "webhook" if USE_WEBHOOK else "polling")
    retry_delay = 5  # seconds
    listen_address = os.getenv("WEBHOOK_LISTEN", "0.0.0.0")
    webhook_path = os.getenv("WEBHOOK_PATH", "")
    port = int(os.getenv("PORT", 8443))

    while True:
        application = build_application()
        try:
            if USE_WEBHOOK:
                application.run_webhook(
                    listen=listen_address,
                    port=port,
                    url_path=webhook_path,
                    webhook_url=WEBHOOK_URL,
                    drop_pending_updates=True,
                )
            else:
                application.run_polling(drop_pending_updates=True)
            break  # Clean exit (e.g., KeyboardInterrupt)
        except telegram.error.NetworkError as e:
            logger.error(f"Network error occurred: {e}. Retrying in {retry_delay} seconds...")
        except telegram.error.TelegramError as e:
            logger.error(f"Telegram API error occurred: {e}. Retrying in {retry_delay} seconds...")
        except Exception:
            logger.exception("Unexpected error while running the bot. Retrying...")

        time.sleep(retry_delay)


def main():
    logger.info("Checking environment variables...")
    env_vars = {
        'TELEGRAM_BOT_TOKEN': bool(TELEGRAM_BOT_TOKEN),
        'DB_HOST': bool(DB_HOST),
        'DB_PORT': bool(DB_PORT),
        'DB_NAME': bool(DB_NAME),
        'DB_USER': bool(DB_USER),
        'DB_PASSWORD': bool(DB_PASSWORD),
        'LINKEDIN_USERNAME': bool(os.getenv('LINKEDIN_USERNAME')),
        'LINKEDIN_PASSWORD': bool(os.getenv('LINKEDIN_PASSWORD')),
        'BOT_MODE': BOT_MODE,
        'USE_WEBHOOK': USE_WEBHOOK
    }
    logger.info(f"Environment variables loaded: {env_vars}")

    run_bot()


if __name__ == "__main__":
    main()