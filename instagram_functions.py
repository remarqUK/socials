import json
import facebook

from aws_functions import get_secret


class InstagramClient:
    def __init__(self, page_name: str = 'Trade Sales'):
        self.page_name = page_name
        self.page_token = None
        self.instagram_page_id = None
        self.setup_credentials()

    def setup_credentials(self):
        secret = json.loads(get_secret("FacebookCredentials"))
        self.instagram_page_id = secret['InstagramPageId']
        self.page_token = secret['PageAccessToken']

    def post_to_instagram(self, caption: str, image_url: str) -> None:
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