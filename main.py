import os
import logging
import time
import re
from urllib.request import urlretrieve
from telethon.sync import TelegramClient, events
from telethon.sessions import StringSession
from tweepy import Client as TwitterClient
from tweepy.errors import TweepyException

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('smart_posting_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SmartPostingBot:
    def __init__(self):
        # Load configuration from environment variables
        self.config = {
            'TELEGRAM_API_ID': os.getenv('TELEGRAM_API_ID'),
            'TELEGRAM_API_HASH': os.getenv('TELEGRAM_API_HASH'),
            'TELEGRAM_BOT_TOKEN': os.getenv('TELEGRAM_BOT_TOKEN'),
            'SOURCE_CHANNELS': [int(x.strip()) for x in os.getenv('SOURCE_CHANNELS', '').split(',') if x.strip()],
            'LOG_CHANNEL': int(os.getenv('LOG_CHANNEL')),
            
            'TWITTER_BEARER_TOKEN': os.getenv('TWITTER_BEARER_TOKEN'),
            'TWITTER_CONSUMER_KEY': os.getenv('TWITTER_CONSUMER_KEY'),
            'TWITTER_CONSUMER_SECRET': os.getenv('TWITTER_CONSUMER_SECRET'),
            'TWITTER_ACCESS_TOKEN': os.getenv('TWITTER_ACCESS_TOKEN'),
            'TWITTER_ACCESS_SECRET': os.getenv('TWITTER_ACCESS_SECRET'),
            
            # Processing options
            'MAX_TWITTER_LENGTH': int(os.getenv('MAX_TWITTER_LENGTH', '280')),
            'SKIP_LONG_POSTS': os.getenv('SKIP_LONG_POSTS', 'True').lower() == 'true',
            'REMOVE_URLS': os.getenv('REMOVE_URLS', 'True').lower() == 'true',
            'REMOVE_HASHTAGS': os.getenv('REMOVE_HASHTAGS', 'False').lower() == 'true',
            'REMOVE_MENTIONS': os.getenv('REMOVE_MENTIONS', 'False').lower() == 'true',
            'ADD_PREFIX': os.getenv('ADD_PREFIX', '📢 '),
            'ADD_SUFFIX': os.getenv('ADD_SUFFIX', ''),
            'REMOVE_EMOJIS': os.getenv('REMOVE_EMOJIS', 'False').lower() == 'true',
            'TRIM_EXTRA_SPACES': os.getenv('TRIM_EXTRA_SPACES', 'True').lower() == 'true'
        }
        
        # Validate required environment variables
        self.validate_config()
        
        # Initialize Telegram Client
        self.client = TelegramClient(
            StringSession(), 
            self.config['TELEGRAM_API_ID'], 
            self.config['TELEGRAM_API_HASH']
        ).start(bot_token=self.config['TELEGRAM_BOT_TOKEN'])
        
        # Initialize Twitter Client
        self.twitter_client = TwitterClient(
            bearer_token=self.config['TWITTER_BEARER_TOKEN'],
            consumer_key=self.config['TWITTER_CONSUMER_KEY'],
            consumer_secret=self.config['TWITTER_CONSUMER_SECRET'],
            access_token=self.config['TWITTER_ACCESS_TOKEN'],
            access_token_secret=self.config['TWITTER_ACCESS_SECRET']
        )
        
        # Add handlers for all source channels
        for channel_id in self.config['SOURCE_CHANNELS']:
            self.client.add_event_handler(
                lambda e: self.handle_source_channel_message(e, channel_id),
                events.NewMessage(chats=channel_id)
            )
            logger.info(f"Added handler for channel: {channel_id}")

    def validate_config(self):
        """Validate that all required environment variables are set"""
        required_vars = [
            'TELEGRAM_API_ID', 'TELEGRAM_API_HASH', 'TELEGRAM_BOT_TOKEN',
            'SOURCE_CHANNELS', 'LOG_CHANNEL',
            'TWITTER_BEARER_TOKEN', 'TWITTER_CONSUMER_KEY', 
            'TWITTER_CONSUMER_SECRET', 'TWITTER_ACCESS_TOKEN', 
            'TWITTER_ACCESS_SECRET'
        ]
        
        for var in required_vars:
            if not self.config.get(var):
                raise ValueError(f"Environment variable {var} is required but not set")

    def process_text(self, text, source_channel=None):
        """Process text with all configured options"""
        if not text:
            return ""
            
        processed_text = text
        
        if self.config['REMOVE_URLS']:
            processed_text = re.sub(r'http\S+|www\S+|https\S+', '', processed_text, flags=re.MULTILINE)
        
        if self.config['REMOVE_HASHTAGS']:
            processed_text = re.sub(r'#\w+', '', processed_text)
        
        if self.config['REMOVE_MENTIONS']:
            processed_text = re.sub(r'@\w+', '', processed_text)
        
        if self.config['REMOVE_EMOJIS']:
            emoji_pattern = re.compile("["
                u"\U0001F600-\U0001F64F"  # emoticons
                u"\U0001F300-\U0001F5FF"  # symbols & pictographs
                u"\U0001F680-\U0001F6FF"  # transport & map symbols
                u"\U0001F1E0-\U0001F1FF"  # flags (iOS)
                u"\U00002702-\U000027B0"
                u"\U000024C2-\U0001F251"
                "]+", flags=re.UNICODE)
            processed_text = emoji_pattern.sub(r'', processed_text)
        
        if self.config['TRIM_EXTRA_SPACES']:
            processed_text = re.sub(r'\s+', ' ', processed_text).strip()
        
        if self.config['ADD_PREFIX']:
            processed_text = f"{self.config['ADD_PREFIX']}{processed_text}"
        
        if self.config['ADD_SUFFIX']:
            processed_text = f"{processed_text}{self.config['ADD_SUFFIX']}"
        
        return processed_text.strip()

    async def handle_source_channel_message(self, event, source_channel_id):
        """Handle new messages from source channels"""
        try:
            message = event.message
            logger.info(f"New message from channel {source_channel_id} (ID: {message.id})")
            
            # Process text (without length truncation)
            text = message.text or ""
            processed_text = self.process_text(text, source_channel_id)
            
            # Check length before Twitter posting
            if self.config['SKIP_LONG_POSTS'] and len(processed_text) > self.config['MAX_TWITTER_LENGTH']:
                logger.warning(f"Message too long for Twitter ({len(processed_text)} chars), skipping Twitter post")
                skip_twitter = True
            else:
                skip_twitter = False
            
            # Post to log channel (always)
            await self.post_to_log_channel(message, processed_text, source_channel_id)
            
            # Post to Twitter only if not skipped
            if not skip_twitter:
                await self.process_for_twitter(message, processed_text, source_channel_id)
            else:
                logger.info("Skipped Twitter posting as per configuration")
                
        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def post_to_log_channel(self, message, processed_text, source_channel_id):
        """Post to log channel without forward tag"""
        try:
            if message.media:
                # Download and re-upload media
                media_path = await self.client.download_media(
                    message.media,
                    file=f"temp_media_{message.id}"
                )
                
                await self.client.send_file(
                    self.config['LOG_CHANNEL'],
                    file=media_path,
                    caption=processed_text
                )
                
                # Clean up temp file
                if os.path.exists(media_path):
                    os.remove(media_path)
            else:
                await self.client.send_message(
                    self.config['LOG_CHANNEL'],
                    processed_text
                )
                
            logger.info(f"Posted to log channel from {source_channel_id}")
            
        except Exception as e:
            logger.error(f"Error posting to log channel: {e}")

    async def process_for_twitter(self, message, processed_text, source_channel_id):
        """Process message for Twitter posting"""
        try:
            media_path = None
            
            if message.media:
                logger.info("Downloading media for Twitter...")
                media_path = await self.client.download_media(
                    message.media,
                    file=f"twitter_media_{message.id}"
                )
            
            logger.info("Posting to Twitter...")
            success = self.post_to_twitter(processed_text, media_path)
            
            if success:
                logger.info(f"Successfully posted to Twitter from {source_channel_id}")
            else:
                logger.warning(f"Failed to post to Twitter from {source_channel_id}")
                
        except Exception as e:
            logger.error(f"Error processing for Twitter: {e}")
        finally:
            if media_path and os.path.exists(media_path):
                os.remove(media_path)

    def post_to_twitter(self, text, media_path=None):
        """Post to Twitter using API v2"""
        try:
            if media_path:
                # Check media size
                file_size = os.path.getsize(media_path) / (1024 * 1024)
                if file_size > 50:
                    logger.warning(f"Media file too large ({file_size:.2f}MB)")
                    raise ValueError("Media file exceeds 50MB limit")
                
                # Upload media using v1.1 API
                from tweepy import OAuth1UserHandler, API
                auth = OAuth1UserHandler(
                    self.config['TWITTER_CONSUMER_KEY'],
                    self.config['TWITTER_CONSUMER_SECRET'],
                    self.config['TWITTER_ACCESS_TOKEN'],
                    self.config['TWITTER_ACCESS_SECRET']
                )
                legacy_api = API(auth)
                media = legacy_api.media_upload(media_path)
                
                # Post with media using v2 API
                response = self.twitter_client.create_tweet(
                    text=text,
                    media_ids=[media.media_id]
                )
            else:
                # Text-only tweet
                response = self.twitter_client.create_tweet(text=text)
                
            logger.info(f"Tweet posted! ID: {response.data['id']}")
            return True
            
        except TweepyException as e:
            logger.error(f"Twitter API error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            return False

    def run(self):
        """Run the bot"""
        logger.info("Starting Smart Posting Bot...")
        logger.info(f"Monitoring {len(self.config['SOURCE_CHANNELS'])} source channels")
        logger.info(f"Log channel: {self.config['LOG_CHANNEL']}")
        logger.info(f"Max Twitter length: {self.config['MAX_TWITTER_LENGTH']}")
        logger.info(f"Skip long posts: {self.config['SKIP_LONG_POSTS']}")
        self.client.run_until_disconnected()

if __name__ == "__main__":
    import os
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    
    # Simple health check server
    class HealthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Bot is running")
    
    def run_health_server():
        server = HTTPServer(('0.0.0.0', 8000), HealthHandler)
        server.serve_forever()
    
    # Start health server in background
    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()
    
    # Start the bot
    bot = SmartPostingBot()
    bot.run()
