import logging
import multiprocessing as mp
from math import ceil
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
from .run_chunk import run_trips
from .trip import Trip


class MapMatcher:
    """Performs map-matching.

    .. code-block:: python

        >>> from mapmatcher import MapMatcher

        >>> matcher = MapMatcher.from_aequilibrae(project, "c")
        >>> matcher.load_gps_traces(nauru_gps)
        >>> matcher.map_match()
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
        links = gpd.GeoDataFrame.from_postgis(link_sql, proj.conn, geom_col="geometry", crs=4326)

        mmatcher = MapMatcher()
        mmatcher.load_network(graph=graph, links=links)
        return mmatcher

    def set_output_folder(self, output_folder: str):
        """Name of the output folder.

        :Arguments:

            **output_folder** (:obj:`str`): path to folder
        """
        self.output_folder = output_folder

    def load_network(self, graph: Graph, links: gpd.GeoDataFrame):
        """Loads the project network.

        :Arguments:

            **graph** (:obj:`aequilibrae.graph.Graph`): AequilibraE graph

            **links** (:obj:`gpd.GeoDataFrame`): GeoDataFrame with the network links
        """
        self.network = Network(graph=graph, links=links, parameters=self.parameters)

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
        for _, gdf in tqdm(self.__traces.groupby(["trace_id"]), "building trips"):
            self.trips.append(Trip(gps_trace=gdf, parameters=self.parameters, network=self.network))

    def map_match(self, ignore_errors=False, parallel_threads: int = 0):
        """Executes map-matching.

        :Arguments:
            **ignore_errors** (:obj:`bool`): Attempts to perform map-matching even when the data does not meet all
            data quality criteria

            **parallel_threads** (:obj:`int`, optional): Number of CPU threads to use. Defaults to all

        :Returns:

            *object* (:obj:`np.ndarray`): NumPy array
        """
        self.network._orig_crs = self.__orig_crs
        success = 0
        if parallel_threads <= 0:
            parallel_threads = max(1, mp.cpu_count() - int(parallel_threads))
        if parallel_threads == 1:
            self.__logger()
            logging.critical("Building up data structures")
            self._build_trips()
            for trip in tqdm(self.trips, "Map matching trips"):  # type: Trip
                try:
                    trip.map_match(ignore_errors)
                    success += trip.success
                finally:
                    logging.getLogger("mapmatcher").critical(f"{trip.id} failed to map-match with critical error")
        else:
            logging.getLogger("mapmatcher").info("Preparing multi-processing")

            def jobs(all_ids, threads):
                return [all_ids[i : i + threads] for i in range(0, len(all_ids), threads)]

            all_ids = self.__traces.trace_id.unique()
            all_jobs = jobs(all_ids, ceil(len(all_ids) / parallel_threads))

            self.__traces = self.__traces.assign(chunk_id__=0)
            for i, trace_set in enumerate(all_jobs):
                self.__traces.loc[self.__traces.trace_id.isin(trace_set), "chunk_id__"] = i

            all_trips = []

            def accumulator(trip_list):
                all_trips.extend(trip_list)

            logging.getLogger("mapmatcher").info("Starting parallel processing")
            with mp.Pool(int(min(parallel_threads, len(all_jobs)))) as pool:
                for _, job_gdf in self.__traces.groupby("chunk_id__"):
                    pool.apply_async(
                        run_trips,
                        args=(
                            job_gdf,
                            self.parameters,
                            self.network,
                            ignore_errors,
                        ),
                        callback=accumulator,
                    )
                pool.close()
                pool.join()

            success = sum([trip.success for trip in all_trips])
            self.trips = all_trips

        logging.getLogger("mapmatcher").critical(f"Succeeded:{success:,}")
        logging.getLogger("mapmatcher").critical(f"Failed:{len(self.trips) - success:,}")

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
