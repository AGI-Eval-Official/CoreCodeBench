repo_name=$1
python -m CorePipe.Single-Function.repo_test_file_mapper --repo_name $repo_name 
python -m CorePipe.Single-Function.test_all_test --repo_name $repo_name
python -m CorePipe.Single-Function.functionTree_generate --repo_name $repo_name