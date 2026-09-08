from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import json
import os
import re
import sys
import tempfile
from dataclasses import asdict, dataclass
from functools import total_ordering
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import yaml
from jsonschema import Draft202012Validator, FormatChecker

from scripts.agora_materialize import ManifestError, _validate_manifest_semantics


ROOT = Path(__file__).resolve().parents[1]
REGISTRY_SCHEMA_PATH = ROOT / "registry/schema/materializers.schema.json"
MATERIALIZER_SCHEMA_PATH = ROOT / "registry/schema/materializer-plugin.schema.json"
DEFAULT_API_BASE = "https://api.github.com"
DEFAULT_TIMEOUT_SECONDS = 20
MAX_TAG_DEPTH = 8
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_SEMVER_RE = re.compile(
    r"^(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)\."
    r"(0|[1-9][0-9]*)"
    r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
    r"(?:\+([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?$"
)


class ReleaseDiscoveryError(RuntimeError):
    """Passive release discovery or proposal construction failed closed."""


@total_ordering
@dataclass(frozen=True, eq=False)
class SemVer:
    major: int
    minor: int
    patch: int
    prerelease: tuple[int | str, ...] | None = None
    build: tuple[str, ...] = ()

    @classmethod
    def parse(cls, text: str) -> "SemVer":
        if not isinstance(text, str):
            raise ValueError("SemVer must be text")
        match = _SEMVER_RE.fullmatch(text)
        if match is None:
            raise ValueError(f"invalid SemVer: {text!r}")

        prerelease_text = match.group(4)
        prerelease: tuple[int | str, ...] | None = None
        if prerelease_text is not None:
            parsed: list[int | str] = []
            for identifier in prerelease_text.split("."):
                if identifier.isdigit():
                    if len(identifier) > 1 and identifier.startswith("0"):
                        raise ValueError(
                            f"numeric SemVer prerelease identifier has leading zero: {identifier!r}"
                        )
                    parsed.append(int(identifier))
                else:
                    parsed.append(identifier)
            prerelease = tuple(parsed)

        build_text = match.group(5)
        build = tuple(build_text.split(".")) if build_text is not None else ()
        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=prerelease,
            build=build,
        )

    def __str__(self) -> str:
        value = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease is not None:
            value += "-" + ".".join(str(item) for item in self.prerelease)
        if self.build:
            value += "+" + ".".join(self.build)
        return value

    def _precedence_key(self) -> tuple[int, int, int]:
        return (self.major, self.minor, self.patch)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        return self._precedence_key() == other._precedence_key() and self.prerelease == other.prerelease

    def __hash__(self) -> int:
        return hash((self._precedence_key(), self.prerelease))

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, SemVer):
            return NotImplemented
        if self._precedence_key() != other._precedence_key():
            return self._precedence_key() < other._precedence_key()
        if self.prerelease is None:
            return False
        if other.prerelease is None:
            return True
        for left, right in zip(self.prerelease, other.prerelease):
            if left == right:
                continue
            left_numeric = isinstance(left, int)
            right_numeric = isinstance(right, int)
            if left_numeric and right_numeric:
                return left < right
            if left_numeric != right_numeric:
                return left_numeric
            return str(left) < str(right)
        return len(self.prerelease) < len(other.prerelease)


@dataclass(frozen=True)
class ReleaseProposal:
    plugin_id: str
    previous_version: str
    previous_ref: str
    candidate_version: str
    candidate_tag: str
    candidate_ref: str
    release_url: str
    manifest_sha256: str


Requester = Callable[..., bytes]


class GitHubApi:
    def __init__(
        self,
        *,
        token: str | None = None,
        api_base: str = DEFAULT_API_BASE,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        requester: Requester | None = None,
    ) -> None:
        self.token = token or ""
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.requester = requester or self._default_requester

    @staticmethod
    def _default_requester(url: str, *, headers: dict[str, str], timeout: int) -> bytes:
        request = Request(url, headers=headers, method="GET")
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:500]
            raise ReleaseDiscoveryError(
                f"GitHub API HTTP {exc.code} for {url}: {detail or exc.reason}"
            ) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise ReleaseDiscoveryError(f"GitHub API request failed for {url}: {exc}") from exc

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "Agora-materializer-release-checker",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _bytes(self, url: str) -> bytes:
        try:
            payload = self.requester(url, headers=self._headers(), timeout=self.timeout)
        except ReleaseDiscoveryError:
            raise
        except Exception as exc:
            raise ReleaseDiscoveryError(f"GitHub API request failed for {url}: {exc}") from exc
        if not isinstance(payload, (bytes, bytearray)):
            raise ReleaseDiscoveryError(f"GitHub API transport returned non-bytes payload for {url}")
        return bytes(payload)

    def _json(self, url: str) -> Any:
        raw = self._bytes(url)
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ReleaseDiscoveryError(f"GitHub API returned invalid JSON for {url}: {exc}") from exc

    @staticmethod
    def _repository_path(repository: str) -> str:
        parts = repository.split("/")
        if len(parts) != 2 or not all(parts):
            raise ReleaseDiscoveryError(f"invalid GitHub repository identity: {repository!r}")
        return f"{quote(parts[0], safe='')}/{quote(parts[1], safe='')}"

    def list_releases(self, repository: str) -> list[dict[str, Any]]:
        repository_path = self._repository_path(repository)
        releases: list[dict[str, Any]] = []
        page = 1
        while True:
            url = (
                f"{self.api_base}/repos/{repository_path}/releases"
                f"?per_page=100&page={page}"
            )
            payload = self._json(url)
            if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
                raise ReleaseDiscoveryError(
                    f"GitHub releases response for {repository!r} is not an object list"
                )
            releases.extend(payload)
            if len(payload) < 100:
                return releases
            page += 1
            if page > 100:
                raise ReleaseDiscoveryError(
                    f"GitHub releases pagination exceeded safety bound for {repository!r}"
                )

    def get_ref(self, repository: str, tag: str) -> dict[str, Any]:
        repository_path = self._repository_path(repository)
        url = f"{self.api_base}/repos/{repository_path}/git/ref/tags/{quote(tag, safe='')}"
        payload = self._json(url)
        if not isinstance(payload, dict):
            raise ReleaseDiscoveryError(f"Git tag ref response is not an object for {tag!r}")
        return payload

    def get_tag_object(self, repository: str, sha: str) -> dict[str, Any]:
        repository_path = self._repository_path(repository)
        url = f"{self.api_base}/repos/{repository_path}/git/tags/{quote(sha, safe='')}"
        payload = self._json(url)
        if not isinstance(payload, dict):
            raise ReleaseDiscoveryError(f"Git annotated tag response is not an object for {sha!r}")
        return payload

    def get_file(self, repository: str, path: str, ref: str) -> bytes:
        repository_path = self._repository_path(repository)
        path_encoded = quote(path, safe="/")
        query = urlencode({"ref": ref})
        url = f"{self.api_base}/repos/{repository_path}/contents/{path_encoded}?{query}"
        payload = self._json(url)
        if not isinstance(payload, dict) or payload.get("encoding") != "base64":
            raise ReleaseDiscoveryError(
                f"candidate manifest response for {repository}:{path}@{ref} is not base64 file content"
            )
        content = payload.get("content")
        if not isinstance(content, str):
            raise ReleaseDiscoveryError(
                f"candidate manifest response for {repository}:{path}@{ref} has no content"
            )
        try:
            return base64.b64decode(content, validate=False)
        except (ValueError, TypeError) as exc:
            raise ReleaseDiscoveryError("candidate manifest has invalid base64 content") from exc


def _commit_sha(value: Any, *, where: str) -> str:
    if not isinstance(value, str) or _SHA_RE.fullmatch(value) is None:
        raise ReleaseDiscoveryError(f"{where} is not a full 40-character commit SHA")
    return value.lower()


def _tag_target(value: Any, *, where: str) -> tuple[str, str]:
    if not isinstance(value, dict):
        raise ReleaseDiscoveryError(f"{where} is missing object metadata")
    target = value.get("object")
    if not isinstance(target, dict):
        raise ReleaseDiscoveryError(f"{where}.object is missing")
    target_type = target.get("type")
    sha = target.get("sha")
    if not isinstance(target_type, str) or not isinstance(sha, str):
        raise ReleaseDiscoveryError(f"{where}.object is malformed")
    return target_type, sha


def resolve_tag_commit(api: Any, repository: str, tag: str) -> str:
    try:
        target_type, sha = _tag_target(api.get_ref(repository, tag), where=f"tag {tag!r}")
    except ReleaseDiscoveryError:
        raise
    except Exception as exc:
        raise ReleaseDiscoveryError(f"cannot resolve tag {tag!r} in {repository}: {exc}") from exc

    visited: set[str] = set()
    for depth in range(MAX_TAG_DEPTH + 1):
        if target_type == "commit":
            return _commit_sha(sha, where=f"resolved target for tag {tag!r}")
        if target_type != "tag":
            raise ReleaseDiscoveryError(
                f"tag {tag!r} resolves to unsupported Git object type {target_type!r}"
            )
        tag_sha = _commit_sha(sha, where=f"annotated tag object for {tag!r}")
        if tag_sha in visited:
            raise ReleaseDiscoveryError(f"annotated tag cycle detected while resolving {tag!r}")
        visited.add(tag_sha)
        if depth >= MAX_TAG_DEPTH:
            raise ReleaseDiscoveryError(f"annotated tag nesting exceeds safety bound for {tag!r}")
        try:
            target_type, sha = _tag_target(
                api.get_tag_object(repository, tag_sha),
                where=f"annotated tag object {tag_sha}",
            )
        except ReleaseDiscoveryError:
            raise
        except Exception as exc:
            raise ReleaseDiscoveryError(
                f"cannot dereference annotated tag {tag!r} object {tag_sha}: {exc}"
            ) from exc
    raise ReleaseDiscoveryError(f"could not resolve tag {tag!r} to a commit")


def _validate_candidate_document(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ReleaseDiscoveryError("candidate materializer manifest must be a JSON object")
    try:
        schema = json.loads(MATERIALIZER_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - repository corruption
        raise RuntimeError(f"cannot read Agora materializer schema: {exc}") from exc
    errors = sorted(
        Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(document),
        key=lambda item: item.json_path,
    )
    if errors:
        error = errors[0]
        location = error.json_path if getattr(error, "json_path", None) else "$"
        raise ReleaseDiscoveryError(
            f"candidate materializer manifest violates schema at {location}: {error.message}"
        )
    try:
        _validate_manifest_semantics(document)
    except ManifestError as exc:
        raise ReleaseDiscoveryError(f"candidate materializer manifest is unsafe: {exc}") from exc
    return document


def _candidate_manifest(plugin: dict[str, Any], api: Any, version: SemVer, commit: str) -> tuple[dict[str, Any], str]:
    try:
        raw = api.get_file(plugin["repository"], plugin["manifest"], commit)
    except ReleaseDiscoveryError:
        raise
    except Exception as exc:
        raise ReleaseDiscoveryError(
            f"cannot fetch {plugin['manifest']!r} for {plugin['id']!r} at {commit}: {exc}"
        ) from exc
    if not isinstance(raw, (bytes, bytearray)):
        raise ReleaseDiscoveryError("candidate materializer manifest transport returned non-bytes data")
    raw = bytes(raw)
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ReleaseDiscoveryError(f"candidate materializer manifest is not valid UTF-8 JSON: {exc}") from exc
    document = _validate_candidate_document(document)

    manifest_plugin = document["plugin"]
    if manifest_plugin["id"] != plugin["id"]:
        raise ReleaseDiscoveryError(
            f"candidate plugin id drift: expected {plugin['id']!r}, got {manifest_plugin['id']!r}"
        )
    manifest_repository = manifest_plugin.get("repository")
    if manifest_repository is not None and manifest_repository != plugin["repository"]:
        raise ReleaseDiscoveryError(
            f"candidate repository drift: expected {plugin['repository']!r}, got {manifest_repository!r}"
        )
    candidate_version = str(version)
    if manifest_plugin["version"] != candidate_version:
        raise ReleaseDiscoveryError(
            f"candidate manifest version mismatch: tag is {candidate_version!r}, manifest is {manifest_plugin['version']!r}"
        )
    expected_ids = set(plugin["materializers"])
    actual_ids = {item["id"] for item in document["materializers"]}
    if actual_ids != expected_ids:
        raise ReleaseDiscoveryError(
            "candidate materializer identity drift: "
            f"expected {sorted(expected_ids)!r}, got {sorted(actual_ids)!r}"
        )
    return document, hashlib.sha256(raw).hexdigest()


def discover_plugin_update(plugin: dict[str, Any], api: Any) -> ReleaseProposal | None:
    tracking = plugin.get("release_tracking")
    if tracking is None or tracking.get("mode") == "disabled":
        return None
    if tracking.get("mode") != "github-releases" or tracking.get("channel") != "stable":
        raise ReleaseDiscoveryError(f"unsupported release tracking policy for {plugin.get('id')!r}")

    try:
        current = SemVer.parse(str(plugin["version"]))
    except ValueError as exc:
        raise ReleaseDiscoveryError(
            f"registered version for {plugin.get('id')!r} is not strict SemVer: {exc}"
        ) from exc

    try:
        releases = api.list_releases(plugin["repository"])
    except ReleaseDiscoveryError:
        raise
    except Exception as exc:
        raise ReleaseDiscoveryError(
            f"cannot list releases for {plugin.get('id')!r}: {exc}"
        ) from exc

    prefix = tracking["tag_prefix"]
    candidates: list[tuple[SemVer, dict[str, Any]]] = []
    for release in releases:
        if not isinstance(release, dict):
            raise ReleaseDiscoveryError(f"release record for {plugin['id']!r} is not an object")
        if release.get("draft") or release.get("prerelease"):
            continue
        tag = release.get("tag_name")
        if not isinstance(tag, str) or not tag.startswith(prefix):
            continue
        text = tag[len(prefix) :]
        try:
            version = SemVer.parse(text)
        except ValueError:
            continue
        if version.prerelease is not None or version <= current:
            continue
        candidates.append((version, release))

    if not candidates:
        return None
    highest = max(version for version, _ in candidates)
    selected = [(version, release) for version, release in candidates if version == highest]
    if len(selected) != 1:
        identities = [
            (release.get("id"), release.get("tag_name")) for _, release in selected
        ]
        raise ReleaseDiscoveryError(
            f"ambiguous highest release {highest} for {plugin['id']!r}: {identities!r}"
        )

    version, release = selected[0]
    tag = release.get("tag_name")
    release_url = release.get("html_url")
    if not isinstance(tag, str) or not isinstance(release_url, str) or not release_url:
        raise ReleaseDiscoveryError(f"selected release for {plugin['id']!r} lacks tag/url identity")
    commit = resolve_tag_commit(api, plugin["repository"], tag)
    _, manifest_sha256 = _candidate_manifest(plugin, api, version, commit)
    return ReleaseProposal(
        plugin_id=plugin["id"],
        previous_version=str(plugin["version"]),
        previous_ref=plugin["ref"],
        candidate_version=str(version),
        candidate_tag=tag,
        candidate_ref=commit,
        release_url=release_url,
        manifest_sha256=manifest_sha256,
    )


def discover_updates(registry: dict[str, Any], api: Any) -> list[ReleaseProposal]:
    proposals: list[ReleaseProposal] = []
    for plugin in registry.get("plugins", []):
        try:
            proposal = discover_plugin_update(plugin, api)
        except ReleaseDiscoveryError as exc:
            raise ReleaseDiscoveryError(f"{plugin.get('id', '<unknown>')}: {exc}") from exc
        if proposal is not None:
            proposals.append(proposal)
    return proposals


def _validate_registry_document(document: Any) -> dict[str, Any]:
    if not isinstance(document, dict):
        raise ReleaseDiscoveryError("materializer registry must be a YAML object")
    try:
        schema = json.loads(REGISTRY_SCHEMA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:  # pragma: no cover - repository corruption
        raise RuntimeError(f"cannot read materializer registry schema: {exc}") from exc
    errors = sorted(Draft202012Validator(schema).iter_errors(document), key=lambda item: item.json_path)
    if errors:
        error = errors[0]
        location = error.json_path if getattr(error, "json_path", None) else "$"
        raise ReleaseDiscoveryError(
            f"materializer registry violates schema at {location}: {error.message}"
        )
    ids = [item["id"] for item in document["plugins"]]
    if len(ids) != len(set(ids)):
        raise ReleaseDiscoveryError("materializer registry contains duplicate plugin ids")
    return document


def _replace_block_scalar(
    lines: list[str],
    *,
    start: int,
    end: int,
    key: str,
    expected: str,
    replacement: str,
    plugin_id: str,
) -> None:
    pattern = re.compile(rf"^(    {re.escape(key)}: )([^\r\n]+)(\r?\n)?$")
    matches: list[tuple[int, re.Match[str]]] = []
    for index in range(start, end):
        match = pattern.fullmatch(lines[index])
        if match is not None:
            matches.append((index, match))
    if len(matches) != 1:
        raise ReleaseDiscoveryError(
            f"plugin {plugin_id!r} must have exactly one canonical {key!r} line"
        )
    index, match = matches[0]
    if match.group(2) != expected:
        raise ReleaseDiscoveryError(
            f"plugin {plugin_id!r} {key} changed since discovery: expected {expected!r}, got {match.group(2)!r}"
        )
    lines[index] = f"{match.group(1)}{replacement}{match.group(3) or ''}"


def apply_proposals_to_text(
    original_text: str,
    parsed_registry: dict[str, Any],
    proposals: list[ReleaseProposal],
) -> str:
    _validate_registry_document(parsed_registry)
    by_id: dict[str, ReleaseProposal] = {}
    for proposal in proposals:
        if proposal.plugin_id in by_id:
            raise ReleaseDiscoveryError(f"duplicate proposal for plugin {proposal.plugin_id!r}")
        by_id[proposal.plugin_id] = proposal

    plugin_by_id = {item["id"]: item for item in parsed_registry["plugins"]}
    unknown = set(by_id) - set(plugin_by_id)
    if unknown:
        raise ReleaseDiscoveryError(f"proposal targets missing materializer plugins: {sorted(unknown)!r}")

    expected_document = copy.deepcopy(parsed_registry)
    active: list[ReleaseProposal] = []
    expected_by_id = {item["id"]: item for item in expected_document["plugins"]}
    for plugin in parsed_registry["plugins"]:
        proposal = by_id.get(plugin["id"])
        if proposal is None:
            continue
        current = (str(plugin["version"]), plugin["ref"])
        previous = (proposal.previous_version, proposal.previous_ref)
        candidate = (proposal.candidate_version, proposal.candidate_ref)
        if current == candidate:
            continue
        if current != previous:
            raise ReleaseDiscoveryError(
                f"plugin {plugin['id']!r} changed since discovery: expected {previous!r}, got {current!r}"
            )
        active.append(proposal)
        expected_by_id[plugin["id"]]["version"] = proposal.candidate_version
        expected_by_id[plugin["id"]]["ref"] = proposal.candidate_ref

    if not active:
        return original_text

    lines = original_text.splitlines(keepends=True)
    block_starts: dict[str, int] = {}
    marker = re.compile(r"^  - id: ([a-z0-9][a-z0-9-]*)(?:\r?\n)?$")
    ordered_starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        match = marker.fullmatch(line)
        if match is not None:
            plugin_id = match.group(1)
            if plugin_id in block_starts:
                raise ReleaseDiscoveryError(f"duplicate canonical YAML block for {plugin_id!r}")
            block_starts[plugin_id] = index
            ordered_starts.append((index, plugin_id))

    active_by_id = {proposal.plugin_id: proposal for proposal in active}
    for position, (start, plugin_id) in enumerate(ordered_starts):
        proposal = active_by_id.get(plugin_id)
        if proposal is None:
            continue
        end = ordered_starts[position + 1][0] if position + 1 < len(ordered_starts) else len(lines)
        _replace_block_scalar(
            lines,
            start=start,
            end=end,
            key="ref",
            expected=proposal.previous_ref,
            replacement=proposal.candidate_ref,
            plugin_id=plugin_id,
        )
        _replace_block_scalar(
            lines,
            start=start,
            end=end,
            key="version",
            expected=proposal.previous_version,
            replacement=proposal.candidate_version,
            plugin_id=plugin_id,
        )

    missing_blocks = set(active_by_id) - set(block_starts)
    if missing_blocks:
        raise ReleaseDiscoveryError(
            f"canonical YAML blocks missing for proposals: {sorted(missing_blocks)!r}"
        )

    changed = "".join(lines)
    try:
        reparsed = yaml.safe_load(changed)
    except yaml.YAMLError as exc:
        raise ReleaseDiscoveryError(f"proposed registry patch is not valid YAML: {exc}") from exc
    _validate_registry_document(reparsed)
    if reparsed != expected_document:
        raise ReleaseDiscoveryError(
            "proposed registry patch changed semantics outside the intended version/ref fields"
        )
    return changed


def _write_atomic(path: Path, data: bytes) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.release-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _report_payload(state: str, proposals: list[ReleaseProposal], error: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": 1,
        "state": state,
        "proposals": [asdict(proposal) for proposal in proposals],
    }
    if error is not None:
        payload["error"] = error
    return payload


def _write_report(path: Path | None, payload: dict[str, Any]) -> None:
    if path is None:
        return
    encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    _write_atomic(path, encoded)


def render_pr_body(proposals: list[ReleaseProposal]) -> str:
    lines = [
        "## Automated materializer release proposals",
        "",
        "Agora passively validated the release metadata and candidate manifest at each resolved immutable commit. Candidate packaging/plugin code was not built, imported, installed, or executed.",
        "",
        "| Plugin | Version | Release | Resolved commit | Manifest SHA-256 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for proposal in proposals:
        lines.append(
            f"| `{proposal.plugin_id}` | `{proposal.previous_version}` → `{proposal.candidate_version}` | "
            f"[{proposal.candidate_tag}]({proposal.release_url}) | `{proposal.candidate_ref}` | `{proposal.manifest_sha256}` |"
        )
    lines.extend(
        [
            "",
            "Review is still required. The registry keeps immutable commit SHAs, this automation never auto-merges, and the existing explicit code-execution approval remains required before third-party packaging/build code can run.",
            "",
        ]
    )
    return "\n".join(lines)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Passively discover registered materializer releases.")
    parser.add_argument(
        "--registry",
        type=Path,
        default=ROOT / "registry/materializers.yaml",
        help="canonical materializer registry",
    )
    parser.add_argument("--report", type=Path, default=None, help="write deterministic JSON report")
    parser.add_argument("--pr-body", type=Path, default=None, help="write deterministic review PR body")
    parser.add_argument("--apply", action="store_true", help="atomically apply validated version/ref proposals")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    registry_path = args.registry.resolve()
    original_bytes = registry_path.read_bytes()
    try:
        original_text = original_bytes.decode("utf-8")
        parsed = yaml.safe_load(original_text)
        _validate_registry_document(parsed)
        api = GitHubApi(token=os.environ.get("GITHUB_TOKEN"))
        proposals = discover_updates(parsed, api)
        state = "no-update"
        if proposals and args.apply:
            changed = apply_proposals_to_text(original_text, parsed, proposals)
            if changed != original_text:
                _write_atomic(registry_path, changed.encode("utf-8"))
            state = "updated"
        elif proposals:
            state = "updates-available"
        _write_report(args.report, _report_payload(state, proposals))
        if args.pr_body is not None:
            _write_atomic(args.pr_body, render_pr_body(proposals).encode("utf-8"))
        print(json.dumps(_report_payload(state, proposals), sort_keys=True))
        return 0
    except (ReleaseDiscoveryError, UnicodeDecodeError, yaml.YAMLError, OSError) as exc:
        error = str(exc)
        try:
            _write_report(args.report, _report_payload("error", [], error))
        except OSError:
            pass
        print(f"materializer release discovery failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
