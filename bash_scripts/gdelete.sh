#!/bin/bash

# Fetch the latest remote branches
git fetch --prune > /dev/null 2>&1

# Updated to match git version 2.35.2 from modulefiles
branches_to_delete=$(git branch -vv | grep -E '\[origin/.*: gone\]' | awk '{print $1}')

# Delete each branch that is both fully merged and in the list to delete
for branch in $branches_to_delete; do
  git branch -D $branch > /dev/null 2>&1
  echo "Local [$branch] -> Deleted."
done

echo "Cleanup completed!"
