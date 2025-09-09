# xbot
# Telegram to Twitter Cross-Posting Bot

This bot forwards messages from Telegram channels to Twitter.

## Setup

1. Clone this repository
2. Install dependencies: `pip install -r requirements.txt`
3. Set up environment variables (see below)
4. Run the bot: `python bot.py`

## Environment Variables

Required environment variables:
- `TELEGRAM_API_ID` - Your Telegram API ID
- `TELEGRAM_API_HASH` - Your Telegram API Hash
- `TELEGRAM_BOT_TOKEN` - Your Telegram Bot Token
- `SOURCE_CHANNELS` - Comma-separated list of source channel IDs
- `LOG_CHANNEL` - Log channel ID
- `TWITTER_BEARER_TOKEN` - Twitter Bearer Token
- `TWITTER_CONSUMER_KEY` - Twitter Consumer Key
- `TWITTER_CONSUMER_SECRET` - Twitter Consumer Secret
- `TWITTER_ACCESS_TOKEN` - Twitter Access Token
- `TWITTER_ACCESS_SECRET` - Twitter Access Secret

Optional environment variables (with defaults):
- `MAX_TWITTER_LENGTH` = 280
- `SKIP_LONG_POSTS` = True
- `REMOVE_URLS` = True
- `REMOVE_HASHTAGS` = False
- `REMOVE_MENTIONS` = False
- `ADD_PREFIX` = "📢 "
- `ADD_SUFFIX` = ""
- `REMOVE_EMOJIS` = False
- `TRIM_EXTRA_SPACES` = True
