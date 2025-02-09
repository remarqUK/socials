import json
import logging
import hashlib
import datetime
import random
import time
from typing import List, Dict, Optional
from dataclasses import dataclass
import feedparser
import requests
from feedparser import FeedParserDict

from aws_functions import get_secret
from facebook_functions import FacebookClient
from instagram_functions import InstagramClient
from linkedin_auth import post_to_linkedin
from x_functions import post_tweet, setup_twitter_vars
import platform_summary_functions as psf
from dynamo_service import DynamoDBService

logger = logging.getLogger()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

FEED_URLS = [
    "https://www.autoexpress.co.uk/feed/all",
    "https://www.am-online.com/news/latest-news/rss.xml",
    "https://www.fleetnews.co.uk/news/latest-fleet-news/rss.xml",
    "https://cardealermagazine.co.uk/publish/category/latest-news/feed"
]

@dataclass
class NewsItem:
    text: str
    image_url: str


class FeedParser:
    def __init__(self, feed_urls: List[str]):
        self.feed_urls = feed_urls

    def parse_feed(self, feed: FeedParserDict) -> List[NewsItem]:
        news_items = []
        for item in feed.entries:
            news_items.append(NewsItem(
                text=f"{item.get('title', '')}\n\n{item.get('description', '')}",
                image_url=item.get('media_content', [{}])[0].get('url', '')
            ))
        return news_items

    def get_aggregated_news(self, items_per_feed: int = 5) -> List[NewsItem]:
        aggregated_items = []
        for url in self.feed_urls:
            feed = feedparser.parse(url)
            if feed.bozo:
                logger.warning(f"Failed to parse feed: {url}")
                continue

            items = self.parse_feed(feed)
            num_items = min(items_per_feed, len(items))
            aggregated_items.extend(random.sample(items, num_items))
            logger.info(f"Processed feed: {url}")

        return aggregated_items


class SocialMediaService:
    def __init__(self, dynamo_service: DynamoDBService):
        self.dynamo_service = dynamo_service

    def post_to_linkedin(self, content: Dict) -> bool:
        try:
            post_to_linkedin(text=content['Text'], image_url=content['Image'])
            return True
        except Exception as e:
            logger.error(f"LinkedIn posting failed: {e}")
            return False

    def post_to_twitter(self, tweets: List[Dict]) -> bool:
        try:
            setup_twitter_vars()
            for tweet in tweets:
                post_tweet(tweet_text=tweet['tweet'])
                time.sleep(random.uniform(60, 180))  # Random delay 1-3 minutes
            return True
        except Exception as e:
            logger.error(f"Twitter posting failed: {e}")
            return False

    def post_to_instagram(self, content: Dict) -> bool:
        try:
            instagram_client = InstagramClient()

            # Join hashtags as a single string since they're now a list
            hashtags = ' '.join(content['Hashtags'])

            instagram_client.post_to_instagram(
                caption=f"{content['Text']}\n\n{hashtags}",
                image_url=content['Image']
            )
            return True
        except Exception as e:
            logger.error(f"Instagram posting failed: {str(e)}")
            logger.error(f"Content was: {json.dumps(content, indent=2)}")
            return False

    def post_to_facebook(self, content: Dict) -> bool:
        try:
            facebook_client = FacebookClient()
            facebook_client.post_to_facebook(
                post_text=content['Text'],
                image_url=content['Image']
            )
            return True
        except Exception as e:
            logger.error(f"Facebook posting failed: {e}")
            return False

    def post_to_all_platforms(self, news_items: List[NewsItem]) -> Dict[str, bool]:
        results = {}

        # Generate all summaries and content first
        summaries = psf.get_social_media_summaries(news_items)

        # Generate platform-specific content
        # linkedin won't work without approval
        # linkedin_content = json.loads(psf.get_linkedin_post(news_items))
        facebook_content = json.loads(psf.get_facebook_post(news_items))
        twitter_content = json.loads(psf.get_x_post(news_items))
        instagram_content = json.loads(psf.get_instagram_post(news_items))

        # Post to each platform
        # results['facebook'] = self.post_to_facebook(facebook_content)
        # results['twitter'] = self.post_to_twitter(twitter_content)
        results['instagram'] = self.post_to_instagram(instagram_content)

        # Store summary in DynamoDB
        if summaries:
            summary_str = str(summaries)
            post_id = hashlib.sha256(summary_str.encode('utf-8')).hexdigest()
            self.dynamo_service.insert_item(
                post_date=datetime.datetime.now(datetime.UTC).isoformat(),
                post_id=post_id,
                summary=summary_str
            )

        return results

def lambda_handler(event, context):
    logger.info(f"Received event: {event}")

    # Initialize services
    dynamo_service = DynamoDBService('social_media_posts')
    social_media_service = SocialMediaService(dynamo_service)

    # Parse feeds and post content
    feed_parser = FeedParser(FEED_URLS)
    news_items = feed_parser.get_aggregated_news()

    if not news_items:
        logger.warning("No news items found")
        return {
            'statusCode': 200,
            'body': 'No news items to process'
        }

    # Post to social media platforms
    results = social_media_service.post_to_all_platforms(news_items)

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Social media posting complete',
            'results': results
        })
    }


# For testing
if __name__ == "__main__":
    # Test individual components
    db_service = DynamoDBService('social_media_posts')
    social_media = SocialMediaService(db_service)

    # Test feed parsing
    parser = FeedParser(FEED_URLS)
    items = parser.get_aggregated_news(items_per_feed=2)

    # Test posting
    results = social_media.post_to_all_platforms(items)
    print(f"Posting results: {results}")