import pandas as pd
import boto3
import time

df = pd.read_csv("../data/Suicide_Ideation_Dataset(Twitter-based).csv")

bedrock_client = boto3.client("bedrock-runtime",region_name="us-east-1")

if 'Tweet' not in df.columns: 
  raise ValueError("Tweet column not found")

if df.empty: 
  raise ValueError("Table is empty")

row_count = len(df)

if row_count < 100: 
  # Randomly selects rows from the dataset without duplicates
  sample_df = df.sample(row_count)
else: 
  sample_df = df.sample(n=100)


def classify_tweet(tweet): 
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

  # Sends the prompt to the Nova Micro model through Amazon Bedrock
  response = bedrock_client.converse(
    modelId="amazon.nova-micro-v1:0",
    messages = [{ "role": "user", "content": [{"text": prompt}]}]
  )

  # Takes the classification text from Bedrock and clean its formatting
  output = response['output']['message']['content'][0]['text'].lower().strip().strip(".!?,/;:")

  valid_output = False 
  allowed_values = ["high risk", "potentially likely", "neutral", "unlikely"]
  alert_of_risk = None

  if output in allowed_values: 
    valid_output = True 

  if output == "high risk" or output == "potentially likely": 
    alert_of_risk = 1
  elif output == "neutral" or output == "unlikely": 
    alert_of_risk = 0
  else: 
    alert_of_risk = None

  return valid_output, alert_of_risk, output


classifications = []
alerts = []

for tweet in sample_df["Tweet"]: 
  tweet_valid_output, tweet_alert_of_risk, tweet_output = classify_tweet(tweet)

  classifications.append(tweet_output)
  alerts.append(tweet_alert_of_risk)

  
  print(tweet_valid_output, tweet_alert_of_risk, tweet_output)

  # Waits 0.1 seconds between the rquests to limit the Bedrock calls to 10 tweets per second
  time.sleep(0.1)

sample_df['suicide_likelihood'] = classifications 
sample_df['alert_of_risk'] = alerts

sample_df.to_csv("results.csv", index=False)

