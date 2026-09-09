from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable
from urllib.parse import quote

from scripts.check_materializer_releases import (
    DEFAULT_API_BASE,
    DEFAULT_TIMEOUT_SECONDS,
    GitHubApi,
    ReleaseDiscoveryError,
    SemVer,
    _commit_sha,
    resolve_tag_commit,
)


@dataclass(frozen=True)
class SourceCandidate:
    """Immutable upstream source observation before TF dataset inspection."""

    resource_id: str
    publication_version: str | None
    signal: str
    source_revision: str
    release_url: str | None = None


class PublicGitHubApi(GitHubApi):
    """Read public upstream metadata without forwarding Agora repository auth."""

    def __init__(
        self,
        *,
        api_base: str = DEFAULT_API_BASE,
        timeout: int = DEFAULT_TIMEOUT_SECONDS,
        requester: Callable[..., bytes] | None = None,
    ) -> None:
        super().__init__(
            token="",
            api_base=api_base,
            timeout=timeout,
            requester=requester,
        )

    def get_default_branch_head(self, repository: str) -> str:
        repository_path = self._repository_path(repository)
        metadata = self._json(f"{self.api_base}/repos/{repository_path}")
        if not isinstance(metadata, dict):
            raise ReleaseDiscoveryError(
                f"GitHub repository metadata for {repository!r} is not an object"
            )
        branch = metadata.get("default_branch")
        if not isinstance(branch, str) or not branch:
            raise ReleaseDiscoveryError(
                f"GitHub repository metadata for {repository!r} has no default branch"
            )
        branch_payload = self._json(
            f"{self.api_base}/repos/{repository_path}/branches/{quote(branch, safe='')}"
        )
        if not isinstance(branch_payload, dict):
            raise ReleaseDiscoveryError(
                f"GitHub default branch response for {repository!r} is not an object"
            )
        commit = branch_payload.get("commit")
        if not isinstance(commit, dict):
            raise ReleaseDiscoveryError(
                f"GitHub default branch response for {repository!r} has no commit object"
            )
        return _commit_sha(
            commit.get("sha"),
            where=f"default branch head for {repository!r}",
        )


def public_github_api(
    *,
    requester: Callable[..., bytes] | None = None,
    api_base: str = DEFAULT_API_BASE,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> PublicGitHubApi:
    """Construct the deliberately unauthenticated client used for public upstream reads."""

    return PublicGitHubApi(
        requester=requester,
        api_base=api_base,
        timeout=timeout,
    )


def _tag_pattern(discovery: dict[str, Any]) -> re.Pattern[str]:
    value = discovery.get("tag_pattern")
    if not isinstance(value, str) or not value:
        raise ReleaseDiscoveryError(
            "github-releases corpus discovery requires a non-empty tag_pattern"
        )
    try:
        pattern = re.compile(value)
    except re.error as exc:
        raise ReleaseDiscoveryError(f"invalid corpus release tag_pattern: {exc}") from exc
    if "version" not in pattern.groupindex:
        raise ReleaseDiscoveryError(
            "corpus release tag_pattern must define a named 'version' capture"
        )
    return pattern


def _stable_release_candidates(
    resource: dict[str, Any],
    api: Any,
    pattern: re.Pattern[str],
) -> list[tuple[SemVer, dict[str, Any]]]:
    repository = resource["upstream"]["repository"]
    try:
        releases = api.list_releases(repository)
    except ReleaseDiscoveryError:
        raise
    except Exception as exc:
        raise ReleaseDiscoveryError(
            f"cannot list releases for resource {resource.get('id')!r}: {exc}"
        ) from exc

    candidates: list[tuple[SemVer, dict[str, Any]]] = []
    for release in releases:
        if not isinstance(release, dict):
            raise ReleaseDiscoveryError(
                f"release record for resource {resource.get('id')!r} is not an object"
            )
        if release.get("draft") or release.get("prerelease"):
            continue
        tag = release.get("tag_name")
        if not isinstance(tag, str):
            continue
        match = pattern.fullmatch(tag)
        if match is None:
            continue
        version_text = match.group("version")
        try:
            version = SemVer.parse(version_text)
        except ValueError:
            continue
        if version.prerelease is not None:
            continue
        candidates.append((version, release))
    return candidates


def _accepted_version(resource: dict[str, Any]) -> SemVer | None:
    accepted = resource["version_tracking"].get("accepted")
    if not isinstance(accepted, dict):
        return None
    version_text = accepted.get("publication_version")
    if not isinstance(version_text, str):
        raise ReleaseDiscoveryError(
            f"accepted publication version for {resource.get('id')!r} is missing"
        )
    try:
        return SemVer.parse(version_text)
    except ValueError as exc:
        raise ReleaseDiscoveryError(
            f"accepted publication version for {resource.get('id')!r} is not strict SemVer: {exc}"
        ) from exc


def _resolve_selected_release(
    resource: dict[str, Any], api: Any, version: SemVer, release: dict[str, Any]
) -> SourceCandidate:
    tag = release.get("tag_name")
    if not isinstance(tag, str) or not tag:
        raise ReleaseDiscoveryError(
            f"selected release for resource {resource.get('id')!r} lacks tag identity"
        )
    try:
        commit = resolve_tag_commit(api, resource["upstream"]["repository"], tag)
    except ReleaseDiscoveryError as exc:
        raise ReleaseDiscoveryError(
            f"selected release {tag!r} for resource {resource.get('id')!r} cannot be resolved: {exc}"
        ) from exc
    release_url = release.get("html_url")
    if release_url is not None and (not isinstance(release_url, str) or not release_url):
        raise ReleaseDiscoveryError(
            f"selected release for resource {resource.get('id')!r} has malformed URL identity"
        )
    return SourceCandidate(
        resource_id=resource["id"],
        publication_version=str(version),
        signal=tag,
        source_revision=commit,
        release_url=release_url,
    )


def _discover_release_source(resource: dict[str, Any], api: Any) -> SourceCandidate | None:
    tracking = resource["version_tracking"]
    discovery = tracking["discovery"]
    if discovery.get("channel") != "stable":
        raise ReleaseDiscoveryError(
            f"unsupported release channel for resource {resource.get('id')!r}"
        )
    pattern = _tag_pattern(discovery)
    candidates = _stable_release_candidates(resource, api, pattern)
    if not candidates:
        return None

    highest = max(version for version, _ in candidates)
    selected = [(version, release) for version, release in candidates if version == highest]
    if len(selected) != 1:
        identities = [
            (release.get("id"), release.get("tag_name"))
            for _, release in selected
        ]
        raise ReleaseDiscoveryError(
            f"ambiguous highest release {highest} for resource {resource.get('id')!r}: "
            f"{identities!r}"
        )

    accepted_version = _accepted_version(resource)
    if accepted_version is not None and highest < accepted_version:
        return None

    version, release = selected[0]
    resolved = _resolve_selected_release(resource, api, version, release)

    if accepted_version is not None and highest == accepted_version:
        accepted = tracking["accepted"]
        accepted_signal = accepted.get("signal")
        expected_commit = _commit_sha(
            accepted.get("source_revision"),
            where=f"accepted source revision for {resource.get('id')!r}",
        )
        if resolved.signal != accepted_signal or resolved.source_revision != expected_commit:
            raise ReleaseDiscoveryError(
                f"accepted release for {resource.get('id')!r} was retargeted or replaced: "
                f"same publication version {str(highest)!r} resolves as "
                f"{resolved.signal!r}@{resolved.source_revision}, but accepted commit is "
                f"{accepted_signal!r}@{expected_commit}"
            )
        return None

    return resolved


def _discover_default_branch_source(resource: dict[str, Any], api: Any) -> SourceCandidate:
    repository = resource["upstream"]["repository"]
    try:
        commit = api.get_default_branch_head(repository)
    except ReleaseDiscoveryError:
        raise
    except Exception as exc:
        raise ReleaseDiscoveryError(
            f"cannot resolve default branch head for resource {resource.get('id')!r}: {exc}"
        ) from exc
    commit = _commit_sha(commit, where=f"default branch head for resource {resource.get('id')!r}")
    return SourceCandidate(
        resource_id=resource["id"],
        publication_version=None,
        signal="default-branch",
        source_revision=commit,
    )


def discover_source_candidate(resource: dict[str, Any], api: Any) -> SourceCandidate | None:
    """Discover only immutable upstream source identity; never inspect TF roots here."""

    tracking = resource.get("version_tracking")
    if not isinstance(tracking, dict):
        return None
    discovery = tracking.get("discovery")
    if not isinstance(discovery, dict):
        raise ReleaseDiscoveryError(
            f"resource {resource.get('id')!r} has malformed version discovery policy"
        )
    mode = discovery.get("mode")
    if mode == "disabled":
        return None
    if mode == "github-releases":
        return _discover_release_source(resource, api)
    if mode == "default-branch":
        return _discover_default_branch_source(resource, api)
    if mode == "tf-directories":
        # RED3 owns dataset-root inspection. The source commit must still be
        # frozen before that inspection, so reuse the default-branch source seam.
        return _discover_default_branch_source(resource, api)
    raise ReleaseDiscoveryError(
        f"unsupported version discovery mode {mode!r} for resource {resource.get('id')!r}"
    )
