from __future__ import annotations

from pathlib import Path
from typing import NoReturn

from typer.testing import CliRunner

from panfamflow.cli import app

TOY_CONFIG = Path(__file__).parents[1] / "examples" / "toy" / "config.yaml"
runner = CliRunner()


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "0.1.2a0" in result.stdout


def test_list_modules() -> None:
    result = runner.invoke(app, ["list-modules"])
    assert result.exit_code == 0
    assert "pan_family" in result.stdout
    assert "expression" in result.stdout


def test_validate_toy_qc() -> None:
    result = runner.invoke(app, ["validate", "-c", str(TOY_CONFIG), "-m", "qc"])
    assert result.exit_code == 0, result.stdout
    assert "Validation passed" in result.stdout


def test_status_reports_missing_engine_without_traceback(monkeypatch: object) -> None:
    def missing_engine(_: object) -> NoReturn:
        raise FileNotFoundError(2, "No such file or directory", "snakemake")

    monkeypatch.setattr("panfamflow.cli.execute_capture", missing_engine)  # type: ignore[attr-defined]
    result = runner.invoke(app, ["status", "-c", str(TOY_CONFIG)])
    assert result.exit_code == 127
    assert "Launch error" in result.stdout
    assert "snakemake" in result.stdout
    assert "Traceback" not in result.stdout


def test_init_is_non_destructive(tmp_path: Path) -> None:
    destination = tmp_path / "project"
    result = runner.invoke(app, ["init", str(destination)])
    assert result.exit_code == 0, result.stdout
    assert (destination / "config.yaml").is_file()
    assert (destination / ".panfamflow" / "config.schema.json").is_file()
    second = runner.invoke(app, ["init", str(destination), "--force"])
    assert second.exit_code == 2
    assert "Refusing to overwrite" in second.stdout
