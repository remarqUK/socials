import json
import facebook
import requests
from datetime import datetime, timedelta
from aws_functions import get_secret, save_tokens_to_secrets


class InstagramClient:
    def __init__(self, page_name: str = 'Trade Sales'):
        self.page_name = page_name
        self.page_token = None
        self.instagram_page_id = None
        self.app_id = None
        self.app_secret = None
        self.token_expiration = None
        self.setup_credentials()

    def setup_credentials(self):
        secret = json.loads(get_secret("FacebookCredentials"))
        self.instagram_page_id = secret['InstagramPageId']
        self.page_token = secret['InstaPageAccessToken']
        self.app_id = secret['AppId']
        self.app_secret = secret['AppSecret']

        # Check if token needs refresh
        self._check_and_refresh_token()

    def _check_and_refresh_token(self):
        """Check token expiration and refresh if needed"""
        # First, get token info
        token_info_url = f"https://graph.facebook.com/v18.0/debug_token"
        params = {
            'input_token': self.page_token,
            'access_token': f"{self.app_id}|{self.app_secret}"
        }

        response = requests.get(token_info_url, params=params)
        token_info = response.json()

        # Check if token is expired or will expire soon
        if 'data' in token_info:
            expiration = token_info['data'].get('expires_at', 0)
            if expiration:
                self.token_expiration = datetime.fromtimestamp(expiration)
                # If token expires in less than 24 hours, refresh it
                if self.token_expiration - datetime.now() < timedelta(hours=24):
                    self._refresh_token()

    def _refresh_token(self):
        """Refresh the page access token"""
        refresh_url = f"https://graph.facebook.com/v18.0/oauth/access_token"
        params = {
            'grant_type': 'fb_exchange_token',
            'client_id': self.app_id,
            'client_secret': self.app_secret,
            'fb_exchange_token': self.page_token
        }

        response = requests.get(refresh_url, params=params)
        if response.status_code == 200:
            new_token_data = response.json()
            self.page_token = new_token_data['access_token']

            # Update the token in AWS Secrets Manager
            secret = json.loads(get_secret("FacebookCredentials"))
            secret['PageAccessToken'] = self.page_token
            # You'll need to implement update_secret function
            self._update_secret("FacebookCredentials", json.dumps(secret))
        else:
            raise Exception(f"Failed to refresh token: {response.text}")

    def _update_secret(self, secret_name: str, secret_value: str):
        """Update secret in AWS Secrets Manager"""
        tokens = json.loads(secret_value)
        save_tokens_to_secrets(secret_name, tokens)

    def post_to_instagram(self, caption: str, image_url: str) -> None:
        # Check token before posting
        self._check_and_refresh_token()

        graph = facebook.GraphAPI(self.page_token)

        # Create media container
        media_object = graph.put_object(
            self.instagram_page_id,
            "media",
            image_url=image_url,
            caption=caption
        )

        if not media_object.get('id'):
            raise Exception("Failed to create media object")

        # Publish media
        result = graph.put_object(
            self.instagram_page_id,
            "media_publish",
            creation_id=media_object['id']
        )

        if not result.get('id'):
            raise Exception("Failed to publish media object")