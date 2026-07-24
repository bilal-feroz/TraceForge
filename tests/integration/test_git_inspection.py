from pathlib import Path

from scripts.bootstrap_demo_repo import bootstrap

from traceforge.endpoints import EndpointExtractor
from traceforge.git_inspector import GitInspector


def test_generated_repo_has_real_history_and_endpoint_scope(tmp_path: Path) -> None:
    # The bootstrap intentionally only writes below the repository fixture root.
    from scripts import bootstrap_demo_repo as module

    original_root = module.ROOT
    original_default = module.DEFAULT_TARGET
    try:
        module.ROOT = tmp_path
        module.DEFAULT_TARGET = tmp_path / "fixtures/generated-demo-repositories/demo"
        module.SOURCE = original_root / "services/demo-target"
        repo = bootstrap(module.DEFAULT_TARGET)
    finally:
        module.ROOT = original_root
        module.DEFAULT_TARGET = original_default
        module.SOURCE = original_root / "services/demo-target"

    inspector = GitInspector(repo)
    change = inspector.inspect("demo-baseline", "demo-lock")
    endpoints = EndpointExtractor(inspector).extract(change)
    assert change.base.sha != change.candidate.sha
    assert any(item.path == "/api/visits" and item.method == "POST" for item in endpoints)
