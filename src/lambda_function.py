import pandas as pd
import boto3
import time
import random
from urllib.parse import unquote_plus

s3_client = boto3.client("s3")
bedrock_client = boto3.client("bedrock-runtime",region_name="us-east-1")

def classify_tweet(tweet): 
  max_attempts = 3

  prompt = f"""
  You are classifying the suicide related risk in a tweet. Classify the tweet into one of these four categories: high risk, potentially likely, neutral, or unlikely. Return only the category and nothing else.

  Tweet: {tweet}
  """

  for attempt in range(max_attempts):
    try:
      time.sleep(0.1)
      response = bedrock_client.converse(modelId="amazon.nova-micro-v1:0", messages = [{ "role": "user", "content": [{"text": prompt}]}])

      output = response['output']['message']['content'][0]['text'].lower().strip()

      allowed_values = ["high risk", "potentially likely", "neutral", "unlikely"]
      alert_of_risk = None

      if output not in allowed_values: 
        return None, None 
   
      if output == "high risk" or output == "potentially likely": 
        alert_of_risk = 1
      elif output == "neutral" or output == "unlikely": 
        alert_of_risk = 0
      else: 
        alert_of_risk = None

      return alert_of_risk, output

    except Exception as error:
      print(f"Attempt {attempt + 1} failed: {error}")

      # Prevents program from waiting after final failed attempt
      if attempt < max_attempts - 1: 
        wait_time = (2 ** attempt) + random.uniform(0, 1)
        time.sleep(wait_time)

  return None, None

def lambda_handler(event, context):
  

  bucket_name = event["Records"][0]["s3"]["bucket"]["name"]
  object_key = unquote_plus(event["Records"][0]["s3"]["object"]["key"])
  response = s3_client.get_object(Bucket=bucket_name, Key=object_key)

  df = pd.read_csv(response["Body"])

  if 'Tweet' not in df.columns: 
    raise ValueError("Tweet column not found")

  if df.empty: 
    raise ValueError("Table is empty")

  row_count = len(df)

  if row_count < 100: 
    sample_df = df.sample(row_count)
  else: 
    sample_df = df.sample(n=100)

  classifications = []
  alerts = []

  for tweet in sample_df["Tweet"]: 
    tweet_alert_of_risk, tweet_output = classify_tweet(tweet)

    classifications.append(tweet_output)
    alerts.append(tweet_alert_of_risk)

    print(tweet_alert_of_risk, tweet_output)

  sample_df['suicide_likelihood'] = classifications 
  sample_df['alert_of_risk'] = alerts

  csv_output = sample_df.to_csv(index=False)

  s3_client.put_object( Bucket="tweet-risk-analysis-output-jenushan44", Key= "results.csv", Body = csv_output)