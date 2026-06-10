"""Tests for the rubric scoring agent's API call contract (ORPHEUS-75).

Pins the temperature=0 default on the Dim 1 / Dim 4 Claude calls.
API-default sampling produced band-crossing composite swings on borderline
profiles (75.75/Tuned vs. 83/Resonant on identical data); temperature 0
measured zero variance over 20 runs per profile in the ORPHEUS-75
consistency experiment. These tests fail if the determinism contract is
accidentally dropped.
"""

import json
from unittest.mock import MagicMock

import pytest

from backend.agents.rubric import (
    score_dimension_1,
    score_dimension_4,
    score_rubrics,
)
from backend.ingestion.types import ZipData

DIM1_RESPONSE = json.dumps({
    "Headline Clarity": 2,
    "About Section Coherence": 3,
    "Experience Description Quality": 2,
    "Profile Completeness": 4,
    "Identity Clarity": 3,
})

DIM4_RESPONSE = json.dumps({
    "Topic Consistency": 4,
    "Profile-Content Coherence": 4,
})


def _mock_client(response_text: str) -> MagicMock:
    client = MagicMock()
    message = MagicMock()
    message.content = [MagicMock(text=response_text)]
    client.messages.create.return_value = message
    return client


class TestRubricTemperature:
    """The determinism contract: rubric calls run at temperature 0 by default."""

    @pytest.mark.asyncio
    async def test_dim1_defaults_to_temperature_zero(self):
        client = _mock_client(DIM1_RESPONSE)
        await score_dimension_1(client, ZipData())
        kwargs = client.messages.create.call_args.kwargs
        assert kwargs["temperature"] == 0.0

    @pytest.mark.asyncio
    async def test_dim4_defaults_to_temperature_zero(self):
        client = _mock_client(DIM4_RESPONSE)
        await score_dimension_4(client, ZipData())
        kwargs = client.messages.create.call_args.kwargs
        assert kwargs["temperature"] == 0.0

    @pytest.mark.asyncio
    async def test_temperature_none_omits_parameter(self):
        """None means 'use the API default' — the parameter is omitted entirely."""
        client = _mock_client(DIM1_RESPONSE)
        await score_dimension_1(client, ZipData(), temperature=None)
        kwargs = client.messages.create.call_args.kwargs
        assert "temperature" not in kwargs

    @pytest.mark.asyncio
    async def test_explicit_temperature_passes_through(self):
        client = _mock_client(DIM4_RESPONSE)
        await score_dimension_4(client, ZipData(), temperature=0.5)
        kwargs = client.messages.create.call_args.kwargs
        assert kwargs["temperature"] == 0.5

    @pytest.mark.asyncio
    async def test_score_rubrics_applies_default_to_both_calls(self):
        client = MagicMock()
        dim1_msg = MagicMock()
        dim1_msg.content = [MagicMock(text=DIM1_RESPONSE)]
        dim4_msg = MagicMock()
        dim4_msg.content = [MagicMock(text=DIM4_RESPONSE)]
        client.messages.create.side_effect = [dim1_msg, dim4_msg]

        dim1, dim4 = await score_rubrics(client, ZipData())

        assert dim1["Headline Clarity"] == 2
        assert dim4["Topic Consistency"] == 4
        for call in client.messages.create.call_args_list:
            assert call.kwargs["temperature"] == 0.0
