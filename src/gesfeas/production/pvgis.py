import pvlib
import pandas as pd
from typing import Tuple

def fetch_pvgis_tmy(lat: float, lon: float) -> Tuple[pd.DataFrame, dict]:
    """
    Fetches TMY data from PVGIS for the given coordinates.
    Isolated to allow mocking during tests.
    """
    data, meta = pvlib.iotools.get_pvgis_tmy(lat, lon, map_variables=True)
    return data, meta
