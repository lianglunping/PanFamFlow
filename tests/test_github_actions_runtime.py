"""Release workflow contracts for supported GitHub-hosted runtimes."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UPLOAD_ARTIFACT_V7 = "actions/upload-artifact@043fb46d1a93c77aae656e7c1c64a875d1fc6a0a # v7.0.1"
CONFIGURE_PAGES_V6 = "actions/configure-pages@45bfe0192ca1faeb007ade9deae92b16b8254a0d # v6.0.0"
NODE20_UPLOAD_ARTIFACT = "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"


def test_artifact_uploads_use_pinned_node24_release() -> None:
    for workflow in (
        ROOT / ".github/workflows/ci.yml",
        ROOT / ".github/workflows/publish-expression-container.yml",
    ):
        text = workflow.read_text(encoding="utf-8")
        assert UPLOAD_ARTIFACT_V7 in text
        assert NODE20_UPLOAD_ARTIFACT not in text


def test_pages_configuration_uses_pinned_node24_release() -> None:
    text = (ROOT / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    assert CONFIGURE_PAGES_V6 in text
    assert "actions/configure-pages@v5" not in text
