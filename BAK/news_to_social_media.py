import json
import logging
import hashlib
import datetime
import feedparser
import boto3
import x_functions
from feedparser import FeedParserDict

from x_functions import setup_twitter, post_tweet

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger()

table_name = 'social_media_posts'

# define news feed sources
feed_urls = [
    "https://www.autoexpress.co.uk/feed/all",
    "https://www.autocar.co.uk/rss",
    "https://www.carbuyer.co.uk/feed/all",
    "https://cardealermagazine.co.uk/publish/category/latest-news/feed"
]

def create_dynamodb_table(table_name):
    session = boto3.Session(profile_name='tradesales')
    dynamodb = session.client('dynamodb')

    table_definition = {
        'TableName': table_name,
        'KeySchema': [
            {'AttributeName': 'PostDate', 'KeyType': 'HASH'}, # partition-key
            {'AttributeName': 'PostId', 'KeyType': 'RANGE'} #sort-key
        ],
        'AttributeDefinitions': [
            { 'AttributeName': 'PostDate', 'AttributeType': 'S' },
            { 'AttributeName': 'PostId', 'AttributeType': 'S'}
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

def get_feed_items_summary(feed: FeedParserDict[str, bool]):
    newsfeeds = []

    for item in feed.entries:
        # if 'media_content' in item:
        #     # Extract image URL from the item's content if available
        #     image_url = item.get('media_content', [{}])[0].get('url', '')
        #     logger.info(f"Image URL: {image_url}")

        # Create post text
        if 'title' in item:
            newsfeeds.append(item.description)
            #post_text = f"{item.title}\n\n{item.description}\n\nRead more: {item.link}"
            #logger.info(f"Feed text: {post_text}")

    summary = get_formal_news_feed_summary(newsfeeds)
    logger.info(f"Summary of news: {summary}")

    return summary

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


def get_social_media_summaries(news_items):
    """
    Returns a dictionary containing formatted posts for each social platform
    """
    # Base prompt elements that apply to all platforms
    base_requirements = """
    For all versions:
    - Focus only on concrete facts and developments
    - Avoid meta-references (like "the report states" or "according to")
    - Include concrete numbers and data points where relevant
    """

    # Platform-specific prompts
    platform_prompts = {
        "linkedin": """Create a LinkedIn post version of these automotive news items.
        Format as:
        HEADER: [Professional header with 1-2 relevant emojis]
        MAIN TEXT: [3-4 professional paragraphs including key data points]
        KEY INSIGHTS: [3 bullet points focused on industry implications]
        HASHTAGS: [3-4 industry-specific hashtags]
        CALL TO ACTION: [Professional engagement prompt]
        RECOMMENDED IMAGE: [URL and business reasoning]""",

        "x": """Create an X (Twitter) post version of these automotive news items.
        Format as:
        MAIN TEXT: [Concise summary within 280 characters]
        THREAD: [2-3 follow-up tweets with key data points]
        HASHTAGS: [2-3 relevant hashtags integrated naturally]
        RECOMMENDED IMAGE: [URL and visibility reasoning]""",

        "facebook": """Create a Facebook post version of these automotive news items.
        Format as:
        HOOK: [Engaging opening line with emoji]
        MAIN TEXT: [2-3 conversational paragraphs with spacing]
        KEY POINTS: [2-3 bullet points with emojis]
        QUESTION: [Engagement question]
        HASHTAGS: [1-2 general hashtags]
        RECOMMENDED IMAGE: [URL and engagement reasoning]""",

        "instagram": """Create an Instagram post version of these automotive news items.
        Format as:
        FIRST LINE: [Strong attention-grabbing opening visible in feed]
        MAIN TEXT: [3-4 key points with emojis and spacing]
        CLOSING: [Engaging call to action]
        FIRST COMMENT: [Grouped hashtags - up to 30 relevant tags]
        RECOMMENDED IMAGE: [URL and visual impact reasoning]"""
    }

    # Format news items with their images
    formatted_items = "\n\n".join(
        f"Item {i + 1}:\nText: {item['text']}\nImage: {item['image_url']}"
        for i, item in enumerate(news_items)
    )

    # Generate summaries for each platform
    summaries = {}
    for platform, platform_prompt in platform_prompts.items():
        content = f"{platform_prompt}\n{base_requirements}\n\nNews items:\n{formatted_items}"
        summaries[platform] = get_claude_summary(content)

    return summaries


def post_to_social_media(summaries):

    # Now you can access each platform's content separately
    linkedin_post = summaries['linkedin']
    x_post = summaries['x']
    facebook_post = summaries['facebook']
    instagram_post = summaries['instagram']

    logger.info(f"X Tweet: {x_post}")

    #x_api = setup_twitter()
    #post_tweet(api=x_api, tweet_text=x_post)

    # Handle each platform separately
    # post_to_linkedin(linkedin_post)
    # post_to_x(x_post)
    # etc.

def get_formal_news_feed_summary(news_items):
    # Consolidate news items into a single text
    prompt = """Please create a professional news summary paragraph that combines all the following news items into a cohesive narrative. The summary should:

    - Use formal journalistic language appropriate for a news wire service
    - Focus only on concrete facts and developments
    - Avoid meta-references (like "the report states" or "according to")
    - Connect related information across different items
    - Present information in order of significance
    - Maintain neutral, objective tone
    - Be contained in a single paragraph
    - Include specific numbers and data points when available

    Here are the news items to summarize:

    {}

    Create a single paragraph that flows naturally and captures all important developments while maintaining journalistic style."""

    # Format news items
    formatted_items = "\n\n".join(f"Item {i + 1}:\n{item}" for i, item in enumerate(news_items))
    content = f"{prompt}\n{formatted_items}"

    return get_claude_summary(content)

def get_claude_summary(content: str):
    # Initialize Bedrock runtime client
    session = boto3.Session(profile_name="tradesales")
    client = session.client("bedrock-runtime", region_name="eu-west-2")

    payload = {
        "anthropic_version": "bedrock-2023-05-31",  # Required field
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": content  # Ensure this is a single string
            }
        ]
    }

    # Send the request
    try:
        response = client.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload)
        )

        # Parse the response
        result = json.loads(response["body"].read().decode("utf-8"))

        # Extract the summary text from the response content
        if "content" in result and isinstance(result["content"], list):
            summary = "".join(
                item.get("text", "") for item in result["content"] if item["type"] == "text"
            )
            return summary.strip()
        else:
            return "No summary text found in the response."

    except Exception as e:
        print(f"Error invoking model: {e}")
        return None

def lambda_handler(event, context):
    logger.info(f"Received message : {event}")

    # iterate feeds and extract all news items
    for feedURL in feed_urls:
        # request feed
        feed = feedparser.parse(feedURL)

        if feed.bozo:  # feedparser's way of indicating feed parsing errors
            raise Exception(f"Feed parsing error: {feed.bozo_exception}")

        #summary = get_feed_items_summary(feed)
        #logger.info(f"News Summary: {summary}")

        parsed_feeds = get_parsed_feed_items(feed)
        summaries = get_social_media_summaries(parsed_feeds)

        post_to_social_media(summaries)

        logger.info(f"Finished processing feed: {feedURL}")

        # add to dynamo table
        # table = create_dynamodb_table(table_name)
        #
        # if summary is not None:
        #     feeds = [{"url": url, "name": f"Feed {i + 1}"} for i, url in enumerate(feed_urls)]
        #     summary_str = str(summary)
        #     insert_item_into_table(post_date=datetime.datetime.now(datetime.UTC).isoformat(),
        #                            post_id=generate_post_id(summary_str), summary=summary_str, metadata=feeds)

