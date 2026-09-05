"""Fresh external synthetic SQLite only: exact C13 passages, never copied user data."""
import hashlib
import sqlite3
from pathlib import Path

from backend.infrastructure.composition.factories.local_browser import Read15RuntimeTarget

PASSAGES = (
    ("r2.synth.bilan", "Le bilan fonctionnel regroupe les postes selon leur fonction : emplois stables, "
     "ressources stables, actif circulant d'exploitation, passif circulant d'exploitation et trésorerie. "
     "Le dossier fournit les règles de classement et toutes les données nécessaires."),
    ("r2.synth.bfr", "Pour le cas fictif sans éléments hors exploitation : FRNG = ressources stables - "
     "emplois stables ; BFR = actif circulant d'exploitation - passif circulant d'exploitation ; "
     "trésorerie nette = FRNG - BFR. Les données doivent permettre de confronter calcul et interprétation."),
    ("r2.synth.cas", "Entreprise fictive Atelier Horizon. Montants en milliers d'euros : emplois stables "
     "180 ; ressources stables 220 ; actif circulant d'exploitation 85 ; passif circulant d'exploitation "
     "60 ; trésorerie active 18 ; trésorerie passive 3. Aucun retraitement, valeur manquante ou élément "
     "hors exploitation n'est à supposer. Créer des questions progressives en trois dossiers, sur 20 "
     "points et 60 minutes."),
)


def synthetic_target(root: Path) -> Read15RuntimeTarget:
    repo = Path(__file__).resolve().parents[2]
    assert not root.resolve().is_relative_to(repo)
    root.mkdir(parents=True, exist_ok=False)
    path = root / "r2-synthetic.sqlite"
    connection = sqlite3.connect(path)
    try:
        connection.executescript("""
            CREATE TABLE object_registry(object_id TEXT PRIMARY KEY, object_type TEXT NOT NULL);
            CREATE TABLE notion(id TEXT PRIMARY KEY, canonical_label TEXT, identity_status TEXT);
            CREATE TABLE resource(id TEXT PRIMARY KEY, resource_type TEXT,
                                  canonical_title TEXT, identity_status TEXT);
            CREATE TABLE search_chunk(id TEXT PRIMARY KEY, object_id TEXT, chunk_type TEXT,
                                      chunk_hash TEXT, text TEXT, status TEXT);
            CREATE VIRTUAL TABLE search_chunk_fts USING fts5(
                text, content='search_chunk', content_rowid='rowid');
        """)
        for ref, text in PASSAGES:
            source = "resource:" + ref
            connection.execute("INSERT INTO object_registry VALUES (?, 'RESOURCE')", (source,))
            connection.execute("INSERT INTO resource VALUES (?, 'COURSE', ?, 'ACTIVE')",
                               (source, "SUPPORT_SYNTHETIQUE_R2"))
            connection.execute("INSERT INTO search_chunk VALUES (?, ?, 'BODY', ?, ?, 'CURRENT')",
                               (ref, source, hashlib.sha256(text.encode()).hexdigest(), text))
        connection.execute("INSERT INTO search_chunk_fts(rowid, text) SELECT rowid, text FROM search_chunk")
        connection.commit()
    finally:
        connection.close()
    return Read15RuntimeTarget(path, root, hashlib.sha256(path.read_bytes()).hexdigest())
