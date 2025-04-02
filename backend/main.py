from fastapi import FastAPI
import psycopg2
from datetime import datetime

app = FastAPI()

DB_PARAMS = {
    "host": "newschain-db.cr4wc8ma675y.us-east-2.rds.amazonaws.com",
    "database": "newschain",
    "user": "newschainadmin",
    "password": "Largemoney11$$",
    "sslmode": "verify-full",
    "sslrootcert": "global-bundle.pem"
}

@app.get("/narratives")
def get_narratives():
    conn = psycopg2.connect(**DB_PARAMS)
    cur = conn.cursor()
    
    cur.execute("SELECT cluster_id, title, summary, left_angle, right_angle, articles FROM narratives")
    narratives = [
        {"cluster_id": row[0], "title": row[1], "summary": row[2], "left_angle": row[3], "right_angle": row[4], "articles": row[5]}
        for row in cur.fetchall()
    ]
    
    cur.close()
    conn.close()
    return narratives

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)