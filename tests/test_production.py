import pytest
import pandas as pd
import json
import os
from gesfeas.input.models import SiteParameters, Location, MountType, ShiftPattern, ConnectionType
from gesfeas.production import run_production_model

FIXTURE_CSV = os.path.join(os.path.dirname(__file__), "fixtures", "pvgis_tmy_ankara.csv")

@pytest.fixture
def ankara_weather():
    # Read the cached CSV file. TMY from PVGIS usually has a DatetimeIndex
    df = pd.read_csv(FIXTURE_CSV, index_col=0, parse_dates=True)
    # pvlib expects the index to have a timezone. We assume UTC for PVGIS.
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC')
    return df

@pytest.fixture
def base_site():
    return SiteParameters(
        location=Location(lat=39.92077, lon=32.85411),
        available_area_m2=1000.0,
        transformer_capacity_kva=400.0,
        mount_type=MountType.ROOFTOP,
        shift_pattern=ShiftPattern.SINGLE,
        connection_type=ConnectionType.ON_GRID
    )

def test_production_rooftop(ankara_weather, base_site):
    """Test standard rooftop calculation using offline weather data."""
    result = run_production_model(site=base_site, weather_df=ankara_weather)
    
    # 1000 m2 / 5.0 = 200 kWp expected
    assert result.system_size_kwp == 200.0
    
    # Check that we have exactly 8760 hours of data
    assert len(result.hourly_production_kwh) == 8760
    
    # Check that annual energy is roughly within sensible bounds
    # Ankara CF is usually around 15-18% (1300 - 1600 kWh/kWp)
    # 200 kWp * 1300 = 260,000 kWh minimum, 200 * 1600 = 320,000 kWh max
    assert 200000 < result.annual_energy_kwh < 350000
    
    # Check capacity factor consistency
    assert result.capacity_factor == result.annual_energy_kwh / (200.0 * 8760)

def test_production_ground(ankara_weather, base_site):
    """Test standard ground calculation using offline weather data."""
    ground_site = base_site.model_copy(update={'mount_type': MountType.GROUND})
    
    result = run_production_model(site=ground_site, weather_df=ankara_weather)
    
    # 1000 m2 / 10.0 = 100 kWp expected
    assert result.system_size_kwp == 100.0
    
    # Check output
    assert len(result.hourly_production_kwh) == 8760
    assert 100000 < result.annual_energy_kwh < 180000

def test_production_ground_tracking(ankara_weather, base_site):
    """Test single-axis tracking."""
    ground_site = base_site.model_copy(update={'mount_type': MountType.GROUND})
    
    result_fixed = run_production_model(site=ground_site, weather_df=ankara_weather, tracking=False)
    result_track = run_production_model(site=ground_site, weather_df=ankara_weather, tracking=True)
    
    # Tracking should generally produce more energy annually than fixed
    assert result_track.annual_energy_kwh > result_fixed.annual_energy_kwh

@pytest.mark.skip(reason="Live PVGIS API call")
def test_production_live_api(base_site):
    """Optional live integration test."""
    result = run_production_model(site=base_site)
    assert result.system_size_kwp == 200.0
    assert len(result.hourly_production_kwh) == 8760
    assert result.annual_energy_kwh > 0
