from flask import Flask, jsonify, request
import psycopg2
import boto3
import json
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

@app.route("/previous_validations", methods=["GET"])
def get_previous_validations():
    current_execution_id = request.args.get("execution_id")
    if not current_execution_id:
        return jsonify({"error": "execution_id is required"}), 400
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Get previous execution_id with validated clusters
        cur.execute("""
            SELECT execution_id
            FROM cluster_status
            WHERE created_at < (SELECT MAX(created_at) FROM cluster_status WHERE execution_id = %s)
            AND status IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
        """, (current_execution_id,))
        prev_execution_id = cur.fetchone()
        if not prev_execution_id:
            cur.close()
            conn.close()
            return jsonify([])
        prev_execution_id = prev_execution_id[0]
        # Fetch articles for clusters
        cur.execute("""
            SELECT ach.execution_id, ach.hdbscan_cluster, array_agg(json_build_object('url', a.url, 'title', a.title)) AS articles
            FROM article_cluster_history ach
            JOIN articles a ON ach.article_id = a.id
            WHERE ach.execution_id IN (%s, %s)
            GROUP BY ach.execution_id, ach.hdbscan_cluster
        """, (current_execution_id, prev_execution_id))
        cluster_articles = cur.fetchall()
        prev_clusters = {row[1]: row[2] for row in cluster_articles if row[0] == prev_execution_id}
        current_clusters = {row[1]: row[2] for row in cluster_articles if row[0] == current_execution_id}
        matches = []
        cur.execute("""
            SELECT hdbscan_cluster, status
            FROM cluster_status
            WHERE execution_id = %s AND status IS NOT NULL
        """, (prev_execution_id,))
        prev_statuses = {row[0]: row[1] for row in cur.fetchall()}
        for curr_cluster, curr_articles in current_clusters.items():
            curr_hash = hash(frozenset(sorted((article['url'], article['title']) for article in curr_articles)))
            for prev_cluster, prev_articles in prev_clusters.items():
                prev_hash = hash(frozenset(sorted((article['url'], article['title']) for article in prev_articles)))
                if curr_hash == prev_hash and prev_cluster in prev_statuses:
                    matches.append({
                        "current_cluster": curr_cluster,
                        "previous_cluster": prev_cluster,
                        "status": prev_statuses[prev_cluster]
                    })
                    # Auto-validate
                    cur.execute("""
                        UPDATE cluster_status
                        SET status = %s, reviewed_at = %s, updated_by = 'system'
                        WHERE execution_id = %s AND hdbscan_cluster = %s
                    """, (prev_statuses[prev_cluster], datetime.now(), current_execution_id, curr_cluster))
                    if prev_statuses[prev_cluster]:
                        cur.execute("""
                            INSERT INTO pending_narratives (
                                cluster_id, title, summary, left_angle, right_angle, articles, 
                                date_added, execution_id, left_reasonableness_score, right_reasonableness_score, reasonableness_reason
                            )
                            SELECT cluster_id, title, summary, left_angle, right_angle, articles, 
                                   %s, %s, left_reasonableness_score, right_reasonableness_score, reasonableness_reason
                            FROM narratives
                            WHERE execution_id = %s AND cluster_id = %s
                        """, (datetime.now(), current_execution_id, prev_execution_id, prev_cluster))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify(matches)
    except Exception as e:
        app.logger.error("Error fetching previous validations: {}".format(e))
        return jsonify({"error": "Failed to fetch previous validations"}), 500

@app.route("/clusters", methods=["GET"])
def get_clusters():
    execution_id = request.args.get("execution_id")
    if not execution_id:
        return jsonify({"error": "execution_id is required"}), 400
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        # Fetch clusters with status=NULL
        cur.execute("""
            SELECT a.hdbscan_cluster, a.title, a.source
            FROM articles a
            JOIN cluster_status c ON a.execution_id = c.execution_id AND a.hdbscan_cluster = c.hdbscan_cluster
            WHERE a.execution_id = %s AND a.hdbscan_cluster != -1 AND c.status IS NULL
            ORDER BY a.hdbscan_cluster
        """, (execution_id,))
        articles = cur.fetchall()
        # Fetch cluster status (all for display)
        cur.execute("""
            SELECT hdbscan_cluster, status
            FROM cluster_status
            WHERE execution_id = %s
        """, (execution_id,))
        cluster_status = {row[0]: row[1] for row in cur.fetchall()}
        # Group articles by cluster
        clusters = {}
        for article in articles:
            cluster_id = article[0]
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
        # Include validated clusters for display
        cur.execute("""
            SELECT a.hdbscan_cluster, a.title, a.source
            FROM articles a
            JOIN cluster_status c ON a.execution_id = c.execution_id AND a.hdbscan_cluster = c.hdbscan_cluster
            WHERE a.execution_id = %s AND a.hdbscan_cluster != -1 AND c.status IS NOT NULL
            ORDER BY a.hdbscan_cluster
        """, (execution_id,))
        validated_articles = cur.fetchall()
        for article in validated_articles:
            cluster_id = article[0]
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
        # Update cluster status
        cur.execute("""
            UPDATE cluster_status
            SET status = %s, reviewed_at = %s, updated_by = %s
            WHERE execution_id = %s AND hdbscan_cluster = %s
        """, (status, datetime.now(), "user", execution_id, cluster_id))
        if is_valid:
            # Drop S3 file for summarization
            timestamp = datetime.now().strftime("%Y%m%d_%H%M")
            body = json.dumps({"execution_id": execution_id, "cluster_id": cluster_id})
            S3_CLIENT.put_object(Bucket=BUCKET_NAME, Key=f"greenlight_complete_{timestamp}.txt", Body=body)
        # Completion check
        cur.execute("SELECT COUNT(*) FROM cluster_status WHERE execution_id = %s AND status IS NULL", (execution_id,))
        null_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cluster_status WHERE execution_id = %s AND status = true", (execution_id,))
        greenlit_count = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM pending_narratives WHERE execution_id = %s", (execution_id,))
        narrative_count = cur.fetchone()[0]
        if null_count == 0 and greenlit_count == narrative_count:
            cur.execute("""
                INSERT INTO narratives (
                    cluster_id, title, summary, left_angle, right_angle, articles, 
                    date_added, execution_id, left_reasonableness_score, right_reasonableness_score, reasonableness_reason
                )
                SELECT cluster_id, title, summary, left_angle, right_angle, articles, 
                       date_added, execution_id, left_reasonableness_score, right_reasonableness_score, reasonableness_reason
                FROM pending_narratives
                WHERE execution_id = %s
            """, (execution_id,))
            cur.execute("DELETE FROM pending_narratives WHERE execution_id = %s", (execution_id,))
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "success"})
    except Exception as e:
        app.logger.error("Error validating cluster: {}".format(e))
        return jsonify({"error": "Failed to validate cluster"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)