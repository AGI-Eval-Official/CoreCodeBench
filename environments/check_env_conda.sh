root_path="/workspace"

repos=("cloudnetpy" "d3rlpy" "datachain" "finam" "haystack" "inference" "langchain" "open-iris" "rdt" "skfolio" "transformers" "uniref")

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
    # check testcase number
    echo "checking environment.... repo_name: $repo_name"
    if [ "$repo_name" = "uniref" ]; then
        repo_name_arg="UniRef"
    else
        repo_name_arg="$repo_name"
    fi
    conda run -n "$repo_name" python $root_path/environments/check_environment.py --repo_name $repo_name_arg --root_path $root_path  2>&1
    if [[ $? -ne 0 ]]; then
        echo "Execution failed for repo: $repo_name"
    else
        echo "repo_name: $repo_name check done!"
    fi
done
