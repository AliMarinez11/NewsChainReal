from flask import Flask, jsonify, request
import pandas as pd
import psycopg2
import boto3
import os
from datetime import datetime

app = Flask(__name__, static_folder='frontend/greenlight', static_url_path='/')

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

def get_latest_csv():
    response = S3_CLIENT.list_objects_v2(Bucket=BUCKET_NAME, Prefix="clustered_articles_")
    files = sorted([obj['Key'] for obj in response.get('Contents', [])], key=lambda x: x[-12:-4], reverse=True)
    return files[0] if files else None

@app.route('/')
def index():
    return app.send_static_file('index.html')

@app.route('/clusters', methods=['GET'])
def get_clusters():
    latest_csv = get_latest_csv()
    if not latest_csv:
        return jsonify({"error": "No clustered articles found"}), 404
    
    local_file = "temp_clustered_articles.csv"
    S3_CLIENT.download_file(BUCKET_NAME, latest_csv, local_file)
    df = pd.read_csv(local_file)
    os.remove(local_file)
    
    clusters = df.groupby('hdbscan_cluster').apply(
        lambda x: {
            'cluster_id': int(x['hdbscan_cluster'].iloc[0]),
            'size': len(x),
            'sample': x[['title', 'source', 'pub_date', 'topic']].head(5).to_dict('records')
        }
    ).tolist()
    
    return jsonify([c for c in clusters if c['cluster_id'] != -1])

@app.route('/validate', methods=['POST'])
def validate_cluster():
    data = request.json
    cluster_id = data['cluster_id']
    is_valid = data['is_valid']
    status = "valid" if is_valid else "invalid"
    
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    
    latest_csv = get_latest_csv()
    local_file = "temp_clustered_articles.csv"
    S3_CLIENT.download_file(BUCKET_NAME, latest_csv, local_file)
    df = pd.read_csv(local_file)
    os.remove(local_file)
    
    cluster_ids = df[df['hdbscan_cluster'] == cluster_id]['id'].tolist()
    cur.execute(
        "UPDATE articles SET status = %s WHERE id IN %s",
        (status, tuple(cluster_ids))
    )
    
    conn.commit()
    cur.close()
    conn.close()
    
    if is_valid:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        S3_CLIENT.put_object(Bucket=BUCKET_NAME, Key=f"greenlight_complete_{timestamp}.txt", Body="Greenlight completed")
    
    return jsonify({"status": "success"})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)