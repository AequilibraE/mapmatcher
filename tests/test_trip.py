import uuid
from os.path import join
from pathlib import Path
from tempfile import gettempdir

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from aequilibrae.utils.create_example import create_example

from mapmatcher.network import Network
from mapmatcher.parameters import Parameters
from mapmatcher.trip import Trip


@pytest.fixture
def gps_trace() -> gpd.GeoDataFrame:
    df = pd.read_csv(Path(__file__).parent / "data" / "trace_all_fields.csv")
    df.timestamp = pd.to_datetime(df.timestamp)
    geometry = gpd.points_from_xy(df.x, df.y, crs="EPSG:4326")
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


@pytest.fixture
def param() -> Parameters:
    par = Parameters()
    par.data_quality.maximum_jittery = 20000
    par.data_quality.max_speed = 41
    par.map_matching.buffer_size = 10000000000000000
    return par


def test_trip(gps_trace, param, network):
    trp = Trip(gps_trace=gps_trace, parameters=param, network=network)
    assert not trp.has_error


def test_buffer_size(gps_trace, param, network):
    param.map_matching.buffer_size = 50
    param.data_quality.maximum_jittery = 0.01
    param.data_quality.max_speed_time = 0

    trp = Trip(gps_trace=gps_trace, parameters=param, network=network)

    error = ",".join(trp._err)
    assert trp.has_error
    assert "from any network lin" in error
    assert "jitter" in error
    assert "surpassed" in error


def test_unmatchable(gps_trace, param, network):
    param.map_matching.buffer_size = 0.1
    param.map_matching.keep_ping_classification = True
    param.map_matching.buffer_size = 0
    trp = Trip(gps_trace=gps_trace, parameters=param, network=network)

    assert trp._unmatchable.shape[0] == trp.trace.shape[0]

    param.map_matching.buffer_size = 10000000000000000
    trp2 = Trip(gps_trace=gps_trace, parameters=param, network=network)

    assert trp2._unmatchable.shape[0] == 0
