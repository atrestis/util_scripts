#!/bin/bash

if [ "$#" -ne 2 ]; then
    echo "Usage: gupd <project> <branch>"
    exit 1
fi

project="$1"
branch="$2"
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
        while [ $count -lt $retries ]; do
            # Ensure no other Git processes are running
            if [ -f "$(git rev-parse --git-dir)/index.lock" ]; then
                echo "Git process is still running. Removing the lock file."
                rm -f "$(git rev-parse --git-dir)/index.lock"
            fi

            # Checkout to branch given via cmd
            git checkout $branch

            # Pull the latest changes from the remote repository
            if git pull; then
                echo "Pull successful."
                break
            else
                echo "Pull failed. Retrying..."
                ((count++))
                sleep 1
            fi
        done

        # Check if retries are exhausted
        if [ $count -eq $retries ]; then
            echo "Failed to pull after $retries retries. Skipping."
        fi

        echo "================="
    done
}

update_repositories "$base_directory" "$branch"
