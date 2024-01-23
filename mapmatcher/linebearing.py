# Based on https://gist.github.com/jeromer/2005586
import geopandas as gpd
import numpy as np


def bearing_for_gps(trace: gpd.GeoDataFrame):
    longs = trace.geometry.x.values
    lats = trace.geometry.y.values
    compass_bearing = vectorized_line_bearing(lats[:-1], longs[:-1], lats[1:], longs[1:])
    array = np.zeros(trace.shape[0])
    array[:-1] = compass_bearing[:]
    array[-1] = compass_bearing[-1]
    return array


def bearing_for_lines(line_gdf: gpd.GeoDataFrame):
    points = line_gdf.geometry.extract_unique_points().explode(index_parts=True).reset_index()

    first = points.loc[points.groupby(["link_id"]).level_1.idxmax()][["link_id", 0]].rename(columns={0: "first_geo"})
    last = points.loc[points.groupby(["link_id"]).level_1.idxmin()][["link_id", 0]].rename(columns={0: "last_geo"})
    data = first.merge(last, on="link_id")

    first_ = gpd.GeoSeries(data.first_geo)
    last_ = gpd.GeoSeries(data.last_geo)
    bearing = vectorized_line_bearing(
        first_.geometry.y.values, first_.geometry.x.values, last_.geometry.y.values, last_.geometry.x.values
    )

    return data.assign(net_link_az=bearing)[["net_link_az", "link_id"]]


def vectorized_line_bearing(lat1, long1, lat2, long2):
    latA = lat1
    latB = lat2

    delta_long = long2 - long1

    x = np.sin(delta_long) * np.cos(latB)
    y = np.cos(latA) * np.sin(latB) - (np.sin(latA) * np.cos(latB) * np.cos(delta_long))
    bearing_radians = np.arctan2(x, y)
    return np.degrees(bearing_radians)
