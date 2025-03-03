import json
import logging
import hashlib
import datetime
import webbrowser
from http.server import HTTPServer

import feedparser
import boto3
import x_functions
import facebook_functions
import platform_summary_functions as psf
from feedparser import FeedParserDict
import random

from aws_functions import get_secret
from facebook_functions import post_to_facebook, setup_facebook
from linkedin_auth import LinkedInAuth, CallbackHandler, post_to_linkedin, perform_initial_auth
from x_functions import post_tweet, setup_twitter_vars

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'  # Hours:Minutes:Seconds format (no milliseconds)
)
logger = logging.getLogger()

table_name = 'social_media_posts'

# define news feed sources
feed_urls = [
    "https://www.autoexpress.co.uk/feed/all",
    "https://www.am-online.com/news/latest-news/rss.xml",
    "https://www.fleetnews.co.uk/news/latest-fleet-news/rss.xml",
    "https://cardealermagazine.co.uk/publish/category/latest-news/feed"
]

def create_dynamodb_table(table_name):
    session = boto3.Session(profile_name='tradesales')
    dynamodb = session.client('dynamodb')

    table_definition = {
        'TableName': table_name,
        'KeySchema': [
            {'AttributeName': 'PostId', 'KeyType': 'HASH'},  # Partition key
            {'AttributeName': 'PostDate', 'KeyType': 'RANGE'}  # Sort key
        ],
        'AttributeDefinitions': [
            {'AttributeName': 'PostId', 'AttributeType': 'S'},
            {'AttributeName': 'PostDate', 'AttributeType': 'S'}
        ],
        'ProvisionedThroughput': {
            'ReadCapacityUnits': 5,
            'WriteCapacityUnits': 5
        }
    }

    try:
        response = dynamodb.create_table(**table_definition)
        #print(f"Table '{table_name}' creation initiated.")
        logger.info(f"Table '{table_name}' creation initiated.")
        return response
    except dynamodb.exceptions.ResourceInUseException:
        logger.info(f"Table '{table_name}' already exists.")
    except Exception as e:
        logger.error(f"Error creating table: {e}")

def insert_item_into_table(post_date, post_id, summary, metadata):
    session = boto3.Session(profile_name='tradesales')
    dynamodb = session.resource('dynamodb')
    table = dynamodb.Table(table_name)

    try:
        response = table.put_item(Item={
            'PostDate': post_date,
            "PostId": post_id,
            "Summary": summary,
            "Metadata": metadata
        })

        return response
    except Exception as e:
        logger.error(f"Error inserting item into table '{table_name}': {e}")
        return None

def get_parsed_feed_items(feed: FeedParserDict):
    news_items = []

    for item in feed.entries:
        news_item = {
            "text": item.get("title", "") + "\n\n" + item.get("description", ""),
            "image_url": item.get("media_content", [{}])[0].get("url", "")  # Extract image if available
        }
        news_items.append(news_item)

    logger.info(f"Extracted {len(news_items)} news items.")
    return news_items

def generate_post_id(post_content: str) -> str:
    """Generates a unique hash ID for a post."""
    # Create a SHA256 hash of the post content
    post_hash = hashlib.sha256(post_content.encode('utf-8')).hexdigest()
    return post_hash

# Example usage:
def post_to_social_media(news_items):

    # x(news_items); # This works
    facebook(news_items);
    linkedin(news_items);
    instagram(news_items);
    record_to_dynamodb(news_items)

    logger.info("Finished posting to social media")

def x(news_items):

    x_content = psf.get_x_post(news_items)
    tweets = json.loads(x_content)

    #tweets = [{"tweet": "This is a test tweet"}]

    setup_twitter_vars()
    tweet = random.choice(tweets)
    post_tweet(tweet_text=tweet['tweet'])

def facebook(news_items):

  setup_facebook();
  # facebook_content = psf.get_facebook_post(news_items)
  facebook_posts = [{'image_url': 'https://media.autoexpress.co.uk/image/private/s--w1hzAwTC--/t_rss_image_w_845/v1562243855/autoexpress/2016/12/selling-cars-107.jpg', 'text': 'Car photography: how to take great pics of your car\n\nFollow our car photography top tips to make your car presentable when selling it on an online marketplace or just showing it of on social media'}, {'image_url': 'https://media.autoexpress.co.uk/image/private/s--EKLqobUt--/t_rss_image_w_845/v1741010593/autoexpress/2025/03/Mercedes-AMG SUV - front 3_4_nq8pjy.jpg', 'text': 'Mercedes-AMG electric super-SUV - pictures\n\nImages of the soon to arrive Mercedes-AMG electric super-SUV'}, {'image_url': 'https://media.autoexpress.co.uk/image/private/s--UwdEnL9V--/t_rss_image_w_845/v1740758822/autoexpress/2025/02/Kia EV6 vs Skoda Enyaq Coupe-13.jpg', 'text': 'Kia EV6 and Skoda Enyaq Coupe - pictures\n\nPictures of the Kia EV6 and Skoda Enyaq Coupe being driven on UK roads. Pictures taken by Auto Express photographer Otis Clay'}]
  facebook_content = facebook_posts[0]

  post_to_facebook(facebook_content['text'], facebook_content['image_url'])

def linkedin(news_items):

  linkedin_content = psf.get_linkedin_post(news_items)
  post_to_linkedin(linkedin_content)
  print(linkedin_content)

def instagram(news_items):
  # post_to_instagram(instagram_content)
  return

def record_to_dynamodb(news_items):
  # add to dynamo table
  #if summary is not None:
  #  feeds = [{"url": url, "name": f"Feed {i + 1}"} for i, url in enumerate(feed_urls)]
  #  summary_str = str(summary)
  #  insert_item_into_table(post_date=datetime.datetime.now(datetime.UTC).isoformat(),
  #  post_id=generate_post_id(summary_str), summary=summary_str, metadata=feeds)
  return

def lambda_handler(event, context):

    logger.info(f"Received message : {event}")

    # Load credentials from AWS Secrets Manager
    #secret_name = "LinkedInCredentials"
    #secrets = json.loads(get_secret(secret_name))
    #
    # # Perform initial authorization

    #tokens = perform_initial_auth(
    #     client_id=secrets['ClientId'],
    #     client_secret=secrets['ClientSecret'],
    #     redirect_uri="http://localhost:8000/callback"
    #)

    ## create dynamodb table if it doesn't exist
    table = create_dynamodb_table(table_name)

    ## Test an image
    # post_to_linkedin(text="Test message", image_url="https://testimages.org/img/testimages_screenshot.jpg")

    # Aggregate news items from all feeds
    aggregated_news_items = []
    for feedURL in feed_urls:
        feed = feedparser.parse(feedURL)

        if feed.bozo:
            logger.warning(f"Failed to parse feed: {feedURL}")
            continue

        # Get the parsed feed items (assuming get_parsed_feed_items is defined elsewhere)
        parsed_feed_items = get_parsed_feed_items(feed)

        # Limit the number of stories from each feed to 5, selected randomly
        num_items_to_select = min(5, len(parsed_feed_items))
        random_items = random.sample(parsed_feed_items, num_items_to_select)

        aggregated_news_items.extend(random_items)
        logger.info(f"Finished processing feed: {feedURL}")

    if not aggregated_news_items:
        logger.warning("No news items found. Exiting.")
        return

    logger.info("Finished processing all feeds")
    post_to_social_media(aggregated_news_items)

    logger.info("End of script")
