import json
import os
import facebook
import requests
from io import BytesIO
from aws_functions import save_tokens_to_secrets, get_secret

def setup_facebook():
    # generate a page access token and store
    secret = get_secret(secret_name="FacebookCredentials")
    secrets = json.loads(secret)

    user_access_token = secrets['AccessToken']
    instagram_page_id = secrets['InstagramPageId']

    graph = facebook.GraphAPI(user_access_token)

    # Refresh long lived access token
    new_token_object = graph.extend_access_token(secrets['AppId'], secrets['AppSecret'])

    secrets['AccessToken'] = new_token_object['access_token']

    print("Tokens saved to AWS Secrets Manager", secrets['AccessToken'])

    # Update token in secrets manager
    save_tokens_to_secrets(secret_name="FacebookCredentials", tokens=secrets)

    pages = graph.get_object("me/accounts")

    # Extract the section for 'name': 'Trade Sales'
    trade_sales_data = next((item for item in pages['data'] if item['name'] == 'Trade Sales'), None)

    # print(f"Trade Sales Data: {trade_sales_data}")

    os.environ['FaceBook_PageToken'] = trade_sales_data['access_token']
    os.environ['InstagramPageId'] = instagram_page_id


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

def post_to_instagram(post_text: str, image_url: str) -> None:
    try:

        # Initialize the Graph API object
        graph = facebook.GraphAPI(os.environ['FaceBook_PageToken'])

        creation_resp = graph.request(
            path=f"{os.environ['InstagramPageId']}/media",
            args={
                "image_url": image_url,  # Must be a publicly accessible image URL
                "caption": post_text,
            },
            method="POST"
        )

        if "id" not in creation_resp:
            raise Exception(f"Error creating media container: {creation_resp}")

        creation_id = creation_resp["id"]

        # 2) Publish the container
        publish_resp = graph.request(
            path=f"{os.environ['InstagramPageId']}/media_publish",
            args={
                "creation_id": creation_id,
            },
            method="POST"
        )

        return publish_resp

    except facebook.GraphAPIError as e:
        print(f"An error occurred: {str(e)}")


