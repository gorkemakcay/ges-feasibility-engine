import pytest
from pathlib import Path

from gesfeas.input.models import SiteParameters, Location, MountType, ShiftPattern, ConnectionType
from gesfeas.regulation.models import RegulationConfig, GroundMountEligibility, NettingMode
from gesfeas.regulation.engine import evaluate_compliance, load_regulation_config

@pytest.fixture
def base_site():
    return SiteParameters(
        location=Location(lat=39.9, lon=32.8),
        available_area_m2=1000.0,
        transformer_capacity_kva=100.0,
        mount_type=MountType.ROOFTOP,
        shift_pattern=ShiftPattern.SINGLE,
        connection_type=ConnectionType.ON_GRID
    )

@pytest.fixture
def rooftop_config(tmp_path):
    config_str = """
max_capacity_kw: 25.0
transformer_capacity_check_ratio: 1.0
self_consumption_ratio_min: 0.0
netting_mode: "hourly"
hybrid_storage_allowed: true
ground_mount_eligibility: null
    """
    p = tmp_path / "rooftop.yaml"
    p.write_text(config_str)
    return load_regulation_config(p)

@pytest.fixture
def ground_mount_config(tmp_path):
    config_str = """
max_capacity_kw: 1000.0
transformer_capacity_check_ratio: 1.0
self_consumption_ratio_min: 0.0
netting_mode: "hourly"
hybrid_storage_allowed: false
ground_mount_eligibility:
  industrial_or_agricultural_use: true
  zoning_status_approved: true
  eia_approved: true
    """
    p = tmp_path / "ground_mount.yaml"
    p.write_text(config_str)
    return load_regulation_config(p)

def test_rooftop_compliant(base_site, rooftop_config):
    res = evaluate_compliance(base_site, system_size_kw=20.0, self_consumption_ratio=None, regulation_config=rooftop_config)
    assert res.is_compliant is True
    assert len(res.violations) == 0

def test_rooftop_violation_max_capacity(base_site, rooftop_config):
    res = evaluate_compliance(base_site, system_size_kw=30.0, self_consumption_ratio=None, regulation_config=rooftop_config)
    assert res.is_compliant is False
    assert any("max_capacity_kw" in v for v in res.violations)

def test_config_driven_proof(base_site, tmp_path):
    # Change max_capacity_kw to 50, so 30 kW passes
    config_str = """
max_capacity_kw: 50.0
transformer_capacity_check_ratio: 1.0
self_consumption_ratio_min: 0.0
netting_mode: "hourly"
hybrid_storage_allowed: true
ground_mount_eligibility: null
    """
    p = tmp_path / "custom.yaml"
    p.write_text(config_str)
    config = load_regulation_config(p)
    
    res = evaluate_compliance(base_site, system_size_kw=30.0, self_consumption_ratio=None, regulation_config=config)
    assert res.is_compliant is True

def test_transformer_capacity_violation(base_site, rooftop_config):
    # Transformer is 100 kVA, system is 110 kW
    rooftop_config.max_capacity_kw = 200.0 # Make sure we only hit transformer limit
    res = evaluate_compliance(base_site, system_size_kw=110.0, self_consumption_ratio=None, regulation_config=rooftop_config)
    assert res.is_compliant is False
    assert any("transformer_capacity_check" in v for v in res.violations)

def test_self_consumption_ratio_violation(base_site, rooftop_config):
    base_site.connection_type = ConnectionType.SELF_CONSUMPTION_LIMITED
    rooftop_config.self_consumption_ratio_min = 0.5
    res = evaluate_compliance(base_site, system_size_kw=20.0, self_consumption_ratio=0.4, regulation_config=rooftop_config)
    assert res.is_compliant is False
    assert any("self_consumption_ratio_min" in v for v in res.violations)

def test_hybrid_storage_allowed_violation(base_site, ground_mount_config):
    # ground_mount_config has hybrid_storage_allowed: false
    base_site.mount_type = MountType.GROUND
    flags = GroundMountEligibility(industrial_or_agricultural_use=True, zoning_status_approved=True, eia_approved=True)
    res = evaluate_compliance(base_site, system_size_kw=500.0, self_consumption_ratio=None, regulation_config=ground_mount_config, is_hybrid_storage=True, ground_mount_flags=flags)
    assert res.is_compliant is False
    assert any("hybrid_storage_allowed" in v for v in res.violations)

def test_ground_mount_eligibility_violations(base_site, ground_mount_config):
    base_site.mount_type = MountType.GROUND
    # Missing flags completely
    res = evaluate_compliance(base_site, system_size_kw=500.0, self_consumption_ratio=None, regulation_config=ground_mount_config, ground_mount_flags=None)
    assert res.is_compliant is False
    assert any("Missing eligibility flags" in v for v in res.violations)

    # Missing specific flags
    flags = GroundMountEligibility(industrial_or_agricultural_use=False, zoning_status_approved=True, eia_approved=False)
    res2 = evaluate_compliance(base_site, system_size_kw=500.0, self_consumption_ratio=None, regulation_config=ground_mount_config, ground_mount_flags=flags)
    assert res2.is_compliant is False
    assert len([v for v in res2.violations if "ground_mount_eligibility" in v]) >= 2
