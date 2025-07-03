repo_name=$1
python -m CorePipe.Single.repo_test_file_mapper --repo_name $repo_name 
python -m CorePipe.Single.test_all_test --repo_name $repo_name
python -m CorePipe.Single.functionTree_generate --repo_name $repo_name