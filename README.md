# patch-version

A Github Action to patch the version inside a CMakeList file with the latest SemVer-formatted version

## Usage

If the pull request description (or the commit message) has the following strings, then the Action will attempt to patch the version information on CMakeLists

| To Bump | Key Phrases |
|----------|------------|
| Major | "bump version major", "bump major version", "#major" |
| Minor | "bump version minor", "bump minor version", "#minor" |
| Patch | Default |