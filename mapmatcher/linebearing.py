# Based on https://gist.github.com/jeromer/2005586
import math
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
    points = line_gdf.geometry.extract_unique_points().explode().reset_index()
    first = points.loc[points.groupby(["link_id"]).level_1.idxmin()][0]
    last = points.loc[points.groupby(["link_id"]).level_1.idxmax()][0]
    return vectorized_line_bearing(
        first.geometry.y.values, first.geometry.x.values, last.geometry.y.values, last.geometry.x.values
    )


def vectorized_line_bearing(lat1, long1, lat2, long2):
    latA = np.radians(lat1)
    latB = np.radians(lat2)

    delta_long = np.radians(long2 - long1)

    x = np.sin(delta_long) * np.cos(latB)
    y = np.cos(latA) * np.sin(latB) - (np.sin(latA) * np.cos(latB) * np.cos(delta_long))
    bearing_radians = np.arctan2(x, y)
    bearing_degrees = np.degrees(bearing_radians)
    return (bearing_degrees + 360) % 360
