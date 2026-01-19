"""Env store: age-encrypted .env files in a private GitHub repo."""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from . import get_credential


class EnvStoreError(Exception):
    """Env store operation failed."""

    pass


def _get_config() -> tuple[str, str, str]:
    """Get env store config (secret_key, repo, public_key)."""
    secret_key = get_credential("ENV_STORE_KEY")
    repo = get_credential("ENV_STORE_REPO")
    public_key = get_credential("ENV_STORE_PUBLIC_KEY")

    if not secret_key:
        raise EnvStoreError("Missing ENV_STORE_KEY. Run: aitk env init")
    if not repo:
        raise EnvStoreError("Missing ENV_STORE_REPO. Add to ~/.config/aitk/config")
    if not public_key:
        raise EnvStoreError("Missing ENV_STORE_PUBLIC_KEY. Run: aitk env init")

    return secret_key, repo, public_key


def _check_age_installed() -> None:
    """Verify age CLI is available."""
    try:
        subprocess.run(["age", "--version"], capture_output=True, check=True)
    except FileNotFoundError:
        raise EnvStoreError("age CLI not found. Install: brew install age")
    except subprocess.CalledProcessError:
        raise EnvStoreError("age CLI check failed")


def _is_valid_env_file(name: str) -> bool:
    """Check if filename is a valid .env file (not example/sample/template)."""
    if not name.startswith(".env"):
        return False
    excludes = (".env.example", ".env.sample", ".env.template")
    return name not in excludes and not name.endswith((".example", ".sample", ".template"))


def _parse_env_keys(content: str) -> dict[str, str]:
    """Parse env file content into key-value dict."""
    result = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _encrypt(content: str, public_key: str) -> bytes:
    """Encrypt content with age."""
    _check_age_installed()
    result = subprocess.run(
        ["age", "-r", public_key],
        input=content.encode(),
        capture_output=True,
    )
    if result.returncode != 0:
        raise EnvStoreError(f"Encryption failed: {result.stderr.decode()}")
    return result.stdout


def _decrypt(encrypted: bytes, secret_key: str) -> str:
    """Decrypt content with age."""
    _check_age_installed()

    # Write secret key to temp file (age requires file for identity)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False) as f:
        f.write(secret_key)
        key_file = f.name

    try:
        result = subprocess.run(
            ["age", "-d", "-i", key_file],
            input=encrypted,
            capture_output=True,
        )
        if result.returncode != 0:
            raise EnvStoreError(f"Decryption failed: {result.stderr.decode()}")
        return result.stdout.decode()
    finally:
        Path(key_file).unlink()


def _gh_api(method: str, endpoint: str, data: dict | None = None) -> dict | list | None:
    """Call GitHub API via gh CLI."""
    cmd = ["gh", "api", "-X", method, endpoint]
    if data:
        import json

        cmd.extend(["-H", "Accept: application/vnd.github+json", "--input", "-"])
        result = subprocess.run(cmd, input=json.dumps(data).encode(), capture_output=True)
    else:
        result = subprocess.run(cmd, capture_output=True)

    if result.returncode != 0:
        stderr = result.stderr.decode()
        if "Not Found" in stderr or "empty" in stderr.lower():
            return None
        raise EnvStoreError(f"GitHub API error: {stderr}")

    if result.stdout:
        import json

        return json.loads(result.stdout)
    return None


def _gh_get_file(repo: str, path: str) -> bytes | None:
    """Get file content from GitHub repo."""
    import base64

    data = _gh_api("GET", f"/repos/{repo}/contents/{path}")
    if data and isinstance(data, dict) and "content" in data:
        return base64.b64decode(data["content"])
    return None


def _gh_put_file(repo: str, path: str, content: bytes, message: str) -> None:
    """Create or update file in GitHub repo."""
    import base64

    # Get current SHA if file exists
    existing = _gh_api("GET", f"/repos/{repo}/contents/{path}")
    sha = existing.get("sha") if existing and isinstance(existing, dict) else None

    b64_content = base64.b64encode(content).decode()

    # Use -f fields instead of --input to avoid encoding issues
    cmd = [
        "gh", "api", "-X", "PUT",
        f"/repos/{repo}/contents/{path}",
        "-f", f"message={message}",
        "-f", f"content={b64_content}",
    ]
    if sha:
        cmd.extend(["-f", f"sha={sha}"])

    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        raise EnvStoreError(f"GitHub API error: {result.stderr.decode()}")


def _gh_list_contents(repo: str, path: str = "") -> list[dict]:
    """List contents of a directory in GitHub repo."""
    result = _gh_api("GET", f"/repos/{repo}/contents/{path}")
    if result and isinstance(result, list):
        return result
    return []


def init() -> tuple[str, str]:
    """
    Generate age key pair.

    Returns (secret_key, public_key).
    Raises EnvStoreError if keys already exist.
    """
    _check_age_installed()

    # Check if keys already exist
    if get_credential("ENV_STORE_KEY"):
        raise EnvStoreError("ENV_STORE_KEY already configured. Refusing to overwrite.")

    result = subprocess.run(["age-keygen"], capture_output=True)
    if result.returncode != 0:
        raise EnvStoreError(f"Key generation failed: {result.stderr.decode()}")

    output = result.stdout.decode()

    # Parse output: "# public key: age1..."  and "AGE-SECRET-KEY-..."
    public_key = None
    secret_key = None

    for line in output.splitlines():
        line = line.strip()
        if line.startswith("# public key:"):
            public_key = line.split(":", 1)[1].strip()
        elif line.startswith("AGE-SECRET-KEY-"):
            secret_key = line

    if not public_key or not secret_key:
        raise EnvStoreError("Failed to parse age-keygen output")

    return secret_key, public_key


def pull(repo_path: str) -> list[str]:
    """
    Pull and decrypt .env files from store.

    Args:
        repo_path: owner/repo format

    Returns:
        List of created .env filenames
    """
    secret_key, store_repo, _ = _get_config()

    # List .age files in store for this repo
    contents = _gh_list_contents(store_repo, repo_path)
    if not contents:
        raise EnvStoreError(
            f"Repo '{repo_path}' not found in env store.\n"
            f"Push first with: aitk env push {repo_path}"
        )

    created = []
    for item in contents:
        name = item.get("name", "")
        if not name.endswith(".age"):
            continue

        # Derive .env filename from .age filename
        env_name = name[:-4]  # strip .age
        if not _is_valid_env_file(env_name):
            continue

        # Fetch and decrypt
        encrypted = _gh_get_file(store_repo, f"{repo_path}/{name}")
        if not encrypted:
            continue

        content = _decrypt(encrypted, secret_key)

        # Write with secure permissions
        env_path = Path(env_name)
        env_path.write_text(content)
        env_path.chmod(0o600)
        created.append(env_name)

    if not created:
        raise EnvStoreError(f"No .env files found for '{repo_path}' in store")

    return created


def push(repo_path: str) -> list[str]:
    """
    Encrypt and push .env files to store.

    Args:
        repo_path: owner/repo format

    Returns:
        List of pushed .env filenames
    """
    _, store_repo, public_key = _get_config()

    # Find local .env files
    env_files = []
    for f in Path(".").iterdir():
        if f.is_file() and _is_valid_env_file(f.name):
            env_files.append(f)

    if not env_files:
        raise EnvStoreError("No .env files found in current directory")

    pushed = []
    for env_file in env_files:
        content = env_file.read_text()

        # Skip if file has no actual key=value pairs
        if not _parse_env_keys(content):
            continue

        encrypted = _encrypt(content, public_key)

        # Push to store
        store_path = f"{repo_path}/{env_file.name}.age"
        _gh_put_file(
            store_repo,
            store_path,
            encrypted,
            f"Update {env_file.name} for {repo_path}",
        )
        pushed.append(env_file.name)

    if not pushed:
        raise EnvStoreError("No valid .env content to push")

    return pushed


def diff(repo_path: str, reveal: bool = False) -> dict[str, dict]:
    """
    Compare local .env keys with store.

    Args:
        repo_path: owner/repo format
        reveal: If True, show actual values (default: masked)

    Returns:
        Dict with 'local_only', 'store_only', 'both' keys
    """
    secret_key, store_repo, _ = _get_config()

    # Get local keys
    local_keys: dict[str, str] = {}
    for f in Path(".").iterdir():
        if f.is_file() and _is_valid_env_file(f.name):
            local_keys.update(_parse_env_keys(f.read_text()))

    # Get store keys
    store_keys: dict[str, str] = {}
    contents = _gh_list_contents(store_repo, repo_path)
    for item in contents:
        name = item.get("name", "")
        if not name.endswith(".age"):
            continue
        env_name = name[:-4]
        if not _is_valid_env_file(env_name):
            continue

        encrypted = _gh_get_file(store_repo, f"{repo_path}/{name}")
        if encrypted:
            content = _decrypt(encrypted, secret_key)
            store_keys.update(_parse_env_keys(content))

    # Compare
    local_set = set(local_keys.keys())
    store_set = set(store_keys.keys())

    def mask(val: str) -> str:
        if reveal:
            return val
        if len(val) <= 4:
            return "****"
        return val[:2] + "*" * (len(val) - 4) + val[-2:]

    return {
        "local_only": {k: mask(local_keys[k]) for k in local_set - store_set},
        "store_only": {k: mask(store_keys[k]) for k in store_set - local_set},
        "both": {k: mask(local_keys[k]) for k in local_set & store_set},
    }


def list_repos() -> list[str]:
    """List all repos in the env store."""
    _, store_repo, _ = _get_config()

    repos = []
    owners = _gh_list_contents(store_repo)
    for owner in owners:
        if owner.get("type") != "dir":
            continue
        owner_name = owner.get("name", "")
        repo_items = _gh_list_contents(store_repo, owner_name)
        for repo_item in repo_items:
            if repo_item.get("type") == "dir":
                repos.append(f"{owner_name}/{repo_item.get('name', '')}")

    return repos


def list_files(repo_path: str) -> list[str]:
    """List .env files for a repo in the store."""
    _, store_repo, _ = _get_config()

    files = []
    contents = _gh_list_contents(store_repo, repo_path)
    for item in contents:
        name = item.get("name", "")
        if name.endswith(".age"):
            env_name = name[:-4]
            if _is_valid_env_file(env_name):
                files.append(env_name)

    return files
