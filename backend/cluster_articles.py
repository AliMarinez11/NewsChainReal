import os
import pandas as pd
import psycopg2
import boto3
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
import hdbscan

# Database connection parameters
DB_PARAMS = {
    "host": "newschain-db.cr4wc8ma675y.us-east-2.rds.amazonaws.com",
    "database": "newschain",
    "user": "newschainadmin",
    "password": "Largemoney11$$",
    "sslmode": "verify-full",
    "sslrootcert": "/app/global-bundle.pem"
}

BUCKET_NAME = "newschain-bucket"
S3_CLIENT = boto3.client('s3')

def cluster_articles():
    # Get execution_id from environment variable
    execution_id = os.getenv('EXECUTION_ID')
    if not execution_id:
        raise ValueError("EXECUTION_ID environment variable not set")

    # Connect to RDS
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()

    # Fetch articles (e.g., all articles or those not yet clustered)
    cur.execute("SELECT id, title, content FROM articles WHERE execution_id IS NULL")
    articles = cur.fetchall()
    print(f"Fetched {len(articles)} articles from RDS.")

    if not articles:
        print("No articles to cluster.")
        cur.close()
        conn.close()
        return

    # Prepare data for clustering
    article_ids = [row[0] for row in articles]
    texts = [row[1] + " " + (row[2] or "") for row in articles]  # Combine title and content

    # Vectorize texts using TF-IDF
    vectorizer = TfidfVectorizer(max_df=0.8, min_df=2, stop_words='english')
    X = vectorizer.fit_transform(texts)
    print(f"Vectorized {len(articles)} articles with {X.shape[1]} features.")

    # Cluster using HDBSCAN
    clusterer = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=1)
    labels = clusterer.fit_predict(X)
    print(f"Found {len(set(labels)) - (1 if -1 in labels else 0)} clusters (-1 is noise, {list(labels).count(-1)} articles).")

    # Update articles with cluster labels and execution_id
    for article_id, label in zip(article_ids, labels):
        cur.execute(
            "UPDATE articles SET hdbscan_cluster = %s, execution_id = %s WHERE id = %s",
            (label, execution_id, article_id)
        )

    # Insert clusters into cluster_status
    unique_clusters = set(labels)
    for cluster in unique_clusters:
        cur.execute(
            "INSERT INTO cluster_status (execution_id, hdbscan_cluster, status, reviewed_at, summarized, updated_by) "
            "VALUES (%s, %s, NULL, NULL, FALSE, 'system')",
            (execution_id, cluster)
        )

    conn.commit()

    # Write clustered articles to S3
    cur.execute("SELECT id, title, content, hdbscan_cluster FROM articles WHERE execution_id = %s", (execution_id,))
    clustered_articles = cur.fetchall()
    df = pd.DataFrame(clustered_articles, columns=['id', 'title', 'content', 'hdbscan_cluster'])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = f"clustered_articles_{timestamp}.csv"
    df.to_csv(csv_file, index=False)
    S3_CLIENT.upload_file(csv_file, BUCKET_NAME, f"clustered_articles_output/{csv_file}")
    print(f"Uploaded {csv_file} to S3 bucket {BUCKET_NAME}")
    os.remove(csv_file)

    cur.close()
    conn.close()

if __name__ == "__main__":
    cluster_articles()