import uuid
from os.path import join
from pathlib import Path
from tempfile import gettempdir

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
    proj.conn.execute("Update Nodes set is_centroid=1 where node_id = 1")
    proj.network.build_graphs(modes=["c"])
    graph = proj.network.graphs["c"]

    graph.set_graph("distance")
    link_sql = """SELECT link_id, a_node, b_node, Hex(ST_AsBinary(geometry)) as geometry FROM links where instr(modes, "c")>0;"""
    links = gpd.GeoDataFrame.from_postgis(link_sql, proj.conn, geom_col="geometry", crs=4326)
    links.drop(["a_node", "b_node"], axis=1, inplace=True)
    return Network(graph=graph, links=links, parameters=Parameters())


def test_mapmatcher(gps_traces, network):
    mm = MapMatcher()
    mm.parameters.map_matching.maximum_waypoints = 2
    mm.network = network
    mm.load_gps_traces(gps_traces)
    mm.map_match(True, parallel_threads=1)
    assert len(mm.trips) == len(gps_traces.trace_id.unique())
