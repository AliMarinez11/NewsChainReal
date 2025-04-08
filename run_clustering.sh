#!/bin/bash
EXECUTION_ID=$1
docker run -e AWS_ACCESS_KEY_ID=$(aws configure get aws_access_key_id) \
           -e AWS_SECRET_ACCESS_KEY=$(aws configure get aws_secret_access_key) \
           -e AWS_SESSION_TOKEN=$(aws configure get aws_session_token) \
           858286809900.dkr.ecr.us-east-2.amazonaws.com/newschain-clustering:latest \
           python cluster_articles.py --execution-id="$EXECUTION_ID"
