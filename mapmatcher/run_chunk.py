import geopandas as gpd
from typing import List

from .trip import Trip
from .parameters import Parameters
from .network import Network


def run_trips(trace_set: gpd.GeoDataFrame, parameters: Parameters, network: Network, ignore_errors: bool) -> List[Trip]:
    trips = []
    for _, gdf in trace_set.groupby(["trace_id"]):
        trips.append(Trip(gps_trace=gdf, parameters=parameters, network=network))

    for trip in trips:
        trip.map_match(ignore_errors)
    return trips
