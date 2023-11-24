import logging
from os import PathLike
from pathlib import Path
from tempfile import gettempdir
from typing import List, Optional, Union

import geopandas as gpd
import numpy as np
import pandas as pd
from aequilibrae import Project
from aequilibrae.paths import Graph
from tqdm import tqdm

from .network import Network
from .parameters import Parameters
from .trip import Trip


class MapMatcher:
    """Performs map-matching.

    .. code-block:: python

        >>> from mapmatcher import MapMatcher

        >>> matcher = MapMatcher.from_aequilibrae(project, "c")
        >>> mmatcher.load_gps_traces(nauru_gps)
        >>> mmatcher.execute()
    """

    __mandatory_fields = ["trace_id", "timestamp"]

    def __init__(self):
        self.__orig_crs = 4326
        self.network: Network() = None
        self.trips: List[Trip] = []
        self.output_folder = None
        self.__traces: gpd.GeoDataFrame
        self.parameters = Parameters()
        self.__log_folder = Path(gettempdir())

    @staticmethod
    def from_aequilibrae(proj: Project, mode: str):
        """Loads the network and creates the graph from an existing AequilibraE project.

        :Arguments:
            **proj** (:obj:`aequilibrae.project.Project`): path to existing project.

            **mode** (:obj:`str`): mode to create the graph
        """
        proj.network.build_graphs(modes=[mode])
        graph = proj.network.graphs[mode]
        graph.prepare_graph(np.array([1]))
        graph.set_graph("distance")
        link_sql = "SELECT link_id, Hex(ST_AsBinary(geometry)) as geometry FROM links;"
        nodes_sql = "SELECT node_id, Hex(ST_AsBinary(geometry)) as geometry FROM nodes;"
        links = gpd.GeoDataFrame.from_postgis(link_sql, proj.conn, geom_col="geometry", crs=4326)
        nodes = gpd.GeoDataFrame.from_postgis(nodes_sql, proj.conn, geom_col="geometry", crs=4326)

        mmatcher = MapMatcher()
        mmatcher.load_network(graph=graph, links=links, nodes=nodes)
        return mmatcher

    def set_output_folder(self, output_folder: str):
        """Name of the output folder.

        :Arguments:

            **output_folder** (:obj:`str`): path to folder
        """
        self.output_folder = output_folder

    def load_network(self, graph: Graph, links: gpd.GeoDataFrame, nodes: Optional[gpd.GeoDataFrame] = None):
        """Loads the project network.

        :Arguments:

            **graph** (:obj:`aequilibrae.graph.Graph`): AequilibraE graph

            **links** (:obj:`gpd.GeoDataFrame`): GeoDataFrame with the network links

            **nodes** (:obj:`gpd.GeoDataFrame`, optional): GeoDataFrame with the network nodes
        """
        self.network = Network(graph=graph, links=links, nodes=nodes, parameters=self.parameters)

    def load_gps_traces(self, gps_traces: Union[gpd.GeoDataFrame, PathLike], crs: Optional[int] = None):
        """
        Loads the GPS traces to the map-matcher.

        Coordinate system for GPS pings must ALWAYS be 4326 when loading from CSV.
        Required fields are:  ["trace_id", "latitude", "longitude", "timestamp"]

        :Arguments:

            **gps_trace** (:obj:`gpd.GeoDataFrame`): GeoDataFrame containing the vehicle GPS traces.

            **crs** (:obj: `int`, optional): coordinate system

        """

        if isinstance(gps_traces, gpd.GeoDataFrame):
            self.__orig_crs = gps_traces.crs
            traces = gps_traces
        else:
            traces = pd.read_csv(gps_traces)
            traces = gpd.GeoDataFrame(
                traces, geometry=gpd.points_from_xy(traces.longitude, traces.latitude), crs=f"EPSG:{crs}"
            )

        for fld in self.__mandatory_fields:
            if fld not in traces:
                raise ValueError(f"Field {fld} is missing from the data")

        self.__traces = traces.to_crs(self.parameters.geoprocessing.projected_crs)

    def _build_trips(self):
        self.trips.clear()
        for _, gdf in self.__traces.groupby(["trace_id"]):
            self.trips.append(Trip(gps_trace=gdf, parameters=self.parameters, network=self.network))

    def map_match(self, ignore_errors=False, robust=True):
        """Executes map-matching."""
        self.__logger()
        self._build_trips()
        self.network._orig_crs = self.__orig_crs
        success = 0
        if robust:
            for trip in tqdm(self.trips, "Map matching trips"):  # type: Trip
                try:
                    trip.map_match(ignore_errors)
                    success += trip.success
                finally:
                    logging.getLogger("mapmatcher").critical(f"{trip.id} failed to map-match with critical error")
        else:
            for trip in tqdm(self.trips, "Map matching trips"):  # type: Trip
                trip.map_match(ignore_errors)
                success += trip.success

        logging.critical(f"Succeeded:{success:,}")
        logging.critical(f"Failed:{len(self.trips) - success:,}")

    def set_logging_folder(self, folder):
        self.__log_folder = Path(folder)

    def __logger(self):
        logger = logging.getLogger("mapmatcher")
        logger.setLevel(1000)
        for h in [h for h in logger.handlers if h.name and "mapmatcherfile" == h.name]:
            h.close()
            logger.removeHandler(h)

        log_path = self.__log_folder / "mapmatcher.log"

        FORMATTER = logging.Formatter("%(asctime)s;%(levelname)s ; %(message)s", datefmt="%H:%M:%S:")
        ch = logging.FileHandler(log_path)
        ch.setFormatter(FORMATTER)
        ch.set_name("mapmatcherfile")
        ch.setLevel(logging.INFO)
        logger.addHandler(ch)
