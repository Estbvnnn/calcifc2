from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from flask import Flask, jsonify, render_template, request, send_file

UPLOAD_DIR = Path("uploads")
DATA_DIR = Path("data")
DATABASE_PATH = DATA_DIR / "analysis.db"
ALLOWED_EXTENSIONS = {".ifc"}

ZONE_CONFIG = {
    "France - Zone Neige A": {"snow": 0.45, "wind": 0.5, "seismic": 0.7},
    "France - Zone Neige B": {"snow": 0.65, "wind": 0.55, "seismic": 0.8},
    "France - Zone Neige C": {"snow": 0.9, "wind": 0.6, "seismic": 0.9},
    "Belgique": {"snow": 0.7, "wind": 0.55, "seismic": 0.6},
    "Suisse": {"snow": 0.85, "wind": 0.6, "seismic": 0.9},
}

ENTITY_PATTERNS = {
    "beams": re.compile(r"IFCBEAM\b", re.IGNORECASE),
    "columns": re.compile(r"IFCCOLUMN\b", re.IGNORECASE),
    "braces": re.compile(r"IFCMEMBER\b", re.IGNORECASE),
    "plates": re.compile(r"IFCPLATE\b", re.IGNORECASE),
    "connections": re.compile(r"IFCFASTENER\b|IFCMECHANICALFASTENER\b", re.IGNORECASE),
}

app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR


@dataclass
class AnalysisResult:
    analysis_id: int
    filename: str
    project: str
    zone: str
    building_use: str
    summary: dict[str, Any]
    loads: dict[str, float]
    checks: list[dict[str, str]]
    created_at: str
    saved_as: str


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def ensure_dirs() -> None:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    ensure_dirs()
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                project TEXT NOT NULL,
                zone TEXT NOT NULL,
                building_use TEXT NOT NULL,
                summary TEXT NOT NULL,
                loads TEXT NOT NULL,
                checks TEXT NOT NULL,
                saved_as TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


@app.before_first_request
def setup_app() -> None:
    init_db()


def allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


def iter_lines(contents: str) -> Iterable[str]:
    return (line.strip() for line in contents.splitlines() if line.strip())


def parse_ifc_summary(contents: str) -> dict[str, Any]:
    lines = list(iter_lines(contents))
    entity_lines = [line for line in lines if line.startswith("#")]
    header_lines = [line for line in lines if line.startswith("IFC")]
    counts = {
        name: sum(1 for line in entity_lines if pattern.search(line))
        for name, pattern in ENTITY_PATTERNS.items()
    }
    return {
        "total_lines": len(lines),
        "entity_count": len(entity_lines),
        "header_count": len(header_lines),
        "counts": counts,
    }


def compute_loads(zone: str, building_use: str) -> dict[str, float]:
    base = ZONE_CONFIG.get(zone, {"snow": 0.0, "wind": 0.0, "seismic": 0.0})
    usage_factor = 1.0
    if building_use == "Stockage":
        usage_factor = 1.15
    if building_use == "Bureau":
        usage_factor = 1.05
    return {
        "snow_kN_m2": round(base["snow"] * usage_factor, 3),
        "wind_kN_m2": round(base["wind"] * usage_factor, 3),
        "seismic_ag": round(base["seismic"] * usage_factor, 3),
    }


def generate_checks(zone: str, summary: dict[str, Any], loads: dict[str, float]) -> list[dict[str, str]]:
    entity_count = summary["entity_count"]
    beam_count = summary["counts"]["beams"]
    column_count = summary["counts"]["columns"]
    return [
        {
            "name": "Complétude du modèle",
            "status": "OK" if entity_count > 0 else "À compléter",
            "details": "Le modèle IFC contient des entités structurelles à analyser.",
        },
        {
            "name": "Zone normative",
            "status": "OK" if zone else "À renseigner",
            "details": f"Zone sélectionnée : {zone or 'non définie'}.",
        },
        {
            "name": "Typologie structurelle",
            "status": "OK" if beam_count and column_count else "À vérifier",
            "details": f"Poutres: {beam_count}, poteaux: {column_count}.",
        },
        {
            "name": "Pré-charges Eurocode",
            "status": "Pré-calcul",
            "details": (
                "Charges estimées (neige/vent/sismique): "
                f"{loads['snow_kN_m2']} / {loads['wind_kN_m2']} / {loads['seismic_ag']}"
            ),
        },
    ]


def persist_analysis(
    filename: str,
    project: str,
    zone: str,
    building_use: str,
    summary: dict[str, Any],
    loads: dict[str, float],
    checks: list[dict[str, str]],
    saved_as: str,
) -> int:
    with sqlite3.connect(DATABASE_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO analyses
                (filename, project, zone, building_use, summary, loads, checks, saved_as, created_at)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                filename,
                project,
                zone,
                building_use,
                json.dumps(summary),
                json.dumps(loads),
                json.dumps(checks),
                saved_as,
                utc_now(),
            ),
        )
        conn.commit()
        return int(cursor.lastrowid)


def fetch_history(limit: int = 10) -> list[dict[str, Any]]:
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, filename, project, zone, building_use, created_at
            FROM analyses
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def fetch_analysis(analysis_id: int) -> AnalysisResult | None:
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT * FROM analyses WHERE id = ?
            """,
            (analysis_id,),
        ).fetchone()

    if not row:
        return None

    return AnalysisResult(
        analysis_id=row["id"],
        filename=row["filename"],
        project=row["project"],
        zone=row["zone"],
        building_use=row["building_use"],
        summary=json.loads(row["summary"]),
        loads=json.loads(row["loads"]),
        checks=json.loads(row["checks"]),
        created_at=row["created_at"],
        saved_as=row["saved_as"],
    )


@app.route("/")
def index() -> str:
    return render_template("index.html", zones=sorted(ZONE_CONFIG.keys()))


@app.route("/analyze", methods=["POST"])
def analyze() -> tuple[str, int] | tuple[dict[str, Any], int]:
    zone = request.form.get("zone", "").strip()
    project = request.form.get("project", "").strip() or "Sans titre"
    building_use = request.form.get("building_use", "").strip() or "Industriel"
    file = request.files.get("ifc_file")

    if not file or file.filename == "":
        return jsonify({"error": "Aucun fichier IFC fourni."}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Le fichier doit être au format .ifc"}), 400

    contents = file.read().decode("utf-8", errors="ignore")
    summary = parse_ifc_summary(contents)
    loads = compute_loads(zone, building_use)
    checks = generate_checks(zone, summary, loads)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    safe_name = f"{timestamp}_{Path(file.filename).name}"
    target_path = UPLOAD_DIR / safe_name
    with target_path.open("w", encoding="utf-8") as handle:
        handle.write(contents)

    analysis_id = persist_analysis(
        filename=file.filename,
        project=project,
        zone=zone,
        building_use=building_use,
        summary=summary,
        loads=loads,
        checks=checks,
        saved_as=str(target_path),
    )

    response = {
        "analysis_id": analysis_id,
        "filename": file.filename,
        "project": project,
        "zone": zone,
        "building_use": building_use,
        "summary": summary,
        "loads": loads,
        "checks": checks,
        "next_steps": [
            "Configurer les paramètres de charge (neige, vent, sismique).",
            "Associer les sections aux profils normatifs.",
            "Lancer le calcul complet Eurocode.",
        ],
        "saved_as": str(target_path),
    }

    return jsonify(response), 200


@app.route("/history")
def history() -> tuple[dict[str, Any], int]:
    limit = int(request.args.get("limit", "10"))
    return jsonify({"items": fetch_history(limit)}), 200


@app.route("/report/<int:analysis_id>")
def report(analysis_id: int) -> Any:
    analysis = fetch_analysis(analysis_id)
    if not analysis:
        return jsonify({"error": "Analyse introuvable."}), 404

    report_payload = asdict(analysis)
    report_path = DATA_DIR / f"report_{analysis_id}.json"
    report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
    return send_file(report_path, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=True)
