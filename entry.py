import requests
from bs4 import BeautifulSoup
from requests_oauthlib import OAuth1Session
import google.generativeai as genai
import json
import schedule
import time
from datetime import datetime
import pytz
import os

# Configure Gemini
genai.configure()
model = genai.GenerativeModel("gemini-1.5-pro")


def get_nigeria_trends():
    url = "https://getdaytrends.com/nigeria/"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.content, "html.parser")
    trends = soup.find_all("tr")

    trend_list = []
    for trend in trends:
        name = trend.find("td", class_="main")
        if name and name.find("a"):
            trend_list.append(name.find("a").get_text(strip=True))

    return trend_list[:10]  # Return top 10 trends


def generate_tweet(trends):
    prompt = f"""
    You are a Twitter bot that creates catchy and controversial tweets based on current trends in Nigeria. Your goal is to attract comments and engage users in discussion. Here are the current top trends in Nigeria:

    {', '.join(trends)}

    Create a tweet that incorporates one or more of these trends. The tweet should be:
    1. Conversational or controversial
    2. Engaging and likely to provoke responses
    3. Relevant to Nigerian culture and current events
    4. No longer than 280 characters
    5. Include relevant hashtags when appropriate
    
    If including a poll, follow these additional rules:
    6. Each poll option must be 25 characters or less
    7. Provide 2 to 4 poll options

    Format your response as a JSON object with the following structure:
    {{
        "text": "The tweet content without hashtags",
        "hashtags": ["list", "of", "hashtags"],
        "poll_options": ["Option 1", "Option 2", "Option 3", "Option 4"] (optional)
    }}
    
    Important: Return ONLY the JSON object, without any additional text, formatting, or code block indicators.
    """

    response = model.generate_content(prompt)
    return response.text


def create_tweet_payload(tweet_data):
    payload = {"text": tweet_data["text"]}

    if tweet_data.get("hashtags"):
        payload["text"] += " " + " ".join(f"#{tag}" for tag in tweet_data["hashtags"])

    if tweet_data.get("media_description"):
        payload["media"] = {"media_ids": ["PLACEHOLDER_MEDIA_ID"]}

    if tweet_data.get("poll_options"):
        payload["poll"] = {
            "options": tweet_data["poll_options"][:4],
            "duration_minutes": 1440,
        }

    return payload


def post_tweet(payload):
    twitter = OAuth1Session(
        os.environ.get("TWITTER_CONSUMER_KEY"),
        os.environ.get("TWITTER_CONSUMER_SECRET"),
        os.environ.get("TWITTER_ACCESS_TOKEN"),
        os.environ.get("TWITTER_ACCESS_TOKEN_SECRET")
    )

    response = twitter.post("https://api.twitter.com/2/tweets", json=payload)

    if response.status_code in (200, 201):
        print("Tweet posted successfully:")
        print(response.json())
    else:
        print(f"Error posting tweet: {response.status_code} - {response.text}")


def post_scheduled_tweet():
    trends = get_nigeria_trends()
    tweet_data_str = generate_tweet(trends)
    try:
        tweet_data = json.loads(tweet_data_str)
        payload = create_tweet_payload(tweet_data)
        post_tweet(payload)
    except json.JSONDecodeError:
        pass


def is_active_hours():
    nigeria_tz = pytz.timezone("Africa/Lagos")
    current_time = datetime.now(nigeria_tz)
    return 9 <= current_time.hour < 23


def schedule_tweets():
    print("Scheduling tweets...")
    # Schedule tweets during active hours (9 AM to 11 PM Nigerian time)
    schedule.every(30).minutes.do(
        lambda: post_scheduled_tweet() if is_active_hours() else None
    )

    # Schedule less frequent tweets during non-active hours
    schedule.every(2).hours.do(
        lambda: post_scheduled_tweet() if not is_active_hours() else None
    )


def main():
    schedule_tweets()

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
