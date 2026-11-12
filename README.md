# ECOSIGNAL

Global ecological intelligence platform for traceable biodiversity and environmental monitoring across ecosystems and regions.

## Development

The platform uses FastAPI and PostgreSQL/PostGIS. Start the API and database with:

```sh
docker compose up --build
```

Then open http://localhost:8000. For local Python development, run `pip install -e '.[dev]'` from the repository root, set `DATABASE_URL` to a PostGIS database, and run `uvicorn ecosignal.main:app --reload` from the repository root.

The monitor never treats missing observations as ecological stability. Coverage is reported only for explicit searches and their selected sources; external catalog availability is not evidence that a particular region has usable data. Data source licenses and limitations remain attached to records.

See [docs/architecture.md](docs/architecture.md) for the architecture, data-source constraints, and operational caveats.