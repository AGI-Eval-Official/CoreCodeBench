#!/bin/bash

#  no set -x

echo "=== Conda 初始化开始 ==="
# 尝试找到 conda.sh 文件
CONDA_BASE=$(conda info --base 2>/dev/null)
if [ -f "${CONDA_BASE}/etc/profile.d/conda.sh" ]; then
    source "${CONDA_BASE}/etc/profile.d/conda.sh"
    echo "Conda 初始化成功 (使用 conda.sh)"
else
    # 备选方法
    eval "$(conda shell.bash hook)" 2>/dev/null
    echo "Conda 初始化尝试完成 (使用 shell.bash hook)"
fi

# 验证 conda 是否正确初始化
if type conda 2>/dev/null | grep -q function; then
    echo "Conda 已成功初始化为 shell 函数"
else
    echo "警告: Conda 未正确初始化为 shell 函数，将使用 conda run 替代"
    # 设置一个标志，表示我们应该只使用 conda run
    USE_CONDA_RUN_ONLY=1
fi
echo "=== Conda 初始化结束 ==="


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
echo "Running python3 single_evaluate_response.py --type ${types} --model $model --output_dir ${output_dir} --model_ip $model_ip"

NASCONDA=/mnt/dolphinfs/hdd_pool/docker/user/hadoop-aipnlp/fulingyue/miniconda3/envs

# 替换这一行
# conda deactivate ;conda deactivate ; conda activate $NASCONDA/$conda_env;

# 使用这段代码
# if [ -z "$USE_CONDA_RUN_ONLY" ]; then
#     # 如果 conda 已正确初始化为函数，尝试使用 activate
#     conda deactivate 2>/dev/null || true
#     conda deactivate 2>/dev/null || true
#     if ! conda activate "$NASCONDA/$conda_env" 2>/dev/null; then
#         echo "警告: conda activate 失败，将使用 conda run"
#     fi
# else
#     echo "使用 conda run 替代 conda activate"
# fi

# conda run -n $NASCONDA/$conda_env python3 single_evaluate_response.py --type $types --model $model --output_dir $output_dir --model_ip $model_ip > "${log_dir}/evaluate_response.log" 2>&1  
conda run -p $NASCONDA/$conda_env python3 single_evaluate_response.py --type "$types" --model $model --output_dir $output_dir --model_ip $model_ip > "${log_dir}/evaluate_response.log" 2>&1  


# conda run -n $conda_env python3 single_evaluate_response.py --type $types --model $model --output_dir $output_dir --model_ip $model_ip > "${log_dir}/evaluate_response.log" 2>&1  
if [[ $? -ne 0 ]]; then
  echo "Error encountered while generating response. Check ${log_dir}/evaluate_response.log for details."
  exit 1
fi  
echo "Response generated! "


for repo_name in "${repos[@]}"; do
  conda_env="${repo_env_map[$repo_name]}"
  echo "Running evaluation for repo: $repo_name"
  echo $NASCONDA/$conda_env
  echo "conda_env"
  echo $conda_env
  echo "which conda"
  which conda
  conda run -p "$NASCONDA/$conda_env" python3 single_evaluate_run.py --type "$types" --model $model --output_dir $output_dir --repo_name $repo_name 2> "${log_dir}/evaluate_${repo_name}.log"
  if [[ $? -ne 0 ]]; then
    echo "Error encountered while running evaluation for repo: $repo_name. Check ${log_dir}/evaluate_${repo_name}.log for details."
    exit 1
  fi
  echo "Evaluation completed for repo: $repo_name"
done



conda_env="${repo_env_map['transformers']}"
conda run -p $NASCONDA/$conda_env python get_results.py --model $model --output_dir $output_dir

echo "Script execution completed."

# 在脚本末尾添加
if [ -f "${log_dir}/evaluate_open-iris.log" ]; then
    echo "=== open-iris 错误日志内容 ==="
    tail -20 "${log_dir}/evaluate_open-iris.log"  # 显示最后 20 行
    echo "==========================="
fi

# /mnt/dolphinfs/hdd_pool/docker/user/hadoop-aipnlp/fulingyue/miniconda3/bin/conda