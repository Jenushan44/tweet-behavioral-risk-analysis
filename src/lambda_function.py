import pandas as pd
import boto3
import time
import random
from urllib.parse import unquote_plus

# Creates an s3 client to interact with Amazon S3
s3_client = boto3.client("s3")
# Creates a bedrock client to interact with bedrock
bedrock_client = boto3.client("bedrock-runtime",region_name="us-east-1")

def classify_tweet(tweet): 
  # Gives bedrock 3 chances to classify the given tweet
  max_attempts = 3

  prompt = f"""
  You are classifying the suicide related risk in a tweet. Classify the tweet into one of these four categories:
  - high risk: The tweet clearly shows suicidal thoughts, the intent to die or self-harm.
  - potentially likely: The tweet shows that there are signs of possible suicidal thinking or serious negative feelings but does not show clear intent to die or self-harm.
  - neutral: The tweet can mention negative emotions, death or difficult situations but there is not enough evidence to determine suicide-related risk.
  - unlikely: The tweet does not show any suicide-related risk and is not related to suicidal thoughts or self-harm.

  Only use the text of the tweet to make the classification and do not assume information outside of what is written in the tweet.

  Return only one of these exact values: high risk, potentially likely, neutral, unlikely
  
  Tweet: {tweet}
  """

  for attempt in range(max_attempts):
    try:
      # Limit the bedrock requests to 10 tweets per second
      time.sleep(0.1)
      response = bedrock_client.converse(modelId="amazon.nova-micro-v1:0", messages = [{ "role": "user", "content": [{"text": prompt}]}])

      # Cleans the output to keep comparisons consistent
      output = response['output']['message']['content'][0]['text'].lower().strip().strip(".!?,/;:")

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
        # Increase the retry delay and add randomness to avoid repeating requests at the same time
        wait_time = (2 ** attempt) + random.uniform(0, 1)
        time.sleep(wait_time)

  return None, None

# event provides information about the S3 trigger such as the bucket name, file name, and event type
def lambda_handler(event, context):
  
  # Get the name of the S3 bucket that triggered the Lambda function
  bucket_name = event["Records"][0]["s3"]["bucket"]["name"]
  # Get the uploaded file name from the S3 event
  object_key = unquote_plus(event["Records"][0]["s3"]["object"]["key"])

  #Fetch the uploaded csv from the S3 bucket
  response = s3_client.get_object(Bucket=bucket_name, Key=object_key)

  df = pd.read_csv(response["Body"])

  if 'Tweet' not in df.columns: 
    raise ValueError("Tweet column not found")

  if df.empty: 
    raise ValueError("Table is empty")

  # Randomly select up to 100 tweets to analyze
  row_count = len(df)

  if row_count < 100: 
    sample_df = df.sample(row_count)
  else: 
    sample_df = df.sample(n=100)

  # Stores the sucide risk classification for each tweet
  classifications = []

  # Stores the alert value for each tweet
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