"""Readonly Application boundary refuses authority and historical writes."""

import pytest

from backend.adapters.inbound.application.p0_finite_origin import FiniteOriginInbound
from backend.modules.work_orchestration.application.queries.p0_finite_origin import ReadFiniteOrigin


@pytest.mark.parametrize(
    "change", ({}, {"authority": "SEND"}, {"historical_writes": 1}, {"slots": {}})
)
def test_origin_metadata_is_readonly_and_closed(change):
    class Port:
        def inspect_readonly(self):
            return {
                "schema": "P0-FINITE-ORIGIN-OBSERVATION-1.0",
                "authority": "NONE",
                "historical_writes": 0,
                "slots": [],
                **change,
            }

    app = FiniteOriginInbound(ReadFiniteOrigin(Port()))
    if change:
        with pytest.raises(ValueError, match="P0_CHAIN_ORIGIN_METADATA_CONTRACT"):
            app.inspect()
    else:
        assert app.inspect()["historical_writes"] == 0
