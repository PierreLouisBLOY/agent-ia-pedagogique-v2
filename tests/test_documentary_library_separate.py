"""Synthetic packages only. The actual supplied archive is imported separately by Application."""
import csv
import hashlib
import io
import json
import sqlite3
import zipfile

import pytest

from backend.adapters.inbound.cli.documentary_library import main
from backend.adapters.outbound.resource_library.documentary_package import LocalDocumentaryPackage
from backend.infrastructure.composition.factories.documentary_library import (
    build_documentary_library,
)
from backend.modules.resource_library.contracts.dto.documentary_library import DocumentarySnapshot


def packed(value):
    return json.dumps(value, ensure_ascii=False).encode()


def archive_fixture(tmp_path):
    sources = [{"id": "DEC-01", "url": "https://example.org/synthetic-dec", "publisher": "SYNTHETIC"},
               {"id": "ORA-01", "url": "https://example.org/synthetic-ora", "publisher": "SYNTHETIC"}]
    docs = [{"id": key, "organisation": org, "title": "SYNTHETIC DOCUMENT", "sources": [source],
        "classification": "SYNTHÈSE PÉDAGOGIQUE ORIGINALE DE SOURCES PUBLIQUES",
        "pedagogical_approval": "NON_VALIDÉE_PAR_PROPRIÉTAIRE"}
        for key, org, source in [("D01", "DECATHLON", "DEC-01"), ("O01", "ORANGE", "ORA-01")]]
    files = {}
    docs[0]["sources"] = ["ORA-01", "DEC-01"]  # Order must survive the normalized relational index.
    for key, prefix in [("D01", "01_DECATHLON"), ("O01", "02_ORANGE")]:
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as docx:
            docx.writestr("word/document.xml", f'''<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>
              <w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>{key} SYNTHETIC DOCUMENT</w:t></w:r></w:p>
              <w:p><w:r><w:t>SYNTHETIC REFORMULATION NOT PRIMARY QUOTATION</w:t></w:r></w:p>
              <w:tbl><w:tr><w:tc><w:p><w:r><w:t>Header</w:t></w:r></w:p></w:tc></w:tr><w:tr><w:tc><w:p><w:r><w:t>Value</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
            </w:body></w:document>''')
        files[prefix + ".docx"] = data.getvalue()
    files["05_MANIFESTE_SOURCES_POUR_V2.json"] = packed({"schema": "v2.documentary_source_package.1.0",
        "owner_approval": "PENDING", "automatic_ingestion_allowed": False, "documents": docs, "sources": sources})
    csv_text = io.StringIO()
    writer = csv.DictWriter(csv_text, fieldnames=["id", "url", "publisher"], delimiter=";")
    writer.writeheader()
    writer.writerows(sources)
    files["04_INDEX_SOURCES_VERIFIEES.csv"] = csv_text.getvalue().encode()
    files["08_MANIFESTE_SHA256.json"] = packed({"count": len(files), "files": [{"filename": name,
        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()} for name, raw in files.items()]})
    path = tmp_path / "SYNTHETIC-input.zip"
    with zipfile.ZipFile(path, "w") as archive:
        for name, raw in files.items():
            archive.writestr("SYNTHETIC/" + name, raw)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def test_application_import_idempotent_reopen_read_only_and_originals(tmp_path):
    path, checksum = archive_fixture(tmp_path)
    db = tmp_path / "library" / "documentary.sqlite"
    app = build_documentary_library(database=db, data_root=tmp_path, archive=path, archive_sha256=checksum)
    imported = app.execute("import")
    assert imported["state"] == "IMPORTED_NOT_ADMITTED"
    assert imported["authority"]["generation_right"] == "NONE"
    initial_bytes = db.read_bytes()
    assert app.execute("import")["state"] == "ALREADY_PRESENT_UNCHANGED"
    assert db.read_bytes() == initial_bytes
    before = db.read_bytes()
    read = build_documentary_library(database=db, data_root=tmp_path)
    summary = read.execute("summary")["packages"][0]
    assert (summary["organizations"], summary["documents"], summary["sources"], summary["files"]) == (2, 2, 2, 5)
    doc = read.execute("read", archive=checksum, document="D01")
    assert doc["document"]["blocks"][-1] == {"kind": "TABLE", "rows": [["Header"], ["Value"]]}
    assert [s["id"] for s in doc["sources"]] == ["ORA-01", "DEC-01"]
    assert read.execute("verify", archive=checksum)["files"] == 5
    with pytest.raises(ValueError, match="IMPORT_NOT_CONFIGURED"):
        read.execute("import")
    with pytest.raises(ValueError, match="ID_REJECTED"):
        read.execute("read", archive=checksum, document="D01' OR 1=1")
    assert db.read_bytes() == before


def test_wrong_hash_or_foreign_database_is_never_modified(tmp_path):
    path, checksum = archive_fixture(tmp_path)
    absent = tmp_path / "must-not-exist.sqlite"
    with pytest.raises(ValueError, match="ARCHIVE_CHANGED"):
        build_documentary_library(database=absent, data_root=tmp_path, archive=path, archive_sha256="0" * 64)
    assert not absent.exists()
    foreign = tmp_path / "SYNTHETIC-canonical.sqlite"
    with sqlite3.connect(foreign) as connection:
        connection.execute("CREATE TABLE canonical(id TEXT)")
    before = foreign.read_bytes()
    with pytest.raises(ValueError, match="FOREIGN_DATABASE_REFUSED"):
        build_documentary_library(database=foreign, data_root=tmp_path, archive=path, archive_sha256=checksum)
    assert foreign.read_bytes() == before
    assert not foreign.with_suffix(".sqlite-wal").exists()


def test_conflicting_snapshot_and_corrupted_index_are_refused(tmp_path):
    from backend.adapters.outbound.resource_library.documentary_sqlite import DocumentarySQLite

    path, checksum = archive_fixture(tmp_path)
    db = tmp_path / "isolated-library.sqlite"
    app = build_documentary_library(database=db, data_root=tmp_path, archive=path, archive_sha256=checksum)
    app.execute("import")
    before = db.read_bytes()
    snapshot, files = LocalDocumentaryPackage(path, checksum).read()
    changed = snapshot.as_dict()
    changed["documents"][0]["metadata"]["title"] = "Conflicting title for the same archive"
    with pytest.raises(ValueError, match="IMMUTABLE_CONFLICT"):
        DocumentarySQLite(db, allowed_root=tmp_path).append(DocumentarySnapshot(changed), files)
    assert db.read_bytes() == before
    # Deliberate corruption of this synthetic fixture only, never a user library.
    with sqlite3.connect(db) as connection:
        connection.execute("UPDATE documentary_source SET payload='{}' WHERE id='DEC-01'")
    with pytest.raises(ValueError, match="STORED_INDEX_CHANGED"):
        app.execute("summary")


@pytest.mark.parametrize("mutation", ["dangling_source", "body_changed", "false_authority", "wrong_origin"])
def test_snapshot_refuses_broken_links_rewritten_text_and_invented_authority(tmp_path, mutation):
    path, checksum = archive_fixture(tmp_path)
    snapshot, _ = LocalDocumentaryPackage(path, checksum).read()
    value = snapshot.as_dict()
    if mutation == "dangling_source":
        value["documents"][0]["source_ids"] = ["NOT-PRESENT"]
    elif mutation == "body_changed":
        value["documents"][0]["blocks"][0]["text"] += " invented"
    elif mutation == "false_authority":
        value["authority"]["canonical_admission"] = "ADMITTED"
    else:
        value["documents"][0]["origin"]["file_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        DocumentarySnapshot(value)


def test_actual_cli_import_summary_document_and_verify(tmp_path, capsys):
    path, checksum = archive_fixture(tmp_path)
    db = tmp_path / "cli-library.sqlite"
    args = ["--database", str(db), "--data-root", str(tmp_path)]
    assert main(["import", *args, "--archive", str(path), "--archive-sha256", checksum]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "IMPORTED_NOT_ADMITTED"
    assert main(["summary", *args]) == 0
    assert len(json.loads(capsys.readouterr().out)["packages"]) == 1
    assert main(["read", *args, "--package", checksum, "--document", "O01"]) == 0
    assert json.loads(capsys.readouterr().out)["document"]["id"] == "O01"
    assert main(["verify", *args, "--package", checksum]) == 0
    assert json.loads(capsys.readouterr().out)["state"] == "ALL_ORIGINAL_FILES_VERIFIED"
