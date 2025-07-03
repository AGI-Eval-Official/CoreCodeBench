#!/bin/bash
# Initialize variables with default values
repo_name=""
model=""
validate_model=""
gen_model="mix"
rewrite_model="mix"

# Parse named arguments
while [ $# -gt 0 ]; do
    case "$1" in
        --repo_name=*)
            repo_name="${1#*=}"
            ;;
        --model=*)
            model="${1#*=}"
            ;;
        --validate_model=*)
            validate_model="${1#*=}"
            ;;
        --gen_model=*)
            gen_model="${1#*=}"
            ;;
        --rewrite_model=*)
            rewrite_model="${1#*=}"
            ;;
        *)
            echo "Unknown parameter: $1"
    esac
    shift
done

# Single-Dev
python -m CorePipe.Single.dev_gen --repo_name $repo_name --model $model --validate_model $validate_model
python -m CorePipe.Single.dev_retest --repo_name $repo_name


# Single-TDD
python -m CorePipe.Single.TDD_gen --repo_name $repo_name

# Single-BugFix
python -m CorePipe.Single.debug_gen --repo_name $repo_name --gen_model $gen_model --rewrite_model $rewrite_model