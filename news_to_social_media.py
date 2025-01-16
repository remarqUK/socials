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
    #setup_facebook()

    # Generate posts for each platform
    linkedin_content = psf.get_linkedin_post(news_items)
    #x_content = psf.get_x_post(news_items)
    #facebook_content = psf.get_facebook_post(news_items)
    #instagram_content = psf.get_instagram_post(news_items)

    #summaries = psf.get_social_media_summaries(news_items)

    #logger.info(f"X: {x_content}")
    #x_api = setup_twitter()

    #logger.info(f"Facebook: {facebook_content}")

    # Convert to JSON string
    #json_string = json.dumps(facebook_content)
    #print(type(json_string))

    print(linkedin_content)

    # If you need to load it back
    #loaded_content = json.loads(facebook_content)

    #json_string = json.dumps(linkedin_content)
    loaded_content = json.loads(linkedin_content)

    # Check the type of the loaded content
    #print(type(loaded_content))  # Should be <class 'dict'>

    # If it's not a dictionary, you can check the raw content


    logger.info(f"Content: {loaded_content}")

    #post_to_facebook(post_text=loaded_content['Text'], image_url=loaded_content['Image'])

    post_to_linkedin(text=loaded_content['Text'], image_url=loaded_content['Image'])

    # setup_twitter_vars()
    #
    # tweets = json.loads(x_content)
    # for tweet in tweets:
    #     post_tweet(tweet_text=tweet['tweet'])

    # add to dynamo table
    #
    # if summary is not None:
    #     feeds = [{"url": url, "name": f"Feed {i + 1}"} for i, url in enumerate(feed_urls)]
    #     summary_str = str(summary)
    #     insert_item_into_table(post_date=datetime.datetime.now(datetime.UTC).isoformat(),
    #                            post_id=generate_post_id(summary_str), summary=summary_str, metadata=feeds)

    #logger.info(f"Facebook: {facebook_content}")

    # Post to each platform (implementation would depend on your social media APIs)
    # post_to_linkedin(linkedin_content)
    # post_to_x(x_content)
    # post_to_facebook(facebook_content)
    # post_to_instagram(instagram_content)

    logger.info("Finished posting to social media")

def lambda_handler(event, context):
    logger.info(f"Received message : {event}")

    # Load credentials from AWS Secrets Manager
    # secret_name = "LinkedInCredentials"
    # secrets = json.loads(get_secret(secret_name))
    #
    # # Perform initial authorization
    # tokens = perform_initial_auth(
    #     client_id=secrets['ClientId'],
    #     client_secret=secrets['ClientSecret'],
    #     redirect_uri="http://localhost:8000/callback"
    # )

    ## create dynamodb table if it doesn't exist
    table = create_dynamodb_table(table_name)

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
