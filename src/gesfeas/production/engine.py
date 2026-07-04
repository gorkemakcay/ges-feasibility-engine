import pandas as pd
from pvlib import pvsystem, location, modelchain
from typing import Optional
from .models import ProductionResult
from .pvgis import fetch_pvgis_tmy
from gesfeas.input.models import SiteParameters, MountType

def estimate_system_size_kwp(area_m2: float, mount_type: MountType) -> float:
    """Estimate system size based on available area and mount type."""
    if mount_type == MountType.ROOFTOP:
        return area_m2 / 5.0  # roughly 200 W/m2
    else:
        return area_m2 / 10.0 # roughly 100 W/m2 due to spacing for ground mount

def run_production_model(
    site: SiteParameters,
    system_size_kwp: Optional[float] = None,
    tracking: bool = False,
    weather_df: Optional[pd.DataFrame] = None
) -> ProductionResult:
    """
    Compute PV production using pvlib.
    """
    # 1. Determine System Size
    if system_size_kwp is None:
        kwp = estimate_system_size_kwp(site.available_area_m2, site.mount_type)
    else:
        kwp = system_size_kwp

    # 2. Fetch Weather Data (if not provided via mock/offline)
    if weather_df is None:
        weather_df, _ = fetch_pvgis_tmy(site.location.lat, site.location.lon)

    # Make sure timezone is set properly for the location if not already
    # PVGIS data is in UTC by default. The Location object should match.
    tz = 'UTC'
    loc = location.Location(site.location.lat, site.location.lon, tz=tz)

    # 3. Define PV System
    # We use pvwatts model which is simple and robust for feasibility.
    
    # DC size in Watts
    pdc0 = kwp * 1000.0

    # Mount/Tilt rules:
    tilt = 20.0
    if site.mount_type == MountType.GROUND:
        tilt = site.location.lat - 10 if site.location.lat > 10 else 20.0
        
    azimuth = 180.0 # South facing

    temperature_model_parameters = pvsystem.temperature.TEMPERATURE_MODEL_PARAMETERS['sapm']['open_rack_glass_glass']

    if site.mount_type == MountType.GROUND and tracking:
        mount = pvsystem.SingleAxisTrackerMount(
            axis_tilt=0.0,
            axis_azimuth=180.0,
            max_angle=60.0,
            backtrack=True,
            gcr=0.3
        )
    else:
        mount = pvsystem.FixedMount(surface_tilt=tilt, surface_azimuth=azimuth)

    array = pvsystem.Array(
        mount=mount,
        module_parameters={'pdc0': pdc0, 'gamma_pdc': -0.004},
        temperature_model_parameters=temperature_model_parameters
    )

    system = pvsystem.PVSystem(
        arrays=[array],
        inverter_parameters={'pdc0': pdc0 / 1.2, 'eta_inv_nom': 0.96} # 1.2 DC/AC ratio
    )

    # 4. Run ModelChain
    mc = modelchain.ModelChain(system, loc, aoi_model='physical', spectral_model='no_loss')
    mc.run_model(weather_df)

    # 5. Extract Results
    ac_power_w = mc.results.ac
    ac_power_w = ac_power_w.fillna(0) # replace NaNs with 0
    # AC power from PVWatts could be a Series. Extract as float list.
    hourly_kwh = (ac_power_w / 1000.0).tolist()
    
    annual_kwh = sum(hourly_kwh)
    capacity_factor = annual_kwh / (kwp * 8760.0)

    return ProductionResult(
        annual_energy_kwh=annual_kwh,
        capacity_factor=capacity_factor,
        system_size_kwp=kwp,
        hourly_production_kwh=hourly_kwh
    )
