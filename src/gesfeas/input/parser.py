import pandas as pd
from typing import Union
import io
import os

from .errors import InvalidDataFormatError, MissingMonthError, OutOfRangeError

def parse_consumption_csv(file_path_or_buffer: Union[str, os.PathLike, io.StringIO]) -> pd.DataFrame:
    """
    Parses a consumption CSV file and returns a normalized pandas DataFrame.
    Supports both monthly totals (12 rows) and hourly data (8760 or 8784 rows).
    """
    try:
        df = pd.read_csv(file_path_or_buffer)
    except Exception as e:
        raise InvalidDataFormatError(f"Could not read CSV: {str(e)}")

    if df.empty:
        raise InvalidDataFormatError("CSV file is empty.")

    columns = [str(col).lower().strip() for col in df.columns]
    df.columns = columns

    if 'consumption_kwh' not in columns:
        raise InvalidDataFormatError("Missing required column 'consumption_kwh'.")

    # Validate consumption_kwh is numeric and non-negative
    try:
        df['consumption_kwh'] = pd.to_numeric(df['consumption_kwh'])
    except ValueError:
        raise InvalidDataFormatError("'consumption_kwh' contains non-numeric values.")

    if df['consumption_kwh'].isnull().any():
        raise InvalidDataFormatError("'consumption_kwh' contains null or non-numeric values.")

    if (df['consumption_kwh'] < 0).any():
        raise OutOfRangeError("'consumption_kwh' cannot contain negative values.")

    if 'month' in columns:
        # Expecting 12 monthly rows
        if len(df) != 12:
            raise MissingMonthError(f"Monthly data expected exactly 12 rows, got {len(df)}.")
        
        try:
            df['month'] = pd.to_numeric(df['month'])
            if set(df['month']) != set(range(1, 13)):
                raise MissingMonthError("Month column must contain all months from 1 to 12.")
        except ValueError:
            raise InvalidDataFormatError("Month column must be numeric integers (1-12).")
        
        df = df.set_index('month').sort_index()
        return df[['consumption_kwh']]

    elif 'datetime' in columns or 'timestamp' in columns:
        time_col = 'datetime' if 'datetime' in columns else 'timestamp'
        # Expecting hourly data (8760 or 8784 rows)
        if len(df) not in (8760, 8784):
            raise InvalidDataFormatError(f"Hourly data expected 8760 or 8784 rows, got {len(df)}.")
        
        try:
            df[time_col] = pd.to_datetime(df[time_col])
        except Exception as e:
            raise InvalidDataFormatError(f"Could not parse '{time_col}' column as datetime: {str(e)}")
        
        df = df.set_index(time_col).sort_index()
        return df[['consumption_kwh']]
    else:
        raise InvalidDataFormatError("CSV must contain either 'month' or 'datetime'/'timestamp' column.")
