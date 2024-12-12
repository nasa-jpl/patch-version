#!/usr/bin/env python3

import os
import re
import subprocess
import sys


def is_commit_a_merge_commit(msg):
    """Check if the commit msg indicates this was a merge commit from a PR

    Performs a case insensitive check for strings "Merge pull request"
    """
    if msg is None:
        return False
    else:
        return "merge pull request" in msg.lower()


def get_merge_request_description(sha):
    """Get merge request associated with current git commit

    returns None if a merge request was not found
    """
    import github

    description = None
    gh = github.Github(os.getenv("GITHUB_TOKEN"))

    # Get PR desc via the input SHA
    repo = gh.get_repo(os.getenv("GITHUB_REPOSITORY"))
    commit = repo.get_commit(sha)
    pull_reqs = commit.get_pulls()
    if pull_reqs.totalCount == 1 and pull_reqs[0].is_merged():
        description = pull_reqs[0].body

    if description is None:
        print("Unable to retrieve an associated pull request description")
        sys.exit(-1)
    return description


def is_bump_major_requested(description):
    """Check if bump major was description in merge request text"

    performs a case insensitive check for strings "bump version major"
    or "bump major version"
    """
    if description is None:
        return False
    else:
        key_phrases = ["bump version major", "bump major version", "#major"]
        return any([phrase in description.lower() for phrase in key_phrases])


def is_bump_minor_requested(description):
    """Check if bump major was description in merge request text"

    performs a case insensitive check for strings "bump version minor"
    or "bump minor version"
    """
    if description is None:
        return False
    else:
        key_phrases = ["bump version minor", "bump minor version", "#minor"]
        return any([phrase in description.lower() for phrase in key_phrases])


def parse_cmakelists_for_version(fpath_cmakelists):
    """Parses input CMakeLists.txt file for version string with regex

    Returns
      - a re.Match object for further dissection
      - the lines of the read CMakeLists for search and replace
    """
    try:
        with open(fpath_cmakelists) as f:
            lines = f.read()
    except IOError:
        print(f"No {fpath_cmakelists} found in this repository")
        return None

    r = re.compile(
        r"project\(.*?VERSION.*?(\d+\.\d+\.\d+).*?\)",
        re.MULTILINE | re.IGNORECASE | re.DOTALL,
    )
    return (r.search(lines), lines)


def get_version_info_from_cmakelists_txt():
    """Retrieve current version information in CMakeLists.txt

    Retrieves current version information from CMakeLists.txt as a list of
    integers
    """
    m, __ = parse_cmakelists_for_version("CMakeLists.txt")
    try:
        return [int(i) for i in m.group(1).split(".")]
    except Exception:
        return None


def patch_cmakelists_txt(version):
    """Patch CMakeLists.txt with current version information

    Patches current CMakeLists version information

    returns True if CMakeLists.txt was patched;
            current_version and version info did not match
    returns False if CMakeLists.txt was not patched;
            current_version and version info already match, no patching necessary
    returns None if no CMakeLists.txt file exists or no version information
            available
    """
    m, lines = parse_cmakelists_for_version("CMakeLists.txt")
    current_version = None
    if len(m.groups()) == 0:
        print("Could not find version information in CMakeLists.txt")
        return None
    try:
        current_version = [int(i) for i in m.group(1).split(".")]
    except Exception:
        return None

    if current_version != version:
        s = m.span(1)
        # fmt: off
        lines = lines[:s[0]] + "%d.%d.%d" % tuple(version) + lines[s[1]:]
        # fmt: on
        with open("CMakeLists.txt", "w") as f:
            f.write(lines)
        subprocess.call(["git", "add", "CMakeLists.txt"])
        return True
    else:
        return False


##########
## MAIN ##
##########

# since https://github.blog/2022-04-12-git-security-vulnerability-announced/ runner uses?
cmd = "git config --global --add safe.directory /github/workspace"
subprocess.call(cmd.split())

commit_msg = None
commit_sha = None
if len(sys.argv) > 2:
    commit_msg = sys.argv[1]
    commit_sha = sys.argv[2]
    print(f"The commit_msg is:\n\t'{commit_msg}'")
    print(f"The commit_sha is:\n\t'{commit_sha}'")

current_version = get_version_info_from_cmakelists_txt()
if current_version is None:
    print("Unsupported case where no current version is found, exiting")
    sys.exit(-1)

if is_commit_a_merge_commit(commit_msg):
    commit_msg = get_merge_request_description(commit_sha)

bump_major = is_bump_major_requested(commit_msg)
bump_minor = is_bump_minor_requested(commit_msg)

part = "patch"
new_version = current_version.copy()
if bump_major:
    new_version[0] += 1
    new_version[1] = 0
    new_version[2] = 0
    part = "major"
elif bump_minor:
    new_version[1] += 1
    new_version[2] = 0
    part = "minor"
else:
    # default is to always bump patch
    new_version[2] += 1
patch_cmakelists_txt(new_version)

# Save and report on outputs of this action
outputs = {
    "old_tag": f"v{'.'.join(map(str, current_version))}",
    "new_tag": f"v{'.'.join(map(str, new_version))}",
    "bumped": f"{part}",
}
fp_github_output = os.getenv("GITHUB_OUTPUT")
with open(fp_github_output, "a") as fp:
    for key in outputs.keys():
        fp.write(f"{key}={outputs[key]}\n")
        print(f"{key}={outputs[key]}")
