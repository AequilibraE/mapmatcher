from pathlib import Path

import geopandas as gpd
import pandas as pd


def test_compute_stop():
    df = pd.read_csv(Path(__file__).parent / "data" / "traces.csv")

    df.timestamp = pd.to_datetime(df.timestamp, unit="s")
    df.rename(columns={"x": "longitude", "y": "latitude"}, inplace=True)
    df = df[df.trace_id == 12]
    geometry = gpd.points_from_xy(df.longitude, df.latitude, crs="EPSG:4326")
    trace = gpd.GeoDataFrame(df, geometry=geometry)
    assert trace.shape[0] > 0
