import uuid
from os.path import join
from pathlib import Path
from tempfile import gettempdir

import numpy as np
import geopandas as gpd
import pandas as pd
import pytest
from aequilibrae.utils.create_example import create_example

from mapmatcher.map_matcher import MapMatcher
from mapmatcher.network import Network
from mapmatcher.parameters import Parameters


@pytest.fixture
def gps_traces() -> gpd.GeoDataFrame:
    df = pd.read_csv(Path(__file__).parent / "data" / "traces.csv")
    df.timestamp = pd.to_datetime(df.timestamp, unit="s")
    df.rename(columns={"x": "longitude", "y": "latitude"}, inplace=True)
    geometry = gpd.points_from_xy(df.longitude, df.latitude, crs="EPSG:4326")
    return gpd.GeoDataFrame(df, geometry=geometry)


@pytest.fixture
def network() -> Network:
    proj = create_example(join(gettempdir(), uuid.uuid4().hex), "nauru")
    with proj.db_connection as conn:
        conn.execute("Update Nodes set is_centroid=1 where node_id = 1")
    proj.network.build_graphs(modes=["c"])
    graph = proj.network.graphs["c"]
    graph.prepare_graph(np.array([1], int))
    graph.set_graph("distance")
    links = proj.network.links.data
    links.drop(["a_node", "b_node"], axis=1, inplace=True)
    return Network(graph=graph, links=links, parameters=Parameters())


def test_mapmatcher(gps_traces, network):
    mm = MapMatcher()
    mm.parameters.map_matching.maximum_waypoints = 2
    mm.network = network
    mm.load_gps_traces(gps_traces)
    mm.map_match(True, parallel_threads=1)
    assert len(mm.trips) == len(gps_traces.trace_id.unique())
