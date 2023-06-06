#!/usr/bin/env python3

import argparse
import time
import subprocess
import fileinput
import re

from http_methods import post, put

PIPELINE_TESTING_TIME = 10

# matches opening tags e.g. '</tag>' or '</dependency>', doesn't match closing tags </tag>
OPENING_TAG_REGEX = r"<[^\/][A-z]*>"
# matches closing tags e.g. '<tag>' or '<dependency>', doesn't match opening tags </tag>
CLOSING_TAG_REGEX = r"</[^\/][A-z]*>"

VERSION_OPENING_TAG = '<version>'
VERSION_CLOSING_TAG = '</version>'


def log_red(prt): print("\033[91m {}\033[00m".format(prt))


def log_green(prt): print("\033[92m {}\033[00m".format(prt))


def log_yellow(prt): print("\033[93m {}\033[00m".format(prt))


def run_command(command):
    log_yellow("Command: {}".format(command))
    result = subprocess.run(command, shell=True)
    if result.stderr:
        raise subprocess.CalledProcessError(
            returncode=result.returncode,
            cmd=result.args,
            stderr=result.stderr
        )
    if result.stdout:
        print("Command Result: {}".format(result.stdout.decode('utf-8')))
    return result


def create_merge_request_url(source_branch, target_branch, merge_title):
    return f'https://entwgit01.ama.at/api/v4/projects/{arguments.project_id}/merge_requests?' \
           f'source_branch={source_branch}' \
           f'&target_branch={target_branch}' \
           f'&title={merge_title.replace(" ", "%20")}'


def initialize_arguments():
    """
    initializes arguments that program accepts
    :return argument_parser: parser program that contains the arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--release-date', '-d', help="release date", type=str, required=True)
    argument_parser.add_argument('--project-id', '-p', help="project id", type=str, required=True)
    argument_parser.add_argument('--auto-merge', '-am', help="should perform merges automatically",
                                 type=bool, nargs='?', const='True', default=False)
    return argument_parser


def create_and_merge_mr(source_branch, target_branch, release_name, auto_merge=False):
    merge_title = f'{release_name} FINISH: Merging {source_branch} into {target_branch}'
    mr_response = post(
        create_merge_request_url(source_branch, target_branch, merge_title)
    )
    mr_iid = mr_response['iid']

    if auto_merge:
        # Sleep 2 mins for pipeline to finish testing
        time.sleep(PIPELINE_TESTING_TIME)
        put(f'https://entwgit01.ama.at/api/v4/projects/{arguments.project_id}/merge_requests/{mr_iid}/merge')


def find_nth(line_to_search, string_to_find, n):
    start = line_to_search.find(string_to_find)
    while start >= 0 and n > 1:
        start = line_to_search.find(string_to_find, start + len(string_to_find))
        n -= 1
    return start


def create_and_push_update_master(master_update_branch):
    run_command(f'git checkout master')
    run_command(f'git checkout -b {master_update_branch}')
    run_command(f'git merge release/REL_{arguments.release_date} {master_update_branch}')
    run_command(f'git tag REL_{arguments.release_date}')

    run_command(f'git push --set-upstream origin {master_update_branch}')
    run_command('git push --tags')


def create_and_push_update_develop(develop_update_branch):
    run_command(f'git checkout develop')
    run_command(f'git checkout -b {develop_update_branch}')
    run_command(f'git merge release/REL_{arguments.release_date} {develop_update_branch}')

    new_version, pom_increment_successful = increment_version_in_pom_to_snapshot()
    if pom_increment_successful:
        run_command('git add pom.xml')
        run_command(f'git commit -m "Set version after release to {new_version}"')
    else:
        log_red('The version in POM is NOT a correct RELEASE version, please increment the version manually.')
        log_red('Will NOT auto merge, please merge manually after committing the correct version')

    run_command(f'git push --set-upstream origin {develop_update_branch}')
    return pom_increment_successful


def increment_version_in_pom_to_snapshot(path_to_pom='pom.xml'):
    pom_increment_successful = True
    new_version = ''
    with fileinput.FileInput(path_to_pom, inplace=True, backup='.bak') as file:
        depth = 0
        for line in file:
            if re.search(OPENING_TAG_REGEX, line):
                depth += 1

            if re.search(CLOSING_TAG_REGEX, line):
                depth -= 1

            # The depth is checked so that only the version of a project and not of any of the nested <version> tags is changed
            if depth == 0 and VERSION_OPENING_TAG in line:
                version_to_bump = line[line.index(VERSION_OPENING_TAG) + len(VERSION_OPENING_TAG):line.index(
                    VERSION_CLOSING_TAG)]
                index_of_minor_version_start = find_nth(version_to_bump, '.', 2) + 1
                index_of_minor_version_end = find_nth(version_to_bump, '.', 3)
                if index_of_minor_version_end == -1 and '-SNAPSHOT' in version_to_bump:
                    pom_increment_successful = False
                    print(line, end='')
                    continue
                new_minor_version = int(version_to_bump[index_of_minor_version_start:index_of_minor_version_end]) + 1
                new_version = version_to_bump[:index_of_minor_version_start] + str(new_minor_version) + '-SNAPSHOT'
                print(line.replace(version_to_bump, new_version), end='')
            else:
                print(line, end='')

    return new_version, pom_increment_successful


################
# SCRIPT START #
################
parser = initialize_arguments()
arguments = parser.parse_args()

master_update_branch = f'master_after_{arguments.release_date}_update'
develop_update_branch = f'develop_after_{arguments.release_date}_update'

# Checkout master & develop branches and update them
run_command('git checkout master && git pull')
run_command('git checkout develop && git pull')

# checkout release branch
release_name = f'release/REL_{arguments.release_date}'
run_command(f'git checkout {release_name} && git pull')

# Update master
create_and_push_update_master(master_update_branch)
create_and_merge_mr(master_update_branch, 'master', release_name, arguments.auto_merge)

# Update develop
pom_increment_successful = create_and_push_update_develop(develop_update_branch)
create_and_merge_mr(develop_update_branch, 'develop', release_name, arguments.auto_merge and pom_increment_successful)

if pom_increment_successful:
    success_message = f'Release {release_name} finished, Merge Requests were created'
    if arguments.auto_merge:
        success_message += " and merged"
    log_green(success_message)

if arguments.auto_merge:
    # Cleanup
    run_command('git checkout develop')

    run_command(f'git b -d {release_name}')
    run_command(f'git push origin -d {release_name}')

    run_command(f'git b -d {master_update_branch}')
    run_command(f'git push origin -d {master_update_branch}')

    if pom_increment_successful:
        run_command(f'git b -d {develop_update_branch}')
        run_command(f'git push origin -d {develop_update_branch}')
    else:
        log_yellow(f'Will not remove {develop_update_branch}, please remove it manually after fixing version')
