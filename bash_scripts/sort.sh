#!/bin/bash

# Get a list of all branches with their last commit date
branch_dates=$(for branch in $(git for-each-ref --format '%(refname:short)' refs/heads/); do
    echo $(git log -n 1 --format="%ci" $branch) $branch
done)

# Sort branches by date in descending order
sorted_branches=$(echo "$branch_dates" | sort)

# Print the sorted branches
echo "$sorted_branches"
