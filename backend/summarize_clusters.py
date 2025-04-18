import psycopg2
import boto3
import requests
import json
from datetime import datetime

DB_PARAMS = {
    "host": "newschain-db.cr4wc8ma675y.us-east-2.rds.amazonaws.com",
    "database": "newschain",
    "user": "newschainadmin",
    "password": "Largemoney11$$",
    "sslmode": "verify-full",
    "sslrootcert": "global-bundle.pem"
}
BUCKET_NAME = "newschain-bucket"
S3_CLIENT = boto3.client('s3')
XAI_API_URL = "https://api.x.ai/v1/completions"
XAI_API_KEY = "xai-sw099z6S2UmYxqv8uWMQGpXM8nn8TKhTWXC6NfHFRJFgTBqNjOCiWBxravDvBBJ7Si6PZ2rRGgazkfs8"

PROMPT = """
Grok, you are provided with a cluster of news articles, each including the following fields: id, title, content, source, url. The sources vary in bias—some are left-leaning (e.g., CNN, HuffPost), some are right-leaning (e.g., Fox News, Daily Caller), and some are neutral (e.g., BBC, Reuters). Your task is to analyze these articles and X (Twitter) sentiment to produce the following:

1. **Title**: A concise, neutral title summarizing the core story (5 words maximum).
2. **Neutral Summary**: Review all articles in the cluster and provide a 100-150 word summary of the story that is as neutral and unbiased as possible, focusing on factual overlap and key events across all sources.
3. **Left-Leaning Angle**: Based solely on the content and framing of articles from left-leaning sources (e.g., CNN, HuffPost) within the cluster, provide a 40 word maximum angle reflecting how these sources portray the story. Incorporate relevant X sentiment from left-leaning users or posts aligning with this perspective, if available.
4. **Right-Leaning Angle**: Based solely on the content and framing of articles from right-leaning sources (e.g., Fox News, Daily Caller) within the cluster, provide a 40 word maximum angle reflecting how these sources portray the story. Incorporate relevant X sentiment from right-leaning users or posts aligning with this perspective, if available.
5. **Left Reasonableness Score**: On a scale from 0 (illogical, contradicts verifiable facts in articles or X sentiment) to 1 (logically consistent, fully supported by evidence), score the left-leaning angle’s adherence to facts and logical coherence.
6. **Right Reasonableness Score**: On a scale from 0 (illogical, contradicts evidence) to 1 (logically consistent, supported), score the right-leaning angle’s adherence to facts and logical coherence.
7. **Reasonableness Reason**: In 15 words max, explain both scores, citing specific evidence or contradictions in articles/X sentiment.

Input: JSON array of articles [{id, title, content, source, url}, ...]
Output: JSON {title, summary, left_angle, right_angle, left_reasonableness_score, right_reasonableness_score, reasonableness_reason}
"""

def lambda_handler(event, context):
    print("Processing S3 event:", json.dumps(event))
    for record in event['Records']:
        bucket = record['s3']['bucket']['name']
        key = record['s3']['object']['key']
        # Get S3 object content
        response = S3_CLIENT.get_object(Bucket=bucket, Key=key)
        body = json.loads(response['Body'].read().decode('utf-8'))
        execution_id = body['execution_id']
        cluster_id = body['cluster_id']
        print(f"Summarizing cluster {cluster_id} for execution_id {execution_id}")
        # Connect to RDS
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()
        # Verify cluster is greenlit
        cur.execute("""
            SELECT status FROM cluster_status
            WHERE execution_id = %s AND hdbscan_cluster = %s
        """, (execution_id, cluster_id))
        status = cur.fetchone()
        if not status or status[0] != True:
            print(f"Cluster {cluster_id} for {execution_id} is not greenlit. Skipping.")
            cur.close()
            conn.close()
            continue
        # Fetch articles for the cluster
        cur.execute("""
            SELECT id, title, content, source, url
            FROM articles
            WHERE execution_id = %s AND hdbscan_cluster = %s
        """, (execution_id, cluster_id))
        articles = [
            {"id": row[0], "title": row[1], "content": row[2], "source": row[3], "url": row[4]}
            for row in cur.fetchall()
        ]
        if not articles:
            print(f"No articles found for cluster {cluster_id} in {execution_id}")
            cur.close()
            conn.close()
            continue
        # Call xAI Grok API
        payload = {
            "model": "grok-3-beta",
            "prompt": PROMPT + "\n\nInput: " + json.dumps({"articles": articles}),
            "max_tokens": 1000,
            "temperature": 0.7
        }
        headers = {"Authorization": f"Bearer {XAI_API_KEY}", "Content-Type": "application/json"}
        response = requests.post(XAI_API_URL, json=payload, headers=headers)
        if response.status_code == 200:
            result = response.json()
            grok_response = json.loads(result['choices'][0]['text'].strip('```json\n').strip('\n```'))
            articles_json = json.dumps([
                {"id": a["id"], "url": a["url"], "source": a["source"]}
                for a in articles
            ])
            # Insert into pending_narratives
            cur.execute("""
                INSERT INTO pending_narratives (
                    cluster_id, title, summary, left_angle, right_angle, articles, 
                    date_added, execution_id, left_reasonableness_score, right_reasonableness_score, reasonableness_reason
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                cluster_id,
                grok_response.get("title"),
                grok_response.get("summary"),
                grok_response.get("left_angle"),
                grok_response.get("right_angle"),
                articles_json,
                datetime.utcnow(),
                execution_id,
                grok_response.get("left_reasonableness_score"),
                grok_response.get("right_reasonableness_score"),
                grok_response.get("reasonableness_reason")
            ))
            print(f"Inserted narrative for cluster {cluster_id} in {execution_id}")
        else:
            print(f"Error summarizing cluster {cluster_id}: {response.text}")
        conn.commit()
        cur.close()
        conn.close()
    return {"statusCode": 200, "body": "Summarization completed"}