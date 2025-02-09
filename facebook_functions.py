import json
import os
import time
from typing import Optional
import facebook
import requests
from io import BytesIO

from aws_functions import get_secret


class FacebookClient:
    def __init__(self, page_name: str = 'Trade Sales'):
        self.page_name = page_name
        self.page_token: Optional[str] = None
        self.token_expiry: Optional[float] = None
        self.refresh_token()

    def refresh_token(self) -> None:
        """Fetch fresh tokens from Facebook"""
        secret = get_secret(secret_name="FacebookCredentials")
        secrets = json.loads(secret)

        user_access_token = secrets['AccessToken']
        graph = facebook.GraphAPI(user_access_token)
        pages = graph.get_object("me/accounts")

        page_data = next((item for item in pages['data'] if item['name'] == self.page_name), None)
        if not page_data:
            raise ValueError(f"Page '{self.page_name}' not found")

        self.page_token = page_data['access_token']
        # Set token expiry to 55 minutes (tokens typically last 60 minutes)
        self.token_expiry = time.time() + (55 * 60)

    def get_valid_token(self) -> str:
        """Return a valid token, refreshing if necessary"""
        if not self.token_expiry or time.time() >= self.token_expiry:
            self.refresh_token()
        return self.page_token

    def post_to_facebook(self, post_text: str, image_url: str) -> None:
        """Post content to Facebook with automatic token refresh"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                graph = facebook.GraphAPI(self.get_valid_token())
                response = requests.get(image_url)
                image_content = BytesIO(response.content)
                graph.put_photo(image=image_content, message=post_text)
                print("Successfully posted to Facebook!")
                return

            except facebook.GraphAPIError as e:
                if attempt < max_retries - 1 and ("expired" in str(e).lower() or "invalid" in str(e).lower()):
                    self.refresh_token()
                    continue
                raise