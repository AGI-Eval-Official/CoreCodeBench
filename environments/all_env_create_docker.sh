#!/bin/bash

# Usage example: bash all_env_create_docker.sh --repo_idx=2

# Define all environment names (i.e., docker tag names)
ENV_NAMES=("d3rlpy" "cloudnetpy" "datachain" "finam" "haystack" "inference" "langchain" "open-iris" "rdt" "skfolio" "transformers" "uniref")

# Parse --repo_idx argument
for arg in "$@"; do
    case $arg in
        --repo_idx=*)
        REPO_IDX="${arg#*=}"
        shift
        ;;
    esac
done

if [ -n "$REPO_IDX" ]; then
    ENV_NAMES=("${ENV_NAMES[$REPO_IDX]}")
fi

echo "Docker image tags to be pulled: ${ENV_NAMES[@]}"

for ENV_NAME in "${ENV_NAMES[@]}"; do
    IMAGE_NAME="fulingyue/corecodebench:${ENV_NAME}"
    # Check if the image already exists locally
    if docker image inspect "$IMAGE_NAME" > /dev/null 2>&1; then
        echo "Image already exists locally: $IMAGE_NAME, no need to pull."
    else
        echo "Image does not exist locally: $IMAGE_NAME, start pulling..."
        docker pull "$IMAGE_NAME"
        if [ $? -eq 0 ]; then
            echo "Image $IMAGE_NAME pulled successfully!"
        else
            echo "Failed to pull image $IMAGE_NAME, please check your network or image name."
        fi
    fi
done
