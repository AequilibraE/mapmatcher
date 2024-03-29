import geopandas as gpd
import numpy as np
import pandas as pd

from mapmatcher.linebearing import bearing_for_gps


def test_line_bearing():
    df = pd.DataFrame(
        {
            "node_id": np.arange(4),
            "Latitude": [0, 0, 0, -1],
            "Longitude": [0, 1, 0, 0],
        }
    )
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.Longitude, df.Latitude), crs="EPSG:4326")
    a = bearing_for_gps(gdf)
    np.testing.assert_array_equal(np.array([90, -90, 180, 180]), a)
