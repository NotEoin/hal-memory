"""Tests for halmem/hal-module.toml as halhub's strict schema v2 loader reads it."""

import importlib
from pathlib import Path

import pytest

manifest = pytest.importorskip("halhub.manifest")

MANIFEST = Path(__file__).resolve().parents[1] / "halmem" / "hal-module.toml"
TOOL_COUNT = 15  # REQ-MEM-03
CONTENT_PARAMS = ("memory_remember.text", "memory_append.text")  # REQ-PACK-33


@pytest.fixture(scope="module")
def spec():
    return manifest.load_manifest(MANIFEST, source="path")


def test_manifest_loads_as_schema_v2_pack_memory(spec):
    assert spec.schema == 2
    assert spec.pack == "memory"


def test_manifest_declares_fifteen_tools(spec):
    assert len(spec.tools) == TOOL_COUNT


def test_every_tool_has_an_explicit_tier(spec):
    assert not [t.name for t in spec.tools if t.tier_inferred]


def test_reading_tools_are_read_tier_and_writing_tools_are_write_tier(spec):
    tiers = {t.name: t.tier for t in spec.tools}
    assert tiers["memory_search"] == "read"
    assert tiers["memory_remember"] == "write"
    assert {"read", "write"} >= set(tiers.values())


def test_vault_content_tools_mark_output_untrusted(spec):
    untrusted = {t.name for t in spec.tools if t.untrusted_output}
    assert {"memory_search", "memory_recall", "memory_read", "memory_profile"} <= untrusted


def test_content_params_are_marked(spec):
    params = {f"{t.name}.{p.name}": p for t in spec.tools for p in t.params}
    for key in CONTENT_PARAMS:
        assert params[key].content, key


def test_tool_functions_exist_in_the_tools_module(spec):
    tools = importlib.import_module("halmem.tools")
    for t in spec.tools:
        assert callable(getattr(tools, t.function)), t.function
