from pathlib import Path
from fire import Fire
import json

def main(
    dataset_jsonl: str,
    report_json: str,
    output_jsonl: str,
):
    with open(dataset_jsonl, 'r') as f:
        dataset = [json.loads(line) for line in f.readlines()]
    with open(report_json, 'r') as f:
        report = json.load(f)

    eval_results = []

    for instance in dataset:
        if instance["instance_id"] in report["resolved_ids"]:
            instance["resolved"] = True
        else:
            instance["resolved"] = False
        instance = {
            "instance_id": instance["instance_id"],
            "resolved": instance["resolved"],
            "difficulty": instance["difficulty"],
            "created_at": instance["created_at"],
        }
        eval_results.append(instance)

    with open(output_jsonl, 'w') as f:
        for instance in eval_results:
            f.write(json.dumps(instance) + '\n')

if __name__ == "__main__":
    Fire(main)
