import httpx
import pytest
from ecosignal.sources import GBIFConnector


@pytest.mark.asyncio
async def test_gbif_connector_preserves_record_license_taxon_and_date_precision():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["hasCoordinate"] == "true"
        assert request.url.params["limit"] == "200"
        return httpx.Response(200, json={
            "count": 1,
            "results": [{
                "key": 123,
                "taxonKey": 456,
                "scientificName": "Testus exemplar",
                "decimalLongitude": -70.2,
                "decimalLatitude": -42.8,
                "coordinateUncertaintyInMeters": 100,
                "eventDate": "2020-03",
                "license": "http://creativecommons.org/licenses/by/4.0/",
                "datasetKey": "dataset-1",
            }],
        })

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await GBIFConnector(client).search((-71, -43, -70, -42), "2020-01-01", None, None)

    assert result.ok
    assert result.total_available == 1
    record = result.records[0]
    assert record.source_taxon_id == "456"
    assert record.taxon_identifier_scheme == "gbifTaxonKey"
    assert record.date_precision == "month"
    assert record.license_id == "http://creativecommons.org/licenses/by/4.0/"
    assert record.source_metadata["datasetKey"] == "dataset-1"
    assert record.original_record["key"] == 123