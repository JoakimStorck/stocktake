"""Structural validation: everything a declaration can get wrong is a
hard failure before the audit runs."""

import copy
from pathlib import Path

import pytest

from stocktake import SchemaError, load_config
from stocktake.schema import validate

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def config():
    return load_config(FIXTURES / "map.toml")


def test_fixture_config_is_valid(config):
    assert config.figures[0]["name"] == "fixture_figure"
    assert config.aliases["np"] == ""
    assert "state" in config.ignore


def test_rank_referencing_removed_node_fails(config):
    """A saved layout that references a node the declaration no longer
    has is a build failure, not a warning. Graphviz would otherwise
    silently invent a phantom node."""
    broken = copy.deepcopy(config)
    broken.figures[0]["nodes"] = [
        n for n in broken.figures[0]["nodes"] if n["id"] != "P"
    ]
    broken.figures[0]["edges"] = [
        e for e in broken.figures[0]["edges"]
        if "P" not in (e["from"], e["to"])
    ]
    # ranks still mentions P
    with pytest.raises(SchemaError, match="rank group.*'P'"):
        validate(broken)


def test_edge_to_undeclared_node_fails(config):
    broken = copy.deepcopy(config)
    broken.figures[0]["edges"][0]["to"] = "ghost"
    with pytest.raises(SchemaError, match="undeclared node 'ghost'"):
        validate(broken)


def test_duplicate_node_id_fails(config):
    broken = copy.deepcopy(config)
    broken.figures[0]["nodes"].append(
        {"id": "S", "kind": "aux", "label": "dup"}
    )
    with pytest.raises(SchemaError, match="duplicate node id 'S'"):
        validate(broken)


def test_unknown_kind_fails(config):
    broken = copy.deepcopy(config)
    broken.figures[0]["nodes"][0]["kind"] = "cloud"
    with pytest.raises(SchemaError, match="unknown kind 'cloud'"):
        validate(broken)


def test_unknown_channel_fails(config):
    broken = copy.deepcopy(config)
    broken.figures[0]["edges"][0]["channel"] = "psychic"
    with pytest.raises(SchemaError, match="unknown channel 'psychic'"):
        validate(broken)


def test_variable_mapping_to_unknown_concept_fails(config):
    broken = copy.deepcopy(config)
    broken.variables["demand"] = "demannd"  # typo
    with pytest.raises(SchemaError, match="unknown concept 'demannd'"):
        validate(broken)


def test_witness_naming_unknown_concept_fails(config):
    """A typo in a witness must read 'unknown concept', not the
    misleading 'no AST support'."""
    broken = copy.deepcopy(config)
    broken.figures[0]["edges"][1]["audit"] = ["inflow->stok"]
    with pytest.raises(SchemaError, match="unknown concept 'stok'"):
        validate(broken)


def test_malformed_witness_fails(config):
    broken = copy.deepcopy(config)
    broken.figures[0]["edges"][1]["audit"] = ["inflow->stock->extra"]
    with pytest.raises(SchemaError, match="malformed witness"):
        validate(broken)


def test_duplicate_figure_name_fails(config):
    broken = copy.deepcopy(config)
    broken.figures.append(copy.deepcopy(broken.figures[0]))
    with pytest.raises(SchemaError, match="duplicate figure name"):
        validate(broken)
