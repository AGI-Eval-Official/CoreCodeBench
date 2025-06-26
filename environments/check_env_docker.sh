# Usage example: bash check_env_docker.sh --repo_idx=2 --root_path=~/CoreCodeBench
# 默认root_path为空
root_path=""

repos=("cloudnetpy" "d3rlpy" "datachain" "finam" "haystack" "inference" "langchain" "open-iris" "rdt" "skfolio" "transformers" "uniref")

# 解析 --repo_idx 和 --root_path
for arg in "$@"; do
    case $arg in
        --repo_idx=*)
        REPO_IDX="${arg#*=}"
        shift
        ;;
        --root_path=*)
        root_path="${arg#*=}"
        shift
        ;;
    esac
done

if [ -z "$root_path" ]; then
    echo "Please provide root_path parameter via --root_path=PATH"
    exit 1
fi

if [ -n "$REPO_IDX" ]; then
    repos=("${repos[$REPO_IDX]}")
fi

echo "repos: $repos"
echo "root_path: $root_path"

for repo_name in "${repos[@]}"; do
    # check docker image is exist
    echo "repo_name: $repo_name"
    docker_env="$repo_name"
    echo "docker_env: $docker_env"
     
    IMAGE_NAME="fulingyue/corecodebench:${docker_env}"
    
    # Check if the image exists locally
    if ! docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
        echo "Error: Docker image does not exist locally: $IMAGE_NAME"
        echo "Please pull the image first using: docker pull $IMAGE_NAME"
        continue
    fi
    echo "docker_env: $docker_env" 
    echo "IMAGE_NAME: $IMAGE_NAME"

    # check testcase number
    echo "checking environment.... repo_name: $repo_name"
    docker run --rm -v "$root_path:/workspace" "$IMAGE_NAME" bash -c "
        source /opt/conda/etc/profile.d/conda.sh && \
        export PATH=/opt/conda/bin:\$PATH && \
        conda activate $docker_env && \
        python /workspace/environments/check_environment.py --repo_name $repo_name --root_path /workspace
    " 2>&1

    if [[ $? -ne 0 ]]; then
        echo "Execution failed for repo: $repo_name"
    else
        echo "repo_name: $repo_name check done!"
    fi
done
