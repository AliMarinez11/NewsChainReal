from flask import Flask, jsonify, request
import psycopg2
import boto3
from datetime import datetime

app = Flask(__name__, static_folder="frontend/greenlight", static_url_path="/")

DB_PARAMS = {
    "host": "newschain-db.cr4wc8ma675y.us-east-2.rds.amazonaws.com",
    "database": "newschain",
    "user": "newschainadmin",
    "password": "Largemoney11$$",
    "sslmode": "verify-full",
    "sslrootcert": "global-bundle.pem"
}
BUCKET_NAME = "newschain-bucket"
S3_CLIENT = boto3.client("s3")

def get_db_connection():
    try:
        return psycopg2.connect(**DB_PARAMS)
    except psycopg2.Error as e:
        app.logger.error("Database connection failed: {}".format(e))
        raise

@app.route("/")
def index():
    return app.send_static_file("index.html")

@app.route("/executions", methods=["GET"])
def get_executions():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT execution_id FROM articles ORDER BY execution_id DESC")
        executions = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return jsonify(executions)
    except Exception as e:
        app.logger.error("Error fetching executions: {}".format(e))
        return jsonify({"error": "Failed to fetch executions"}), 500

@app.route("/clusters", methods=["GET"])
def get_clusters():
    execution_id = request.args.get("execution_id")
    if not execution_id:
        return jsonify({"error": "execution_id is required"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Fetch clusters and articles for the given execution_id, including only title and source
        cur.execute("""
            SELECT a.hdbscan_cluster, a.title, a.source
            FROM articles a
            WHERE a.execution_id = %s AND a.hdbscan_cluster != -1
            ORDER BY a.hdbscan_cluster
        """, (execution_id,))
        articles = cur.fetchall()

        # Fetch cluster status
        cur.execute("""
            SELECT hdbscan_cluster, status
            FROM cluster_status
            WHERE execution_id = %s
        """, (execution_id,))
        cluster_status = {row[0]: row[1] for row in cur.fetchall()}

        # Group articles by cluster
        clusters = {}
        for article in articles:
            cluster_id = article[0]  # hdbscan_cluster
            if cluster_id not in clusters:
                clusters[cluster_id] = {
                    "cluster_id": int(cluster_id),
                    "size": 0,
                    "sample": [],
                    "status": cluster_status.get(cluster_id, None)
                }
            clusters[cluster_id]["size"] += 1
            clusters[cluster_id]["sample"].append({
                "title": article[1],
                "source": article[2]
            })

        cur.close()
        conn.close()

        cluster_list = [c for c in clusters.values() if c["cluster_id"] != -1]
        return jsonify(cluster_list)
    except Exception as e:
        app.logger.error("Error fetching clusters: {}".format(e))
        return jsonify({"error": "Failed to fetch clusters"}), 500

@app.route("/validate", methods=["POST"])
def validate_cluster():
    data = request.json
    execution_id = data.get("execution_id")
    cluster_id = data.get("cluster_id")
    is_valid = data.get("is_valid")

    if not all([execution_id, cluster_id is not None, is_valid is not None]):
        return jsonify({"error": "execution_id, cluster_id, and is_valid are required"}), 400

    status = True if is_valid else False

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Update the cluster status
        cur.execute("""
            UPDATE cluster_status
            SET status = %s, reviewed_at = %s, updated_by = %s
            WHERE execution_id = %s AND hdbscan_cluster = %s
        """, (status, datetime.now(), "user", execution_id, cluster_id))

        conn.commit()
        cur.close()
        conn.close()

        if is_valid:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            S3_CLIENT.put_object(Bucket=BUCKET_NAME, Key="greenlight_complete_{}.txt".format(timestamp), Body="Greenlight completed")

        return jsonify({"status": "success"})
    except Exception as e:
        app.logger.error("Error validating cluster: {}".format(e))
        return jsonify({"error": "Failed to validate cluster"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)