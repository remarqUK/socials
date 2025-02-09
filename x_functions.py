import json
import os
import time
import tweepy
import logging
from aws_functions import get_secret

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'  # Hours:Minutes:Seconds format (no milliseconds)
)
logger = logging.getLogger()


def post_tweet(tweet_text, max_retries=3):
    for attempt in range(max_retries):
        try:
            bearer = os.environ['X_BearerToken']
            api = os.environ['X_APIKey']
            api_secret = os.environ['X_APIKeySecret']
            access = os.environ['X_AccessToken']
            secret = os.environ['X_AccessTokenSecret']

            client = tweepy.Client(
                bearer_token=bearer,
                access_token=access,
                access_token_secret=secret,
                consumer_key=api,
                consumer_secret=api_secret
            )

            tweet = client.create_tweet(text=tweet_text)
            logger.info(f"Tweet posted successfully: {tweet.data['id']}")
            return True

        except tweepy.TooManyRequests:
            if attempt == max_retries - 1:
                logger.error("Rate limit exceeded, max retries reached")
                raise
            time.sleep(60)  # Wait before retry

        except tweepy.Unauthorized:
            logger.error("Authentication failed - check credentials")
            raise

        except tweepy.TweepyException as e:
            logger.error(f"Tweet failed: {e}")
            raise

    return False

def setup_twitter_vars():
    secret = get_secret(secret_name = "TwitterAPICredentials")

    logger.info(f"SECRET: ", secret)
    secrets = json.loads(secret)

    os.environ['X_APIKey'] = secrets['APIKey']
    os.environ['X_APIKeySecret'] = secrets['APIKeySecret']
    os.environ['X_AccessToken'] = secrets['AccessToken']
    os.environ['X_AccessTokenSecret'] = secrets['AccessTokenSecret']
    os.environ['X_BearerToken'] = secrets['BearerToken']

    # return authenticate_twitter(api_key=secrets['APIKey'],
    #                      api_key_secret=secrets['APIKeySecret'],
    #                      access_token=secrets['AccessToken'],
    #                      access_token_secret=secrets['AccessTokenSecret'])
