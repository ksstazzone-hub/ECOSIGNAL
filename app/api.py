from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import DATA_COVERAGE_LEVELS, ECOSYSTEM_CATEGORIES
from app.services.adaptive_analysis import AdaptiveAnalyzer
from app.services.data_connectors import ConnectorRegistry
from app.services.geography import GeographyService

_ROOT = Path(__file__).resolve().parent.parent
_FRONTEND_DIR = _ROOT / "frontend"


def create_app() -> FastAPI:
    app = FastAPI(
        title="ECOSIGNAL — Global Ecological Intelligence Platform",
        description="A global ecosystem monitoring architecture with PostGIS-compatible spatial logic, modular connectors, and ecosystem-aware analysis.",
        version="0.1.0",
    )

    registry = ConnectorRegistry()
    analyzer = AdaptiveAnalyzer()
    geography = GeographyService()

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok", "platform": "ECOSIGNAL"}

    @app.get("/api/ecosystems")
    async def ecosystems() -> dict:
        return {
            "ecosystem_categories": ECOSYSTEM_CATEGORIES,
            "count": len(ECOSYSTEM_CATEGORIES),
        }

    @app.get("/api/coverage")
    async def coverage() -> dict:
        return {
            "coverage_levels": DATA_COVERAGE_LEVELS,
            "message": "Coverage is explicit and contextual; data gaps are not interpreted as ecological stability.",
        }

    @app.get("/api/geography/validate")
    async def validate_geography(lat: float, lon: float) -> dict:
        return {
            "valid": geography.validate_coordinate(lat, lon),
            "latitude": lat,
            "longitude": lon,
            "postgis_compatible": True,
        }

    @app.get("/api/connectors")
    async def connectors() -> dict:
        return registry.list_sources()

    @app.get("/api/analytic-modules")
    async def analytic_modules() -> dict:
        return {"modules": analyzer.modules}

    @app.get("/api/adaptive-analysis")
    async def adaptive_analysis(
        ecosystem: str,
        taxonomic_group: str = "unknown",
        data_quality: str = "good",
        temporal_resolution: str = "monthly",
        geographic_resolution: str = "regional",
    ) -> dict:
        return {
            "ecosystem": ecosystem,
            "taxonomic_group": taxonomic_group,
            "selected_modules": [
                {
                    "module_id": item.module_id,
                    "ecosystem": item.ecosystem,
                    "rationale": item.rationale,
                    "confidence": item.confidence,
                    "required_data": item.required_data,
                }
                for item in analyzer.select_modules(
                    ecosystem=ecosystem,
                    taxonomic_group=taxonomic_group,
                    data_quality=data_quality,
                    temporal_resolution=temporal_resolution,
                    geographic_resolution=geographic_resolution,
                )
            ],
        }

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(_FRONTEND_DIR / "index.html")

    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIR)), name="assets")
    app.mount("/static", StaticFiles(directory=str(_FRONTEND_DIR)), name="static")
    return app


app = create_app()
