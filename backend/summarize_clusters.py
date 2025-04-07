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
XAI_API_URL = "https://api.x.ai/v1/chat/completions"
XAI_API_KEY = "xai-sw099z6S2UmYxqv8uWMQGpXM8nn8TKhTWXC6NfHFRJFgTBqNjOCiWBxravDvBBJ7Si6PZ2rRGgazkfs8"

PROMPT = """
Grok, you are provided with a cluster of news articles, each including the following fields: id, title, content, source, url. The sources vary in bias—some are left-leaning (e.g., CNN, HuffPost), some are right-leaning (e.g., Fox News, Daily Caller), and some are neutral (e.g., BBC, Reuters). Your task is to analyze these articles and X (Twitter) sentiment to produce the following:

1. **Title**: A concise, neutral title summarizing the core story (5 words maximum).
2. **Neutral Summary**: Review all articles in the cluster and provide a 100-150 word summary of the story that is as neutral and unbiased as possible, focusing on factual overlap and key events across all sources.
3. **Left-Leaning Angle**: Based solely on the content and framing of articles from left-leaning sources (e.g., CNN, HuffPost) within the cluster, provide a 40 word maximum angle reflecting how these sources portray the story. Incorporate relevant X sentiment from left-leaning users or posts aligning with this perspective, if available.
4. **Right-Leaning Angle**: Based solely on the content and framing of articles from right-leaning sources (e.g., Fox News, Daily Caller) within the cluster, provide a 40 word maximum angle reflecting how these sources portray the story. Incorporate relevant X sentiment from right-leaning users or posts aligning with this perspective, if available.
5. **Reasonableness Score**: On a scale from -1 (left-leaning angle is unreasonable) to 0 (both angles are reasonable) to 1 (right-leaning angle is unreasonable), score which angle aligns more closely with the factual content of all articles and X sentiment. Unreasonable means the angle distorts facts or sounds "crazy" relative to the evidence.
6. **Reasonableness Reason**: Provide a 15-word max explanation for the reasonableness score, justifying the assessment.

Input: JSON array of articles [{id, title, content, source, url}, ...]
Output: JSON {title, summary, left_angle, right_angle, reasonableness_score, reasonableness_reason}
"""

def lambda_handler(event, context):
    print("Fetching valid clusters from RDS...")
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    
    cur.execute("SELECT hdbscan_cluster, array_agg(id) as ids, array_agg(url) as urls, array_agg(source) as sources FROM articles WHERE status='valid' GROUP BY hdbscan_cluster")
    clusters = cur.fetchall()
    
    for cluster_id, ids, urls, sources in clusters:
        cur.execute("SELECT content FROM articles WHERE hdbscan_cluster = %s AND status='valid'", (cluster_id,))
        contents = [row[0] for row in cur.fetchall()]
        
        articles = [{"id": id, "content": content, "url": url, "source": source} for id, content, url, source in zip(ids, contents, urls, sources)]
        payload = {
            "model": "grok-2-latest",
            "messages": [
                {"role": "system", "content": PROMPT},
                {"role": "user", "content": json.dumps({"articles": articles})}
            ]
        }
        
        headers = {"Authorization": f"Bearer {XAI_API_KEY}", "Content-Type": "application/json"}
        response = requests.post(XAI_API_URL, json=payload, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            grok_response = json.loads(result['choices'][0]['message']['content'].strip('```json\n').strip('\n```'))
            articles_json = json.dumps([{"id": id, "url": url, "source": source} for id, url, source in zip(ids, urls, sources)])
            cur.execute("""
                INSERT INTO narratives (cluster_id, title, summary, left_angle, right_angle, articles, date_added)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                cluster_id,
                grok_response.get("title"),
                grok_response.get("summary"),
                grok_response.get("left_angle"),
                grok_response.get("right_angle"),
                articles_json,
                datetime.utcnow()
            ))
        else:
            print(f"Error summarizing cluster {cluster_id}: {response.text}")
    
    conn.commit()
    cur.close()
    conn.close()
    print("Summarization completed.")
    return {"statusCode": 200, "body": "Summarization completed"}