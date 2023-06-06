#!/usr/bin/env python3

import argparse
import fileinput
import re
import subprocess

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


def initialize_arguments():
    """
    initializes arguments that program accepts
    :return argument_parser: parser program that contains the arguments
    """
    argument_parser = argparse.ArgumentParser()
    argument_parser.add_argument('--release-date', '-d', help="release date", type=str, required=True)
    return argument_parser


def create_release_branch(release_branch, release_date):
    run_command(f'git checkout develop && git checkout -b {release_branch}')

    new_version, pom_increment_successful = set_release_version_in_pom(release_date)
    if pom_increment_successful:
        run_command('git add pom.xml')
        run_command(f'git commit -m "Set version for release to {new_version}"')
    else:
        log_red('The version in POM is NOT a correct SNAPSHOT version, please increment the version manually.')

    run_command(f'git push --set-upstream origin {release_branch}')
    return pom_increment_successful


def set_release_version_in_pom(release_date, path_to_pom='pom.xml'):
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
                if '-SNAPSHOT' in line:
                    new_line = line.replace('-SNAPSHOT', '.' + release_date)
                    print(new_line, end='')
                    new_version = new_line.replace(VERSION_OPENING_TAG, '').replace(VERSION_CLOSING_TAG, '').strip()
                    pom_increment_successful = True
                else:
                    pom_increment_successful = False
                    print(line, end='')
            else:
                print(line, end='')

    return new_version, pom_increment_successful


################
# SCRIPT START #
################
parser = initialize_arguments()
arguments = parser.parse_args()

# Checkout master & develop branches and update them
run_command('git checkout master && git pull')
run_command('git checkout develop && git pull')

# create release branch
release_branch_name = f'release/REL_{arguments.release_date}'
if create_release_branch(release_branch_name, arguments.release_date):
    log_green(f'Release {release_branch_name} branch created and pushed')
