FROM python:3.8-slim
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*
RUN pip install --upgrade pip setuptools==44.0.0
RUN pip install numpy==1.19.5
RUN pip install scikit-learn==0.23.1 pandas psycopg2-binary
CMD ["python"]

