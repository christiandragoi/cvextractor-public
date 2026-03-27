"""
candidates_manager.py
=====================
Filesystem-based candidate storage for the CV Extractor app.

Each candidate gets a folder under `candidates/` with:
  - original CV file
  - extracted JSON data
  - generated Word documents
  - ID scans
  - identcheck data and filled templates
"""

import os
import json
import shutil
from pathlib import Path
from datetime import datetime

CANDIDATES_DIR = Path(__file__).parent / "candidates"
CANDIDATES_DIR.mkdir(exist_ok=True)


def _sanitize_name(name: str) -> str:
    """Sanitize a candidate name for use as a folder name."""
    # Remove problematic chars, keep unicode letters
    safe = "".join(c if c.isalnum() or c in ("_", "-", " ") else "" for c in name)
    return safe.strip().replace("  ", " ").replace(" ", "_") or "Unknown"


def _candidate_dir(name: str) -> Path:
    """Get or create the directory for a candidate."""
    d = CANDIDATES_DIR / _sanitize_name(name)
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# Core CRUD operations
# ---------------------------------------------------------------------------

def list_candidates() -> list[dict]:
    """
    List all candidates with summary info.
    Returns list of dicts: {name, folder, has_cv, has_id, has_identcheck, last_modified}
    """
    candidates = []
    if not CANDIDATES_DIR.exists():
        return candidates

    for d in sorted(CANDIDATES_DIR.iterdir()):
        if not d.is_dir():
            continue

        info = {
            "name": d.name.replace("_", " "),
            "folder": d.name,
            "has_cv": (d / "extracted_data.json").exists(),
            "has_populated": (d / "Populated_CV.docx").exists(),
            "has_lebenslauf": (d / "Lebenslauf.docx").exists(),
            "has_id": any(d.glob("id_scan.*")),
            "has_identcheck": (d / "Identcheck_Filled.docx").exists(),
            "file_count": len(list(d.iterdir())),
            "last_modified": datetime.fromtimestamp(d.stat().st_mtime).strftime("%d.%m.%Y %H:%M"),
        }
        candidates.append(info)

    # Sort newest first
    candidates.sort(key=lambda c: c["last_modified"], reverse=True)
    return candidates


def get_candidate(folder_name: str) -> dict:
    """
    Get full candidate data including file paths and extracted JSON.
    """
    d = CANDIDATES_DIR / folder_name
    if not d.exists():
        return {}

    result = {
        "name": folder_name.replace("_", " "),
        "folder": folder_name,
        "dir_path": str(d),
        "files": {},
    }

    # Map known files
    file_map = {
        "cv": list(d.glob("original_cv.*")),
        "extracted_json": [d / "extracted_data.json"] if (d / "extracted_data.json").exists() else [],
        "populated_cv": [d / "Populated_CV.docx"] if (d / "Populated_CV.docx").exists() else [],
        "lebenslauf": [d / "Lebenslauf.docx"] if (d / "Lebenslauf.docx").exists() else [],
        "id_scans": list(d.glob("id_scan.*")) + list(d.glob("id_scan_*.*")),
        "identcheck_json": [d / "identcheck_data.json"] if (d / "identcheck_data.json").exists() else [],
        "identcheck_doc": [d / "Identcheck_Filled.docx"] if (d / "Identcheck_Filled.docx").exists() else [],
        "lebenslauf_json": [d / "lebenslauf_data.json"] if (d / "lebenslauf_data.json").exists() else [],
    }

    for key, paths in file_map.items():
        result["files"][key] = [str(p) for p in paths if p.exists()]

    # Load extracted JSON data if available
    json_path = d / "extracted_data.json"
    if json_path.exists():
        try:
            result["extracted_data"] = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception:
            result["extracted_data"] = {}

    # Load identcheck JSON if available
    ident_json = d / "identcheck_data.json"
    if ident_json.exists():
        try:
            result["identcheck_data"] = json.loads(ident_json.read_text(encoding="utf-8"))
        except Exception:
            result["identcheck_data"] = {}

    # Load lebenslauf JSON if available
    leben_json = d / "lebenslauf_data.json"
    if leben_json.exists():
        try:
            result["lebenslauf_data"] = json.loads(leben_json.read_text(encoding="utf-8"))
        except Exception:
            result["lebenslauf_data"] = {}

    return result


def save_candidate_cv(
    candidate_name: str,
    cv_bytes: bytes,
    cv_filename: str,
    extracted_json: dict,
    populated_docx_path: str | None = None,
) -> str:
    """
    Save a processed CV to a candidate folder.
    Returns the folder name.
    """
    folder_name = _sanitize_name(candidate_name)
    d = _candidate_dir(candidate_name)

    # Save original CV
    suffix = Path(cv_filename).suffix
    cv_dest = d / f"original_cv{suffix}"
    cv_dest.write_bytes(cv_bytes)

    # Save extracted JSON
    json_path = d / "extracted_data.json"
    json_path.write_text(json.dumps(extracted_json, indent=2, ensure_ascii=False), encoding="utf-8")

    # Copy populated Word doc
    if populated_docx_path and os.path.exists(populated_docx_path):
        shutil.copy2(populated_docx_path, d / "Populated_CV.docx")

    return folder_name


def save_candidate_lebenslauf(
    candidate_name: str,
    lebenslauf_data: dict,
    lebenslauf_docx_path: str | None = None,
) -> str:
    """Save lebenslauf data and doc to a candidate folder."""
    folder_name = _sanitize_name(candidate_name)
    d = _candidate_dir(candidate_name)

    # Save lebenslauf JSON
    json_path = d / "lebenslauf_data.json"
    json_path.write_text(json.dumps(lebenslauf_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Copy lebenslauf doc
    if lebenslauf_docx_path and os.path.exists(lebenslauf_docx_path):
        shutil.copy2(lebenslauf_docx_path, d / "Lebenslauf.docx")

    return folder_name


def add_id_document(candidate_folder: str, id_bytes: bytes, filename: str) -> str:
    """
    Save an ID document scan to a candidate folder.
    Supports multiple ID scans with numbered suffixes.
    """
    d = CANDIDATES_DIR / candidate_folder
    d.mkdir(parents=True, exist_ok=True)

    suffix = Path(filename).suffix
    # Check if id_scan already exists, add number suffix
    existing = list(d.glob("id_scan.*")) + list(d.glob("id_scan_*.*"))
    if not existing:
        dest = d / f"id_scan{suffix}"
    else:
        dest = d / f"id_scan_{len(existing) + 1}{suffix}"

    dest.write_bytes(id_bytes)
    return str(dest)


def save_identcheck(
    candidate_folder: str,
    identcheck_data: dict,
    filled_docx_path: str | None = None,
) -> None:
    """Save identcheck extraction results to a candidate folder."""
    d = CANDIDATES_DIR / candidate_folder

    # Save identcheck JSON
    json_path = d / "identcheck_data.json"
    json_path.write_text(json.dumps(identcheck_data, indent=2, ensure_ascii=False), encoding="utf-8")

    # Copy filled doc
    if filled_docx_path and os.path.exists(filled_docx_path):
        shutil.copy2(filled_docx_path, d / "Identcheck_Filled.docx")


def delete_candidate(folder_name: str) -> bool:
    """Delete an entire candidate folder."""
    d = CANDIDATES_DIR / folder_name
    if d.exists():
        shutil.rmtree(d)
        return True
    return False


def get_cv_path(folder_name: str) -> str | None:
    """Get the path to the original CV file for re-processing."""
    d = CANDIDATES_DIR / folder_name
    cvs = list(d.glob("original_cv.*"))
    return str(cvs[0]) if cvs else None


def get_id_paths(folder_name: str) -> list[str]:
    """Get all ID scan file paths."""
    d = CANDIDATES_DIR / folder_name
    scans = list(d.glob("id_scan.*")) + list(d.glob("id_scan_*.*"))
    return [str(p) for p in scans]


def candidate_name_from_data(data: dict) -> str:
    """
    Build a candidate folder name from extracted data.
    Tries nachname_vorname first, then name, finally 'Unknown'.
    """
    # Try Lebenslauf-style fields
    nachname = data.get("nachname", "")
    vorname = data.get("vorname", "")
    if nachname and nachname != "N/A":
        parts = [nachname]
        if vorname and vorname != "N/A":
            parts.append(vorname)
        return "_".join(parts)

    # Try CV-style name field
    name = data.get("name", "")
    if name and name != "N/A":
        return _sanitize_name(name)

    # Try full_name
    full_name = data.get("full_name", "")
    if full_name and full_name != "N/A":
        return _sanitize_name(full_name)

    return f"Unknown_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
