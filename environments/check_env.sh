declare -A repo_env_map=(
    ["d3rlpy"]="d3rlpy"
    ["finam"]="finam"
    ["inference"]="inference"
    ["langchain"]="langchain"
    ["open-iris"]="open-iris"
    ["rdt"]="rdt"
    ["skfolio"]="skfolio"
    ["UniRef"]="UniRef"
    ["transformers"]="transformers"
    ["langchain_core"]="langchain"
    ["datachain"]="datachain"
    ["haystack"]="haystack"
    ["cloudnetpy"]="cloudnetpy"
)

# root_path="/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp/fulingyue/AutoCoderBench/CoreCodeBench"

root_path="/mnt/dolphinfs/hdd_pool/docker/user/hadoop-aipnlp/EVA/fulingyue/AutoCoderBench/CoreCodeBench"
if [ ! -L "/home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp" ]; then
    ln -s /mnt/dolphinfs/hdd_pool/docker/user/hadoop-aipnlp /home/hadoop-aipnlp/dolphinfs_hdd_hadoop-aipnlp
    echo "符号链接创建成功"
else
    echo "符号链接已存在"
fi

repos=("cloudnetpy" "d3rlpy" "datachain" "finam" "haystack" "inference" "langchain" "open-iris" "rdt" "skfolio" "transformers" "UniRef")

# 解析 --repo_idx 参数
for arg in "$@"; do
    case $arg in
        --repo_idx=*)
        REPO_IDX="${arg#*=}"
        shift
        ;;
    esac
done

if [ -n "$REPO_IDX" ]; then
    repos=("${repos[$REPO_IDX]}")
fi

echo "repos: $repos"

for repo_name in "${repos[@]}"; do
    # check conda env is exist
    conda_env="${repo_env_map[$repo_name]}"
    if [[ -z "$conda_env" ]]; then
        echo "Error: No Conda environment mapped for repo '$repo_name'"
        # exit 1
    fi
    # check testcase number
    echo "checking environment.... repo_name: $repo_name"
    conda run -n "$conda_env" python check_environment.py --repo_name $repo_name --root_path $root_path  2>&1
    if [[ $? -ne 0 ]]; then
        echo "Execution failed for repo: $repo_name"
    else
        echo "repo_name: $repo_name check done!"
    fi
done
