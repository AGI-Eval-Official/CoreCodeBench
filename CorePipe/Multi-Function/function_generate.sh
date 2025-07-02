repo_name=$1
python -m CorePipe.Multi-Function.function_generate --repo_name $repo_name --v 7 --d 3
python -m CorePipe.Multi-Function.function_generate_tdd --repo_name $repo_name --v 7 --d 3
python -m CorePipe.Multi-Function.function_generate_difficult --repo_name $repo_name --v 7 --d 3
python -m CorePipe.Multi-Function.function_generate_debug --repo_name $repo_name --v 7 --d 3
python -m CorePipe.Multi-Function.multi_retest --repo_name $repo_name --type Development TDD BugFix Difficult
python -m CorePipe.Multi-Function.function_combine --type Development TDD BugFix Difficult
