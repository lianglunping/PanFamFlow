"""Small, dependency-light helpers shared by Snakemake scripts."""

import gzip
import hashlib
import json
import math
import os
import shutil
import subprocess
import uuid
from collections import OrderedDict, defaultdict
from collections.abc import Iterable, Iterator, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, TextIO

if TYPE_CHECKING:
    import pandas as pd


def partial_path(path: str | Path) -> Path:
    """Return a unique sibling path that is never mistaken for a final output."""

    target = Path(path)
    return target.with_name(f".{target.name}.partial.{os.getpid()}.{uuid.uuid4().hex}")


def commit_partial(temporary: str | Path, target: str | Path) -> None:
    """Atomically publish a completed temporary file on the same filesystem."""

    source = Path(temporary)
    destination = Path(target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    os.replace(source, destination)


def write_text_atomic(text: str, path: str | Path) -> None:
    """Write text through a uniquely named partial file and atomic rename."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = partial_path(target)
    temporary.write_text(text, encoding="utf-8")
    commit_partial(temporary, target)


def copy_atomic(source: str | Path, target: str | Path) -> None:
    """Copy a file without exposing a partially written destination."""

    destination = Path(target)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = partial_path(destination)
    shutil.copy2(source, temporary)
    commit_partial(temporary, destination)


def materialize_uncompressed(source: str | Path, target: str | Path) -> Path:
    """Return a plain-text path for a possibly gzip-compressed input.

    External tools do not handle ``.gz`` consistently.  Compressed inputs are
    therefore expanded into the rule work directory through an atomic partial
    file.  A lightweight source stamp allows a failed job to reuse a complete
    staged file on retry without re-expanding hundreds of megabytes.  Successful
    Snakemake jobs are skipped at the DAG level, so this cache is only a retry aid.
    """

    source_path = Path(source)
    destination = Path(target)
    if source_path.suffix.lower() != ".gz":
        if not source_path.is_file() or source_path.stat().st_size == 0:
            raise FileNotFoundError(f"Missing or empty input: {source_path}")
        if source_path.absolute() == destination.absolute():
            return source_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        stamp_path = destination.with_name(f".{destination.name}.source.json")
        source_stat = source_path.stat()
        stamp = {
            "source": str(source_path.resolve()),
            "size_bytes": source_stat.st_size,
            "mtime_ns": source_stat.st_mtime_ns,
        }
        cached = None
        if stamp_path.is_file():
            try:
                cached = json.loads(stamp_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                cached = None
        if (
            cached == stamp
            and destination.is_file()
            and destination.stat().st_size > 0
            and (not destination.is_symlink() or destination.resolve() == source_path.resolve())
        ):
            return destination
        temporary = partial_path(destination)
        try:
            temporary.symlink_to(source_path.resolve())
        except OSError:
            temporary.unlink(missing_ok=True)
            shutil.copy2(source_path, temporary)
        commit_partial(temporary, destination)
        for suffix in (".fai", ".gzi"):
            destination.with_name(destination.name + suffix).unlink(missing_ok=True)
        write_text_atomic(json.dumps(stamp, sort_keys=True) + "\n", stamp_path)
        return destination
    if not source_path.is_file() or source_path.stat().st_size == 0:
        raise FileNotFoundError(f"Missing or empty gzip input: {source_path}")

    destination.parent.mkdir(parents=True, exist_ok=True)
    stamp_path = destination.with_name(f".{destination.name}.source.json")
    source_stat = source_path.stat()
    stamp = {
        "source": str(source_path.resolve()),
        "size_bytes": source_stat.st_size,
        "mtime_ns": source_stat.st_mtime_ns,
    }
    if destination.is_file() and destination.stat().st_size > 0 and stamp_path.is_file():
        try:
            cached = json.loads(stamp_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            cached = None
        if cached == stamp:
            return destination

    temporary = partial_path(destination)
    try:
        with gzip.open(source_path, "rb") as source_handle, temporary.open("wb") as target_handle:
            shutil.copyfileobj(source_handle, target_handle, length=4 * 1024 * 1024)
        if temporary.stat().st_size == 0:
            raise RuntimeError(f"Gzip input expanded to an empty file: {source_path}")
        commit_partial(temporary, destination)
        write_text_atomic(json.dumps(stamp, sort_keys=True) + "\n", stamp_path)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination


def ensure_nonempty(path: str | Path) -> None:
    """Reject missing or zero-byte outputs before completion metadata is written."""

    target = Path(path)
    if not target.is_file() or target.stat().st_size == 0:
        raise RuntimeError(f"Expected non-empty output was not produced: {target}")


def open_text(path: str | Path, mode: str = "rt") -> TextIO:
    file_path = Path(path)
    if file_path.suffix == ".gz":
        return gzip.open(file_path, mode, encoding="utf-8")  # type: ignore[return-value]
    return file_path.open(mode, encoding="utf-8")


def read_delimited_table(path: str | Path, **kwargs: Any) -> "pd.DataFrame":
    """Read CSV/TSV deterministically without delimiter sniffing on one-column files."""

    import pandas as pd

    source = Path(path)
    suffix = source.suffix.lower()
    if suffix == ".csv":
        separator = ","
    elif suffix in {".tsv", ".tab"}:
        separator = "\t"
    else:
        first_data_line = ""
        with open_text(source) as handle:
            for raw in handle:
                if raw.strip() and not raw.startswith("#"):
                    first_data_line = raw
                    break
        separator = "\t" if "\t" in first_data_line or "," not in first_data_line else ","
    return pd.read_csv(source, sep=separator, **kwargs)


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while chunk := handle.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def iter_fasta_records(path: str | Path) -> Iterator[tuple[str, str]]:
    """Yield FASTA records one at a time while rejecting duplicate identifiers."""

    seen: set[str] = set()
    identifier: str | None = None
    chunks: list[str] = []
    with open_text(path) as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if identifier is not None:
                    yield identifier, "".join(chunks)
                identifier = line[1:].split()[0]
                if identifier in seen:
                    raise ValueError(f"Duplicate FASTA identifier {identifier!r} in {path}")
                seen.add(identifier)
                chunks = []
            else:
                if identifier is None:
                    raise ValueError(f"FASTA sequence encountered before header in {path}")
                chunks.append(line)
    if identifier is not None:
        yield identifier, "".join(chunks)


def read_fasta(path: str | Path) -> OrderedDict[str, str]:
    sequences: OrderedDict[str, str] = OrderedDict()
    for identifier, sequence in iter_fasta_records(path):
        sequences[identifier] = sequence
    return sequences


def fasta_lengths(path: str | Path) -> OrderedDict[str, int]:
    """Read only FASTA identifiers and sequence lengths without storing sequences."""

    lengths: OrderedDict[str, int] = OrderedDict()
    identifier: str | None = None
    sequence_length = 0
    with open_text(path) as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if identifier is not None:
                    lengths[identifier] = sequence_length
                identifier = line[1:].split()[0]
                if identifier in lengths:
                    raise ValueError(f"Duplicate FASTA identifier {identifier!r} in {path}")
                sequence_length = 0
            else:
                if identifier is None:
                    raise ValueError(f"FASTA sequence encountered before header in {path}")
                sequence_length += len(line)
    if identifier is not None:
        lengths[identifier] = sequence_length
    return lengths


def write_fasta(
    records: Mapping[str, str] | Iterable[tuple[str, str]],
    path: str | Path,
    width: int = 60,
) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = partial_path(target)
    items = records.items() if isinstance(records, Mapping) else records
    with temporary.open("w", encoding="utf-8") as handle:
        for identifier, sequence in items:
            handle.write(f">{identifier}\n")
            for start in range(0, len(sequence), width):
                handle.write(sequence[start : start + width] + "\n")
    commit_partial(temporary, target)


def parse_gff_attributes(text: str) -> dict[str, str]:
    attributes: dict[str, str] = {}
    for item in text.strip().strip(";").split(";"):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            key, value = item.split("=", 1)
        elif " " in item:
            key, value = item.split(" ", 1)
            value = value.strip().strip('"')
        else:
            continue
        attributes[key.strip()] = value.strip()
    return attributes


def first_parent(value: str | None) -> str | None:
    if value is None:
        return None
    return value.split(",", 1)[0]


def iter_gff(path: str | Path) -> Iterator[dict[str, Any]]:
    with open_text(path) as handle:
        for line_number, raw in enumerate(handle, start=1):
            if not raw.strip() or raw.startswith("#"):
                continue
            fields = raw.rstrip("\n").split("\t")
            if len(fields) != 9:
                raise ValueError(f"Expected 9 GFF/GTF columns at {path}:{line_number}")
            seqid, source, feature, start, end, score, strand, phase, attributes = fields
            if start != start.strip() or end != end.strip():
                raise ValueError(
                    f"Found whitespace-padded GFF/GTF coordinate at {path}:{line_number}"
                )
            start_value = int(start)
            end_value = int(end)
            if start_value < 1 or end_value < start_value:
                raise ValueError(
                    f"Invalid GFF/GTF coordinate interval at {path}:{line_number}: "
                    f"{start_value}-{end_value}"
                )
            yield {
                "seqid": seqid,
                "source": source,
                "feature": feature,
                "start": start_value,
                "end": end_value,
                "score": score,
                "strand": strand,
                "phase": phase,
                "attributes": parse_gff_attributes(attributes),
                "raw": raw,
            }


def select_longest_cds_gff3(source: str | Path, target: str | Path) -> dict[str, int]:
    """Write one deterministic protein-coding transcript per gene from strict GFF3.

    This portable selector is intentionally narrower than AGAT.  It accepts a
    direct ``gene -> transcript -> child`` hierarchy expressed with GFF3
    ``ID``/``Parent`` attributes and fails closed when parentage is ambiguous.
    CDS lengths are summed after rejecting overlapping CDS segments.  Ties are
    resolved by the lexicographically smallest transcript ID.
    """

    source_path = Path(source)
    source_text = source_path.read_text(encoding="utf-8")
    if any(line.strip() == "##FASTA" for line in source_text.splitlines()):
        raise ValueError(
            f"Portable canonical selection does not accept embedded FASTA: {source_path}"
        )

    records = list(iter_gff(source_path))
    transcript_types = {"mrna", "transcript", "ncrna", "trna", "rrna"}
    genes: dict[str, dict[str, Any]] = {}
    transcripts: dict[str, tuple[str, dict[str, Any]]] = {}

    for record in records:
        feature_name = str(record["feature"]).lower()
        attributes = record["attributes"]
        if feature_name == "gene":
            gene_id = attributes.get("ID")
            if not gene_id:
                raise ValueError(f"Portable canonical selection requires gene ID in {source_path}")
            if gene_id in genes:
                raise ValueError(f"Duplicate gene ID {gene_id!r} in {source_path}")
            genes[gene_id] = record
        elif feature_name in transcript_types:
            transcript_id = attributes.get("ID")
            parent_text = attributes.get("Parent")
            if not transcript_id or not parent_text:
                raise ValueError(
                    "Portable canonical selection requires transcript ID and Parent "
                    f"in {source_path}"
                )
            parents = [item for item in parent_text.split(",") if item]
            if len(parents) != 1:
                raise ValueError(
                    f"Transcript {transcript_id!r} must have exactly one Parent in {source_path}"
                )
            if transcript_id in transcripts:
                raise ValueError(f"Duplicate transcript ID {transcript_id!r} in {source_path}")
            transcripts[transcript_id] = (parents[0], record)

    for transcript_id, (gene_id, _) in transcripts.items():
        if gene_id not in genes:
            raise ValueError(
                f"Transcript {transcript_id!r} references unknown gene {gene_id!r} in {source_path}"
            )

    children: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        feature_name = str(record["feature"]).lower()
        if feature_name == "gene" or feature_name in transcript_types:
            continue
        parent_text = record["attributes"].get("Parent")
        if not parent_text:
            continue
        parents = [item for item in parent_text.split(",") if item]
        if len(parents) != 1:
            raise ValueError(
                f"Child feature {feature_name!r} must have exactly one Parent in {source_path}"
            )
        parent = parents[0]
        if parent not in transcripts:
            if feature_name in {"cds", "exon"}:
                raise ValueError(
                    f"Child feature {feature_name!r} references unknown transcript "
                    f"{parent!r} in {source_path}"
                )
            continue
        children[parent].append(record)

    cds_lengths: dict[str, int] = {}
    for transcript_id in transcripts:
        cds_records = [
            record
            for record in children.get(transcript_id, [])
            if str(record["feature"]).lower() == "cds"
        ]
        if not cds_records:
            continue
        ordered = sorted(
            cds_records,
            key=lambda record: (
                str(record["seqid"]),
                str(record["strand"]),
                int(record["start"]),
                int(record["end"]),
            ),
        )
        previous: dict[str, Any] | None = None
        for record in ordered:
            if (
                previous is not None
                and record["seqid"] == previous["seqid"]
                and record["strand"] == previous["strand"]
                and int(record["start"]) <= int(previous["end"])
            ):
                raise ValueError(
                    f"Overlapping CDS segments for transcript {transcript_id!r} in {source_path}"
                )
            previous = record
        cds_lengths[transcript_id] = sum(
            int(record["end"]) - int(record["start"]) + 1 for record in ordered
        )

    transcripts_by_gene: defaultdict[str, list[str]] = defaultdict(list)
    for transcript_id, (gene_id, _) in transcripts.items():
        if transcript_id in cds_lengths:
            transcripts_by_gene[gene_id].append(transcript_id)

    selected_by_gene: dict[str, str] = {}
    for gene_id, candidates in transcripts_by_gene.items():
        selected_by_gene[gene_id] = sorted(
            candidates,
            key=lambda transcript_id: (-cds_lengths[transcript_id], transcript_id),
        )[0]
    selected_transcripts = set(selected_by_gene.values())
    selected_genes = set(selected_by_gene)
    if not selected_transcripts:
        raise ValueError(f"No protein-coding transcript with CDS was found in {source_path}")

    comments = [line for line in source_text.splitlines() if line.startswith("#")]
    output_lines = comments
    for record in records:
        feature_name = str(record["feature"]).lower()
        attributes = record["attributes"]
        keep = False
        if feature_name == "gene":
            keep = attributes.get("ID") in selected_genes
        elif feature_name in transcript_types:
            keep = attributes.get("ID") in selected_transcripts
        else:
            keep = attributes.get("Parent") in selected_transcripts
        if keep:
            output_lines.append(str(record["raw"]).rstrip("\n"))
    write_text_atomic("\n".join(output_lines) + "\n", target)

    return {
        "genes_with_cds": len(selected_genes),
        "selected_transcripts": len(selected_transcripts),
        "skipped_genes": len(genes) - len(selected_genes),
    }


def save_table(df: "pd.DataFrame", tsv: str | Path, xlsx: str | Path | None = None) -> None:
    import pandas as pd

    tsv_path = Path(tsv)
    tsv_path.parent.mkdir(parents=True, exist_ok=True)
    tsv_temporary = partial_path(tsv_path)
    xlsx_path = Path(xlsx) if xlsx is not None else None
    xlsx_temporary = partial_path(xlsx_path) if xlsx_path is not None else None
    df.to_csv(tsv_temporary, sep="\t", index=False, na_rep="NA")
    if xlsx_path is not None and xlsx_temporary is not None:
        xlsx_path.parent.mkdir(parents=True, exist_ok=True)
        with pd.ExcelWriter(xlsx_temporary, engine="openpyxl") as writer:
            df.to_excel(writer, sheet_name="data", index=False)
    commit_partial(tsv_temporary, tsv_path)
    if xlsx_path is not None and xlsx_temporary is not None:
        commit_partial(xlsx_temporary, xlsx_path)


def save_workbook(tables: Mapping[str, "pd.DataFrame"], path: str | Path) -> None:
    import pandas as pd

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = partial_path(target)
    with pd.ExcelWriter(temporary, engine="openpyxl") as writer:
        for name, table in tables.items():
            safe_name = name[:31] or "data"
            table.to_excel(writer, sheet_name=safe_name, index=False)
    commit_partial(temporary, target)


def write_json(data: Any, path: str | Path) -> None:
    write_text_atomic(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        path,
    )


def run_command(
    command: Sequence[str],
    *,
    stdout_path: str | Path | None = None,
    stderr_path: str | Path | None = None,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> None:
    stdout_target = Path(stdout_path) if stdout_path is not None else None
    stdout_temporary = partial_path(stdout_target) if stdout_target is not None else None
    if stdout_target is not None:
        stdout_target.parent.mkdir(parents=True, exist_ok=True)
    if stderr_path is not None:
        Path(stderr_path).parent.mkdir(parents=True, exist_ok=True)
    stdout_handle = (
        stdout_temporary.open("w", encoding="utf-8") if stdout_temporary is not None else None
    )
    stderr_handle = Path(stderr_path).open("w", encoding="utf-8") if stderr_path else None  # noqa: SIM115
    try:
        completed = subprocess.run(
            list(command),
            check=False,
            cwd=Path(cwd) if cwd is not None else None,
            env={**os.environ, **dict(env or {})},
            stdout=stdout_handle,
            stderr=stderr_handle,
            text=True,
        )
    finally:
        if stdout_handle is not None:
            stdout_handle.close()
        if stderr_handle is not None:
            stderr_handle.close()
    if completed.returncode != 0:
        rendered = " ".join(command)
        partial_note = (
            f" Partial stdout retained at {stdout_temporary}."
            if stdout_temporary is not None and stdout_temporary.exists()
            else ""
        )
        raise RuntimeError(
            f"Command failed with exit code {completed.returncode}: {rendered}.{partial_note}"
        )
    if stdout_target is not None and stdout_temporary is not None:
        commit_partial(stdout_temporary, stdout_target)


def executable_version(
    candidates: Sequence[str], arguments: Sequence[str], *, timeout: int = 30
) -> tuple[str, str]:
    for executable in candidates:
        try:
            completed = subprocess.run(
                [executable, *arguments],
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
        text = (completed.stdout or completed.stderr).strip().splitlines()
        return executable, text[0] if text else "version unavailable"
    raise FileNotFoundError(f"None of the executables were found: {', '.join(candidates)}")


def reverse_complement(sequence: str) -> str:
    table = str.maketrans("ACGTRYMKBDHVNacgtrymkbdhvn", "TGCAYRKMVHDBNtgcayrkmvhdbn")
    return sequence.translate(table)[::-1]


def split_multi_value(value: Any) -> list[str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return []
    text = str(value).strip()
    if not text or text.upper() == "NA":
        return []
    normalized = text.replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


def resolve_column(
    df: "pd.DataFrame", candidates: Sequence[str], required: bool = True
) -> str | None:
    lookup = {column.strip().lower().replace(" ", "_"): column for column in df.columns}
    for candidate in candidates:
        key = candidate.strip().lower().replace(" ", "_")
        if key in lookup:
            return lookup[key]
    if required:
        raise ValueError(f"None of the required columns were found: {', '.join(candidates)}")
    return None
