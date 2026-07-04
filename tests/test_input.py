import pytest
import pandas as pd
import io
from pydantic import ValidationError

from gesfeas.input import (
    SiteParameters,
    Location,
    MountType,
    ShiftPattern,
    ConnectionType,
    parse_consumption_csv,
    InputError,
    MissingMonthError,
    InvalidDataFormatError,
    OutOfRangeError,
)

def test_site_parameters_valid():
    site = SiteParameters(
        location=Location(lat=39.9, lon=32.8),
        available_area_m2=1000.5,
        transformer_capacity_kva=400,
        mount_type=MountType.ROOFTOP,
        shift_pattern=ShiftPattern.SINGLE,
        connection_type=ConnectionType.ON_GRID,
    )
    assert site.location.lat == 39.9
    assert site.available_area_m2 == 1000.5
    assert site.mount_type == MountType.ROOFTOP

def test_site_parameters_invalid_location():
    with pytest.raises(ValidationError):
        Location(lat=100, lon=32.8)  # lat out of range

def test_site_parameters_invalid_area():
    with pytest.raises(ValidationError):
        SiteParameters(
            location=Location(lat=39.9, lon=32.8),
            available_area_m2=-10,  # Negative area
            transformer_capacity_kva=400,
            mount_type=MountType.ROOFTOP,
            shift_pattern=ShiftPattern.SINGLE,
            connection_type=ConnectionType.ON_GRID,
        )

def test_parse_consumption_valid_fixture():
    df = parse_consumption_csv("tests/fixtures/consumption_valid.csv")
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 12
    assert list(df.columns) == ["consumption_kwh"]
    assert df.index.name == "month"
    assert df.loc[1, "consumption_kwh"] == 1000

def test_parse_consumption_missing_month():
    csv_data = """month,consumption_kwh
1,1000
2,1100
"""
    with pytest.raises(MissingMonthError):
        parse_consumption_csv(io.StringIO(csv_data))

def test_parse_consumption_bad_number():
    csv_data = """month,consumption_kwh
1,1000
2,bad_value
"""
    with pytest.raises(InvalidDataFormatError, match="non-numeric"):
        parse_consumption_csv(io.StringIO(csv_data))

def test_parse_consumption_negative_value():
    csv_data = """month,consumption_kwh
1,1000
2,-500
3,1000
4,1000
5,1000
6,1000
7,1000
8,1000
9,1000
10,1000
11,1000
12,1000
"""
    with pytest.raises(OutOfRangeError, match="negative"):
        parse_consumption_csv(io.StringIO(csv_data))

def test_parse_consumption_missing_column():
    csv_data = """month,energy
1,1000
2,1100
"""
    with pytest.raises(InvalidDataFormatError, match="Missing required column"):
        parse_consumption_csv(io.StringIO(csv_data))

def test_parse_consumption_hourly_valid():
    # Generate an 8760 line CSV using pandas
    dates = pd.date_range(start="2023-01-01", periods=8760, freq="h")
    df_hourly = pd.DataFrame({"datetime": dates, "consumption_kwh": 10})
    csv_str = df_hourly.to_csv(index=False)
    
    parsed_df = parse_consumption_csv(io.StringIO(csv_str))
    assert len(parsed_df) == 8760
    assert list(parsed_df.columns) == ["consumption_kwh"]
    assert parsed_df.index.name == "datetime"

def test_parse_consumption_hourly_invalid_length():
    dates = pd.date_range(start="2023-01-01", periods=8000, freq="h")
    df_hourly = pd.DataFrame({"datetime": dates, "consumption_kwh": 10})
    csv_str = df_hourly.to_csv(index=False)
    
    with pytest.raises(InvalidDataFormatError, match="Hourly data expected 8760 or 8784 rows"):
        parse_consumption_csv(io.StringIO(csv_str))
