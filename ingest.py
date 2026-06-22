"""
Weekly ingestion script for "Remates Judiciales en Colombia" listings.

What it does:
1. Reads the weekly .xlsx file (downloaded from Drive or local path)
2. Cleans messy fields (Avalúo formatting, department name typos, misaligned rows)
3. Upserts rows into Supabase (Postgres) on the natural key `codigo`

Run:
    python ingest.py /path/to/file.xlsx

Env vars required (put these in a .env file, see .env.example):
    SUPABASE_URL
    SUPABASE_SERVICE_KEY   (service_role key, NOT the anon key — needed for writes from a script)
"""

import os
import re
import sys
from datetime import date

import pandas as pd
from supabase import create_client

# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

# Canonical list of Colombian departments, used to (a) normalize accent/typo
# variants seen in the source file and (b) flag rows that don't belong here
# (e.g. a misaligned row where a city name lands in the department column).
VALID_DEPARTMENTS = {
    "Amazonas", "Antioquia", "Arauca", "Atlántico", "Bolívar", "Boyacá",
    "Caldas", "Caquetá", "Casanare", "Cauca", "Cesar", "Chocó",
    "Cundinamarca", "Córdoba", "Guainía", "Guaviare", "Huila",
    "La Guajira", "Magdalena", "Meta", "Nariño", "Norte de Santander",
    "Putumayo", "Quindío", "Risaralda", "San Andrés y Providencia",
    "Santander", "Sucre", "Tolima", "Valle del Cauca", "Vaupés",
    "Vichada", "Bogotá D.C.",
}

# Known misspellings/variants -> canonical name (extend as you find more)
DEPARTMENT_FIXES = {
    "Bolivar": "Bolívar",
    "Quindio": "Quindío",
    "Quindió": "Quindío",
    "Valle": "Valle del Cauca",
}


# ---------------------------------------------------------------------------
# Cleaning helpers
# ---------------------------------------------------------------------------

def clean_currency(value) -> float | None:
    """Turn messy currency strings into a clean float.

    Handles:
      - already-numeric values (int/float) -> pass through
      - Colombian-style thousand separators: "1.084.350.000" -> 1084350000
      - OCR/typo artifacts: letter 'O' used instead of digit '0'
      - stray whitespace/newlines: "6.500.000\\n\\n" -> 6500000
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip()
    if not s:
        return None

    # Fix letter O -> digit 0 (seen in source data, e.g. "1.O84.350.000")
    s = s.replace("O", "0").replace("o", "0")
    # Drop everything that isn't a digit (removes dots used as thousand seps,
    # newlines, spaces, etc.)
    s = re.sub(r"[^\d]", "", s)
    if not s:
        return None
    return float(s)


def normalize_department(value) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return DEPARTMENT_FIXES.get(s, s)


def clean_dataframe(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Clean the raw dataframe. Returns (clean_rows, rejected_rows)."""

    df = df.copy()
    df.columns = [
        "codigo", "fecha_remate", "ciudad", "departamento",
        "tipo_bien", "avaluo", "oferta_minima", "referencia",
    ]

    df["avaluo"] = df["avaluo"].apply(clean_currency)
    df["oferta_minima"] = df["oferta_minima"].apply(clean_currency)
    df["departamento"] = df["departamento"].apply(normalize_department)
    df["ciudad"] = df["ciudad"].astype(str).str.strip()
    df["tipo_bien"] = df["tipo_bien"].astype(str).str.strip()
    df["referencia"] = df["referencia"].where(df["referencia"].notna(), None)
    df["fecha_remate"] = pd.to_datetime(df["fecha_remate"], errors="coerce").dt.date

    # Flag rows that don't pass basic sanity checks (misaligned columns,
    # missing required fields, etc.) instead of silently loading bad data.
    is_valid = (
        df["codigo"].notna()
        & df["fecha_remate"].notna()
        & df["avaluo"].notna()
        & df["oferta_minima"].notna()
        & df["departamento"].isin(VALID_DEPARTMENTS)
    )

    clean_rows = df[is_valid].copy()
    rejected_rows = df[~is_valid].copy()
    return clean_rows, rejected_rows


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def read_source_file(path: str) -> pd.DataFrame:
    """Row 0 is metadata (the 0.7 discount factor etc.), row 1 is headers."""
    return pd.read_excel(path, header=1)


def upsert_to_supabase(df: pd.DataFrame, week_uploaded: date) -> None:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_KEY"]
    client = create_client(url, key)

    records = df.to_dict(orient="records")
    for r in records:
        r["week_uploaded"] = week_uploaded.isoformat()
        r["fecha_remate"] = r["fecha_remate"].isoformat()
        if pd.isna(r.get("referencia")):
            r["referencia"] = None

    # Upsert in batches, on the `codigo` natural key. If a listing's price
    # or date changes between weeks, this updates it in place rather than
    # creating a duplicate row.
    batch_size = 200
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        client.table("remates").upsert(batch, on_conflict="codigo").execute()
        print(f"  upserted rows {i}-{i + len(batch)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) < 2:
        print("Usage: python ingest.py /path/to/weekly_file.xlsx")
        sys.exit(1)

    path = sys.argv[1]
    print(f"Reading {path} ...")
    raw = read_source_file(path)
    print(f"  {len(raw)} raw rows")

    clean_rows, rejected_rows = clean_dataframe(raw)
    print(f"  {len(clean_rows)} clean rows, {len(rejected_rows)} rejected")

    if len(rejected_rows):
        rejected_path = "rejected_rows.csv"
        rejected_rows.to_csv(rejected_path, index=False)
        print(f"  rejected rows written to {rejected_path} for review")

    print("Upserting to Supabase ...")
    upsert_to_supabase(clean_rows, week_uploaded=date.today())
    print("Done.")


if __name__ == "__main__":
    main()
