import os
import re
import sys
import argparse
from pathlib import Path

# Try to read current version
VERSION_FILE = Path("_version.py")


def get_current_version():
    if not VERSION_FILE.exists():
        print(f"Error: {VERSION_FILE} not found.")
        sys.exit(1)

    content = VERSION_FILE.read_text()
    match = re.search(r'__version__\s*=\s*"([^"]+)"', content)
    if match:
        return match.group(1)
    return None


def bump_version(part="patch"):
    current = get_current_version()
    if not current:
        print("Error: Could not parse version.")
        sys.exit(1)

    major, minor, patch = map(int, current.split("."))

    if part == "major":
        major += 1
        minor = 0
        patch = 0
    elif part == "minor":
        minor += 1
        patch = 0
    else:  # patch
        patch += 1

    new_version = f"{major}.{minor}.{patch}"

    # Update file
    content = VERSION_FILE.read_text()
    new_content = re.sub(
        r'__version__\s*=\s*"[^"]+"', f'__version__ = "{new_version}"', content
    )
    VERSION_FILE.write_text(new_content)

    return current, new_version


def git_commands(version):
    tag = f"v{version}"
    print("\nReady to execute:")
    print(f"  git add {VERSION_FILE}")
    print(f'  git commit -m "Bump version to {version}"')
    print(f"  git tag {tag}")
    print("  git push origin main")
    print(f"  git push origin {tag}")

    confirm = input("\nExecute these git commands? (y/n): ")
    if confirm.lower() == "y":
        os.system(f"git add {VERSION_FILE}")
        os.system(f'git commit -m "Bump version to {version}"')
        os.system(f"git tag {tag}")
        print("\nLocal changes committed and tagged.")
        print("To push to GitHub and trigger release build:")
        print("  git push origin main")
        print(f"  git push origin {tag}")


def main():
    parser = argparse.ArgumentParser(description="Bump version and create git tag")
    parser.add_argument(
        "part",
        choices=["major", "minor", "patch"],
        default="patch",
        nargs="?",
        help="Part of version to bump",
    )
    args = parser.parse_args()

    old_v, new_v = bump_version(args.part)
    print(f"Bumping version: {old_v} -> {new_v}")

    git_commands(new_v)


if __name__ == "__main__":
    main()
