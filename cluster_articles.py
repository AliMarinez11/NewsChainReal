import psycopg2
import pandas as pd
import boto3
import os
from datetime import datetime
from sklearn.feature_extraction.text import TfidfVectorizer
import hdbscan

DB_PARAMS = {
    "host": "newschain-db.cr4wc8ma675y.us-east-2.rds.amazonaws.com",
    "database": "newschain",
    "user": "newschainadmin",
    "password": "Largemoney11$$",
    "sslmode": "verify-full",
    "sslrootcert": "/home/ec2-user/SageMaker/global-bundle.pem"
}
BUCKET_NAME = "newschain-bucket"
S3_CLIENT = boto3.client('s3')
custom_stop_words = ['the', 'and', 'did', 'is', 'said', 'reports', 'was', 'were', 'has', 'have']

def cluster_articles():
    print("Connecting to RDS and fetching articles...")
    conn = psycopg2.connect(**DB_PARAMS)
    query = "SELECT id, title, content, source, pub_date, topic FROM articles"
    df = pd.read_sql(query, conn)
    conn.close()
    print(f"Fetched {len(df)} articles from RDS.")

    print("Preprocessing article content...")
    df['content'] = df['content'].fillna('').str.lower()
    vectorizer = TfidfVectorizer(
        stop_words=custom_stop_words + ['english'],
        max_features=5000,
        min_df=2
    )
    X = vectorizer.fit_transform(df['content'])
    print(f"Vectorized {X.shape[0]} articles with {X.shape[1]} features.")

    print("Clustering with HDBSCAN...")
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=10,
        min_samples=5,
        cluster_selection_method='eom'
    )
    df['hdbscan_cluster'] = clusterer.fit_predict(X)
    n_clusters = len(df['hdbscan_cluster'].unique()) - (1 if -1 in df['hdbscan_cluster'].values else 0)
    print(f"Found {n_clusters} clusters (-1 is noise, {len(df[df['hdbscan_cluster'] == -1])} articles).")

    print("Saving results...")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    csv_file = f"clustered_articles_{timestamp}.csv"
    df[['id', 'title', 'source', 'pub_date', 'topic', 'hdbscan_cluster']].to_csv(csv_file, index=False)
    S3_CLIENT.upload_file(csv_file, BUCKET_NAME, csv_file)
    print(f"Uploaded {csv_file} to S3 bucket {BUCKET_NAME}")
    os.remove(csv_file)

    print("Sampling clusters for review...")
    for cluster_id in sorted(df['hdbscan_cluster'].unique()):
        if cluster_id != -1:
            cluster_size = len(df[df['hdbscan_cluster'] == cluster_id])
            print(f"\nCluster {cluster_id} ({cluster_size} articles):")
            sample = df[df['hdbscan_cluster'] == cluster_id][['title', 'source']].head(5)
            for _, row in sample.iterrows():
                print(f"  {row['title']} ({row['source']})")
        elif cluster_id == -1:
            print(f"\nNoise (-1) ({len(df[df['hdbscan_cluster'] == -1])} articles):")

    print("Clustering process completed.")

if __name__ == "__main__":
    cluster_articles()