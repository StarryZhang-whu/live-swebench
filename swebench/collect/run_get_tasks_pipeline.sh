#!/usr/bin/env bash

# If you'd like to parallelize, do the following:
# * Create a .env file in this folder
# * Declare GITHUB_TOKENS=token1,token2,token3...

python swebench/collect/get_tasks_pipeline.py \
    --repos_list raw_repo/filtered_python_10000.jsonl \
    --tokens_file .cache/tokens.txt \
    --path_prs results/pr \
    --path_tasks results/task \
    --max_tasks 5 \
    --cutoff_date "20250101"
