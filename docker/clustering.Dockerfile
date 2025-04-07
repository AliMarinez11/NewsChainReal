FROM python:3.10-slim
RUN apt-get update && apt-get install -y gcc g++ python3-dev libpq-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --index-url https://pypi.org/simple psycopg2-binary==2.9.9 pandas==1.5.3 boto3==1.28.38 scikit-learn==1.5.2 hdbscan==0.8.40 numpy==1.26.4 scipy==1.15.1 joblib==1.4.2 threadpoolctl==3.5.0
COPY cluster_articles.py /app/cluster_articles.py
COPY global-bundle.pem /app/global-bundle.pem
WORKDIR /app
CMD ['python', 'cluster_articles.py']

