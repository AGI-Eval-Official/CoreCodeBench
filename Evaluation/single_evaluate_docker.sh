#!/bin/bash
# Example: bash single_evaluate_docker.sh --model=deepseek-r1 --types="Development" --output_dir=/workspace --model_ip=10.10.10.10 --root_path=/path/to/CoreCodeBench

# Initialize variables with default values
model=""
types=""
output_dir=""
model_ip="None"
root_path=""

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
        --root_path=*)
            root_path="${1#*=}"
            ;;
        *)
            echo "Unknown parameter: $1"
            exit 1
            ;;
    esac
    shift
done

# Validate required parameters
if [ -z "$model" ] || [ -z "$types" ] || [ -z "$output_dir" ] || [ -z "$root_path" ]; then
    echo "Error: Missing required parameters"
    echo "Usage: $0 --model=<model> --types=<types> --output_dir=<output_dir> --root_path=<root_path> [--model_ip=<model_ip>]"
    exit 1
fi

repos=("d3rlpy" "finam" "inference" "langchain" "open-iris" "rdt" "skfolio" "uniref" "transformers" "langchain_core" "datachain" "haystack" "cloudnetpy")

unset http_proxy
unset https_proxy

log_dir="logs"

if [ ! -d "$log_dir" ]; then
  mkdir -p "$log_dir"
fi

# 使用transformers环境生成响应
echo "Running python3 single_evaluate_response.py --type ${types} --model $model --output_dir ${output_dir} --model_ip $model_ip"

IMAGE_NAME="fulingyue/corecodebench:transformers"

# Check if the image exists locally
if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
    echo "Error: Docker image does not exist locally: $IMAGE_NAME"
    echo "Please pull the image first using: docker pull $IMAGE_NAME"
    exit 1
fi

# 生成响应
docker run --rm -v "${root_path}:/workspace" "$IMAGE_NAME" bash -c "
    source /opt/conda/etc/profile.d/conda.sh && \
    export PATH=/opt/conda/bin:\$PATH && \
    conda activate transformers && \
    cd /workspace/Evaluation && \
    python3 single_evaluate_response.py --type $types --model $model --output_dir $output_dir --model_ip $model_ip
" > "${log_dir}/evaluate_response.log" 2>&1

if [[ $? -ne 0 ]]; then
  echo "Error encountered while generating response. Check ${log_dir}/evaluate_response.log for details."
  exit 1
fi  
echo "Response generated! "

# 对每个repo运行评估
for repo_name in "${repos[@]}"; do
  echo "Running evaluation for repo: $repo_name"
  
  IMAGE_NAME="fulingyue/corecodebench:${repo_name}"
  
  # Check if the image exists locally
  if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
      echo "Error: Docker image does not exist locally: $IMAGE_NAME"
      echo "Please pull the image first using: docker pull $IMAGE_NAME"
      continue
  fi
  
  docker run --rm -v "${root_path}:/workspace" "$IMAGE_NAME" bash -c "
      source /opt/conda/etc/profile.d/conda.sh && \
      export PATH=/opt/conda/bin:\$PATH && \
      conda activate $repo_name && \
      cd /workspace/Evaluation && \
      python3 single_evaluate_run.py --type $types --model $model --output_dir $output_dir --repo_name $repo_name
  " 2> "${log_dir}/evaluate_${repo_name}.log"
  
  if [[ $? -ne 0 ]]; then
    echo "Error encountered while running evaluation for repo: $repo_name. Check ${log_dir}/evaluate_${repo_name}.log for details."
    exit 1
  fi
  echo "Evaluation completed for repo: $repo_name"
done

# 获取结果
IMAGE_NAME="fulingyue/corecodebench:transformers"

docker run --rm -v "${root_path}:/workspace" "$IMAGE_NAME" bash -c "
    source /opt/conda/etc/profile.d/conda.sh && \
    export PATH=/opt/conda/bin:\$PATH && \
    conda activate transformers && \
    cd /workspace/Evaluation && \
    python get_results.py --model $model --output_dir $output_dir
"

echo "Script execution completed."
