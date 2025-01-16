import json
import boto3

def _format_news_items(news_items):
    """Helper function to format news items consistently"""
    return "\n\n".join(
        f"Item {i + 1}:\nText: {item['text']}\nImage: {item['image_url']}"
        for i, item in enumerate(news_items)
    )

def get_claude_summary(content: str):
    # Initialize Bedrock runtime client
    session = boto3.Session(profile_name="tradesales")
    client = session.client("bedrock-runtime", region_name="eu-west-2")

    payload = {
        "anthropic_version": "bedrock-2023-05-31",  # Required field
        "max_tokens": 1000,
        "messages": [
            {
                "role": "user",
                "content": content  # Ensure this is a single string
            }
        ]
    }

    # Send the request
    try:
        response = client.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            contentType="application/json",
            accept="application/json",
            body=json.dumps(payload)
        )

        # Parse the response
        result = json.loads(response["body"].read().decode("utf-8"))

        # Extract the summary text from the response content
        if "content" in result and isinstance(result["content"], list):
            summary = "".join(
                item.get("text", "") for item in result["content"] if item["type"] == "text"
            )
            return summary.strip()
        else:
            return "No summary text found in the response."

    except Exception as e:
        print(f"Error invoking model: {e}")
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
    """Generate a structured thread of tweets summarizing news items."""
    prompt = """Create a thread of tweets summarizing these automotive news items where:
    - Each tweet must be under 280 characters, including spaces and hashtags.
    - Focus only on concrete facts and developments.
    - Avoid meta-references (e.g., "the report states" or "according to").
    - Ensure a professional and engaging tone, avoiding casual phrases like "Let me know if you need any other details."
    - Each tweet must stand alone as a concise summary.

    Format the output as an array of JSON objects, where each object contains:
    {{
      "tweet": "[Tweet content]"
    }}

    Use this format strictly:
    [
      {{"tweet": "First tweet content here."}},
      {{"tweet": "Second tweet content here."}},
      {{"tweet": "Third tweet content here."}},
      ...
    ]

    Summarize the news items as follows:
    - Highlight major announcements or launches (e.g., new car models, EV updates).
    - Emphasize key data points (e.g., range, performance, pricing).
    - Include up to 2 relevant hashtags in each tweet, integrated naturally.

    Here are the news items:
    {}

    Output strictly as an array of JSON objects with no additional text or explanations."""

    # Format news items
    content = f"{prompt}\n\nNews items:\n{_format_news_items(news_items)}"

    # Call Claude summarization
    return get_claude_summary(content)



def get_facebook_post(news_items):
    """Generate a Facebook-optimized post"""
    prompt = """Create a Facebook post version of these automotive news items that:
    - Uses a conversational but informative tone
    - Focuses on concrete facts and developments
    - Avoids meta-references
    - Includes specific numbers and data points

    Output the result in **valid JSON format** with double quotes for all keys and string values, escaped special characters (e.g., newlines as \\n), and no additional comments or errors.

    Format the JSON exactly as:
    {
        "Text": "[Engaging opening line with emoji]\\n\\n[2-3 conversational paragraphs with spacing]\\n\\nKEY POINTS:\\n[2-3 bullet points with emojis]\\n\\n[Engagement question]\\n\\n[1-2 general hashtags]",
        "Image": "[URL]",
        "Image Reasoning": "[Engagement reasoning for Image]"
    }
    """

    content = f"{prompt}\n\nNews items:\n{_format_news_items(news_items)}"
    return get_claude_summary(content)


def get_instagram_post(news_items):
    """Generate an Instagram-optimized post"""
    prompt = """Create an Instagram post version of these automotive news items that:
   - Begins with an attention-grabbing first line that's visible in feed
   - Focuses on concrete facts and developments
   - Uses emojis effectively
   - Avoids meta-references

   Format exactly as:
   FIRST LINE: [Strong attention-grabbing opening]

   MAIN TEXT:
   [3-4 key points with emojis and spacing between each]

   CLOSING: [Engaging call to action]

   FIRST COMMENT:
   [Up to 30 relevant hashtags grouped by theme]

   RECOMMENDED IMAGE: [URL and visual impact reasoning]"""

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
        f"Item {i + 1}:\nText: {item['text']}\nImage: {item['image_url']}"
        for i, item in enumerate(news_items)
    )

    # Generate summaries for each platform
    summaries = {}
    for platform, platform_prompt in platform_prompts.items():
        content = f"{platform_prompt}\n{base_requirements}\n\nNews items:\n{formatted_items}"
        summaries[platform] = get_claude_summary(content)

    return summaries