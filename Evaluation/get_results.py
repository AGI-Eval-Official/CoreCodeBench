import argparse
import json
import os
import pandas as pd
import config


def setup_arg_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=str, default='gpt-4o2', help='model to evaluate')
    parser.add_argument('--output_dir', type=str, default='/mnt/dolphinfs/hdd_pool/docker/user/hadoop-aipnlp/EVA/fulingyue/AutoCoderBench/CoreCodeBench', help='Output directory for results')
    return parser


if __name__ == "__main__":
    parser = setup_arg_parser()
    args = parser.parse_args()
    results_dir = os.path.join(args.output_dir, 'results', args.model)
    
    single_scores = {
        "ac_rate": 0.0,
        "pass_rate": 0.0,
        "dev_ac_rate": 0.0,
        "dev_pass_rate": 0.0,
        "bugfix_ac_rate": 0.0,
        "bugfix_pass_rate": 0.0,
        "tdd_ac_rate": 0.0,
        "tdd_pass_rate": 0.0
    }
    
    multi_scores = {
        "ac_rate": 0.0,
        "pass_rate": 0.0,
        "dev_ac_rate": 0.0,
        "dev_pass_rate": 0.0,
        "bugfix_ac_rate": 0.0,
        "bugfix_pass_rate": 0.0,
        "tdd_ac_rate": 0.0,
        "tdd_pass_rate": 0.0
    }

    # Process single score csv
    single_score_path = os.path.join(results_dir, 'single_scores.csv')
    if os.path.exists(single_score_path):
        df = pd.read_csv(single_score_path)
        single_scores["pass_rate"] = df["pass_rate"].mean()
        single_scores["ac_rate"] = df["pass_all"].mean()
        
        dev_df = df[df["ID"].str.startswith("Development")]
        bugfix_df = df[df["ID"].str.startswith("BugFix")]
        tdd_df = df[df["ID"].str.startswith("TDD")]
        
        # Calculate per-repo averages first, then average across repos
        dev_rates = []
        dev_ac_rates = []
        bugfix_rates = []
        bugfix_ac_rates = []
        tdd_rates = []
        tdd_ac_rates = []
        
        for repo in config.repo_list:
            repo_dev_df = dev_df[dev_df["repo_name"] == repo]
            if not repo_dev_df.empty:
                dev_rates.append(repo_dev_df["pass_rate"].mean())
                dev_ac_rates.append(repo_dev_df["pass_all"].mean())
                
            repo_bugfix_df = bugfix_df[bugfix_df["repo_name"] == repo]
            if not repo_bugfix_df.empty:
                bugfix_rates.append(repo_bugfix_df["pass_rate"].mean())
                bugfix_ac_rates.append(repo_bugfix_df["pass_all"].mean())
                
            repo_tdd_df = tdd_df[tdd_df["repo_name"] == repo]
            if not repo_tdd_df.empty:
                tdd_rates.append(repo_tdd_df["pass_rate"].mean())
                tdd_ac_rates.append(repo_tdd_df["pass_all"].mean())
        
        single_scores["dev_pass_rate"] = sum(dev_rates) / len(dev_rates) if dev_rates else 0.0
        single_scores["dev_ac_rate"] = sum(dev_ac_rates) / len(dev_ac_rates) if dev_ac_rates else 0.0
        single_scores["bugfix_pass_rate"] = sum(bugfix_rates) / len(bugfix_rates) if bugfix_rates else 0.0
        single_scores["bugfix_ac_rate"] = sum(bugfix_ac_rates) / len(bugfix_ac_rates) if bugfix_ac_rates else 0.0
        single_scores["tdd_pass_rate"] = sum(tdd_rates) / len(tdd_rates) if tdd_rates else 0.0
        single_scores["tdd_ac_rate"] = sum(tdd_ac_rates) / len(tdd_ac_rates) if tdd_ac_rates else 0.0

    # Process multi score csv  
    multi_score_path = os.path.join(results_dir, 'multi_scores.csv')
    if os.path.exists(multi_score_path):
        df = pd.read_csv(multi_score_path)
        multi_scores["pass_rate"] = df["pass_rate"].mean()
        multi_scores["ac_rate"] = df["pass_all"].mean()
        
        dev_df = df[df["ID"].str.startswith("Development")]
        bugfix_df = df[df["ID"].str.startswith("BugFix")] 
        tdd_df = df[df["ID"].str.startswith("TDD")]
        
        # Calculate per-repo averages first, then average across repos
        dev_rates = []
        dev_ac_rates = []
        bugfix_rates = []
        bugfix_ac_rates = []
        tdd_rates = []
        tdd_ac_rates = []
        
        for repo in config.repo_list:
            repo_dev_df = dev_df[dev_df["repo_name"] == repo]
            if not repo_dev_df.empty:
                dev_rates.append(repo_dev_df["pass_rate"].mean())
                dev_ac_rates.append(repo_dev_df["pass_all"].mean())
                
            repo_bugfix_df = bugfix_df[bugfix_df["repo_name"] == repo]
            if not repo_bugfix_df.empty:
                bugfix_rates.append(repo_bugfix_df["pass_rate"].mean())
                bugfix_ac_rates.append(repo_bugfix_df["pass_all"].mean())
                
            repo_tdd_df = tdd_df[tdd_df["repo_name"] == repo]
            if not repo_tdd_df.empty:
                tdd_rates.append(repo_tdd_df["pass_rate"].mean())
                tdd_ac_rates.append(repo_tdd_df["pass_all"].mean())

        
        multi_scores["dev_pass_rate"] = sum(dev_rates) / len(dev_rates) if dev_rates else 0.0
        multi_scores["dev_ac_rate"] = sum(dev_ac_rates) / len(dev_ac_rates) if dev_ac_rates else 0.0
        multi_scores["bugfix_pass_rate"] = sum(bugfix_rates) / len(bugfix_rates) if bugfix_rates else 0.0
        multi_scores["bugfix_ac_rate"] = sum(bugfix_ac_rates) / len(bugfix_ac_rates) if bugfix_ac_rates else 0.0
        multi_scores["tdd_pass_rate"] = sum(tdd_rates) / len(tdd_rates) if tdd_rates else 0.0
        multi_scores["tdd_ac_rate"] = sum(tdd_ac_rates) / len(tdd_ac_rates) if tdd_ac_rates else 0.0

    # Save results
    with open(os.path.join(results_dir, 'single_score.json'), 'w') as f:
        json.dump(single_scores, f, indent=4)
        
    with open(os.path.join(results_dir, 'multi_score.json'), 'w') as f:
        json.dump(multi_scores, f, indent=4)