#!/usr/bin/env python3

"""Script to collect pull requests and convert them to candidate task instances"""

import argparse
import os
import traceback
import json
from fire import Fire

from dotenv import load_dotenv
from multiprocessing import Pool
from swebench.collect.utils import Repo
from swebench.collect.build_dataset import (
    create_instance,
    is_valid_pull,
    is_valid_instance,
    has_test_patch,
)
from swebench.collect.print_pulls import get_pull_batches


load_dotenv()


def split_instances(input_list: list, n: int) -> list:
    """
    Split a list into n approximately equal length sublists

    Args:
        input_list (list): List to split
        n (int): Number of sublists to split into
    Returns:
        result (list): List of sublists
    """
    avg_length = len(input_list) // n
    remainder = len(input_list) % n
    result, start = [], 0

    for i in range(n):
        length = avg_length + 1 if i < remainder else avg_length
        sublist = input_list[start : start + length]
        result.append(sublist)
        start += length

    return result


def construct_data_files(data: dict):
    """
    Logic for:
      - For each repo in data["repos"], gather PRs in batches of 100.
      - Write each pull to the repo's PR JSONL file as soon as it arrives.
      - Build tasks from those pulls and write them to a tasks JSONL file.
      - If `max_tasks` is reached, stop early.
    """
    repos = data["repos"]
    path_prs = data["path_prs"]
    path_tasks = data["path_tasks"]
    max_pulls = data["max_pulls"]
    cutoff_date = data["cutoff_date"]
    token = data["token"]
    max_tasks = data["max_tasks"]

    for repo_name in repos:
        repo_name = repo_name.strip(",").strip()
        file_prefix = repo_name.replace("/", "_")

        try:
            path_pr = os.path.join(path_prs, f"{file_prefix}-prs.jsonl")
            path_task = os.path.join(path_tasks, f"{file_prefix}-task-instances.jsonl")

            if cutoff_date:
                path_pr = path_pr.replace(".jsonl", f"-{cutoff_date}.jsonl")
                path_task = path_task.replace(".jsonl", f"-{cutoff_date}.jsonl")

            # Check existence
            if os.path.exists(path_pr):
                print(f"📁 Pull request data for {repo_name} already exists at {path_pr}, skipping re-download...")
            if os.path.exists(path_task):
                print(f"📁 Task data for {repo_name} already exists at {path_task}, skipping re-build...")

            if not os.path.exists(path_pr) or not os.path.exists(path_task):
                print(f"Collecting PRs for {repo_name} in batches...")

                # Open files in append mode so we can safely add new lines
                pr_f_mode = "a" if os.path.exists(path_pr) else "w"
                task_f_mode = "a" if os.path.exists(path_task) else "w"

                with open(path_pr, pr_f_mode) as pr_file, open(path_task, task_f_mode) as task_file:
                    # Prepare GH Repo object
                    owner, short = repo_name.split("/")
                    gh_repo = Repo(owner, short, token=token)

                    total_pulls_used = 0
                    total_tasks_created = 0

                    for batch in get_pull_batches(gh_repo, max_pulls=max_pulls, cutoff_date=cutoff_date, batch_size=10):
                        for pull in batch:
                            # Write the raw pull to the .jsonl file
                            pr_file.write(json.dumps(pull) + "\n")
                            total_pulls_used += 1

                            if is_valid_pull(pull):
                                instance = create_instance(gh_repo, pull)
                                if has_test_patch(instance):
                                    task_file.write(json.dumps(instance) + "\n")
                                    total_tasks_created += 1

                            if max_tasks is not None and total_tasks_created >= max_tasks:
                                print(
                                    f"🚨 Reached max_tasks={max_tasks} for {repo_name}. "
                                    f"Stopping after {total_pulls_used} pulls."
                                )
                                break

                        if max_tasks is not None and total_tasks_created >= max_tasks:
                            break

                    print(
                        f"✅ Done collecting for {repo_name}. "
                        f"Used {total_pulls_used} pulls, created {total_tasks_created} tasks."
                    )
            else:
                print(f"Skipping {repo_name} because its data files already exist.")

        except Exception as e:
            print("-" * 80)
            print(f"Something went wrong for {repo_name}, skipping: {e}")
            print("Here is the full traceback:")
            traceback.print_exc()
            print("-" * 80)



def main(
        repos_list: str,
        tokens_file: str,
        path_prs: str,
        path_tasks: str,
        max_tasks: int = None,
        max_pulls: int = None,
        cutoff_date: str = None,
    ):
    """
    Spawns multiple threads given multiple GitHub tokens for collecting fine tuning data

    Args:
        repos (list): List of repositories to retrieve instruction data for
        path_prs (str): Path to save PR data files to
        path_tasks (str): Path to save task instance data files to
        cutoff_date (str): Cutoff date for PRs to consider in format YYYYMMDD
    """
    with open(repos_list, "r") as f:
        repos_data = [json.loads(line) for line in f.readlines()]
    repos = [repo["full_name"] for repo in repos_data]

    path_prs, path_tasks = os.path.abspath(path_prs), os.path.abspath(path_tasks)
    print(f"Will save PR data to {path_prs}")
    print(f"Will save task instance data to {path_tasks}")
    print(f"Received {len(repos)} repos to create task instances for:\n{repos}")

    with open(tokens_file, "r") as f:
        tokens = [line.strip() for line in f.readlines() if line.strip()]

    data_task_lists = split_instances(repos, len(tokens))

    data_pooled = [
        {
            "repos": repos,
            "path_prs": path_prs,
            "path_tasks": path_tasks,
            "max_tasks": max_tasks,
            "max_pulls": max_pulls,
            "cutoff_date": cutoff_date,
            "token": token,
        }
        for repos, token in zip(data_task_lists, tokens)
    ]

    with Pool(len(tokens)) as p:
        p.map(construct_data_files, data_pooled)


if __name__ == "__main__":
    Fire(main)
