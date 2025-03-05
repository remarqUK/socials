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


    linkedIn = LinkedInAuth()
    x = linkedIn.handle_callback(auth_code)

    print("X ", x)
    exit(1);

    secret = get_secret(secret_name="LinkedInCredentials")
    secrets = json.load(secret)

    # Normally, you would exchange the auth_code for an access token here
    # by making a POST request to the LinkedIn OAuth token endpoint.

    # For now, we'll just print the code and state
    print(f"Authorization Code: {auth_code}")
    print(f"State: {state}")

    # Exchange auth code for tokens



    # Update token in secrets manager
    save_tokens_to_secrets(secret_name="LinkedInCredentials", tokens=secrets)

    return "LinkedIn callback received! Check your terminal output."

if __name__ == "__main__":
    # Run the Flask app on localhost:5000
    # Ensure your LinkedIn redirect URI matches this address + '/callback'
    app.run(host="0.0.0.0", port=5000, debug=True)

