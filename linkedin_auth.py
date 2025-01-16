import datetime
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlencode, parse_qs, urlparse
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


class LinkedInAuth:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str, token_store: dict = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.access_token = token_store.get('access_token') if token_store else None
        self.refresh_token = token_store.get('refresh_token') if token_store else None
        self.token_expiry = token_store.get('token_expiry') if token_store else None

    def get_authorization_url(self) -> str:
        params = {
            'response_type': 'code',
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': 'w_member_social profile email openid',
            'state': '89675r98ughbsdakjufgiuSSdhiughdhydffs'
        }
        return f"https://www.linkedin.com/oauth/v2/authorization?{urlencode(params)}"

    def handle_callback(self, code: str) -> dict:
        """Exchange authorization code for tokens."""
        token_url = 'https://www.linkedin.com/oauth/v2/accessToken'
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'redirect_uri': self.redirect_uri
        }

        response = requests.post(token_url, data=data)
        response.raise_for_status()
        token_data = response.json()

        self.access_token = token_data['access_token']
        self.refresh_token = token_data.get('refresh_token')
        expires_in = token_data.get('expires_in', 5184000)  # Default to 60 days
        self.token_expiry = datetime.datetime.now() + datetime.timedelta(seconds=expires_in)

        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "token_expiry": self.token_expiry.isoformat()
        }

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


def perform_initial_auth(client_id, client_secret, redirect_uri):
    """Complete OAuth flow and return tokens."""
    auth = LinkedInAuth(client_id, client_secret, redirect_uri)

    # Get and print authorization URL
    auth_url = auth.get_authorization_url()
    print(f"\nPlease visit this URL to authorize the application:\n{auth_url}\n")

    # Set up local server to catch the callback
    server = HTTPServer(('localhost', 8000), CallbackHandler)
    server.auth_code = None
    print("Waiting for authorization...")
    server.handle_request()

    if not server.auth_code:
        raise Exception("Authorization failed - no code received")

    # Exchange code for tokens
    try:
        token_data = auth.handle_callback(server.auth_code)
        print("\nAuthorization successful! Tokens received.")

        # Save tokens to AWS Secrets Manager
        secret_name = "LinkedInCredentials"
        secrets = json.loads(get_secret(secret_name))
        secrets.update(token_data)
        save_tokens_to_secrets(secret_name, secrets)
        print("Tokens saved to AWS Secrets Manager")

        return token_data
    except Exception as e:
        print(f"Error exchanging code for tokens: {e}")
        raise

def post_to_linkedin(text: str, image_url: str, secret_name: str = "LinkedInCredentials") -> dict:
    """Post content to LinkedIn with automatic token refresh."""
    # Load credentials and tokens
    secrets = json.loads(get_secret(secret_name))

    # Initialize auth with stored tokens
    auth = LinkedInAuth(
        client_id=secrets['ClientId'],
        client_secret=secrets['ClientSecret'],
        redirect_uri="http://localhost:8000/callback",
        token_store=secrets
    )

    # Check and refresh token if needed
    if not auth.is_token_valid():
        print("Refreshing LinkedIn token...")
        try:
            updated_tokens = auth.refresh_access_token()
            if updated_tokens:  # Only update if we got new tokens
                secrets.update(updated_tokens)
                save_tokens_to_secrets(secret_name, secrets)
                print("Token refreshed successfully!")
            else:
                print("Failed to refresh token.")
                return None
        except Exception as e:
            print(f"Error during token refresh: {str(e)}")
            return None

    headers = {
        'Authorization': f'Bearer {auth.access_token}',
        'Content-Type': 'application/json',
        'X-Restli-Protocol-Version': '2.0.0'
    }

    print(f"Bearer: {auth.access_token}")

    try:
        # Get user profile ID
        profile_response = requests.get(
            "https://api.linkedin.com/v2/me",
            headers=headers
        )
        profile_response.raise_for_status()
        author = f"urn:li:person:{profile_response.json()['id']}"

        # Prepare post data
        post_data = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {
                        "text": text
                    },
                    "shareMediaCategory": "IMAGE",
                    "media": [
                        {
                            "status": "READY",
                            "description": {
                                "text": "Image"
                            },
                            "media": image_url
                        }
                    ]
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