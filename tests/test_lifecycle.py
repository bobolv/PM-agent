from pm_agent.lifecycle import DEFAULT_PHASES, DOCUMENT_CATALOG, PERIODIC_TEMPLATES


def test_default_lifecycle_has_required_phases() -> None:
    names = [phase.name for phase in DEFAULT_PHASES]

    assert "需求调研" in names
    assert "初步设计" in names
    assert "项目验收" in names
    assert "系统运维" in names


def test_document_catalog_has_expanded_phase_documents() -> None:
    codes = [item.code for item in DOCUMENT_CATALOG]

    assert "req-stakeholder-map" in codes
    assert "req-report" in codes
    assert "prelim-architecture" in codes
    assert "detail-api-spec" in codes
    assert "acceptance-report" in codes


def test_periodic_templates_are_seeded() -> None:
    names = [template[0] for template in PERIODIC_TEMPLATES]

    assert "项目周报" in names
    assert "项目月报" in names
