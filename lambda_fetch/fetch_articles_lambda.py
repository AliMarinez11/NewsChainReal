import requests
import psycopg2
import boto3
import os
from datetime import datetime

API_KEY = "pub_7691435441162e0d6b5e8f7091560b691adde"
BASE_URL = "https://newsdata.io/api/1/latest"
SOURCES = [
    "www.foxnews.com", "nypost.com", "www.breitbart.com", "edition.cnn.com",
    "www.msnbc.com", "www.newsweek.com", "www.bbc.com", "www.huffpost.com",
    "www.reuters.com", "nytimes.com", "washingtonpost.com", "dailycaller.com",
    "washingtontimes.com"
]
TOPICS = ["politics", "world"]

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

def fetch_articles(domain, topic):
    print(f"Fetching {topic} articles for domain: {domain}")
    articles = []
    page = None
    while True:
        params = {
            "apikey": API_KEY,
            "category": topic,
            "domainurl": domain,
            "language": "en",
            "size": 50,
            "full_content": 1
        }
        if page:
            params["page"] = page

        response = requests.get(BASE_URL, params=params)
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            break

        data = response.json()
        if data.get("status") != "success":
            print(f"API error: {data.get('message')}")
            break

        batch_articles = data.get("results", [])
        articles.extend(batch_articles)
        print(f"Fetched {len(batch_articles)} articles, total so far: {len(articles)}")
        
        next_page = data.get("nextPage")
        if not next_page or len(batch_articles) < 50:
            break
        page = next_page

    return articles

def store_articles(articles):
    print("Storing articles in RDS...")
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    
    for article in articles:
        article_id = article.get("article_id") or "unknown_" + str(hash(article.get("title", "no_title")))
        cur.execute("""
            INSERT INTO articles (id, title, content, url, source, pub_date, topic, description)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO NOTHING
        """, (
            article_id,
            article.get("title", "Untitled"),
            article.get("content"),
            article.get("link", "http://example.com"),
            article.get("source_id"),
            article.get("pubDate"),
            article.get("category", ["unknown"])[0],
            article.get("description")
        ))
    
    conn.commit()
    cur.close()
    conn.close()
    print(f"Stored {len(articles)} articles in RDS.")

def lambda_handler(event, context):
    print("Starting fetch process...")
    all_articles = []
    for topic in TOPICS:
        for domain in SOURCES:
            batch_articles = fetch_articles(domain, topic)
            all_articles.extend(batch_articles)
    
    if all_articles:
        unique_articles = {article["article_id"]: article for article in all_articles if article.get("article_id")}.values()
        unique_articles = list(unique_articles)
        print(f"Kept {len(unique_articles)} unique articles after deduplication.")
        
        store_articles(unique_articles)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        signal_file = f"fetch_complete_{timestamp}.txt"
        S3_CLIENT.put_object(Bucket=BUCKET_NAME, Key=signal_file, Body="Fetch completed")
        print(f"Uploaded {signal_file} to S3.")
    else:
        print("No articles fetched.")
    print("Fetch process completed.")
    return {"statusCode": 200, "body": "Fetch completed"}