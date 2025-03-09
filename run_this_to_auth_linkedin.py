# save this file as linkedin_callback_server.py
import json
import webbrowser

from flask import Flask, request

from aws_functions import save_tokens_to_secrets, get_secret
from linkedin_functions import LinkedInAuth

app = Flask(__name__)

def open_linkedin_auth_page():
    linkedin = LinkedInAuth()
    init_auth_url = linkedin.get_authorization_url()
    webbrowser.open(init_auth_url)


open_linkedin_auth_page()

@app.route("/")
def home():
    return "LinkedIn OAuth Test - visit /callback after authorizing with LinkedIn"

@app.route("/callback")
def linkedin_callback():
    """
    LinkedIn will redirect back to this route with query parameters including 'code' and 'state'.
    Example: http://localhost:5000/callback?code=ABC123&state=XYZ
    """
    auth_code = request.args.get("code")
    state = request.args.get("state")

    print("AUTH CODE ", auth_code)
    print("STATE ", state)

    linkedin_handle = LinkedInAuth()
    linkedin_handle.handle_callback(auth_code)

    print("LINKEDIN ACCESS TOKEN UPDATED ", state)

    return "LinkedIn OAuth successful! You can close this window."

if __name__ == "__main__":
    # Run the Flask app on localhost:5000
    # Ensure your LinkedIn redirect URI matches this address + '/callback'
    app.run(host="0.0.0.0", port=5000, debug=True)

