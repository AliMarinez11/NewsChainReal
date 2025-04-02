# NewsChainReal

## Overview

NewsChainReal is a real-time news aggregation and analysis platform designed to cut through media bias and deliver balanced, insightful perspectives. By leveraging advanced clustering and AI summarization powered by xAI's Grok, this application fetches the latest news articles every 3 hours, groups them into coherent narratives, and provides:

- **Neutral Summaries**: Concise, unbiased overviews of each news story.
- **Left and Right Angles**: Perspectives from biased news sources, highlighting how the same story is framed differently.
- **Sentiment Analysis**: Grok’s evaluation of the emotional tone behind each narrative.
- **Source Transparency**: Links to original articles with their sources (e.g., "CNN: cnn.com/article").

Our mission is to empower users to understand the news beyond partisan spin, offering a clear, neutral lens alongside the polarized viewpoints that dominate modern media.

## Features

- **Real-Time Fetching**: Updates every 3 hours from diverse sources using the `newsdata.io` API.
- **Narrative Clustering**: Groups articles into meaningful stories with HDBSCAN.
- **Greenlight Process**: Browser-based tool to validate clusters as “valid” or “invalid.”
- **AI Summarization**: Grok generates neutral summaries, left/right angles, and sentiment insights.
- **Interactive Website**: Displays narratives in a card format with summaries, angles, and article links.

## Architecture

- **Fetching**: AWS Lambda (`fetch_articles_lambda.py`) fetches articles from `newsdata.io` `/latest`, stores in RDS `articles` table, signals S3.
- **Clustering**: SageMaker Notebook (`cluster_articles.py`) clusters all articles, saves to S3 as `clustered_articles_*.csv`.
- **Greenlight**: EC2-hosted Flask/React app (`greenlight_app.py`, `frontend/greenlight/`) updates `articles` `status`.
- **Summarization**: Lambda (`summarize_clusters_lambda.py`) sends valid clusters to Grok, stores in RDS `narratives`.
- **Website**: EC2-hosted FastAPI/React app (`backend/main.py`, `frontend/website/`) displays narratives.

## Components

- **`fetch_articles_lambda.py`**: Fetches articles every 3 hours, deduplicates, and stores in RDS.
- **`cluster_articles.py`**: Clusters articles using HDBSCAN, outputs to S3.
- **`greenlight_app.py`**: Flask backend for the greenlight browser tool.
- **`frontend/greenlight/`**: React UI for cluster validation (`index.html`, `app.js`, `styles.css`).
- **`summarize_clusters_lambda.py`**: Summarizes valid clusters with Grok, stores in `narratives`.
- **`backend/main.py`**: FastAPI backend for the website.
- **`frontend/website/`**: React UI for narrative display (`index.html`, `app.js`, `styles.css`).
- **`global-bundle.pem`**: SSL certificate for RDS connections.

## Setup Instructions

1. **Prerequisites**:

   - AWS account with IAM user (`newschain-deployer`), permissions for Lambda, S3, RDS, SageMaker, EC2.
   - PostgreSQL RDS instance (`newschain`) with `articles` and `narratives` tables.
   - `newsdata.io` API key.
   - xAI API key.

2. **Deployment**:

   - **Fetching**: Deploy `fetch_articles_lambda.py` to Lambda, schedule with EventBridge (every 3 hours).
   - **Clustering**: Upload `cluster_articles.py` to SageMaker Notebook, trigger via S3 signal.
   - **Greenlight**: Deploy `greenlight_app.py` and `frontend/greenlight/` to EC2.
   - **Summarization**: Deploy `summarize_clusters_lambda.py` to Lambda, trigger post-greenlight.
   - **Website**: Deploy `backend/main.py` and `frontend/website/` to EC2.

3. **Run**:
   - Start with Lambda fetch → SageMaker cluster → Greenlight validation → Lambda summarize → Website display.

## Why Grok?

Grok, built by xAI, powers our summarization and sentiment analysis, offering an outside perspective on human news bias. Its ability to generate neutral summaries and dual-angle insights ensures users see the full picture—unfiltered by partisan lenses.

## Future Enhancements

- Real-time sentiment trend analysis.
- Expanded source diversity.
- User-customizable narrative filters.

## Contact

- Repository: [github.com/AliMarinez11/NewsChainReal](https://github.com/AliMarinez11/NewsChainReal)
- Maintainer: Ali Marinez
