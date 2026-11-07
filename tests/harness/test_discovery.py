"""Tests for dbt project discovery service."""

import pytest
from harness.core.config import get_config
from harness.services.discovery import DiscoveryService


@pytest.fixture
def discovery_service():
    return DiscoveryService(get_config())


def test_discover_project(discovery_service):
    overview = discovery_service.discover_project()
    assert overview.project_name == "anac_lakehouse"
    assert overview.total_models >= 5
    assert "trusted" in overview.layers
    assert "staging" in overview.layers
    assert "aeronaves" in overview.entities


def test_list_models_and_filter_layer(discovery_service):
    all_models = discovery_service.list_models()
    assert len(all_models) >= 5

    trusted_models = discovery_service.list_models(layer="trusted")
    assert any(m.name == "dim_aeronaves" for m in trusted_models)
    assert all(m.layer == "trusted" for m in trusted_models)


def test_get_model_details(discovery_service):
    model = discovery_service.get_model_details("dim_aeronaves")
    assert model is not None
    assert model.name == "dim_aeronaves"
    assert model.layer == "trusted"
    assert "marca_aeronave" in model.columns
    col = model.columns["marca_aeronave"]
    assert "unique" in col.tests or "not_null" in col.tests


def test_get_model_lineage(discovery_service):
    lineage = discovery_service.get_model_lineage("dim_aeronaves")
    assert lineage.model_name == "dim_aeronaves"
    assert "stg_anac__rab_aeronaves" in lineage.upstream


def test_get_entity_definitions(discovery_service):
    entities = discovery_service.get_entity_definitions()
    assert len(entities) >= 1
    aeronave = next((e for e in entities if e.entity_name == "aeronaves"), None)
    assert aeronave is not None
    assert aeronave.model_name == "dim_aeronaves"
    assert aeronave.primary_key == "marca_aeronave"
    assert "is_apta_para_voo" in aeronave.features

