from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from traceforge.git_inspector import GitInspectionError, GitInspector
from traceforge.models import AffectedEndpoint, ChangeSet

_FASTAPI_ROUTE = re.compile(
    r"^\s*@(?P<router>[A-Za-z_][\w.]*)\."
    r"(?P<method>get|post|put|patch|delete|head|options)\(\s*"
    r"(?P<quote>['\"])(?P<path>/[^'\"]*)(?P=quote)",
    re.MULTILINE,
)
_FLASK_ROUTE = re.compile(
    r"^\s*@(?P<router>[A-Za-z_][\w.]*)\.route\(\s*"
    r"(?P<quote>['\"])(?P<path>/[^'\"]*)(?P=quote)"
    r"(?P<args>[^)]*)\)",
    re.MULTILINE,
)
_DIFF_HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,(?P<count>\d+))? @@")


def _line_number(text: str, position: int) -> int:
    return text.count("\n", 0, position) + 1


def _example_from_openapi(operation: dict[str, Any]) -> Any:
    body = operation.get("requestBody", {})
    content = body.get("content", {}) if isinstance(body, dict) else {}
    for media in ("application/json", "application/*+json"):
        schema_entry = content.get(media)
        if not isinstance(schema_entry, dict):
            continue
        if "example" in schema_entry:
            return schema_entry["example"]
        schema = schema_entry.get("schema", {})
        if isinstance(schema, dict) and "example" in schema:
            return schema["example"]
    return None


def candidate_changed_lines(diff: str) -> dict[str, set[int]]:
    """Return actual added/replaced candidate line numbers grouped by file."""
    changed: defaultdict[str, set[int]] = defaultdict(set)
    current_file: str | None = None
    candidate_line: int | None = None
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:].replace("\\", "/")
            candidate_line = None
            continue
        match = _DIFF_HUNK.match(line)
        if match:
            candidate_line = int(match.group("start"))
            continue
        if current_file is None or candidate_line is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            changed[current_file].add(candidate_line)
            candidate_line += 1
        elif line.startswith("-") and not line.startswith("---"):
            continue
        else:
            candidate_line += 1
    return dict(changed)


class EndpointExtractor:
    def __init__(self, inspector: GitInspector) -> None:
        self.inspector = inspector

    def _from_python(self, path: str, ref: str) -> list[AffectedEndpoint]:
        try:
            source = self.inspector.file_at(ref, path)
        except GitInspectionError:
            return []
        endpoints: list[AffectedEndpoint] = []
        for match in _FASTAPI_ROUTE.finditer(source):
            endpoints.append(
                AffectedEndpoint(
                    path=match.group("path"),
                    method=match.group("method"),
                    source_file=path,
                    line=_line_number(source, match.start()),
                    confidence=0.65,
                    reason="route declaration is in a source file touched by the change",
                    request_body_example={},
                )
            )
        for match in _FLASK_ROUTE.finditer(source):
            method_match = re.search(r"methods\s*=\s*\[\s*['\"](\w+)['\"]", match.group("args"))
            method = method_match.group(1) if method_match else "GET"
            endpoints.append(
                AffectedEndpoint(
                    path=match.group("path"),
                    method=method,
                    source_file=path,
                    line=_line_number(source, match.start()),
                    confidence=0.6,
                    reason="Flask-compatible route declaration in an affected source file",
                    request_body_example={},
                )
            )
        return endpoints

    def _from_openapi(self, path: str, ref: str) -> list[AffectedEndpoint]:
        if Path(path).suffix.lower() != ".json":
            return []
        try:
            document = json.loads(self.inspector.file_at(ref, path))
        except (GitInspectionError, json.JSONDecodeError):
            return []
        paths = document.get("paths", {}) if isinstance(document, dict) else {}
        endpoints: list[AffectedEndpoint] = []
        if not isinstance(paths, dict):
            return endpoints
        for route, path_item in paths.items():
            if (
                not isinstance(route, str)
                or not route.startswith("/")
                or not isinstance(path_item, dict)
            ):
                continue
            for method in ("get", "post", "put", "patch", "delete", "head", "options"):
                operation = path_item.get(method)
                if not isinstance(operation, dict):
                    continue
                endpoints.append(
                    AffectedEndpoint(
                        path=route,
                        method=method,
                        source_file=path,
                        line=1,
                        confidence=0.9,
                        reason="operation declared in candidate OpenAPI document",
                        request_body_example=_example_from_openapi(operation),
                    )
                )
        return endpoints

    @staticmethod
    def _rank_changed_handlers(
        endpoints: list[AffectedEndpoint],
        changed_lines: dict[str, set[int]],
    ) -> list[AffectedEndpoint]:
        by_file: defaultdict[str, list[AffectedEndpoint]] = defaultdict(list)
        for endpoint in endpoints:
            by_file[endpoint.source_file].append(endpoint)
        ranked: list[AffectedEndpoint] = []
        for path, file_endpoints in by_file.items():
            ordered = sorted(file_endpoints, key=lambda item: item.line)
            additions = changed_lines.get(path, set())
            for index, endpoint in enumerate(ordered):
                next_line = ordered[index + 1].line if index + 1 < len(ordered) else 2**31
                handler_changed = any(endpoint.line <= line < next_line for line in additions)
                if handler_changed:
                    ranked.append(
                        endpoint.model_copy(
                            update={
                                "confidence": 0.99,
                                "reason": "candidate diff changes this route handler",
                            }
                        )
                    )
                else:
                    ranked.append(endpoint)
        return ranked

    def extract(self, change: ChangeSet) -> list[AffectedEndpoint]:
        changed_paths = {item.path for item in change.files}
        candidate_files = self.inspector.list_files(change.candidate.sha)
        api_candidates = [
            path
            for path in candidate_files
            if path in changed_paths
            and (
                path.endswith(".py") or Path(path).name.lower() in {"openapi.json", "swagger.json"}
            )
        ]
        endpoints: list[AffectedEndpoint] = []
        for path in api_candidates:
            endpoints.extend(self._from_python(path, change.candidate.sha))
            endpoints.extend(self._from_openapi(path, change.candidate.sha))

        if not endpoints:
            affected_dirs = {str(Path(path).parent).replace("\\", "/") for path in changed_paths}
            for path in candidate_files:
                normalized_parent = str(Path(path).parent).replace("\\", "/")
                if path.endswith(".py") and normalized_parent in affected_dirs:
                    endpoints.extend(self._from_python(path, change.candidate.sha))

        endpoints = self._rank_changed_handlers(
            endpoints, candidate_changed_lines(change.unified_diff)
        )
        unique: dict[tuple[str, str], AffectedEndpoint] = {}
        for endpoint in endpoints:
            key = (endpoint.method, endpoint.path)
            existing = unique.get(key)
            if existing is None or endpoint.confidence > existing.confidence:
                unique[key] = endpoint
        return sorted(
            unique.values(),
            key=lambda endpoint: (-endpoint.confidence, endpoint.path, endpoint.method),
        )
