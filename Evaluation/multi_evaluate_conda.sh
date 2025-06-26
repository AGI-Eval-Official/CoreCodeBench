#!/bin/bash

# Initialize variables with default values
model=""
types=""
output_dir=""
model_ip="None"

# Parse named arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --model=*)
            model="${1#*=}"
            ;;
        --types=*)
            types="${1#*=}"
            ;;
        --output_dir=*)
            output_dir="${1#*=}"
            ;;
        --model_ip=*)
            model_ip="${1#*=}"
            ;;
        *)
            echo "Unknown parameter: $1"
            exit 1
            ;;
    esac
    shift
done

# Validate required parameters
if [ -z "$model" ] || [ -z "$types" ] || [ -z "$output_dir" ]; then
    echo "Error: Missing required parameters"
    echo "Usage: $0 --model=<model> --types=<types> --output_dir=<output_dir> [--model_ip=<model_ip>]"
    exit 1
fi

declare -A repo_env_map=(
    ["d3rlpy"]="d3rlpy"
    ["finam"]="finam"
    ["inference"]="inference"
    ["langchain"]="langchain"
    ["open-iris"]="iris"
    ["rdt"]="rdt"
    ["skfolio"]="skfolio"
    ["UniRef"]="uniref"
    ["transformers"]="transformers"
    ["langchain_core"]="langchain"
    ["datachain"]="datachain"
    ["haystack"]="haystack"
    ["cloudnetpy"]="cloudnetpy"
)

repos=("d3rlpy" "finam" "inference" "langchain" "open-iris" "rdt" "skfolio" "UniRef" "transformers" "langchain_core"  "datachain" "haystack" "cloudnetpy")

unset http_proxy
unset https_proxy

log_dir="logs"

if [ ! -d "$log_dir" ]; then
  mkdir -p "$log_dir"
fi

for repo_name in "${repos[@]}"; do
  # check conda env is exist
  conda_env="${repo_env_map[$repo_name]}"
  if [[ -z "$conda_env" ]]; then
        echo "Error: No Conda environment mapped for repo '$repo_name'"
        exit 1
  fi
done


conda_env="${repo_env_map['transformers']}"
echo "Running python multi_evaluate_response.py --type ${types} --model $model --output_dir ${output_dir} --model_ip $model_ip"
NASCONDA=/mnt/dolphinfs/hdd_pool/docker/user/hadoop-aipnlp/fulingyue/miniconda3/envs

# conda run -n $conda_env python multi_evaluate_response.py --type $types --model $model --output_dir $output_dir --model_ip $model_ip > "${log_dir}/evaluate_response.log" 2>&1  
conda run -p $NASCONDA/$conda_env python multi_evaluate_response.py --type $types --model $model --output_dir $output_dir --model_ip $model_ip > "${log_dir}/evaluate_response.log" 2>&1  
if [[ $? -ne 0 ]]; then
  echo "Error encountered while generating response. Check ${log_dir}/evaluate_response.log for details."
  exit 1
fi  
echo "Response generated! "

for repo_name in "${repos[@]}"; do
  conda_env="${repo_env_map[$repo_name]}"
  echo "Running evaluation for repo: $repo_name"
  conda run -p "$NASCONDA/$conda_env" python multi_evaluate_run.py --type $types --model $model --output_dir $output_dir --repo_name $repo_name 2> "${log_dir}/evaluate_${repo_name}.log"
#   conda run -n $conda_env python multi_evaluate_run.py --type $types --model $model --output_dir $output_dir --repo_name $repo_name 2> "${log_dir}/evaluate_${repo_name}.log"
  if [[ $? -ne 0 ]]; then
    echo "Error encountered while running evaluation for repo: $repo_name. Check ${log_dir}/evaluate_${repo_name}.log for details."
    exit 1
  fi
  echo "Evaluation completed for repo: $repo_name"
done

conda_env="${repo_env_map['transformers']}"
conda run -p $NASCONDA/$conda_env python get_results.py --model $model --output_dir $output_dir


echo "Script execution completed."