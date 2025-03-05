import json
import os
import tweepy
import logging
from aws_functions import get_secret

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'  # Hours:Minutes:Seconds format (no milliseconds)
)
logger = logging.getLogger()

def post_tweet(tweet_text):
    try:
        bearer = os.environ['X_BearerToken']
        api = os.environ['X_APIKey']
        api_secret = os.environ['X_APIKeySecret']
        access = os.environ['X_AccessToken']
        secret = os.environ['X_AccessTokenSecret']

        logger.info(f"attempting to initialise client with {bearer}")

        client = tweepy.Client(bearer_token=bearer, access_token=access, access_token_secret=secret, consumer_key=api, consumer_secret=api_secret)

        logger.info(f"attempting to post tweet {tweet_text}")
        tweet = client.create_tweet(text=tweet_text)

        print(f"Successfully posted tweet with ID: {tweet.data['id']}")
    except tweepy.TweepyException as e:
        print(f"Failed to post tweet: {e}")

def setup_twitter_vars():
    secret = get_secret(secret_name = "TwitterAPICredentials")

    logger.info(f"SECRET: ", secret)
    secrets = json.loads(secret)

    os.environ['X_APIKey'] = secrets['APIKey']
    os.environ['X_APIKeySecret'] = secrets['APIKeySecret']
    os.environ['X_AccessToken'] = secrets['AccessToken']
    os.environ['X_AccessTokenSecret'] = secrets['AccessTokenSecret']
    os.environ['X_BearerToken'] = secrets['BearerToken']