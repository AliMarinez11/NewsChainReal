import os
import pandas as pd
import psycopg2
import boto3
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
import hdbscan
import argparse
import numpy as np

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

def cluster_articles(execution_id):
    print(f"Starting clustering with execution_id: {execution_id}")
    # Connect to RDS
    print("Connecting to RDS...")
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    print("Connected to RDS.")

    # Fetch all articles
    print("Fetching all articles from RDS...")
    cur.execute("SELECT id, title, content FROM articles")
    articles = cur.fetchall()
    print(f"Fetched {len(articles)} articles from RDS.")

    if not articles:
        print("No articles to cluster.")
        cur.close()
        conn.close()
        return

    # Prepare data for clustering
    print("Preparing data...")
    article_ids = [row[0] for row in articles]
    texts = [row[1] + " " + (row[2] or "") for row in articles]
    print("Data prepared.")

    # Vectorize texts using TF-IDF
    print("Vectorizing texts...")
    vectorizer = TfidfVectorizer(max_df=0.8, min_df=2, stop_words='english')
    X = vectorizer.fit_transform(texts)
    print(f"Vectorized {len(articles)} articles with {X.shape[1]} features.")

    # Cluster using HDBSCAN
    print("Clustering with HDBSCAN...")
    clusterer = hdbscan.HDBSCAN(min_cluster_size=5, min_samples=1)
    labels = clusterer.fit_predict(X).tolist()
    print(f"Found {len(set(labels)) - (1 if -1 in labels else 0)} clusters (-1 is noise, {list(labels).count(-1)} articles).")

    # Update articles with cluster labels and execution_id
    print("Updating articles...")
    for article_id, label in zip(article_ids, labels):
        cluster_value = label if label != -1 else None
        cur.execute(
            "UPDATE articles SET hdbscan_cluster = %s, execution_id = %s WHERE id = %s",
            (cluster_value, execution_id, article_id)
        )

    # Clear previous cluster_status for this execution_id
    print("Clearing previous cluster_status...")
    cur.execute("DELETE FROM cluster_status WHERE execution_id = %s", (execution_id,))

    # Insert new clusters into cluster_status
    print("Inserting new clusters...")
    unique_clusters = set(label for label in labels if label != -1)
    for cluster in unique_clusters:
        cur.execute(
            "INSERT INTO cluster_status (execution_id, hdbscan_cluster, status, reviewed_at, summarized, updated_by) "
            "VALUES (%s, %s, NULL, NULL, FALSE, 'system')",
            (execution_id, cluster)
        )

    print("Committing changes...")
    conn.commit()

    # Write clustered articles to S3
    print("Writing to S3...")
    cur.execute("SELECT id, title, content, hdbscan_cluster FROM articles WHERE execution_id = %s", (execution_id,))
    clustered_articles = cur.fetchall()
    df = pd.DataFrame(clustered_articles, columns=['id', 'title', 'content', 'hdbscan_cluster'])
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_file = f"clustered_articles_{timestamp}.csv"
    df.to_csv(csv_file, index=False)
    S3_CLIENT.upload_file(csv_file, BUCKET_NAME, f"clustered_articles_output/{csv_file}")
    print(f"Uploaded {csv_file} to S3 bucket {BUCKET_NAME}")
    os.remove(csv_file)

    print("Closing connection...")
    cur.close()
    conn.close()
    print("Clustering completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cluster articles using HDBSCAN")
    parser.add_argument("--execution-id", required=True, help="SageMaker pipeline execution ARN")
    args = parser.parse_args()
    cluster_articles(args.execution_id)