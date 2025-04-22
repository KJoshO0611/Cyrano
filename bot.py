import discord
from discord import app_commands
from discord.ext import commands, tasks
import random
import asyncio
import datetime
import json
import os
import logging
import time
from typing import Dict, List, Optional, Union
import aiomysql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("tribble_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("tribble_bot")

# Database configuration
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "uk02-sql.pebblehost.com"),
    "port": int(os.getenv("DB_PORT", "3306")),
    "user": os.getenv("DB_USER", "customer_689278_STFC"),
    "password": os.getenv("DB_PASSWORD", "ckI64@nmO@i=eiU9i+4wNy.K"),
    "db": os.getenv("DB_NAME", "customer_689278_STFC"),
    "autocommit": True,
    "minsize": 5,
    "maxsize": 20,
    "pool_recycle": 3600,  # Recycle connections every hour
    "connect_timeout": 10,
    "echo": False
}

# Custom emoji constants
# ... existing code ...

# Custom emoji constants
TRIBBLE_EMOJI_1TRIBBLE = "<:tribbletrouble:1362451958383906856>"
TRIBBLE_EMOJI_2TRIBBLE = "<:tribbletrouble2:1362461371102396476>"
TRIBBLE_EMOJI_3TRIBBLE = "<:tribbletrouble3:1362461446906188039>"
TRIBBLE_EMOJI_BORG = "<:borgtribble:1362762779429306588>"

# Constants
ADMIN_ROLE_NAME = "TribbleAdmin"  # Change this to your admin role name
EVENT_DATA_FILE = "tribble_event_data.json"
DEFAULT_EVENT_DATA = {
    "active": False,
    "scores": {},
    "start_time": None,
    "end_time": None,
    "current_drops": {},  # Track active tribble drops: {message_id: {"channel_id": id, "rarity": rarity, "claimed_by": None}}
    "infestation_alerts": {}  # Track infestation alerts: {batch_id: {"alert_message_id": id, "alert_channel_id": id, "confirmation_message_id": id, "confirmation_channel_id": id, "tribble_count": count, "captured_count": count, "escaped_count": 0}}
}

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

# --- Hybrid JSON + DB persistence helpers ---
import json

def save_event_data_json(data):
    """Write event data to JSON file."""
    try:
        with open(EVENT_DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, default=str, indent=2)
    except Exception as e:
        logger.error(f"Failed to write event data to JSON: {e}")

def load_event_data_json():
    """Load event data from JSON file, or initialize if missing."""
    if not os.path.exists(EVENT_DATA_FILE):
        save_event_data_json(DEFAULT_EVENT_DATA)
        return DEFAULT_EVENT_DATA.copy()
    try:
        with open(EVENT_DATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        logger.error(f"Failed to load event data from JSON: {e}")
        save_event_data_json(DEFAULT_EVENT_DATA)
        return DEFAULT_EVENT_DATA.copy()

# Global event_data always loaded from JSON at startup
# (This ensures state is preserved across restarts)
event_data = load_event_data_json()

# Replace the existing drop_tribble function with this improved version

async def drop_tribble(channel: discord.TextChannel, rarity: int, batch_id: Optional[str] = None) -> Optional[discord.Message]:
    """Drop a tribble in the specified channel with improved visuals and behavior"""
    if not check_event_active():
        return None
    
    # Create the tribble message
    tribble_emoji = get_tribble_emoji(rarity)
    
    # Define separate message lists for singular and plural tribbles
    singular_tribble_messages = [
        "My friends, my friends! Look at this fine specimen of a tribble! Catch it before it multiplies!",
        "Attention, esteemed customers! This beautiful tribble just arrived from the Klingon homeworld! Grab it while it lasts!",
        "Oh my, what have we here? A precious tribble on the loose! Someone capture it before the captain sees it!",
        "Extraordinary opportunity! Premium quality tribble right before your eyes! Catch it and it could be yours!",
        "By the stars! This magnificent tribble is worth a fortune! Claim it before someone else does!",
        "Would you look at that? A rare breed of tribble has appeared! Secure it before it escapes!",
        "Ladies and gentlemen! This delightful tribble is looking for a new home! Be quick or it will find a way to escape!",
        "Marvelous discovery! A tribble of exceptional quality! Seize it before it reproduces!",
        "Behold! A perfect specimen of tribble! Catch it and it will bring you great fortune!",
        "Quadrotriticale lovers beware! A hungry tribble is on the prowl! Capture it before it finds your grain!",
        "Great galaxies! A tribble of remarkable softness! Claim it before it disappears into someone else's pocket!",
        "Honored space travelers! Witness an exceptional tribble! Acquire it before it brings chaos to the ship!",
        "My goodness! The charming tribble escaped my inventory! Help me catch it before the captain puts me in the brig!",
        "Attention shoppers! The premium tribble is practically giving itself away! Grab it while supplies last!",
        "Remarkable find! A tribble with a coat softer than Vulcan silk! Catch it and feel for yourself!",
        "By all that's profitable! The tribble is from my special collection! Retrieve it and receive a handsome reward!",
        "Fascinating opportunity! A particular tribble with a perfect purr! Capture it and experience the soothing sound!",
        "Alert! Alert! A valuable tribble is not for free viewing! Catch it before it breeds with another!",
        "Sweet mother of Orion! My prized tribble is making a break for it! Contain it immediately!",
        "Unbelievable chance! A rare tribble with unique coloration! Secure it before someone from Starfleet confiscates it!"
    ]
    
    plural_tribble_messages = [
        "My friends, my friends! Look at these fine specimens of tribbles! Catch them before they multiply!",
        "Attention, esteemed customers! These beautiful tribbles just arrived from the Klingon homeworld! Grab them while they last!",
        "Oh my, what have we here? Precious tribbles on the loose! Someone capture them before the captain sees them!",
        "Extraordinary opportunity! Premium quality tribbles right before your eyes! Catch them and they could be yours!",
        "By the stars! These magnificent tribbles are worth a fortune! Claim them before someone else does!",
        "Would you look at that? Rare breeds of tribbles have appeared! Secure them before they escape!",
        "Ladies and gentlemen! These delightful tribbles are looking for a new home! Be quick or they will find a way to escape!",
        "Marvelous discovery! Tribbles of exceptional quality! Seize them before they reproduce!",
        "Behold! Perfect specimens of tribbles! Catch them and they will bring you great fortune!",
        "Quadrotriticale lovers beware! Hungry tribbles are on the prowl! Capture them before they find your grain!",
        "Great galaxies! Tribbles of remarkable softness! Claim them before they disappear into someone else's pocket!",
        "Honored space travelers! Witness exceptional tribbles! Acquire them before they bring chaos to the ship!",
        "My goodness! The charming tribbles escaped my inventory! Help me catch them before the captain puts me in the brig!",
        "Attention shoppers! The premium tribbles are practically giving themselves away! Grab them while supplies last!",
        "Remarkable find! Tribbles with coats softer than Vulcan silk! Catch them and feel for yourself!",
        "By all that's profitable! These tribbles are from my special collection! Retrieve them and receive a handsome reward!",
        "Fascinating opportunity! Particular tribbles with perfect purrs! Capture them and experience the soothing sound!",
        "Alert! Alert! Valuable tribbles are not for free viewing! Catch them before they breed with others!",
        "Sweet mother of Orion! My prized tribbles are making a break for it! Contain them immediately!",
        "Unbelievable chance! Rare tribbles with unique coloration! Secure them before someone from Starfleet confiscates them!"
    ]
    
    # Special messages for Borg tribble
    borg_tribble_messages = [
        "GREAT SCOTT! Is that... Ten of Eleven? The infamous Borg tribble? Catch it if you dare!",
        "RESISTANCE IS FUTILE! Ten of Eleven, the Borg tribble, has escaped containment! Approach with caution!",
        "BY THE STARS! Ten of Eleven has broken free! This Borg tribble is either a great prize or terrible trouble!",
        "ALERT! ALERT! The Borg tribble known as Ten of Eleven is on the loose! Capture at your own risk!"
    ]
    
    # Select a random message
    if rarity == 4:  # Borg tribble
        message = random.choice(borg_tribble_messages)
    else:
        # Use the appropriate list based on rarity (1 = singular, 2-3 = plural)
        if rarity == 1:
            message = random.choice(singular_tribble_messages)
            point_value = "1 point"
        else:
            message = random.choice(plural_tribble_messages)
            point_value = f"{rarity} points"
        
        # Add points information
        message += f" This {'tribble' if rarity == 1 else 'group of tribbles'} is worth {point_value}."
    
    # Create and send the embed
    embed = discord.Embed(description=message)
    
    if rarity == 1:
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1362451958383906856.png")
    elif rarity == 2:
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1362461371102396476.png")
    elif rarity == 3:
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1362461446906188039.png")
    elif rarity == 4:
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/1362762779429306588.png")
    
    # Create the button with emoji
    view = TribbleButton(rarity=rarity, message_id="placeholder", batch_id=batch_id)
    
    try:
        # Send the message with the button
        message = await channel.send(embed=embed, view=view)
        
        # Update the message_id in the view and current_drops
        view.message_id = str(message.id)
        event_data["current_drops"][str(message.id)] = {
            "channel_id": str(channel.id),
            "rarity": rarity,
            "claimed_by": None
        }
        
        if batch_id:
            event_data["current_drops"][str(message.id)]["batch_id"] = batch_id
            
        # Set is_borg flag for rarity 4 tribbles
        if rarity == 4:
            event_data["current_drops"][str(message.id)]["is_borg"] = 1
            
        save_event_data_json(event_data)
        await save_event_data_to_db(event_data)
        
        # Schedule message to expire after a random time between 0-1 minute
        expiration_time = random.randint(10, 60)  # 60-300 seconds (0-1 minute)
        asyncio.create_task(schedule_tribble_expiration(message, str(message.id), expiration_time))
        
        return message
    except Exception as e:
        logger.error(f"Error dropping tribble: {e}")
        return await channel.send(embed=embed)

# Event data handling
def load_event_data() -> Dict:
    """Load event data from file or return default"""
    if os.path.exists(EVENT_DATA_FILE):
        try:
            with open(EVENT_DATA_FILE, 'r') as f:
                data = json.load(f)
                # Convert string timestamps back to datetime if needed
                if data["start_time"]:
                    data["start_time"] = datetime.datetime.fromisoformat(data["start_time"])
                if data["end_time"]:
                    data["end_time"] = datetime.datetime.fromisoformat(data["end_time"])
                return data
        except Exception as e:
            print(f"Error loading event data: {e}")
    
    return DEFAULT_EVENT_DATA.copy()

import datetime

def save_event_data(data: Dict) -> None:
    """Save event data to file"""
    # Convert datetime objects to ISO format strings for JSON serialization
    data_to_save = data.copy()
    if data_to_save["start_time"] and isinstance(data_to_save["start_time"], datetime.datetime):
        data_to_save["start_time"] = data_to_save["start_time"].isoformat()
    if data_to_save["end_time"] and isinstance(data_to_save["end_time"], datetime.datetime):
        data_to_save["end_time"] = data_to_save["end_time"].isoformat()
    
    with open(EVENT_DATA_FILE, 'w') as f:
        json.dump(data_to_save, f, indent=2)


# Load initial dataevent_data = load_event_data_json()

# Find the get_db_pool function and modify it to handle connection issues better
async def get_db_pool():
    """Get or create the database connection pool with retry logic"""
    if hasattr(get_db_pool, "pool"):
        try:
            # Test connection by executing a simple query
            async with get_db_pool.pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
            return get_db_pool.pool
        except Exception as e:
            logger.warning(f"Database connection test failed: {e}, recreating pool")
            # Close and recreate the pool
            await get_db_pool.pool.close()
            delattr(get_db_pool, "pool")

    max_retries = 3
    retry_delay = 2  # seconds
    
    for attempt in range(1, max_retries + 1):
        try:
            get_db_pool.pool = await aiomysql.create_pool(**DB_CONFIG)
            logger.info(f"Database connection pool initialized successfully after {attempt} attempts")
            return get_db_pool.pool
        except Exception as e:
            logger.error(f"Failed to connect to MySQL (attempt {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                logger.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logger.info("Falling back to in-memory data storage")
                global using_in_memory_storage
                using_in_memory_storage = True
                return None

async def init_database():
    """Initialize the database with required tables"""
    global event_data, using_in_memory_storage
    
    try:
        # Initialize database
        pool = await get_db_pool()
        
        if pool is None:
            logger.info("Using in-memory storage instead of database")
            event_data = DEFAULT_EVENT_DATA.copy()
            return
            
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                # Create tables with proper constraints and indexes
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tribble_event (
                        id INT NOT NULL AUTO_INCREMENT,
                        active TINYINT(1) NOT NULL DEFAULT 0,
                        start_time DATETIME NULL,
                        end_time DATETIME NULL,
                        guild_id VARCHAR(20) NOT NULL,
                        event_name VARCHAR(100),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        UNIQUE KEY idx_guild_active (guild_id, active)
                    )
                """)
                
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tribble_scores (
                        id INT NOT NULL AUTO_INCREMENT,
                        user_id VARCHAR(20) NOT NULL,
                        score INT NOT NULL DEFAULT 0,
                        guild_id VARCHAR(20) NOT NULL,
                        event_id INT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        UNIQUE KEY idx_user_event (user_id, event_id),
                        FOREIGN KEY (event_id) REFERENCES tribble_event(id) ON DELETE CASCADE
                    )
                """)
                
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tribble_drops (
                        id INT NOT NULL AUTO_INCREMENT,
                        message_id VARCHAR(20) NOT NULL,
                        channel_id VARCHAR(20) NOT NULL,
                        rarity INT NOT NULL,
                        claimed_by VARCHAR(20),
                        batch_id VARCHAR(36),
                        is_escaped TINYINT(1) NOT NULL DEFAULT 0,
                        is_borg TINYINT(1) NOT NULL DEFAULT 0,
                        was_defeated TINYINT(1) NOT NULL DEFAULT 0,
                        captured_at TIMESTAMP NULL,
                        guild_id VARCHAR(20) NOT NULL,
                        event_id INT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        UNIQUE KEY idx_message (message_id),
                        FOREIGN KEY (event_id) REFERENCES tribble_event(id) ON DELETE CASCADE
                    )
                """)
                
                await cursor.execute("""
                    CREATE TABLE IF NOT EXISTS tribble_infestations (
                        id INT NOT NULL AUTO_INCREMENT,
                        batch_id VARCHAR(36) NOT NULL,
                        alert_message_id VARCHAR(20),
                        alert_channel_id VARCHAR(20),
                        confirmation_message_id VARCHAR(20),
                        confirmation_channel_id VARCHAR(20),
                        tribble_count INT NOT NULL DEFAULT 0,
                        captured_count INT NOT NULL DEFAULT 0,
                        escaped_count INT NOT NULL DEFAULT 0,
                        cleanup_started TINYINT(1) NOT NULL DEFAULT 0,
                        guild_id VARCHAR(20) NOT NULL,
                        event_id INT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (id),
                        UNIQUE KEY idx_batch (batch_id),
                        FOREIGN KEY (event_id) REFERENCES tribble_event(id) ON DELETE CASCADE
                    )
                """)
                
                logger.info("Database tables initialized with proper constraints")
    except Exception as e:
        logger.error(f"Error initializing database: {e}", exc_info=True)
        using_in_memory_storage = True
        event_data = DEFAULT_EVENT_DATA.copy()
        logger.info("Initialized with default in-memory data due to database error")

# Helper functions for database operations
async def get_active_event(guild_id):
    """Get the active event for a guild from the database"""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute(
                "SELECT * FROM tribble_event WHERE guild_id = %s AND active = 1 ORDER BY id DESC LIMIT 1",
                (str(guild_id),)
            )
            event = await cursor.fetchone()
            return event

async def load_event_data_from_db(guild_id) -> Dict:
    """Load event data from database"""
    try:
        # Get active event
        event = await get_active_event(guild_id)
        
        if not event:
            return DEFAULT_EVENT_DATA.copy()
        
        # Load scores for this event
        pool = await get_db_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                # Get scores
                await cursor.execute(
                    "SELECT user_id, score FROM tribble_scores WHERE guild_id = %s AND event_id = %s",
                    (str(guild_id), event['id'])
                )
                scores = await cursor.fetchall()
                
                # Get current drops
                await cursor.execute(
                    "SELECT * FROM tribble_drops WHERE guild_id = %s AND event_id = %s AND is_escaped = 0 AND claimed_by IS NULL",
                    (str(guild_id), event['id'])
                )
                drops = await cursor.fetchall()
                
                # Get infestation alerts
                await cursor.execute(
                    "SELECT * FROM tribble_infestations WHERE guild_id = %s AND event_id = %s",
                    (str(guild_id), event['id'])
                )
                infestations = await cursor.fetchall()
        
        # Format data to match the expected structure
        data = DEFAULT_EVENT_DATA.copy()
        data["active"] = bool(event["active"])
        data["start_time"] = event["start_time"]
        data["end_time"] = event["end_time"]
        data["event_id"] = event["id"]
        data["guild_id"] = str(guild_id)
        
        # Format scores
        data["scores"] = {str(score["user_id"]): score["score"] for score in scores}
        
        # Format current drops
        data["current_drops"] = {}
        for drop in drops:
            data["current_drops"][str(drop["message_id"])] = {
                "channel_id": str(drop["channel_id"]),
                "rarity": drop["rarity"],
                "claimed_by": drop["claimed_by"],
                "batch_id": drop["batch_id"]
            }
        
        # Format infestation alerts
        data["infestation_alerts"] = {}
        for infestation in infestations:
            data["infestation_alerts"][str(infestation["batch_id"])] = {
                "alert_message_id": infestation["alert_message_id"],
                "alert_channel_id": infestation["alert_channel_id"],
                "confirmation_message_id": infestation["confirmation_message_id"],
                "confirmation_channel_id": infestation["confirmation_channel_id"],
                "tribble_count": infestation["tribble_count"],
                "captured_count": infestation["captured_count"],
                "escaped_count": infestation["escaped_count"],
                "cleanup_started": bool(infestation["cleanup_started"])
            }
        
        return data
    except Exception as e:
        logger.error(f"Error loading event data from database: {e}")
        return DEFAULT_EVENT_DATA.copy()
         
async def save_event_data_to_db(data: Dict) -> None:
    """Save event data to database with retry logic. Always write to JSON first."""
    save_event_data_json(data)  # Always write to JSON immediately

    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds

    pool = await get_db_pool()
    if pool is None:
        logger.warning("Cannot save to database: no connection pool available")
        return

    guild_id = data.get("guild_id")
    event_id = data.get("event_id")
    
    if not guild_id or not event_id:
        logger.error("Cannot save event data: missing guild_id or event_id")
        return
        
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    # Update event status
                    await cursor.execute(
                        """
                        UPDATE tribble_event 
                        SET active = %s, 
                            end_time = %s,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                        """,
                        (1 if data["active"] else 0, data["end_time"], event_id)
                    )
                    
                    # Then insert/update current ones
                    for message_id, drop_data in data["current_drops"].items():
                        await cursor.execute(
                            """
                            INSERT INTO tribble_drops 
                            (message_id, channel_id, guild_id, rarity, claimed_by, batch_id, event_id, is_escaped, is_borg, was_defeated) 
                            VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s, %s)
                            ON DUPLICATE KEY UPDATE 
                            channel_id = %s, rarity = %s, claimed_by = %s, batch_id = %s, is_escaped = 0, is_borg = %s, was_defeated = %s
                            """,
                            (
                                message_id, drop_data["channel_id"], guild_id, drop_data["rarity"], 
                                drop_data.get("claimed_by"), drop_data.get("batch_id"), event_id,
                                1 if drop_data.get("is_borg") else 0,
                                1 if drop_data.get("was_defeated") else 0,
                                drop_data["channel_id"], drop_data["rarity"], drop_data.get("claimed_by"), 
                                drop_data.get("batch_id"),
                                1 if drop_data.get("is_borg") else 0,
                                1 if drop_data.get("was_defeated") else 0
                            )
                        )
                    
                    # Update infestation alerts
                    for batch_id, infestation_data in data["infestation_alerts"].items():
                        await cursor.execute(
                            """
                            INSERT INTO tribble_infestations
                            (batch_id, guild_id, event_id, alert_message_id, alert_channel_id, 
                            confirmation_message_id, confirmation_channel_id, tribble_count, 
                            captured_count, escaped_count, cleanup_started)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                            ON DUPLICATE KEY UPDATE
                            alert_message_id = %s, alert_channel_id = %s, confirmation_message_id = %s,
                            confirmation_channel_id = %s, tribble_count = %s, captured_count = %s,
                            escaped_count = %s, cleanup_started = %s
                            """,
                            (
                                batch_id, guild_id, event_id, 
                                infestation_data.get("alert_message_id"), infestation_data.get("alert_channel_id"),
                                infestation_data.get("confirmation_message_id"), infestation_data.get("confirmation_channel_id"),
                                infestation_data.get("tribble_count", 0), infestation_data.get("captured_count", 0),
                                infestation_data.get("escaped_count", 0), 1 if infestation_data.get("cleanup_started", False) else 0,
                                infestation_data.get("alert_message_id"), infestation_data.get("alert_channel_id"),
                                infestation_data.get("confirmation_message_id"), infestation_data.get("confirmation_channel_id"),
                                infestation_data.get("tribble_count", 0), infestation_data.get("captured_count", 0),
                                infestation_data.get("escaped_count", 0), 1 if infestation_data.get("cleanup_started", False) else 0
                            )
                        )
                    logger.debug(f"Successfully saved event data to database (attempt {attempt})")
                    return
        except Exception as e:
            logger.error(f"Database save attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                logger.info(f"Retrying save in {RETRY_DELAY} seconds...")
                await asyncio.sleep(RETRY_DELAY)
            else:
                logger.error("All save attempts failed, data not saved to database")
                raise

# Helper functions
def is_admin(interaction: discord.Interaction) -> bool:
    """Check if user has admin role"""
    try:
        if interaction.user.guild_permissions.administrator:
            return True
        
        admin_role = discord.utils.get(interaction.guild.roles, name=ADMIN_ROLE_NAME)
        return admin_role in interaction.user.roles if admin_role else False
    except Exception as e:
        logger.error(f"Error in is_admin: {e}")
        return False

def check_event_active() -> bool:
    """Check if the event is currently active (always read from JSON for reliability)"""
    try:
        data = load_event_data_json()
        return data["active"]
    except Exception as e:
        logger.error(f"Error in check_event_active: {e}")
        return False

async def end_event_if_needed() -> bool:
    """End the event if end_time has passed (hybrid: update JSON and DB)"""
    data = load_event_data_json()
    
    # Make sure we have end_time and it's properly formatted as datetime
    if data["active"] and data["end_time"]:
        # Convert string end_time to datetime if needed
        end_time = data["end_time"]
        if isinstance(end_time, str):
            try:
                end_time = datetime.datetime.fromisoformat(end_time)
            except ValueError as e:
                logger.error(f"Error parsing end_time: {e}")
                return False
                
        # Now compare with current time
        if datetime.datetime.now() > end_time:
            data["active"] = False
            save_event_data_json(data)
            await save_event_data_to_db(data)
            global event_data
            event_data = data
            return True
            
    return False

def generate_tribble_rarity() -> int:
    """Generate a random tribble rarity based on probabilities"""
    roll = random.random() * 100
    if roll < 65:
        return 1  # 65% chance for 1 tribble (reduced from 70%)
    elif roll < 85:
        return 2  # 20% chance for 2 tribbles
    elif roll < 95:
        return 3  # 10% chance for 3 tribbles
    else:
        return 4  # 5% chance for Borg tribble (Ten of Eleven)

def get_tribble_emoji(rarity: int) -> str:
    """Get the appropriate tribble emoji based on rarity"""
    if rarity == 1:
        return TRIBBLE_EMOJI_1TRIBBLE
    elif rarity == 2:
        return TRIBBLE_EMOJI_2TRIBBLE
    elif rarity == 3:
        return TRIBBLE_EMOJI_3TRIBBLE
    else:  # rarity == 4 (Borg tribble)
        return TRIBBLE_EMOJI_BORG

def get_sorted_leaderboard() -> List[tuple]:
    """Get sorted leaderboard as a list of (user_id, score) tuples (read from JSON)"""
    data = load_event_data_json()
    return sorted(data["scores"].items(), key=lambda x: x[1], reverse=True)

async def resolve_user_name(guild: discord.Guild, user_id: str) -> str:
    """Get the global name of a user from their ID"""
    try:
        user = await guild.fetch_member(int(user_id))
        return user.global_name or user.display_name or user.name
    except (discord.NotFound, discord.Forbidden, ValueError) as e:
        logger.error(f"Error fetching user name: {e}")
        return f"Unknown User ({user_id})"

# Button for tribble capture

class TribbleButton(discord.ui.View):
    def __init__(self, rarity: int, message_id: str, batch_id: Optional[str] = None):
        super().__init__(timeout=None)
        self.rarity = rarity
        self.message_id = message_id
        self.batch_id = batch_id
        
        # Generate a unique button ID
        self.button_id = f"tribble_{message_id}_{int(time.time())}_{random.randint(1000, 9999)}"

    @discord.ui.button(label="Capture the Tribble", emoji="🛸", style=discord.ButtonStyle.primary)
    async def capture_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        import discord
        try:
            # Don't defer the interaction - respond immediately to improve user experience
            # Lock the tribble immediately with a simple dictionary check and update
            lock_result = await self.lock_tribble_for_capture(interaction.user.id)
            
            if not lock_result['success']:
                await interaction.response.send_message(lock_result['message'], ephemeral=True)
                return
                
            # Now we successfully locked this tribble - disable the button immediately
            for child in self.children:
                child.disabled = True
            
            user_id = str(interaction.user.id)
            
            # Prepare to handle different tribble types
            if self.rarity == 4:  # Borg tribble
                # Respond immediately by editing the original message to show combat
                await interaction.response.edit_message(content="⚔️ **COMBAT WITH BORG TRIBBLE IN PROGRESS** ⚔️", view=self)
                
                # Then proceed with combat animation
                success = random.random() < 0.5
                combat_states = [
                    {"style": discord.ButtonStyle.primary, "label": "Engaging Borg Tribble..."},
                    {"style": discord.ButtonStyle.danger, "label": "Resistance Detected!"},
                    {"style": discord.ButtonStyle.success, "label": "Gaining Advantage..."},
                    {"style": discord.ButtonStyle.secondary, "label": "Critical Moment!"},
                ]
                
                # Combat animation
                for state in combat_states:
                    button.style = state["style"]
                    button.label = state["label"]
                    try:
                        await interaction.edit_original_response(view=self)
                    except Exception as e:
                        logger.error(f"Error animating combat state: {e}", exc_info=True)
                    await asyncio.sleep(0.7)
                
                # Process Borg tribble result (moved database operations here)
                if success:
                    # User succeeded in combat
                    event_data["scores"][user_id] = event_data["scores"].get(user_id, 0) + 10
                    success_message = "Huzzah! You've successfully captured Ten of Eleven! The Borg tribble's assimilation powers have been neutralized, and you've earned a handsome 10 points for your valor!"
                    confirmation_text = f"{interaction.user.mention} captured {get_tribble_emoji(self.rarity)} and gained 10 points!"
                    button.style = discord.ButtonStyle.success
                    button.label = "Tribble Captured!"
                    
                    # Update the database in background
                    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    asyncio.create_task(self.update_tribble_capture_in_db(user_id, now))
                else:
                    # User lost to Borg tribble
                    event_data["scores"][user_id] = max(0, event_data["scores"].get(user_id, 0) - 10)
                    success_message = "Oh dear, oh dear! Ten of Eleven has trounced you most thoroughly and — heavens! — loosed a full ten Tribbles into the ether! A costly blunder indeed... I'm afraid you'll be docked 10 points, my friend!"
                    confirmation_text = f"{interaction.user.mention} was defeated by {get_tribble_emoji(self.rarity)} and lost 10 points!"
                    button.style = discord.ButtonStyle.danger
                    button.label = "You Have Been Assimilated"
                    
                    # Update was_defeated and is_escaped in the database and event_data
                    event_data["current_drops"][self.message_id]["was_defeated"] = 1
                    event_data["current_drops"][self.message_id]["is_escaped"] = 1
                    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    asyncio.create_task(self.update_tribble_defeat_in_db(user_id, now))
                
                try:
                    # Update the original message with the result
                    await interaction.edit_original_response(content=success_message, view=self)
                except Exception as e:
                    logger.error(f"Error editing original response for result: {e}", exc_info=True)
            else:
                # Regular tribble - immediately update the original message
                button.style = discord.ButtonStyle.success
                button.label = "Tribble Captured!"
                await interaction.response.edit_message(view=self)
                
                # Process regular tribble capture (database operations moved here)
                event_data["scores"][user_id] = event_data["scores"].get(user_id, 0) + self.rarity
                confirmation_text = f"{interaction.user.mention} captured {get_tribble_emoji(self.rarity)} worth {self.rarity} point{'s' if self.rarity > 1 else ''}!"
                
                # Update the database in background
                now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                asyncio.create_task(self.update_tribble_capture_in_db(user_id, now))
            
            # Save event data to JSON (can be done asynchronously now)
            asyncio.create_task(self.save_event_data_async(event_data))
            
            # Send confirmation message to channel
            confirmation_message = None
            try:
                confirmation_message = await interaction.channel.send(confirmation_text)
                asyncio.create_task(self.cleanup_infestation_messages(self.batch_id, interaction.guild))
            except Exception as e:
                logger.error(f"Error sending confirmation text to channel: {e}", exc_info=True)
            
            # Delete the original tribble message after a short delay
            try:
                original_message = await interaction.channel.fetch_message(int(self.message_id))
                await asyncio.sleep(1)  # Reduced wait time to 1 second
                await original_message.delete()
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                pass  # Message already deleted or no permission
            
            # Delete the confirmation message after a shorter delay
            if confirmation_message:
                try:
                    await asyncio.sleep(3)  # Reduced to 3 seconds total
                    await confirmation_message.delete()
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    pass  # Message already deleted or no permission
        except Exception as e:
            logger.error(f"Error in capture_button: {e}")
            try:
                await interaction.response.send_message("An error occurred while capturing the tribble.", ephemeral=True)
            except discord.InteractionResponded:
                await interaction.followup.send("An error occurred while capturing the tribble.", ephemeral=True)
            except Exception:
                pass  # Already handled

    async def lock_tribble_for_capture(self, user_id: str) -> dict:
        """Atomically check and lock a tribble for capture to prevent race conditions"""
        if self.message_id not in event_data["current_drops"] or event_data["current_drops"][self.message_id].get("claimed_by"):
            return {"success": False, "message": "This tribble has already been captured or has escaped!"}
        
        # Lock the tribble by setting claimed_by
        event_data["current_drops"][self.message_id]["claimed_by"] = str(user_id)
        return {"success": True, "message": "Tribble locked for capture"}

    async def save_event_data_async(self, data):
        """Save event data to JSON and DB asynchronously"""
        save_event_data_json(data)
        await save_event_data_to_db(data)

    async def update_tribble_capture_in_db(self, user_id: str, timestamp: str):
        """Update tribble capture information in the database"""
        try:
            pool = await get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            "UPDATE tribble_drops SET claimed_by = %s, captured_at = %s WHERE message_id = %s",
                            (str(user_id), timestamp, self.message_id)
                        )
                        await conn.commit()
        except Exception as e:
            logger.error(f"Failed to update captured_at timestamp: {e}")

    async def update_tribble_defeat_in_db(self, user_id: str, timestamp: str):
        """Update tribble defeat information in the database"""
        try:
            pool = await get_db_pool()
            if pool:
                async with pool.acquire() as conn:
                    async with conn.cursor() as cursor:
                        await cursor.execute(
                            "UPDATE tribble_drops SET claimed_by = %s, was_defeated = 1, is_escaped = 1, captured_at = %s WHERE message_id = %s",
                            (str(user_id), timestamp, self.message_id)
                        )
                        await conn.commit()
        except Exception as e:
            logger.error(f"Failed to update was_defeated and is_escaped: {e}")

    async def cleanup_infestation_messages(self, batch_id: str, guild: discord.Guild):
        """Clean up infestation alert and confirmation messages"""
        try:
            if "infestation_alerts" in event_data and batch_id in event_data["infestation_alerts"]:
                infestation_data = event_data["infestation_alerts"][batch_id]
                
                # Check if all tribbles have been accounted for
                total_accounted = (infestation_data.get("captured_count", 0) + 
                                  infestation_data.get("escaped_count", 0))
                
                if total_accounted >= infestation_data.get("tribble_count", 0):
                    if infestation_data["alert_message_id"] and infestation_data["alert_channel_id"]:
                        try:
                            channel = guild.get_channel(int(infestation_data["alert_channel_id"]))
                            if channel:
                                try:
                                    message = await channel.fetch_message(int(infestation_data["alert_message_id"]))
                                    
                                    captured = infestation_data.get("captured_count", 0)
                                    escaped = infestation_data.get("escaped_count", 0)
                                    
                                    await message.edit(content=(
                                        f"🧹 **Tribble Infestation Results** 🧹\n\n"
                                        f"• {captured} tribbles were captured\n"
                                        f"• {escaped} tribbles escaped"
                                    ))
                                    
                                    await asyncio.sleep(20)
                                    await message.delete()
                                    
                                except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                                    logger.error(f"Error updating infestation alert message: {e}")
                        except Exception as e:
                            logger.error(f"Error accessing channel for infestation alert message: {e}")
                    
                    # Delete the confirmation message if it exists
                    if infestation_data["confirmation_message_id"] and infestation_data["confirmation_channel_id"]:
                        try:
                            channel = guild.get_channel(int(infestation_data["confirmation_channel_id"]))
                            if channel:
                                try:
                                    message = await channel.fetch_message(int(infestation_data["confirmation_message_id"]))
                                    await message.delete()
                                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                                    pass
                        except Exception as e:
                            logger.error(f"Error deleting infestation confirmation message: {e}")
                    
                    # Remove the infestation data
                    del event_data["infestation_alerts"][batch_id]
                    save_event_data(event_data)
        except Exception as e:
            logger.error(f"Error cleaning up infestation messages: {e}")

# Add this after the TribbleButton class and before the Bot commands section



# Add this after the TribbleButton class and before the Bot commands section

            

# Add this after the TribbleButton class and before the Bot commands section

@tasks.loop(hours=1)  # Changed to run every hour
async def scheduled_tribble_drop():
    """Scheduled task to drop tribbles once per hour at a random minute"""
    if not check_event_active():
        return
    
    if await end_event_if_needed():
        scheduled_tribble_drop.cancel()
        return
    
    # Get current time
    current_time = datetime.datetime.now()
    
    # Choose a random minute for this hour's drop
    random_minute = random.randint(1, 59)
    logger.info(f"Scheduled drop will occur at minute {random_minute} this hour")
    
    # Calculate time until the random minute
    current_minute = current_time.minute
    wait_minutes = 0
    
    if current_minute < random_minute:
        wait_minutes = random_minute - current_minute
    else:
        # If we've already passed the random minute, wait until next hour
        # (this shouldn't happen often since the task runs hourly)
        wait_minutes = 60 - current_minute + random_minute
    
    # Wait until the random minute
    logger.info(f"Waiting {wait_minutes} minutes until scheduled drop at {random_minute} past the hour")
    await asyncio.sleep(wait_minutes * 60)
    
    # Check again if event is still active after waiting
    if not check_event_active():
        return
    
    if await end_event_if_needed():
        scheduled_tribble_drop.cancel()
        return
    
    # Get all valid text channels
    valid_channels = []
    for guild in bot.guilds:
        for channel in guild.channels:
            if isinstance(channel, discord.TextChannel):
                # Check if bot has permission to send messages
                bot_member = guild.get_member(bot.user.id)
                if bot_member and channel.permissions_for(bot_member).send_messages:
                    valid_channels.append(channel)
    
    if not valid_channels:
        logger.warning("No valid channels found for scheduled tribble drop")
        return
    
    # Choose a random channel and drop a tribble
    channel = random.choice(valid_channels)
    rarity = generate_tribble_rarity()
    
    logger.info(f"Scheduled tribble drop: Dropping tribble with rarity {rarity} in {channel.name} ({channel.guild.name})")
    await drop_tribble(channel, rarity)
# Bot commands
@bot.tree.command(name="tribble-start", description="[Admin] Start the Tribble Hunt event")
async def tribble_start(interaction: discord.Interaction, duration_days: Optional[int] = None):
    """Start the Tribble Hunt event"""
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    # Check if there's already an active event
    active_event = await get_active_event(interaction.guild.id)
    if active_event:
        # Double-check if the event is truly active by checking the active flag
        if active_event['active'] == 1:
            await interaction.response.send_message("The Tribble Hunt event is already active!", ephemeral=True)
            return
        else:
            # There's an event but it's not active, so we can start a new one
            # Make sure to deactivate any existing events first
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        "UPDATE tribble_event SET active = 0 WHERE guild_id = %s",
                        (str(interaction.guild.id),)
                    )
    
    # Create new event in database
    start_time = datetime.datetime.now()
    end_time = start_time + datetime.timedelta(days=duration_days) if duration_days else None
    
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute(
                """
                INSERT INTO tribble_event (active, start_time, end_time, guild_id, event_name)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (1, start_time, end_time, str(interaction.guild.id), "Tribble Hunt")
            )
            # Get the new event ID
            event_id = cursor.lastrowid
    
    # Load the event data structure
    global event_data
    event_data = DEFAULT_EVENT_DATA.copy()
    event_data["active"] = True
    event_data["start_time"] = start_time
    event_data["end_time"] = end_time
    event_data["event_id"] = event_id
    event_data["guild_id"] = str(interaction.guild.id)
    
    # Save to database
    await save_event_data_to_db(event_data)
    
    # Start the scheduled drops
    if not scheduled_tribble_drop.is_running():
        scheduled_tribble_drop.start()
    
    embed = discord.Embed(
        title="🎉 Tribble Hunt Event Started! 🎉",
        description=(
            f"The hunt for tribbles has begun! Capture tribbles to earn points.\n\n"
            f"**Event Duration:** {'Indefinite' if not duration_days else f'{duration_days} days'}\n"
            f"**Use /tribbleeventinfo for more details.**"
        ),
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="tribble-end", description="[Admin] End the Tribble Hunt event")
async def tribble_end(interaction: discord.Interaction):
    """End the Tribble Hunt event"""
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if not event_data["active"]:
        await interaction.response.send_message("The Tribble Hunt event is not currently active!", ephemeral=True)
        return
    
    event_data["active"] = False
    event_data["end_time"] = datetime.datetime.now()
    save_event_data(event_data)
    
    # Stop the scheduled drops
    if scheduled_tribble_drop.is_running():
        scheduled_tribble_drop.cancel()
    
    # Generate final leaderboard
    leaderboard_embed = await create_leaderboard_embed(interaction.guild)
    leaderboard_embed.title = "🏆 Final Tribble Hunt Results 🏆"
    
    await interaction.response.send_message(embed=discord.Embed(
        title="Tribble Hunt Event Ended!",
        description="The hunt for tribbles has concluded. Thank you for participating!",
        color=discord.Color.red()
    ))
    
    await interaction.channel.send(embed=leaderboard_embed)

@bot.tree.command(name="tribble-randomdrop", description="[Admin] Drop a random tribble")
@app_commands.describe(channel="Optional channel to drop the tribble in")
async def tribble_random_drop(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
    """Admin command to manually drop a random tribble"""
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if not check_event_active():
        await interaction.response.send_message("The Tribble Hunt event is not active!", ephemeral=True)
        return
    
    # Use provided channel or a random one
    if not channel:
        # Get all text channels the bot has permission to send messages in
        text_channels = []
        for ch in interaction.guild.channels:
            if isinstance(ch, discord.TextChannel):
                # Check if bot has permission to send messages in this channel
                bot_member = interaction.guild.get_member(bot.user.id)
                permissions = ch.permissions_for(bot_member)
                if permissions.send_messages:
                    text_channels.append(ch)
        
        if not text_channels:
            await interaction.response.send_message("No valid text channels found where I can send messages. Please check my permissions.", ephemeral=True)
            return
        
        channel = random.choice(text_channels)
    else:
        # Check if bot has permission to send messages in the specified channel
        bot_member = interaction.guild.get_member(bot.user.id)
        permissions = channel.permissions_for(bot_member)
        if not permissions.send_messages:
            await interaction.response.send_message(f"I don't have permission to send messages in {channel.mention}. Please choose another channel or check my permissions.", ephemeral=True)
            return
    
    # Generate tribble rarity
    rarity = generate_tribble_rarity()
    
    await interaction.response.send_message(
        f"Dropping a tribble with rarity {rarity} in {channel.mention}...",
        ephemeral=True
    )
    
    await drop_tribble(channel, rarity)

@bot.tree.command(name="tribble-infestation", description="[Admin] Create a tribble infestation")
async def tribble_infestation(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None, count: Optional[int] = 5):
    """Admin command to create a tribble infestation"""
    # Admin check
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    # Event active check
    if not check_event_active():
        await interaction.response.send_message("The Tribble Hunt event is not active!", ephemeral=True)
        return
    
    # Validate count
    count = max(5, min(10, count))  # Ensure count is between 5 and 10
    
    # Get available channels
    if channel:
        # Check if bot has permission to send messages in the specified channel
        bot_member = interaction.guild.get_member(bot.user.id)
        permissions = channel.permissions_for(bot_member)
        if not permissions.send_messages:
            await interaction.response.send_message(f"I don't have permission to send messages in {channel.mention}.", ephemeral=True)
            return
        text_channels = [channel] * count  # Fill the list with the specified channel
    else:
        # Get all text channels with permissions
        text_channels = []
        for ch in interaction.guild.channels:
            if isinstance(ch, discord.TextChannel):
                bot_member = interaction.guild.get_member(bot.user.id)
                permissions = ch.permissions_for(bot_member)
                if permissions.send_messages:
                    text_channels.append(ch)
        
        if not text_channels:
            await interaction.response.send_message("No valid text channels found where I can send messages. Please check my permissions.", ephemeral=True)
            return
        
        # If we have fewer channels than requested tribbles, we'll repeat channels
        while len(text_channels) < count:
            text_channels.extend(text_channels[:count - len(text_channels)])
        
        # Shuffle channels to ensure random distribution
        random.shuffle(text_channels)
    
    # Generate a batch ID for this infestation
    batch_id = f"infestation-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # Create initial alert message
    await interaction.response.send_message(
        "🚨 **TRIBBLE INFESTATION ALERT** 🚨\n\n"
        "Tribbles are multiplying across the ship! Find and capture them before they overrun your systems!"
    )
    
    # Get the alert message after it's sent
    alert_message = await interaction.original_response()
    
    # Store the alert message ID in event data for tracking
    if "infestation_alerts" not in event_data:
        event_data["infestation_alerts"] = {}
    
    # Store alert message data
    event_data["infestation_alerts"][batch_id] = {
        "alert_message_id": str(alert_message.id),
        "alert_channel_id": str(interaction.channel.id),
        "tribble_count": 0,
        "captured_count": 0,
        "escaped_count": 0
    }
    save_event_data(event_data)
    
    # Drop tribbles in the selected channels
    dropped_count = 0
    max_drops = min(count, len(text_channels))
    
    for i in range(max_drops):
        target_channel = text_channels[i % len(text_channels)]
        rarity = generate_tribble_rarity()
        
        message = await drop_tribble(target_channel, rarity, batch_id)
        if message:
            dropped_count += 1
        
        # Small delay between drops
        await asyncio.sleep(1)
    
    # Update the infestation data with the count of tribbles
    if batch_id in event_data["infestation_alerts"]:
        event_data["infestation_alerts"][batch_id]["tribble_count"] = dropped_count
        save_event_data(event_data)
    
    # Update the alert message after spawning is complete
    if dropped_count > 0:
        try:
            await alert_message.edit(content=(
                "😅 **Tribble Alert Update** 😅\n\n"
                "Oh dear... it seems some tribbles have slipped out of their crates. Not to worry! They're quite harmless... mostly."
            ))
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
            logger.error(f"Error updating infestation alert message: {e}")
    
    # Schedule periodic check for tribble capture completion
    bot.loop.create_task(check_tribble_capture_completion(batch_id, interaction.guild))

# Add this function after the tribble_infestation command
async def check_tribble_capture_completion(batch_id: str, guild: discord.Guild):
    """Periodically check if all tribbles from a batch have been captured or escaped"""
    # Initial delay before checking
    await asyncio.sleep(10)
    
    while True:
        try:
            # Check if the batch_id still exists in event_data
            if "infestation_alerts" not in event_data or batch_id not in event_data["infestation_alerts"]:
                # This batch has been cleaned up already
                break
                
            infestation_data = event_data["infestation_alerts"][batch_id]
            total_accounted = (infestation_data.get("captured_count", 0) + 
                              infestation_data.get("escaped_count", 0))
            
            if total_accounted >= infestation_data.get("tribble_count", 0):
                if infestation_data["alert_message_id"] and infestation_data["alert_channel_id"]:
                    try:
                        channel = guild.get_channel(int(infestation_data["alert_channel_id"]))
                        if channel:
                            try:
                                message = await channel.fetch_message(int(infestation_data["alert_message_id"]))
                                
                                captured = infestation_data.get("captured_count", 0)
                                escaped = infestation_data.get("escaped_count", 0)
                                
                                await message.edit(content=(
                                    f"🧹 **Tribble Infestation Results** 🧹\n\n"
                                    f"• {captured} tribbles were captured\n"
                                    f"• {escaped} tribbles escaped"
                                ))
                                
                                await asyncio.sleep(20)
                                await message.delete()
                                
                            except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
                                logger.error(f"Error updating infestation alert message: {e}")
                    except Exception as e:
                        logger.error(f"Error accessing channel for infestation alert message: {e}")
                
                # Remove the infestation data
                del event_data["infestation_alerts"][batch_id]
                save_event_data(event_data)
                break
            
            # Check again after a delay
            await asyncio.sleep(5)
        except Exception as e:
            logger.error(f"Error in check_tribble_capture_completion: {e}")
            await asyncio.sleep(5)

# Remove delete_infestation_messages_after_delay as it's no longer needed
# since we're handling everything through the alert message edits now

# Add this function after the tribble_infestation command

@bot.tree.command(name="tribble-dropin", description="[Admin] Drop a tribble in a specific channel")
@app_commands.describe(
    channel="Channel to drop the tribble in",
    rarity="Tribble rarity (1-4, or 0 for random)"
)
async def tribble_drop_in(
    interaction: discord.Interaction, 
    channel: discord.TextChannel,
    rarity: int = 0
):
    """Admin command to drop a tribble in a specific channel"""
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if not check_event_active():
        await interaction.response.send_message("The Tribble Hunt event is not active!", ephemeral=True)
        return
    
    # Check if bot has permission to send messages in the specified channel
    bot_member = interaction.guild.get_member(bot.user.id)
    permissions = channel.permissions_for(bot_member)
    if not permissions.send_messages:
        await interaction.response.send_message(f"I don't have permission to send messages in {channel.mention}. Please choose another channel or check my permissions.", ephemeral=True)
        return
    
    # Validate rarity
    if rarity < 0 or rarity > 4:
        await interaction.response.send_message("Invalid rarity. Must be 0 (random) or 1-4.", ephemeral=True)
        return
    
    # Generate random rarity if 0
    if rarity == 0:
        rarity = generate_tribble_rarity()
    
    await interaction.response.send_message(
        f"Dropping a {'Borg tribble (Ten of Eleven)' if rarity == 4 else f'tribble with rarity {rarity}'} in {channel.mention}...",
        ephemeral=True
    )
    
    await drop_tribble(channel, rarity)

async def create_leaderboard_embed(guild: discord.Guild) -> discord.Embed:
    """Create a formatted leaderboard embed"""
    leaderboard = get_sorted_leaderboard()
    
    embed = discord.Embed(
        title="Tribble Hunt Leaderboard",
        color=discord.Color.gold()
    )
    
    if not leaderboard:
        embed.description = "No tribbles have been captured yet!"
        return embed
    
    medals = ["🥇", "🥈", "🥉"]
    leaderboard_text = ""
    
    # Get medal ranks
    for i, (user_id, score) in enumerate(leaderboard[:10]):
        user_name = await resolve_user_name(guild, user_id)
        
        if i < 3:
            rank = f"{medals[i]} {i+1}."
        else:
            rank = f"{i+1}."
        
        leaderboard_text += f"{rank} **{user_name}** - {score} point{'s' if score != 1 else ''}\n"
    
    embed.description = leaderboard_text
    
    # Add timestamp
    embed.set_footer(text=f"Last updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return embed

@bot.tree.command(name="tribble-leaderboards", description="Check the current leaderboard")
@app_commands.describe(public="Set to True to show the leaderboard to everyone in the channel")
async def tribble_leaderboards(interaction: discord.Interaction, public: bool = False):
    """Command to check the current leaderboard"""
    if not check_event_active() and not event_data["scores"]:
        await interaction.response.send_message("The Tribble Hunt event is not active!", ephemeral=True)
        return
    
    leaderboard_embed = await create_leaderboard_embed(interaction.guild)
    
    if public:
        await interaction.response.send_message(embed=leaderboard_embed)
    else:
        await interaction.response.send_message(embed=leaderboard_embed, ephemeral=True)

@bot.tree.command(name="tribble-mystats", description="Check how many tribbles you've captured")
async def tribbles_count(interaction: discord.Interaction):
    """Command to check personal tribble count"""
    user_id = str(interaction.user.id)
    
    if user_id not in event_data["scores"]:
        await interaction.response.send_message(
            "You haven't captured any tribbles yet!",
            ephemeral=True
        )
        return
    
    score = event_data["scores"][user_id]
    
    embed = discord.Embed(
        title="Your Tribble Hunt Progress",
        description=f"You've captured tribbles worth **{score}** point{'s' if score != 1 else ''}!",
        color=discord.Color.blue()
    )
    
    # Get user rank
    leaderboard = get_sorted_leaderboard()
    rank = next((i + 1 for i, (uid, _) in enumerate(leaderboard) if uid == user_id), 0)
    
    if rank > 0:
        embed.add_field(name="Current Rank", value=f"{rank}/{len(leaderboard)}")
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="tribble-eventinfo", description="Show information about the Tribble Hunt event")
async def tribble_event_info(interaction: discord.Interaction):
    """Command to show event information"""
    embed = discord.Embed(
        title="🐾 Tribble Hunt Event Information 🐾",
        description="Tribbles have invaded the ship! Your mission is to capture as many as possible.",
        color=discord.Color.teal()
    )
    
    embed.add_field(
        name="🔍 How It Works",
        value=(
            f"• Tribbles appear randomly throughout the server\n"
            f"• Click the 'Capture the Tribble' button to capture them\n"
            f"• Different tribbles are worth different points:"
        ),
        inline=False
    )
    
    embed.add_field(
        name="📊 Scoring Metrics",
        value=(
            f"{TRIBBLE_EMOJI_1TRIBBLE} = 1 point (65% chance)\n"
            f"{TRIBBLE_EMOJI_2TRIBBLE} = 2 points (20% chance)\n"
            f"{TRIBBLE_EMOJI_3TRIBBLE} = 3 points (10% chance)\n"
            f"{TRIBBLE_EMOJI_BORG} = +10 or -10 points (5% chance)\n\n"
        ),
        inline=False
    )
    
    embed.add_field(
        name="⚠️ Special Tribble: Ten of Eleven",
        value=(
            f"The rare Borg tribble, Ten of Eleven {TRIBBLE_EMOJI_BORG}, is unpredictable:\n"
            f"• 50% chance to gain 10 points\n"
            f"• 50% chance to lose 10 points\n"
            f"• Proceed with caution!"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🚨 Tribble Infestations",
        value=(
            f"Sometimes, tribbles don't show up alone...\n"
            f"A tribble infestation randomly floods up to 10 channels with tribbles all at once!\n"
            f"• They might appear in the same channel more than once\n"
            f"• Move fast—these outbreaks don't last long!\n"
            f"• It's chaos—but also your best shot at grabbing a bunch of points"
        ),
        inline=False
    )
    
    embed.add_field(
        name="💬 Available Commands",
        value=(
            f"• `/tribble-mystats` - Check your personal tribble count\n"
            f"• `/tribble-leaderboards` - Check the leaderboards\n"
            f"• `/tribble-eventinfo` - Show this information"
        ),
        inline=False
    )
    
    # Add event status
    if event_data["active"]:
        status = "🟢 Active"
        if event_data["end_time"]:
            time_left = event_data["end_time"] - datetime.datetime.now()
            if time_left.total_seconds() > 0:
                days = time_left.days
                hours = time_left.seconds // 3600
                minutes = (time_left.seconds % 3600) // 60
                status += f" (Ends in: {days}d {hours}h {minutes}m)"
    else:
        status = "🔴 Inactive"
    
    embed.add_field(name="📅 Event Status", value=status, inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.tree.command(name="tribble-reset", description="[Admin] Reset all tribble counts")
async def tribble_reset(interaction: discord.Interaction):
    """Admin command to reset all tribble counts"""
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    # Ask for confirmation
    embed = discord.Embed(
        title="⚠️ Reset Confirmation",
        description="Are you sure you want to reset all tribble counts? This cannot be undone.",
        color=discord.Color.red()
    )
    
    class ConfirmView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=60)
            self.confirmed = False
            
        @discord.ui.button(label="Yes, Reset All Data", style=discord.ButtonStyle.danger)
        async def confirm_button(self, confirm_interaction: discord.Interaction, button: discord.ui.Button):
            if confirm_interaction.user.id != interaction.user.id:
                await confirm_interaction.response.send_message("Only the command initiator can confirm this action.", ephemeral=True)
                return
                
            # Reset scores
            event_data["scores"] = {}
            event_data["current_drops"] = {}
            save_event_data(event_data)
            
            self.confirmed = True
            
            await confirm_interaction.response.edit_message(
                content="All tribble counts have been reset!",
                embed=None,
                view=None
            )
            
        @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
        async def cancel_button(self, cancel_interaction: discord.Interaction, button: discord.ui.Button):
            if cancel_interaction.user.id != interaction.user.id:
                await cancel_interaction.response.send_message("Only the command initiator can cancel this action.", ephemeral=True)
                return
                
            await cancel_interaction.response.edit_message(
                content="Reset operation cancelled.",
                embed=None,
                view=None
            )
    
    view = ConfirmView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="tribble-clearchat", description="[Admin] Clear tribble messages from all channels")
async def tribble_clear_chat(interaction: discord.Interaction, count: int = 100):
    """Admin command to clear tribble-related messages from all channels"""
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    await interaction.response.defer(ephemeral=True)
    
    deleted = 0
    text_channels = [channel for channel in interaction.guild.channels if isinstance(channel, discord.TextChannel)]
    
    for channel in text_channels:
        try:
            channel_deleted = 0
            async for message in channel.history(limit=count):
                if message.author == bot.user:
                    try:
                        await message.delete()
                        deleted += 1
                        channel_deleted += 1
                        await asyncio.sleep(0.5)  # Brief delay to avoid rate limits
                    except discord.errors.NotFound:
                        pass  # Message was already deleted
                    except discord.errors.Forbidden:
                        logger.warning(f"Missing permissions to delete messages in {channel.name}")
                        break  # Skip this channel if we don't have permissions
            
            if channel_deleted > 0:
                logger.info(f"Deleted {channel_deleted} messages from {channel.name}")
        except Exception as e:
            logger.error(f"Error clearing messages in {channel.name}: {e}")
    
    await interaction.followup.send(f"Deleted {deleted} tribble-related messages from all channels.", ephemeral=True)

@bot.tree.command(name="tribble-borg", description="[Admin] Drop a Borg tribble (Ten of Eleven)")
@app_commands.describe(channel="Optional channel to drop the Borg tribble in")
async def tribble_borg_drop(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
    """Admin command to manually drop a Borg tribble (Ten of Eleven)"""
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return
    
    if not check_event_active():
        await interaction.response.send_message("The Tribble Hunt event is not active!", ephemeral=True)
        return
    
    # Use provided channel or a random one
    if not channel:
        # Get all text channels the bot has permission to send messages in
        text_channels = []
        for ch in interaction.guild.channels:
            if isinstance(ch, discord.TextChannel):
                # Check if bot has permission to send messages in this channel
                bot_member = interaction.guild.get_member(bot.user.id)
                permissions = ch.permissions_for(bot_member)
                if permissions.send_messages:
                    text_channels.append(ch)
        
        if not text_channels:
            await interaction.response.send_message("No valid text channels found where I can send messages. Please check my permissions.", ephemeral=True)
            return
        
        channel = random.choice(text_channels)
    else:
        # Check if bot has permission to send messages in the specified channel
        bot_member = interaction.guild.get_member(bot.user.id)
        permissions = channel.permissions_for(bot_member)
        if not permissions.send_messages:
            await interaction.response.send_message(f"I don't have permission to send messages in {channel.mention}. Please choose another channel or check my permissions.", ephemeral=True)
            return
    
    # Set rarity to 4 for Borg tribble
    rarity = 4
    
    await interaction.response.send_message(
        f"Dropping Ten of Eleven (Borg tribble) in {channel.mention}...",
        ephemeral=True
    )
    
    await drop_tribble(channel, rarity)

@bot.event
async def on_ready():
    """Initialize the bot and database when ready"""
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    
    try:
        # Initialize database
        await init_database()
        
        # Sync commands
        try:
            synced = await bot.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands: {e}")
        
        # Start scheduled tasks if event is active
        for guild in bot.guilds:
            try:
                event_data = await load_event_data_from_db(guild.id)
                if event_data["active"] and not scheduled_tribble_drop.is_running():
                    scheduled_tribble_drop.start()
            except Exception as e:
                logger.error(f"Error loading event data for guild {guild.id}: {e}")
        
        logger.info("Bot is ready")
    except Exception as e:
        logger.error(f"Error in on_ready: {e}", exc_info=True)
# Simple text command to test basic functionality
@bot.command()
async def hello(ctx):
    await ctx.send('Hello! The bot is working.')

# Simple slash command
@bot.tree.command(name="test", description="Test if slash commands are working")
async def test_command(interaction: discord.Interaction):
    await interaction.response.send_message("Success! Slash commands are working.")
# Simple ping command to test if the bot is responsive
@bot.command()
async def ping(ctx):
    await ctx.send('Pong! Bot is running.')

# Simple slash command to verify slash commands are working
@bot.tree.command(name="ping", description="Check if the bot is responsive")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message("Pong! Slash commands are working.")

# This is to manually force sync commands if they're not appearing
@bot.command()
@commands.is_owner()
async def sync(ctx):
    """Sync the slash commands"""
    try:
        if ctx.guild:
            # Sync to this specific guild
            bot.tree.copy_global_to(guild=discord.Object(id=ctx.guild.id))
            await bot.tree.sync(guild=discord.Object(id=ctx.guild.id))
            await ctx.send(f"Synced commands to the current guild.")
        
        # Also sync globally
        await bot.tree.sync()
        await ctx.send("Synced commands globally.")
    except Exception as e:
        await ctx.send(f"Error syncing commands: {e}")

# Add this function after the drop_tribble function

# Replace the existing schedule_tribble_expiration function with this improved version

async def schedule_tribble_expiration(message: discord.Message, message_id: str, expiration_time: int):
    """Schedule a tribble message to expire after a certain time"""
    await asyncio.sleep(expiration_time)
    
    try:
        # Check if the message still exists and hasn't been claimed
        if message_id in event_data["current_drops"] and not event_data["current_drops"][message_id]["claimed_by"]:
            # Get batch_id if this tribble is part of an infestation
            batch_id = event_data["current_drops"][message_id].get("batch_id")
            
            # If this is part of an infestation, update the escaped count
            if batch_id and batch_id.startswith("infestation-") and batch_id in event_data["infestation_alerts"]:
                event_data["infestation_alerts"][batch_id]["escaped_count"] = event_data["infestation_alerts"][batch_id].get("escaped_count", 0) + 1
                
                # Check if all tribbles from this infestation have been accounted for (captured + escaped)
                total_accounted = (event_data["infestation_alerts"][batch_id]["captured_count"] + 
                                  event_data["infestation_alerts"][batch_id]["escaped_count"])
                
                if total_accounted >= event_data["infestation_alerts"][batch_id]["tribble_count"]:
                    # All tribbles accounted for, clean up the alert messages
                    guild = message.guild
                    # Create a temporary instance of TribbleButton to call the method
                    temp_button = TribbleButton(rarity=0, message_id="0")
                    await temp_button.cleanup_infestation_messages(batch_id, guild)
            
            # Play escape animation before updating the button
            try:
                # Get the original message
                original_message = await message.channel.fetch_message(message.id)
                
                # Play escape animation
                await animate_tribble_escape(original_message)
                
                # Create a new view with the updated button
                escaped_view = TribbleButton(rarity=event_data["current_drops"][message_id]["rarity"], 
                                           message_id=message_id)
                
                # Update the button to show "Escaped"
                for child in escaped_view.children:
                    if isinstance(child, discord.ui.Button):
                        child.style = discord.ButtonStyle.secondary  # Gray color
                        child.label = "Tribble Escaped"
                        child.emoji = "💨"  # :dash: emoji
                        child.disabled = True
                
                # Update the embed description to show the tribble has escaped
                embed = original_message.embeds[0]
                embed.description = "This tribble has escaped and disappeared into the ventilation system! 💨"
                embed.color = discord.Color.dark_gray()
                embed.title = "A Tribble Escaped!"  # Update the title too
                
                # Edit the message with the updated view and embed
                await original_message.edit(embed=embed, view=escaped_view)
                
                # Wait a short moment before deleting to allow the button change to be seen
                await asyncio.sleep(3)
                
                # Remove from current drops
                del event_data["current_drops"][message_id]
                save_event_data(event_data)

                # --- DB update: mark tribble as escaped and set captured_at timestamp ---
                try:
                    pool = await get_db_pool()
                    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    if pool:
                        async with pool.acquire() as conn:
                            async with conn.cursor() as cursor:
                                await cursor.execute(
                                    "UPDATE tribble_drops SET is_escaped = 1, captured_at = %s WHERE message_id = %s",
                                    (now, message_id)
                                )
                                await conn.commit()
                        logger.info(f"Marked tribble {message_id} as escaped in DB with timestamp {now}.")
                except Exception as e:
                    logger.error(f"Failed to update is_escaped for tribble {message_id}: {e}")

                # Delete the message
                await message.delete()
            except Exception as e:
                logger.error(f"Error updating button for escaped tribble: {e}")
                # Still try to clean up even if there was an error
                if message_id in event_data["current_drops"]:
                    del event_data["current_drops"][message_id]
                    save_event_data(event_data)
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        # Message already deleted or no permission
        if message_id in event_data["current_drops"]:
            del event_data["current_drops"][message_id]
            save_event_data(event_data)
    except Exception as e:
        logger.error(f"Error in tribble expiration: {e}")

# Add this function for the escape animation
async def animate_tribble_escape(message: discord.Message):
        """Create a simplified escape animation"""
        try:
            original_embed = message.embeds[0]
            original_description = original_embed.description
            
            # Simplified animation with fewer frames
            frames = [
                {"color": 0xe74c3c, "emoji": "💨", "text": "Tribble escaping..."},
                {"color": 0x7f8c8d, "emoji": "👋", "text": "Tribble escaped!"}
            ]
            
            # Play the animation
            for frame in frames:
                new_embed = discord.Embed(
                    title=original_embed.title,
                    description=f"{original_description}\n\n{frame['emoji']} {frame['text']} {frame['emoji']}",
                    color=frame["color"]
                )
                
                # Copy any fields from the original embed
                for field in original_embed.fields:
                    new_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                
                # Copy footer if it exists
                if original_embed.footer:
                    new_embed.set_footer(text=original_embed.footer.text, icon_url=original_embed.footer.icon_url)
                
                # Copy image if it exists
                if original_embed.image:
                    new_embed.set_image(url=original_embed.image.url)
                
                # Copy thumbnail if it exists
                if original_embed.thumbnail:
                    new_embed.set_thumbnail(url=original_embed.thumbnail.url)
                
                await message.edit(embed=new_embed)
                await asyncio.sleep(0.5)  # Short delay between frames
                
        except Exception as e:
            logger.error(f"Error in escape animation: {e}")

# Run the bot
TOKEN = "MTM2MjU5MDYzOTE4MjgzOTgyOA.Gjg9bc.E8UGTRpO1qQmSWJv6waVU-UJThU7uEeF7R1cA0"  # Replace with your actual bot token
@bot.event
async def on_error(event, *args, **kwargs):
    print(f"Error in {event}: {args} {kwargs}")

async def main():
    async with bot:
        await bot.start(TOKEN)

if __name__ == "__main__":
    # Change this line to use the TOKEN variable directly
    bot.run(TOKEN)