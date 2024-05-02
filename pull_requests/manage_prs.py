#!/usr/bin/env python3

import os
import sys
import requests
import yaml
import urllib3
import argparse

# Disable ssl warnings
urllib3.disable_warnings()

class CustomArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def add_argument(self, *args, **kwargs):
        if "--help" in args or "-h" in args:
            kwargs["help"] = "Show this help message and exit gracefully"
        super().add_argument(*args, **kwargs)

class CustomHelpFormatter(argparse.HelpFormatter):
    def _format_action(self, action):
        if action.option_strings:
            width = self._action_max_length + 2
            help_text = self._expand_help(action)
            return "  {:<{width}} {}\n".format(', '.join(action.option_strings), help_text, width=width)
        else:
            return super()._format_action(action)

def parse_args():
    parser = CustomArgumentParser(
        usage='%(prog)s [required arguments]',
        description='Manage PRs on the fly',
        formatter_class=CustomHelpFormatter,
    )

    parser._action_groups.pop()
    # Which flow?
    flow_required = parser.add_argument_group('Misc - Required Arguments')

    exclusive_group_flow = flow_required.add_mutually_exclusive_group(required=True)
    exclusive_group_flow.add_argument('-c', '--create', action="store_true", help='Create PR (XOR with merge)')
    exclusive_group_flow.add_argument('-m', '--merge', action="store_true", help='Merge PR (XOR with create)')

    flow_required.add_argument('-p', '--provider', help='Hosting provider',
                        default=None, required=True)
    
    repo_or_bulk = flow_required.add_mutually_exclusive_group(required=True)
    repo_or_bulk.add_argument('-r', '--repo', help='Target repo (XOR with bulk)')
    repo_or_bulk.add_argument('-b', '--bulk', help='PR bulk update list (required for merge)')
    
    # Create PRs flow
    create_required = parser.add_argument_group('[ Create PRs ] - Required Arguments')
    create_optional = parser.add_argument_group('[ Create PRs ] - Optional Arguments')
    
    create_required.add_argument('-t', '--title', help='PR title',
                        default=None, required='-c' in sys.argv)
    create_required.add_argument('-s', '--source', help='Feature/Bugfix branch',
                        default=None, required='-c' in sys.argv)
    create_required.add_argument('-dt', '--dest', help='Destination branch',
                        default=None, required='-c' in sys.argv)

    create_optional.add_argument('-dc', '--desc', help='PR description',
                        default=None)
    
    return parser.parse_args()

def load_config(provider):
    script_dir = os.path.dirname(os.path.realpath(__file__))
    config_file = os.path.join(script_dir, f'config/{provider}.yml')
    with open(config_file, 'r') as f:
        return yaml.safe_load(f)

def create_pull_request(config, repo, data, reviewers=None):
    print(f'Handling repo: {repo}')
    headers = {'Authorization': f'Bearer {config["token"]}'}
    if config['server'] == 'Github':
        base_server_url = config['server_url']
        response = requests.post(f'{base_server_url}/{repo}/pulls', headers=headers, json=data)
        pr_url = response.json()['html_url']
        if response.status_code == 201:
            print("Pull request opened successfully.")
            if reviewers:
                rev = requests.post(f'{pr_url}/requested_reviewers', headers=headers, json={"reviewers": reviewers})
                if rev.status_code == 200:
                    print("Reviewers added successfully.")
        else:
            print(f"Failed to open pull request. Status code: {response.status_code}")
    elif config['server'] == 'Bitbucket':
        base_server_url = config['server_url']
        response = requests.post(f'{base_server_url}/{repo}/pull-requests', headers=headers, json=data, verify=False)
        pr_id = response.json()['id']
        if response.status_code == 201:
            print("Pull request opened successfully.")
            if reviewers:
                reviewers_data = [{"user": {"name": reviewer}} for reviewer in reviewers]
                rev_data = {
                    "id": pr_id,
                    "version": 0,
                    "reviewers": reviewers_data
                }
                rev = requests.put(f'{base_server_url}/{repo}/pull-requests/{pr_id}', 
                                   headers=headers, json=rev_data, verify=False)
                
                if rev.status_code == 200:
                    print("Reviewers added successfully.")
        else:
            print(f"Failed to open pull request. Status code: {response.status_code}")
    else:
        print(f"Unsupported/Unknown provider, exiting")
        return
    print("===================================")

def prepare_pull_request(args, inc_repo=None):
    config = load_config(args.provider)
    if not config:
        print("Unsupported/Invalid provider specified.")
        return
    
    title = args.title
    # if inc_repo is None, we dont have bulk req and we have to read repo from args list
    repo = args.repo if inc_repo is None else inc_repo
    source_branch = args.source
    destination_branch = args.dest
    description = args.desc if args.desc is not None else ''
    reviewers = config.get('reviewers', [])
    
    if config['server'] == 'Github':
        data = {
            "title": title,
            "body": description,
            "head": source_branch,
            "base": destination_branch
        }
    else:
        data = {
            "title": title,
            "description": description,
            "fromRef": {
                "id": source_branch,
                "repository": {
                    "slug": repo,
                    "project": {
                        "key": config["project_key"]
                    }
                }
            },
            "toRef": {
                "id": destination_branch,
                "repository": {
                    "slug": repo,
                    "project": {
                        "key": config["project_key"]
                    }
                }
            }
        }

    # print(
    #     f'provider: {args.provider}\n'
    #     f'title: {title}\n'
    #     f'repo: {repo}\n'
    #     f'source_branch: {source_branch}\n'
    #     f'destination_branch: {destination_branch}\n'
    #     f'description: {description}\n'
    #     f'reviewers: {reviewers}\n'
    #     f'data: {data}\n'
    # )
    create_pull_request(config, repo, data, reviewers)

def merge_pull_requests(provider, bulk):
    config = load_config(provider)
    if not config:
        print("Unsupported/Invalid provider specified.")
        return
    
    server_url  = config['server_url']
    author      = config['author']
    headers     = {
        'Authorization': f'Bearer {config["token"]}'
    }
     
    with open(bulk, 'r') as f:
        for line in f:
            repo_name = line.strip()
            url = f"{server_url}/{repo_name}/pull-requests"

            try:
                # Send a GET request to fetch open pull requests
                response = requests.get(url, headers=headers, verify=False)
                response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
                pull_requests = response.json()['values']
            except requests.exceptions.HTTPError as e:
                print(f"An error occurred: {e}")
                return []

            for pr in pull_requests:
                pr_id = pr['id']
                if pr['state'] == 'OPEN' and pr['author']['user']['name'] == author:
                    merge_url = f"{server_url}/{repo_name}/pull-requests/{pr_id}/merge"
                    try:
                        response = requests.post(merge_url, headers=headers, verify=False)
                        response.raise_for_status()  # Raise an exception for 4xx or 5xx status codes
                        print(f"Pull request #{pr_id} merged successfully.")
                    except requests.exceptions.HTTPError as e:
                        print(f"Error merging pull request #{pr_id}: {e}")

def process_bulk_file(args, bulk_file):
    with open(bulk_file, 'r') as f:
        for line in f:
            repo_name = line.strip()
            prepare_pull_request(args, repo_name)

if __name__ == "__main__":
    args = parse_args()
    # Bulk file should be relative to the dir running the script
    if args.create:
        if args.bulk:
            process_bulk_file(args, args.bulk)
        else:
            prepare_pull_request(args)
    elif args.merge:
        merge_pull_requests(args.provider, args.bulk)
    else:
        print("Unsupported mode provided. Exiting...")
        sys.exit(1)
        