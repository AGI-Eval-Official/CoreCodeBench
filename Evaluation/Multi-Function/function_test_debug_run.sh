#!/bin/bash
repo_name=$1
model=$2

python function_debug_test_all.py --repo_name $repo_name --model $model --regenerate --if_comments debug
python function_debug_test_all.py --repo_name $repo_name --model $model --mode evaluate --regenerate --if_comments debug
