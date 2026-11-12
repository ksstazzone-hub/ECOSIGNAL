from __future__ import annotations

import asyncio
import os
from types import SimpleNamespace

import httpx
import psycopg

from ecosignal.database import Database
from ecosignal.main import SearchRequest, _search_occurrences


async def run_worker() -> None:
    database = await Database.connect_from_env()
    if database is None:
        raise RuntimeError("DATABASE_URL is required for the ingestion worker")
    poll_seconds = max(1, int(os.getenv("WORKER_POLL_SECONDS", "3")))
    timeout = httpx.Timeout(25.0, connect=8.0)
    async with httpx.AsyncClient(timeout=timeout, headers={
        "User-Agent": "ECOSIGNAL/0.1 (global ecological research platform)",
    }) as client:
        app = SimpleNamespace(state=SimpleNamespace(db=database, http=client))
        try:
            while True:
                job = await database.claim_job()
                if job is None:
                    await asyncio.sleep(poll_seconds)
                    continue
                try:
                    request = SearchRequest.model_validate(job["request"])
                    result = await _search_occurrences(app, request)
                    await database.finish_job(
                        job["job_id"],
                        records_ingested=result["coverage"]["retrieved_records"],
                    )
                except (httpx.HTTPError, psycopg.Error, ValueError, TypeError, KeyError) as error:
                    await database.finish_job(job["job_id"], error=str(error)[:2000])
        finally:
            await database.close()


if __name__ == "__main__":
    asyncio.run(run_worker())