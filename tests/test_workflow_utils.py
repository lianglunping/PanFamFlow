from __future__ import annotations

from pathlib import Path

import pytest

from panfamflow.workflow.scripts.workflow_utils import (
    fasta_lengths,
    iter_fasta_records,
    project_relative_path,
)


def test_project_relative_path_normalizes_relative_input_against_project_root(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "results" / "00_qc" / "input_manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text("{}\n", encoding="utf-8")

    assert project_relative_path(Path("results/00_qc/input_manifest.json"), tmp_path) == Path(
        "results/00_qc/input_manifest.json"
    )


def test_fasta_lengths_streaming_summary(tmp_path: Path) -> None:
    fasta = tmp_path / "sequences.fa"
    fasta.write_text(">a\nAAAA\nAA\n>b description\nTTT\n", encoding="utf-8")
    assert dict(fasta_lengths(fasta)) == {"a": 6, "b": 3}
    assert list(iter_fasta_records(fasta)) == [("a", "AAAAAA"), ("b", "TTT")]


def test_fasta_duplicate_identifier_is_rejected(tmp_path: Path) -> None:
    fasta = tmp_path / "duplicate.fa"
    fasta.write_text(">a\nAA\n>a\nTT\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate FASTA identifier"):
        list(iter_fasta_records(fasta))


def test_run_command_does_not_publish_partial_stdout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from panfamflow.workflow.scripts.workflow_utils import run_command

    output = tmp_path / "result.tsv"

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        stdout = kwargs["stdout"]
        assert hasattr(stdout, "write")
        stdout.write("partial\n")  # type: ignore[union-attr]
        return subprocess.CompletedProcess(args=[], returncode=1)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="exit code 1"):
        run_command(["fake"], stdout_path=output)
    assert not output.exists()
    partials = list(tmp_path.glob(".result.tsv.partial.*"))
    assert len(partials) == 1
    assert partials[0].read_text(encoding="utf-8") == "partial\n"


def test_run_command_atomically_publishes_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    from panfamflow.workflow.scripts.workflow_utils import run_command

    output = tmp_path / "result.tsv"

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        stdout = kwargs["stdout"]
        assert hasattr(stdout, "write")
        stdout.write("complete\n")  # type: ignore[union-attr]
        return subprocess.CompletedProcess(args=[], returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    run_command(["fake"], stdout_path=output)
    assert output.read_text(encoding="utf-8") == "complete\n"
    assert not list(tmp_path.glob(".result.tsv.partial.*"))


def test_materialize_uncompressed_is_atomic_and_reusable(tmp_path: Path) -> None:
    import gzip

    from panfamflow.workflow.scripts.workflow_utils import materialize_uncompressed

    source = tmp_path / "input.fa.gz"
    with gzip.open(source, "wt", encoding="utf-8") as handle:
        handle.write(">a\nACGT\n")
    target = tmp_path / "work" / "input.fa"

    observed = materialize_uncompressed(source, target)
    assert observed == target
    assert target.read_text(encoding="utf-8") == ">a\nACGT\n"
    first_mtime = target.stat().st_mtime_ns
    assert materialize_uncompressed(source, target) == target
    assert target.stat().st_mtime_ns == first_mtime
    assert not list(target.parent.glob(".input.fa.partial.*"))


def test_materialize_uncompressed_refreshes_when_source_changes(tmp_path: Path) -> None:
    import gzip

    from panfamflow.workflow.scripts.workflow_utils import materialize_uncompressed

    source = tmp_path / "input.gff3.gz"
    target = tmp_path / "staged.gff3"
    with gzip.open(source, "wt", encoding="utf-8") as handle:
        handle.write("##gff-version 3\n")
    materialize_uncompressed(source, target)
    with gzip.open(source, "wt", encoding="utf-8") as handle:
        handle.write("##gff-version 3\nchr1\tX\tgene\t1\t2\t.\t+\t.\tID=g1\n")
    materialize_uncompressed(source, target)
    assert "ID=g1" in target.read_text(encoding="utf-8")


def test_materialize_uncompressed_stages_plain_input_in_work_directory(
    tmp_path: Path,
) -> None:
    from panfamflow.workflow.scripts.workflow_utils import materialize_uncompressed

    source = tmp_path / "input.fa"
    source.write_text(">chr1\nACGT\n", encoding="utf-8")
    target = tmp_path / "work" / "input.fa"

    observed = materialize_uncompressed(source, target)

    assert observed == target
    assert target.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
    assert target.resolve() == source.resolve()
    assert materialize_uncompressed(source, target) == target
    sidecar = target.parent / "input.fa.fai"
    sidecar.write_text("sidecar\n", encoding="utf-8")
    assert not source.with_suffix(".fa.fai").exists()
    source.write_text(">chr1\nACGTACGT\n", encoding="utf-8")
    assert materialize_uncompressed(source, target) == target
    assert not sidecar.exists()
    assert target.read_text(encoding="utf-8") == ">chr1\nACGTACGT\n"


def test_iter_gff_rejects_whitespace_padded_coordinates(tmp_path: Path) -> None:
    import pytest

    from panfamflow.workflow.scripts.workflow_utils import iter_gff

    gff = tmp_path / "invalid.gff3"
    gff.write_text(
        "##gff-version 3\nchr1\ttoy\tgene\t1\t 90\t.\t+\t.\tID=Gene1\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="whitespace-padded GFF/GTF coordinate"):
        list(iter_gff(gff))


def test_select_longest_cds_gff3_is_deterministic_and_filters_isoforms(
    tmp_path: Path,
) -> None:
    from panfamflow.workflow.scripts.workflow_utils import select_longest_cds_gff3

    source = tmp_path / "annotation.gff3"
    target = tmp_path / "canonical.gff3"
    source.write_text(
        "##gff-version 3\n"
        "chr1\ttoy\tgene\t1\t180\t.\t+\t.\tID=Gene1\n"
        "chr1\ttoy\tmRNA\t1\t90\t.\t+\t.\tID=Gene1.z;Parent=Gene1\n"
        "chr1\ttoy\texon\t1\t90\t.\t+\t.\tParent=Gene1.z\n"
        "chr1\ttoy\tCDS\t1\t90\t.\t+\t0\tParent=Gene1.z\n"
        "chr1\ttoy\tmRNA\t91\t180\t.\t+\t.\tID=Gene1.a;Parent=Gene1\n"
        "chr1\ttoy\texon\t91\t180\t.\t+\t.\tParent=Gene1.a\n"
        "chr1\ttoy\tCDS\t91\t180\t.\t+\t0\tParent=Gene1.a\n",
        encoding="utf-8",
    )

    summary = select_longest_cds_gff3(source, target)

    observed = target.read_text(encoding="utf-8")
    assert "ID=Gene1.a;Parent=Gene1" in observed
    assert "Parent=Gene1.a" in observed
    assert "Gene1.z" not in observed
    assert summary == {"genes_with_cds": 1, "selected_transcripts": 1, "skipped_genes": 0}


def test_select_longest_cds_gff3_rejects_ambiguous_multi_parent_cds(
    tmp_path: Path,
) -> None:
    from panfamflow.workflow.scripts.workflow_utils import select_longest_cds_gff3

    source = tmp_path / "annotation.gff3"
    source.write_text(
        "##gff-version 3\n"
        "chr1\ttoy\tgene\t1\t90\t.\t+\t.\tID=Gene1\n"
        "chr1\ttoy\tmRNA\t1\t90\t.\t+\t.\tID=Gene1.1;Parent=Gene1\n"
        "chr1\ttoy\tmRNA\t1\t90\t.\t+\t.\tID=Gene1.2;Parent=Gene1\n"
        "chr1\ttoy\tCDS\t1\t90\t.\t+\t0\tParent=Gene1.1,Gene1.2\n",
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="exactly one Parent"):
        select_longest_cds_gff3(source, tmp_path / "canonical.gff3")


def test_read_delimited_table_preserves_one_column_tsv(tmp_path: Path) -> None:
    from panfamflow.workflow.scripts.workflow_utils import read_delimited_table

    source = tmp_path / "members.tsv"
    source.write_text("stable_id\nSpA__GeneA1\nSpB__GeneB1\n", encoding="utf-8")

    observed = read_delimited_table(source)

    assert list(observed.columns) == ["stable_id"]
    assert observed["stable_id"].tolist() == ["SpA__GeneA1", "SpB__GeneB1"]


def test_executable_version_uses_requested_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import subprocess

    from panfamflow.workflow.scripts.workflow_utils import executable_version

    observed: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed.update(kwargs)
        return subprocess.CompletedProcess(command, 0, stdout="tool 1.0\n", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert executable_version(["tool"], ["--version"], timeout=180) == ("tool", "tool 1.0")
    assert observed["timeout"] == 180
