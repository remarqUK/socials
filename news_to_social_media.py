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
from facebook_functions import post_to_facebook, setup_facebook, post_to_instagram
from linkedin_functions import LinkedInAuth
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
        # print(f"Table '{table_name}' creation initiated.")
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
    # facebook(news_items)
    # instagram(news_items)
    #linkedin(news_items)
    # record_to_dynamodb(news_items)

    linkedIn = LinkedInAuth()

    path = linkedIn.get_authorization_url()

    print("PATH ", path)

    logger.info("Finished posting to social media")


def x(news_items):
    x_content = psf.get_x_post(news_items)
    tweets = json.loads(x_content)

    setup_twitter_vars()
    tweet = random.choice(tweets)
    post_tweet(tweet_text=tweet['tweet'])


def facebook(news_items):
    setup_facebook()

    # Filter out news_items that have a blank image_url
    news_items = [item for item in news_items if item['image_url']]

    facebook_content = psf.get_facebook_post(news_items)
    facebook_json = json.loads(facebook_content)

    post_to_facebook(facebook_json['text'], facebook_json['image_url'])


def linkedin(news_items):

#    linkedin_content = psf.get_linkedin_post(news_items)
#    linkedin_json = json.loads(linkedin_content)

    linkedin_json =   {
        "Text": "Unveiling the Latest Automotive Innovations and Trends\n\nThe automotive industry is abuzz with exciting new developments, from cutting-edge electric vehicles to groundbreaking safety technologies. In this post, we delve into some of the most notable recent advancements and insights.\n\nLeading the charge in sustainable mobility, Volvo has opened order books for its highly anticipated ES90 EV, boasting an impressive range of up to 435 miles thanks to next-generation electric vehicle technology. Meanwhile, BMW's latest offering, the 392bhp X3 M50 SUV, showcases a perfect blend of refinement and performance, setting a new benchmark in its segment.\n\nKEY INSIGHTS:\n\n- Used car values saw a modest 0.4% increase in February, reflecting resilient demand\n- EV adoption continues to surge, accounting for a quarter of new car registrations in the UK\n- Fleets are exploring alternative decarbonization solutions like HVO fuel as EV uptake plateaus\n\nAs the industry navigates the transition to electrification, what strategies do you see as most effective for fleets and consumers alike? We welcome your insights and experiences in this dynamic landscape.\n\n#AutomotiveInnovations #EVTrends",
        "Image": "https://media.autoexpress.co.uk/image/private/s--hZqJKyYZ--/t_rss_image_w_845/v1741186013/autoexpress/2025/03/BMW%20X3%20M50%202025%20UK.jpg",
    }

    post_to_linkedin(linkedin_json['Text'],  linkedin_json['Image'])

def instagram(news_items):
    setup_facebook()

    # Filter out news_items that have a blank image_url
    news_items = [item for item in news_items if item['image_url']]

    instagram_content = psf.get_instagram_post(news_items)
    instagram_json = json.loads(instagram_content)

    post_to_instagram(instagram_json['Text'], instagram_json['Image'])
    return


def record_to_dynamodb(news_items):
    # add to dynamo table
    # if summary is not None:
    #  feeds = [{"url": url, "name": f"Feed {i + 1}"} for i, url in enumerate(feed_urls)]
    #  summary_str = str(summary)
    #  insert_item_into_table(post_date=datetime.datetime.now(datetime.UTC).isoformat(),
    #  post_id=generate_post_id(summary_str), summary=summary_str, metadata=feeds)
    return


def lambda_handler(event, context):

    query_params = event.get("queryStringParameters", {}) or {}
    code = query_params.get("code")

    # This means we have a callback from Linkedin
    if code:
        exit()

    logger.info(f"Received message : {event}")

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
