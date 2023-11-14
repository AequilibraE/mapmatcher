from os import PathLike
import logging
from typing import List, Optional, Union

import geopandas as gpd
import numpy as np
import pandas as pd
from aequilibrae import Project
from aequilibrae.paths import Graph

from .network import Network
from .parameters import Parameters
from .trip import Trip


class MapMatcher:
    """Performs map-matching."""
    __mandatory_fields = ["trace_id", "latitude", "longitude", "timestamp"]

    def __init__(self):
        self.__orig_crs = 4326
        self.network: Network() = None
        self.trips: List[Trip] = []
        self.output_folder = None
        self.__usr_stops = False
        self.__traces: gpd.GeoDataFrame
        self.__stops: Optional[gpd.GeoDataFrame] = None
        self.parameters = Parameters()

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

    def set_stop_algorithm(self, stop_algorithm):
        """Sets the stop algorithm.
        
        :Arguments:

            **stop_algorithm** (:obj:`str`)
        """
        if stop_algorithm not in self.parameters.algorithm_parameters:
            raise ValueError(f"Unknown Stop algorithm: {stop_algorithm}")
        self.parameters.stop_algorithm = stop_algorithm

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

    def load_stops(self, stops: Union[gpd.GeoDataFrame, PathLike]):
        """
        Loads the stops.

        :Arguments:

            **stops** (:obj:`Union[gpd.GeoDataFrame, PathLike]`): GeoDataFrame or PahLike containing the vehicle stops.
            
        """
        if isinstance(stops, gpd.GeoDataFrame):
            self.__stops = stops.to_crs(4326)
        else:
            stops = pd.read_csv(stops)
            self.__stops = gpd.GeoDataFrame(
                stops, geometry=gpd.points_from_xy(stops.longitude, stops.latitude), crs="EPSG:4326"
            )
        self.__usr_stops = True

    def _build_trips(self):
        self.trips.clear()
        for trace_id, gdf in self.__traces.groupby(["trace_id"]):
            stops = gpd.GeoDataFrame([]) if not self.__usr_stops else self.__stops[self.__stops.trace_id == trace_id]
            self.trips.append(Trip(gps_trace=gdf, stops=stops, parameters=self.parameters, network=self.network))

    def execute(self):
        """Executes map-matching."""
        self._build_trips()
        self.network._orig_crs = self.__orig_crs
        success = 0
        for trip in self.trips:  # type: Trip
            trip.map_match()
            success += trip.success
        logging.critical(f"Succeeded:{success:,}")
        logging.critical(f"Failed:{len(self.trips) - success:,}")
