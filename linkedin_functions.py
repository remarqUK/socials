import datetime
import json
import os
import string
import random
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs, urlparse, quote
import requests
from aws_functions import get_secret, save_tokens_to_secrets


class CallbackHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        query_components = parse_qs(urlparse(self.path).query)

        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        if 'code' in query_components:
            self.server.auth_code = query_components['code'][0]
            self.wfile.write(b"Authorization successful! You can close this window.")
        else:
            self.wfile.write(b"Authorization failed! Please try again.")

        # STORE AUTH IN DATABASE


class LinkedInAuth:

    def __init__(self):

        secret = get_secret(secret_name="LinkedInCredentials")
        secrets = json.loads(secret)

        self.client_id = secrets['client_id']
        self.client_secret = secrets['client_secret']
        self.redirect_uri = secrets['redirect_uri']
        # self.access_token = secrets['access_token']
        # self.organisation_urn = secrets['organisation_urn']

    @staticmethod
    def update_linkedin_credentials(secret_label: str, secret_value: str):

        print("UPDATE LINKEDIN CREDENTIALS RECEIVED ", secret_label, secret_value)
        secret = get_secret(secret_name="LinkedInCredentials")
        secrets = json.loads(secret)
        print("RETRIEVED SECRETS", secrets)
        secrets[secret_label] = secret_value
        print("NEW SECRETS", secrets)
        save_tokens_to_secrets(secret_name="LinkedInCredentials", tokens=secrets)
        print("CREDENTIALS SAVED", secret_label, secret_value)

    def get_authorization_url(self) -> str:
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'openid profile email',
            'state': ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(12))
        }
        return f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params, quote_via=quote)}"

    def handle_callback(self, code: str) -> str:
        """Exchange authorization code for tokens."""
        token_url = 'https://www.linkedin.com/oauth/v2/accessToken'
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri
        }

        response = requests.get(token_url, data=data)

        token_data = response.json()

        access_token:str = token_data['access_token']

        if token_data['access_token']:
            LinkedInAuth.update_linkedin_credentials('access_token', access_token)

        return access_token

    def is_token_valid(self) -> bool:
        """
        Check if the current access token is valid based on expiry time.

        Returns:
            bool: True if token exists and hasn't expired, False otherwise
        """
        # Check if we have a token and expiry time
        if not self.access_token or not self.token_expiry:
            return False

        # If token_expiry is a string (from JSON), convert it to datetime
        if isinstance(self.token_expiry, str):
            try:
                self.token_expiry = datetime.datetime.fromisoformat(self.token_expiry)
            except ValueError:
                return False

        # Check if token has expired
        return datetime.datetime.now() < self.token_expiry

    def refresh_access_token(self) -> dict:
        """Refresh the access token using the refresh token."""
        # Check if we have a refresh token
        if not self.refresh_token:
            print("No refresh token available. Need to perform initial authorization.")
            # Perform initial authorization
            token_data = perform_initial_auth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri
            )
            return token_data

        try:
            token_url = 'https://www.linkedin.com/oauth/v2/accessToken'
            data = {
                'grant_type': 'refresh_token',
                'refresh_token': self.refresh_token,
                'client_id': self.client_id,
                'client_secret': self.client_secret
            }

            response = requests.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()

            # Update the instance variables
            self.access_token = token_data['access_token']
            self.refresh_token = token_data.get('refresh_token', self.refresh_token)
            expires_in = token_data.get('expires_in', 5184000)
            self.token_expiry = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)

            return {
                "access_token": self.access_token,
                "refresh_token": self.refresh_token,
                "token_expiry": self.token_expiry.isoformat()
            }

        except requests.exceptions.RequestException as e:
            print(f"Error refreshing token: {str(e)}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                print(f"Response content: {e.response.text}")

            # If refresh fails, try initial authorization
            print("Attempting initial authorization...")
            token_data = perform_initial_auth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri
            )
            return token_data


def post_to_linkedin(text: str, image_url: str, secret_name: str = "LinkedInCredentials") -> dict:

    """Post content to LinkedIn with automatic token refresh."""
    # Load credentials and tokens
    secrets = json.loads(get_secret(secret_name))

    access_token = secrets.get('access_token')

    #print(f"Bearer: {access_token}")

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0'
    }

    try:
        # Get user profile ID
        profile_response = requests.get(
            "https://api.linkedin.com/v2/userinfo",
            headers=headers
        )

        #print("PROFILE RESPONSE ", profile_response.json())

        exit(1)

        profile_response.raise_for_status()
        author = f"urn:li:organization:104956250"

        # Prepare post data
        post_data = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            }
        }

        # Make the post
        response = requests.post(
            "https://api.linkedin.com/v2/ugcPosts",
            headers=headers,
            json=post_data
        )
        response.raise_for_status()
        return response.json()

    except requests.exceptions.RequestException as e:
        print(f"Error posting to LinkedIn: {str(e)}")
        if hasattr(e, 'response') and hasattr(e.response, 'text'):
            print(f"Response content: {e.response.text}")
        return None
