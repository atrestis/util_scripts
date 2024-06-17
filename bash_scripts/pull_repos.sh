#!/bin/bash

# Usage function
display_usage() {
    echo "Usage: gupd <project> <branch> <fallback_branch>"
    exit 1
}

# Check if the correct number of arguments is provided
if [ "$#" -ne 3 ]; then
    display_usage
fi

project="$1"
branch="$2"
fallback_branch="$3"
base_directory="$HOME/Projects/$project"

echo "$base_directory"

if [ ! -d "$base_directory" ]; then
    echo "Directory $base_directory does not exist."
    exit 1
fi

update_repositories() {
    for repo_dir in $(find "$1" -type d -name ".git"); do
        # Change directory to the root of the repository
        repo_path="$(dirname "$repo_dir")"
        folder_name="$(basename "$repo_path")"
        echo "[ REPO: $folder_name ]"
        cd "$repo_path" || exit

        # Check if there are local changes
        if [ -n "$(git status -s)" ]; then
            echo "Stashing local changes..."
            git stash
        fi

        # Retry mechanism for Git operations
        retries=3
        count=0
        branch_to_use="$branch"
        while [ $count -lt $retries ]; do
            # Ensure no other Git processes are running
            if [ -f "$(git rev-parse --git-dir)/index.lock" ]; then
                echo "Git process is still running. Removing the lock file."
                rm -f "$(git rev-parse --git-dir)/index.lock"
            fi

            # Checkout to given branch
            if git checkout $branch_to_use 2>/dev/null; then
                # Pull the latest changes from the remote repository
                if git pull 2>/dev/null; then
                    echo "Pull successful from $branch_to_use"
                    break
                else
                    echo "Pull failed from $branch_to_use. Retrying..."
                fi
            else
                echo "Checkout to $branch_to_use failed"

                # If the branch checkout fails, switch to fallback branch
                if [ "$branch_to_use" = "$branch" ]; then
                    echo "Trying fallback branch $fallback_branch."
                    branch_to_use="$fallback_branch"
                    count=0  # Reset count for retrying fallback branch
                else
                    echo "Retrying..."
                fi
            fi
            
            ((count++))
            sleep 1
        done

        # Check if retries are exhausted
        if [ $count -eq $retries ]; then
            echo "Failed to pull after $retries retries. Skipping."
        fi

        echo "==============================================="
    done
}

update_repositories "$base_directory" "$branch"
