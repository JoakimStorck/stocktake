"""The audit failure modes are the core invariants of the tool."""

import copy
from pathlib import Path

import pytest

from stocktake import (
    MissingMechanismError,
    UnsupportedWitnessError,
    UnwitnessedEdgeError,
    audit_figure,
    build,
    extract_code_edges,
    load_config,
    map_to_concepts,
    unwitnessed_concept_edges,
)

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def config():
    return load_config(FIXTURES / "map.toml")


@pytest.fixture
def concept_edges(config):
    code_edges = extract_code_edges(FIXTURES / "model.py", config.aliases)
    return map_to_concepts(code_edges, config.variables)


def test_green_build(tmp_path):
    report = build(FIXTURES / "model.py", FIXTURES / "map.toml", tmp_path)
    rows = report.audits["fixture_figure"]
    assert [r.status for r in rows] == ["identity", "ast", "ast", "parameter"]
    assert (tmp_path / "fixture_figure.dot").exists()
    assert (tmp_path / "fixture_figure_audit.csv").exists()


def test_unwitnessed_edge_fails(config, concept_edges):
    figure = copy.deepcopy(config.figures[0])
    del figure["edges"][1]["audit"]
    with pytest.raises(UnwitnessedEdgeError, match="fill->S"):
        audit_figure(figure, concept_edges)


def test_witness_without_ast_support_fails(config, concept_edges):
    figure = copy.deepcopy(config.figures[0])
    figure["edges"][1]["audit"] = ["outflow->pressure"]  # not in the code
    with pytest.raises(UnsupportedWitnessError, match="no AST support"):
        audit_figure(figure, concept_edges)


def test_witness_removal_after_code_change_fails(tmp_path, config):
    """The drift scenario: the code loses a mechanism the figure still
    claims. The build must die loudly."""
    drifted = (FIXTURES / "model.py").read_text().replace(
        "inflow = GAMMA * pressure", "inflow = GAMMA"
    )
    model = tmp_path / "model.py"
    model.write_text(drifted)
    with pytest.raises(UnsupportedWitnessError, match="pressure->inflow"):
        build(model, FIXTURES / "map.toml", tmp_path / "out")


def test_failing_audit_emits_nothing(tmp_path, config):
    """A build with a failing figure leaves no partially updated diagram."""
    drifted = (FIXTURES / "model.py").read_text().replace(
        "inflow = GAMMA * pressure", "inflow = GAMMA"
    )
    model = tmp_path / "model.py"
    model.write_text(drifted)
    out = tmp_path / "out"
    with pytest.raises(UnsupportedWitnessError):
        build(model, FIXTURES / "map.toml", out)
    assert not (out / "fixture_figure.dot").exists()


def test_identity_without_mechanism_fails(config, concept_edges):
    figure = copy.deepcopy(config.figures[0])
    del figure["edges"][0]["mechanism"]
    with pytest.raises(MissingMechanismError, match="identity"):
        audit_figure(figure, concept_edges)


def test_parameter_without_mechanism_fails(config, concept_edges):
    figure = copy.deepcopy(config.figures[0])
    del figure["edges"][3]["mechanism"]
    with pytest.raises(MissingMechanismError, match="parameter"):
        audit_figure(figure, concept_edges)


def test_unmapped_variables_reported(tmp_path):
    report = build(FIXTURES / "model.py", FIXTURES / "map.toml", tmp_path)
    names = {name for name, _ in report.unmapped}
    assert "delay" in names          # real unmapped model variable
    assert "report" in names
    assert "state" not in names      # in [extract] ignore
    assert "demand" not in names     # mapped
    assert "np.tanh" not in names    # in [extract] ignore_prefixes
    csv_text = (tmp_path / "unmapped_variables.csv").read_text()
    assert "delay" in csv_text


def test_unwitnessed_concept_edges_reported(config, concept_edges):
    """The dual direction: mechanisms in the code that no figure cites."""
    uncited = unwitnessed_concept_edges(concept_edges, config.figures)
    pairs = {(e.source, e.target) for e in uncited}
    assert ("outflow", "stock") in pairs        # code has it, figure omits it
    assert ("inflow", "stock") not in pairs     # cited as witness
