import json
import logging

logger = logging.getLogger()
from aws_functions import get_boto3_session

def _format_news_items(news_items):
    return "\n\n".join(
        f"Item {i + 1}:\nText: {item.text}\nImage: {item.image_url}"
        for i, item in enumerate(news_items)
    )

def clean_json_string(json_str: str) -> str:
    """Clean and validate JSON string"""
    try:
        # First try to parse it as is (might be already valid)
        json.loads(json_str)
        return json_str
    except json.JSONDecodeError:
        try:
            # Try to clean up common issues
            # Replace literal newlines with \n
            cleaned = json_str.replace('\n', '\\n')
            # Replace any unescaped quotes
            cleaned = cleaned.replace('"', '\\"')
            # Wrap in quotes if it's not already
            if not cleaned.startswith('"'):
                cleaned = f'"{cleaned}"'
            # Validate the cleaned version
            json.loads(cleaned)
            return cleaned
        except json.JSONDecodeError:
            logger.error(f"Could not clean JSON string: {json_str}")
            return None


def get_claude_summary(content: str):
    try:
        session = get_boto3_session()
        client = session.client("bedrock-runtime", region_name="eu-west-2")

        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "messages": [
                {
                    "role": "user",
                    "content": f"{content}\n\nIMPORTANT: Ensure the response is valid JSON with properly escaped characters."
                }
            ]
        }

        logger.info("Calling Bedrock with payload")
        response = client.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload)
        )

        response_body = response["body"].read().decode("utf-8")
        result = json.loads(response_body)

        if "content" in result and isinstance(result["content"], list):
            summary = "".join(
                item.get("text", "") for item in result["content"] if item["type"] == "text"
            ).strip()

            # Try to parse the summary as JSON
            try:
                parsed_json = json.loads(summary)
                # If it parsed successfully, return the original summary
                return summary
            except json.JSONDecodeError:
                # If parsing failed, try to clean it
                cleaned_summary = clean_json_string(summary)
                if cleaned_summary:
                    return cleaned_summary
                logger.error(f"Invalid JSON in Claude response: {summary}")
                return None
        else:
            logger.error(f"Unexpected response format: {json.dumps(result, indent=2)}")
            return None

    except Exception as e:
        logger.error(f"Error in get_claude_summary: {str(e)}")
        return None

def get_linkedin_post(news_items):
    """Generate a LinkedIn-optimized post"""
    prompt = """Create a LinkedIn post version of these automotive news items that:
    - Uses a professional and engaging tone
    - Focuses on concrete facts and industry developments
    - Includes specific data points and insights
    - Avoids emojis in excess and maintains LinkedIn's professional aesthetic
    - Encourages meaningful engagement and sharing

    Output the result in **valid JSON format** with double quotes for all keys and string values, escaped special characters (e.g., newlines as \\n), and no additional comments or errors.

    Format the JSON exactly as:
    {
        "Text": "[Professional opening with insight]\\n\\n[2-3 paragraphs summarizing the news, emphasizing key data and developments]\\n\\nKEY INSIGHTS:\\n[2-3 bullet points]\\n\\n[Engaging question or call to action]\\n\\n[1-2 professional hashtags]",
        "Image": "[URL]",
        "Image Reasoning": "[Reasoning for the image choice focused on LinkedIn engagement]"
    }
    """

    content = f"{prompt}\n\nNews items:\n{_format_news_items(news_items)}"
    return get_claude_summary(content)



def get_x_post(news_items):
    """Generate tweets for X/Twitter"""
    prompt = """Create a thread of tweets summarizing these automotive news items where:
    - Each tweet must be under 280 characters, including spaces and hashtags
    - Focus only on concrete facts and developments
    - Avoid meta-references (e.g., "the report states" or "according to")
    - Ensure a professional and engaging tone
    - Each tweet must stand alone as a concise summary

    IMPORTANT: Output must be VALID JSON with properly escaped characters. All newlines must be \\n, not literal newlines.
    Format the JSON as a single line with escaped newlines, exactly like this example:
    [{"tweet": "First tweet content"}, {"tweet": "Second tweet content"}]

    The JSON must be parseable by Python's json.loads() function. Do not include any additional text or formatting.
    """

    content = f"{prompt}\n\nNews items:\n{_format_news_items(news_items)}"
    return get_claude_summary(content)

def get_instagram_post(news_items):
    """Generate an Instagram-optimized post"""
    prompt = """Create an Instagram post version of these automotive news items that:
    - Places ONE relevant emoji at the START of each news item line
    - Separates each news item with a line break
    - Includes a clear opening line with car emoji
    - Ends with a call-to-action line
    - Places category tags on final line

    IMPORTANT: Output must be VALID JSON with properly escaped characters. All newlines must be \\n, not literal newlines.
    Format the JSON as a single line with escaped newlines, exactly like this example:
    {"Text": "Opening line\\nFirst item\\nSecond item", "Image": "URL", "Hashtags": ["tag1", "tag2"]}

    The JSON must be parseable by Python's json.loads() function. Do not include any additional text or formatting.
    Make sure all emojis are properly encoded in the JSON string.
    """

    content = f"{prompt}\n\nNews items:\n{_format_news_items(news_items)}"
    return get_claude_summary(content)

def get_facebook_post(news_items):
    """Generate a Facebook-optimized post"""
    prompt = """Create a Facebook post version of these automotive news items that:
    - Uses a conversational but informative tone
    - Focuses on concrete facts and developments
    - Avoids meta-references
    - Includes specific numbers and data points

    IMPORTANT: Output must be VALID JSON with properly escaped characters. All newlines must be \\n, not literal newlines.
    Format the JSON as a single line with escaped newlines, exactly like this example:
    {"Text": "First line\\nSecond line\\nThird line", "Image": "URL", "Image Reasoning": "Reason"}

    The JSON must be parseable by Python's json.loads() function. Do not include any additional text or formatting.
    Make sure all emojis are properly encoded in the JSON string.
    """

    content = f"{prompt}\n\nNews items:\n{_format_news_items(news_items)}"
    return get_claude_summary(content)


def get_social_media_summaries(news_items):
    """
    Returns a dictionary containing formatted posts for each social platform
    """
    # Base prompt elements that apply to all platforms
    base_requirements = """
    For all versions:
    - Focus only on concrete facts and developments
    - Avoid meta-references (like "the report states" or "according to")
    - Include concrete numbers and data points where relevant
    """

    # Platform-specific prompts
    platform_prompts = {
        "linkedin": """Create a LinkedIn post version of these automotive news items.
        Format as:
        HEADER: [Professional header with 1-2 relevant emojis]
        MAIN TEXT: [3-4 professional paragraphs including key data points]
        KEY INSIGHTS: [3 bullet points focused on industry implications]
        HASHTAGS: [3-4 industry-specific hashtags]
        CALL TO ACTION: [Professional engagement prompt]
        RECOMMENDED IMAGE: [URL and business reasoning]""",

        "x": """Create an X (Twitter) post version of these automotive news items.
        Format as:
        MAIN TEXT: [Concise summary within 280 characters]
        THREAD: [2-3 follow-up tweets with key data points]
        HASHTAGS: [2-3 relevant hashtags integrated naturally]
        RECOMMENDED IMAGE: [URL and visibility reasoning]""",

        "facebook": """Create a Facebook post version of these automotive news items.
        Format as:
        HOOK: [Engaging opening line with emoji]
        MAIN TEXT: [2-3 conversational paragraphs with spacing]
        KEY POINTS: [2-3 bullet points with emojis]
        QUESTION: [Engagement question]
        HASHTAGS: [1-2 general hashtags]
        RECOMMENDED IMAGE: [URL and engagement reasoning]""",

        "instagram": """Create an Instagram post version of these automotive news items.
        Format as:
        FIRST LINE: [Strong attention-grabbing opening visible in feed]
        MAIN TEXT: [3-4 key points with emojis and spacing]
        CLOSING: [Engaging call to action]
        FIRST COMMENT: [Grouped hashtags - up to 30 relevant tags]
        RECOMMENDED IMAGE: [URL and visual impact reasoning]"""
    }

    # Format news items with their images
    formatted_items = "\n\n".join(
        f"Item {i + 1}:\nText: {item.text}\nImage: {item.image_url}"
        for i, item in enumerate(news_items)
    )

    # Generate summaries for each platform
    summaries = {}
    for platform, platform_prompt in platform_prompts.items():
        content = f"{platform_prompt}\n{base_requirements}\n\nNews items:\n{formatted_items}"
        summaries[platform] = get_claude_summary(content)

    return summaries