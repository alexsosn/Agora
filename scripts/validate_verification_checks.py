from __future__ import annotations

import importlib.util
import json
import sys
import unittest
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator, FormatChecker

VERIFICATION_RANK = {"experimental": 0, "community": 1, "verified": 2}


def _load_yaml(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _schema_errors(instance: Any, schema_path: Path, label: str) -> list[str]:
    validator = Draft202012Validator(
        _load_json(schema_path),
        format_checker=FormatChecker(),
    )
    errors: list[str] = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        path = ".".join(str(part) for part in error.absolute_path)
        where = f"{label}:{path}" if path else label
        errors.append(f"{where}: {error.message}")
    return errors


def _validate_unittest_executor(root: Path, check_id: str, executor: dict[str, Any]) -> list[str]:
    target = executor.get("target")
    if not isinstance(target, str):
        return []
    try:
        module_name, class_name, method_name = target.rsplit(".", 2)
    except ValueError:
        return [f"verification check {check_id!r}: unittest target {target!r} is not executable"]

    module_path = root / (module_name.replace(".", "/") + ".py")
    if not module_path.is_file():
        return [
            f"verification check {check_id!r}: unittest target {target!r} is not executable; "
            f"missing {module_path.relative_to(root)}"
        ]

    spec = importlib.util.spec_from_file_location(
        f"_agora_verification_{check_id.replace('/', '_').replace('-', '_')}",
        module_path,
    )
    if spec is None or spec.loader is None:
        return [f"verification check {check_id!r}: unittest target {target!r} is not executable"]

    module = importlib.util.module_from_spec(spec)
    previous_path = list(sys.path)
    try:
        sys.path.insert(0, str(root))
        spec.loader.exec_module(module)
    except Exception as exc:
        return [
            f"verification check {check_id!r}: unittest target {target!r} is not executable: "
            f"{type(exc).__name__}: {exc}"
        ]
    finally:
        sys.path[:] = previous_path

    loader = unittest.TestLoader()
    suite = loader.loadTestsFromName(f"{class_name}.{method_name}", module)
    if loader.errors or suite.countTestCases() != 1:
        detail = "; ".join(loader.errors) if loader.errors else f"found {suite.countTestCases()} tests"
        return [
            f"verification check {check_id!r}: unittest target {target!r} is not executable: {detail}"
        ]
    return []


def _render_matrix_template(value: str, selector: dict[str, Any]) -> str:
    rendered = value
    for key, selected in selector.items():
        rendered = rendered.replace(f"${{{{ matrix.{key} }}}}", str(selected))
    return rendered


def _validate_actions_executor(root: Path, check_id: str, executor: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    workflow = executor.get("workflow")
    job_id = executor.get("job")
    selector = executor.get("matrix") or {}
    if not isinstance(workflow, str) or not isinstance(job_id, str) or not isinstance(selector, dict):
        return errors

    workflow_path = root / workflow
    if not workflow_path.is_file():
        return [f"verification check {check_id!r}: missing workflow {workflow!r}"]

    workflow_doc = _load_yaml(workflow_path)
    jobs = workflow_doc.get("jobs", {}) if isinstance(workflow_doc, dict) else {}
    job = jobs.get(job_id) if isinstance(jobs, dict) else None
    if not isinstance(job, dict):
        return [f"verification check {check_id!r}: missing workflow job {job_id!r} in {workflow}"]

    matrix = ((job.get("strategy") or {}).get("matrix") or {})
    for key, selected in selector.items():
        configured = matrix.get(key) if isinstance(matrix, dict) else None
        if not isinstance(configured, list) or selected not in configured:
            errors.append(
                f"verification check {check_id!r}: matrix selector {key}={selected!r} "
                f"is not executable by workflow job {job_id!r}"
            )

    artifact = executor.get("artifact")
    if isinstance(artifact, str):
        rendered_artifacts: list[str] = []
        for step in job.get("steps", []):
            if not isinstance(step, dict):
                continue
            uses = step.get("uses")
            if not isinstance(uses, str) or not uses.startswith("actions/upload-artifact@"):
                continue
            name = (step.get("with") or {}).get("name")
            if isinstance(name, str):
                rendered_artifacts.append(_render_matrix_template(name, selector))
        if artifact not in rendered_artifacts:
            errors.append(
                f"verification check {check_id!r}: artifact {artifact!r} is not uploaded by "
                f"workflow job {job_id!r} for matrix selector {selector!r}"
            )

    return errors


def _validate_executor(root: Path, check: dict[str, Any]) -> list[str]:
    check_id = check.get("id", "<unknown>")
    executor = check.get("executor") or {}
    executor_type = executor.get("type")
    if executor_type == "unittest":
        return _validate_unittest_executor(root, check_id, executor)
    if executor_type == "github-actions":
        return _validate_actions_executor(root, check_id, executor)
    if executor_type is not None:
        return [f"verification check {check_id!r}: unsupported executor type {executor_type!r}"]
    return []


def validate_verification_checks(root: Path, plugins_doc: dict[str, Any]) -> list[str]:
    root = Path(root)
    registry = root / "registry"
    checks_path = registry / "verification-checks.yaml"
    schema_path = registry / "schema" / "verification-checks.schema.json"
    errors: list[str] = []

    if not checks_path.is_file():
        return ["verification checks: missing registry/verification-checks.yaml"]
    if not schema_path.is_file():
        return ["verification checks: missing registry/schema/verification-checks.schema.json"]

    checks_doc = _load_yaml(checks_path)
    errors += _schema_errors(
        checks_doc,
        schema_path,
        "verification-checks.yaml",
    )
    checks = checks_doc.get("checks", []) if isinstance(checks_doc, dict) else []

    check_by_id: dict[str, dict[str, Any]] = {}
    for check in checks:
        if not isinstance(check, dict) or not isinstance(check.get("id"), str):
            continue
        check_id = check["id"]
        if check_id in check_by_id:
            errors.append(f"verification-checks.yaml: duplicate id {check_id!r}")
        check_by_id[check_id] = check
        errors += _validate_executor(root, check)

    for plugin in plugins_doc.get("plugins", []):
        plugin_id = plugin.get("id")
        clients = (plugin.get("verification") or {}).get("clients", {})
        for client_id, evidence in clients.items():
            if not isinstance(evidence, dict):
                continue
            transport = evidence.get("transport")
            strongest_rank = -1
            strongest_level: str | None = None
            for reference in evidence.get("checks", []):
                if not isinstance(reference, dict):
                    continue
                check_id = reference.get("check_id")
                check = check_by_id.get(check_id)
                prefix = f"plugin {plugin_id}.verification.clients.{client_id}"
                if check is None:
                    errors.append(f"{prefix}: references missing verification check {check_id!r}")
                    continue
                contract = (check.get("plugin"), check.get("client"), check.get("transport"))
                actual = (plugin_id, client_id, transport)
                if contract != actual:
                    errors.append(
                        f"{prefix}: verification check {check_id!r} does not match evidence contract; "
                        f"check={contract!r}, evidence={actual!r}"
                    )
                    continue
                level = check.get("evidence_level")
                rank = VERIFICATION_RANK.get(level, -1)
                if rank > strongest_rank:
                    strongest_rank = rank
                    strongest_level = level

            status = evidence.get("status")
            status_rank = VERIFICATION_RANK.get(status)
            if status_rank is not None and status_rank > strongest_rank:
                errors.append(
                    f"plugin {plugin_id}.verification.clients.{client_id}: status {status!r} "
                    f"exceeds strongest executable evidence {strongest_level!r}"
                )

    return errors
