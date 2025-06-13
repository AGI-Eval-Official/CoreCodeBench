#!/bin/bash
repo_name=$1
model_name=$2

python function_test_all.py --repo_name $repo_name --model $model --regenerate
python function_test_all.py --repo_name $repo_name --model $model --mode evaluate --regenerate