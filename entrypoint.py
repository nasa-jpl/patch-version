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
    # The get_pulls function grabs all merged PRs that includes the commit SHA in question
    # Although it can be more than one, let's keep our code simple by conditioning the
    # success of this code to the assumption that there's only one returned and it is already merged
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


def get_semantic_tags_from_git():
    """Uses PyGithub to return a list of git tags"""
    import github

    gh = github.Github(os.getenv("GITHUB_TOKEN"))
    repo = gh.get_repo(os.getenv("GITHUB_REPOSITORY"))
    tags = repo.get_tags()

    return [tag.name for tag in tags]


def get_latest_semantic_tag():
    """Given a list of semantic tags, returns the latest one through sorting"""
    tags = get_semantic_tags_from_git()
    if tags is None:
        return None
    try:
        # For each elem, convert to a version, which is a tuple of the
        # major/minor/patch number. Then, sort in ascending order for
        # each element of the tuple, with a bias towards major,
        # then minor, then patch
        sorted_versions = sorted(
            [get_version_from_tag(tag) for tag in tags],
            key=lambda x: (x[0], x[1], x[2]),
        )
        return get_tag_from_version(sorted_versions[-1])
    except IndexError:
        return None


def get_version_from_tag(tag):
    """Retrieve semantic version info from project tag as a list of integers

    Returns semantic version information from a tag in the form of
    "v0.0.1" as a list of integers; returns None if the string could not be
    converted to a list of integers
    """
    if tag is None:
        return None
    match = re.findall(r"\d+", tag)
    if len(match) != 3:
        return None
    try:
        match = [int(i) for i in match]
    except (ValueError, TypeError):
        return None
    return match


def get_tag_from_version(version):
    """Convert a list of three integers to a tag in string format

    For example, [0, 0, 1] is converted to "v0.0.1"
    """
    return "v%d.%d.%d" % tuple(version)


def get_next_version(bump_major=False, bump_minor=False):
    """Get latest tag and increment, patch, version_minor, or version_major
    Returns the new latest version, the previous latest version and the part that got bumped
    """
    # Assume the part that gets bumped is the patch number
    part = "patch"
    latest_tag = get_latest_semantic_tag()
    # If no tags exist, create an initial v0.0.1 release
    if latest_tag is None:
        return ([0, 0, 1], [0, 0, 0], part)

    current_version = get_version_from_tag(latest_tag)
    latest_version = current_version.copy()
    if bump_major:
        latest_version = [latest_version[0] + 1, 0, 0]
        part = "major"
    elif bump_minor:
        latest_version = [latest_version[0], latest_version[1] + 1, 0]
        part = "minor"
    else:
        latest_version[2] += 1

    return (latest_version, current_version, part)


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

if is_commit_a_merge_commit(commit_msg):
    commit_msg = get_merge_request_description(commit_sha)

new_version, current_version, bumped = get_next_version(
    is_bump_major_requested(commit_msg), is_bump_minor_requested(commit_msg)
)
patch_cmakelists_txt(new_version)

# Save and report on outputs of this action
outputs = {
    "old_tag": f"v{'.'.join(map(str, current_version))}",
    "new_tag": f"v{'.'.join(map(str, new_version))}",
    "bumped": f"{bumped}",
}
fp_github_output = os.getenv("GITHUB_OUTPUT")
with open(fp_github_output, "a") as fp:
    for key in outputs.keys():
        fp.write(f"{key}={outputs[key]}\n")
        print(f"{key}={outputs[key]}")
