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
XAI_API_URL = "https://api.xai.com/summarize"  # Placeholder—update with real URL
XAI_API_KEY = "your_xai_api_key"  # Replace with your key

def lambda_handler(event, context):
    print("Fetching valid clusters from RDS...")
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    
    cur.execute("SELECT hdbscan_cluster, array_agg(id) as ids, array_agg(url) as urls, array_agg(source) as sources FROM articles WHERE status='valid' GROUP BY hdbscan_cluster")
    clusters = cur.fetchall()
    
    for cluster_id, ids, urls, sources in clusters:
        cur.execute("SELECT content FROM articles WHERE hdbscan_cluster = %s AND status='valid'", (cluster_id,))
        contents = [row[0] for row in cur.fetchall()]
        
        payload = {
            "articles": [{"id": id, "content": content, "url": url, "source": source} for id, content, url, source in zip(ids, contents, urls, sources)]
        }
        
        headers = {"Authorization": f"Bearer {XAI_API_KEY}", "Content-Type": "application/json"}
        response = requests.post(XAI_API_URL, json=payload, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            articles_json = json.dumps([{"id": id, "url": url, "source": source} for id, url, source in zip(ids, urls, sources)])
            cur.execute("""
                INSERT INTO narratives (cluster_id, title, summary, left_angle, right_angle, articles, date_added)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                cluster_id,
                result.get("title"),
                result.get("summary"),
                result.get("left_angle"),
                result.get("right_angle"),
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