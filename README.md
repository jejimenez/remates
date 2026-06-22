# Remates Judiciales en Colombia

Weekly ingestion pipeline for judicial auction listings in Colombia. Reads a `.xlsx` source file, cleans and validates the data, and upserts it into a Supabase (Postgres) database.

## How it works

1. Download the weekly `.xlsx` file and drop it in the `data/` folder.
2. Run the script locally — or push to GitHub to trigger the automated workflow.
3. Clean rows are upserted into Supabase on the natural key `codigo`. If a listing's price or date changed since the last run, it gets updated in place.

## Local usage

```bash
python ingest.py data/your-file.xlsx
```

**Required environment variables** (create a `.env` file):

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
```

## Automated workflow

The GitHub Actions workflow (`.github/workflows/ingest.yml`) runs automatically when a `.xlsx` file is pushed to the `data/` folder, or manually via the Actions tab.

Add the two environment variables as repository secrets in **Settings → Secrets and variables → Actions**:
- `SUPABASE_URL`
- `SUPABASE_SERVICE_KEY`

## Data validation

Rows are rejected (and written to `rejected_rows.csv`) if they fail any of:
- Missing `codigo`, `fecha_remate`, `avaluo`, or `oferta_minima`
- `departamento` does not match a known Colombian department

## Stack

- Python 3.12
- pandas + openpyxl
- Supabase Python client
- GitHub Actions
