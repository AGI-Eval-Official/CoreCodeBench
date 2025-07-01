#!/bin/bash
# Example: bash multi_evaluate_conda.sh --model=model_name --types=Development,TDD --output_dir=/workspace
# Initialize variables with default values
model=""
types=""
output_dir=""
root_dir="/workspace"

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
        --root_dir=*)
            root_dir="${1#*=}"
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
    echo "Usage: $0 --model=<model> --types=<types> --output_dir=<output_dir> --root_dir=<root_dir>"
    exit 1
fi

declare -A repo_env_map=(
    ["d3rlpy"]="d3rlpy"
    ["finam"]="finam"
    ["inference"]="inference"
    ["langchain"]="langchain"
    ["open-iris"]="open-iris"
    ["rdt"]="rdt"
    ["skfolio"]="skfolio"
    ["UniRef"]="uniref"
    ["transformers"]="transformers"
    ["langchain_core"]="langchain"
    ["datachain"]="datachain"
    ["haystack"]="haystack"
    ["cloudnetpy"]="cloudnetpy"
)

repos=("UniRef" "d3rlpy" "finam" "inference" "langchain" "open-iris" "rdt" "skfolio" "transformers" "langchain_core"  "datachain" "haystack" "cloudnetpy")

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

# Update root_path in config.py
sed -i "s|root_path = .*|root_path = '${root_dir}'|" $root_dir/Evaluation/config.py

conda_env="${repo_env_map['transformers']}"
echo "Running python $root_dir/Evaluation/multi_evaluate_response.py --type ${types} --model $model --output_dir ${output_dir}"
conda run -n $conda_env python $root_dir/Evaluation/multi_evaluate_response.py --type $types --model $model --output_dir $output_dir > "${log_dir}/evaluate_response.log" 2>&1  
if [[ $? -ne 0 ]]; then
  echo "Error encountered while generating response. Check ${log_dir}/evaluate_response.log for details."
  exit 1
fi  
echo "Response generated! "

for repo_name in "${repos[@]}"; do
  conda_env="${repo_env_map[$repo_name]}"
  echo "Running evaluation for repo: $repo_name"
  conda run -n $conda_env python $root_dir/Evaluation/multi_evaluate_run.py --type $types --model $model --output_dir $output_dir --repo_name $repo_name 2> "${log_dir}/evaluate_${repo_name}.log"
  if [[ $? -ne 0 ]]; then
    echo "Error encountered while running evaluation for repo: $repo_name. Check ${log_dir}/evaluate_${repo_name}.log for details."
    exit 1
  fi
  echo "Evaluation completed for repo: $repo_name"
done

conda_env="${repo_env_map['transformers']}"
conda run -n $conda_env python $root_dir/Evaluation/get_results.py --model $model --output_dir $output_dir

# Restore root_path in config.py
sed -i "s|root_path = .*|root_path = '/workspace'|" $root_dir/Evaluation/config.py

echo "Script execution completed."