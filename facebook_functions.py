import json
import os
import facebook
import requests
from io import BytesIO

from aws_functions import get_secret

def setup_facebook():
    # generate a page access token and store
    secret = get_secret(secret_name = "FacebookCredentials")
    secrets = json.loads(secret)

    print(f"SECRETS {secrets}")

    user_access_token = secrets['AccessToken']
    graph = facebook.GraphAPI(user_access_token)

    # Refresh long lived access token
    x1 = graph.extend_access_token(secrets['AppId'], secrets['AppSecret'])

    # PETE SAVE THE NEW TOKEN (X1) BACK TO AWS

    print("X1 ", x1);

    pages = graph.get_object("me/accounts")

    # Extract the section for 'name': 'Trade Sales'
    trade_sales_data = next((item for item in pages['data'] if item['name'] == 'Trade Sales'), None)

    #print(f"Trade Sales Data: {trade_sales_data}")

    os.environ['FaceBook_PageToken'] = trade_sales_data['access_token']

def post_to_facebook(post_text, image_url):
    try:

        # Initialize the Graph API object
        graph = facebook.GraphAPI(os.environ['FaceBook_PageToken'])

        # Download the image
        response = requests.get(image_url)
        image_content = BytesIO(response.content)

        graph.put_photo(image=image_content, message=post_text)

        print("Successfully posted to Facebook!")
    except facebook.GraphAPIError as e:
        print(f"An error occurred: {str(e)}")
