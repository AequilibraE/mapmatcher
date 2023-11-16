import logging
from math import sqrt
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
from aequilibrae.paths.results import PathResults
from shapely.geometry import LineString
from shapely.ops import linemerge

from mapmatcher.network import Network

from .parameters import Parameters


class Trip:
    """Builds the path a vehicle did.

    .. code-block:: python

        >>> from mapmatcher.trip import Trip

        >>> trip = Trip(gps_trace, parameters, network)
        >>> trip.map_match()

        >>> trip.result.plot()

    """

    def __init__(
        self,
        gps_trace: gpd.GeoDataFrame,
        parameters: Parameters,
        network: Network
    ):
        # Fields necessary for running the algorithm
        """
        :Arguments:
            **gps_trace** (:obj:`gpd.GeoDataFrame`): GeoDataFrame containing the vehicle GPS traces.

            **parameters** (:obj:`Parameters`): Map-Matching parameters.

            **network** (:obj:`mapmatcher.network.Network`): MapMatcher Network object.

        """

        self.__coverage = -1.1
        self.__candidate_links = np.array([])
        self.__map_matched = 0
        self.id = -1

        self.parameters = parameters
        self.stops: Optional[gpd.GeoDataFrame] = None
        self._stop_nodes = []
        self.warnings = []
        self.__geo_path = LineString([])
        self.__mm_results = pd.DataFrame([], columns=["links", "direction", "milepost"])
        self.network = network
        self._error_type = "Data not loaded yet"

        # Creates the properties for the outputs
        self.trace = gps_trace.to_crs(parameters.geoprocessing.projected_crs)
        self.__pre_process()

        # Indicators to show if we have the optional fields in the data
        self.has_heading = "heading" in gps_trace

    def map_match(self, ignore_errors=False):
        """
        Performs map-matching.

        :Arguments:
            **ignore_errors** (:obj:`bool`):

        """
        if self.has_error:
            if not ignore_errors:
                logging.warning(
                    f"Cannot map-match trace id {self.id} due to : {self._error_type}. You can also try to ignore errors"
                )
                return

        # TODO: reset_graph takes a LOT of time because of the rebuilding of the graph. We need to hack the change of
        #       the cost field to avoid this insanity
        self.network.reset_graph()
        self.network.discount_graph(self.candidate_links)
        res = PathResults()
        res.prepare(self.network.graph)

        links = []
        directions = []
        mileposts = []
        position = 0

        # TODO: REPLACE WITH GOING FROM THE UPSTREAM (stop1) NODE OF THE FIRST LINK MATCH AND THE LINK DOWNSTREAM (stop2) OF THE LAST LINK MATCH

        res.compute_path(stop1, stop2)
        self.__mm_results = pd.DataFrame({"links": res.path, "direction": res.path_link_directions, "milepost": res.milepost[1:]})
        par = self.parameters.map_matching
        waypoints = 0
        while self.match_quality < par.minimum_match_quality and waypoints < par.maximum_waypoints:

            #TODO: MAKE THIS LOOK IN A WAY WHERE WE GET A WAYPOINT FROM THE NODES NOT MATCHED AND ADD THEM TO THE MIX
            break
            waypoints += 1


    @property
    def success(self):
        """
        Indicates the success of the map-matching procedure. If it succeeded, it returns `1`, otherwise returns `0`.
        """
        return self.__map_matched

    @property
    def path_shape(self) -> LineString:
        """Returns the `shapely.LineString` that represents the map-matched path."""
        if not self.__geo_path.length:
            links = self.network.links.loc[self.__mm_results.links.to_numpy(), :]
            geo_data = []
            for (_, rec), direction in zip(links.iterrows(), self.__mm_results.direction.to_numpy()):
                geo = rec.geometry if direction > 0 else LineString(rec.geometry.coords[::-1])
                geo_data.append(geo)
            self.__geo_path = linemerge(geo_data)
        return self.__geo_path

    @property
    def result(self):
        """Returns a GeoDataFrame containing the network links selected in map-matching."""
        links = self.network.links.loc[self.__mm_results.links.to_numpy(), :]
        # return links
        return gpd.GeoDataFrame(self.__mm_results, geometry=links.geometry.values, crs=links.crs).to_crs(
            self.network._orig_crs
        )

    @property
    def coverage(self) -> float:
        """Returns the distance (in metres) between the bounds of the geometries that represent the path."""
        if self.__coverage < 0:
            x1, y1, x2, y2 = self.trace.total_bounds
            self.__coverage = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        return self.__coverage

    @property
    def has_error(self) -> bool:
        """
        Indicates the presence of errors during the map-matching process.
        Returns `True` if there are any errors, otherwise, it returns `False`.
        """
        return len(self._error_type) > 0

    @property
    def candidate_links(self) -> np.ndarray:
        """Returns an array containing the candidate links."""
        if self.__candidate_links.shape[0] == 0:
            self.__network_links()
        return self.__candidate_links

    def __pre_process(self):
        dqp = self.parameters.data_quality
        self._error_type = ""

        if "trace_id" not in self.trace:
            raise ValueError("Trace does not have field trace_id")

        if len(self.trace.trace_id.unique()) > 1:
            raise ValueError("trace_id is not unique")

        self.id = self.trace.trace_id.values[0]

        self.trace.sort_values(by=["timestamp"], inplace=True)
        self.trace.reset_index(drop=True, inplace=True)
        # Check number of pings
        if self.trace.shape[0] < dqp.minimum_pings:
            self._error_type = f"Vehicle with only {self.trace.shape[0]} pings. Minimum is {dqp.minimum_pings}"

        if self.coverage < dqp.minimum_coverage:
            self._error_type += f"  Vehicle covers only {self.coverage:,.2} m. Minimum is {dqp.minimum_coverage}"

        # removes pings on the same spot
        self.trace["ping_posix_time"] = (self.trace.timestamp - pd.Timestamp("1970-01-01")) // pd.Timedelta("1s")

        diff_pings = self.trace.shape[0] - len(self.trace.ping_posix_time.unique())
        if diff_pings:
            self.warnings.append(f"There are {diff_pings:,} pings with the same timestamp")

            df = pd.DataFrame(
                {"ping_posix_time": self.trace.ping_posix_time, "x": self.trace.geometry.x, "y": self.trace.geometry.y}
            )
            agg = df.groupby(["ping_posix_time"]).agg(["min", "max", "count"])
            jitter = np.sqrt((agg.x["min"] - agg.x["max"]) ** 2 + (agg.y["min"] - agg.y["max"]) ** 2)
            if np.max(jitter) > (dqp.maximum_jittery):
                self._error_type += f"  Data is jittery. Same timestamp {np.max(jitter):,.2} m apart."

            self.trace.drop_duplicates(subset=["ping_posix_time"], inplace=True, keep="first")

            if self.trace.shape[0] < dqp.minimum_pings:
                self._error_type += f"   Vehicle with only {self.trace.shape[0]} pings. Minimum is {dqp.minimum_pings}"
        # Create data quality fields
        dist = self.trace.distance(self.trace.shift(1))
        ttime = (self.trace["timestamp"] - self.trace["timestamp"].shift(1)).dt.seconds.astype(float)
        speed = dist / ttime
        speed[0] = 0
        self.trace["trace_segment_dist"] = dist.fillna(0)
        self.trace["trace_segment_traveled_time"] = ttime.fillna(0)
        self.trace["trace_segment_speed"] = speed
        self.trace.trace_segment_speed.fillna(-1)

        # Verify data quality
        w = int(self.trace.trace_segment_traveled_time[self.trace.trace_segment_speed > dqp.max_speed].sum())
        if w > dqp.max_speed_time:
            # If there is evidence of speeding for longer than tolerated, we will see if it happens continuously
            too_fast = self.trace.groupby(self.trace.trace_segment_speed > dqp.max_speed)[
                "trace_segment_traveled_time"
            ].cumsum()
            if too_fast.max() > dqp.max_speed_time:
                self._error_type += f"  Max speed surpassed for {w} seconds"

    def compute_stops(self):
        """Compute stops."""

        raise NotImplementedError("Not implemented yet. Package supports map-matching only for now")

    def __network_links(self):
        if self.__candidate_links.shape[0]:
            return
        cand = self.network.links.sjoin_nearest(
            self.trace, distance_col="ping_dist", max_distance=self.parameters.map_matching.buffer_size
        ).reset_index()

        if self.network.has_speed:
            cand = cand[cand[self.network._speed_field] <= cand.trace_segment_speed]

        if not self.has_heading:
            self.__candidate_links = cand.link_id.to_numpy()
            return

        # TODO: Add consideration of heading
        # TODO: Many links would've been matched to the same ping, BUT ONLY ONE CAN EXIST!!!
        self.__candidate_links = cand.link_id.to_numpy()

        #TODO: FOR EACH PING, RETURN THE ORIGIN AND DESTINATION NODES OF THE LINK IT WAS MATCHED TO - ORIGIN IS THE LINK UPSTREAM AND DESTINATION IS DOWNSTREAM

    @property
    def match_quality(self):
        """Assesses the map-matching quality. Returns the percentage of GPS pings close to the map-matched trip."""
        buffer = self.parameters.map_matching.buffer_size

        stops_in_buffer = self.trace.intersects(self.path_shape.buffer(buffer)).sum()

        all_stops = self.trace.shape[0]

        return round((stops_in_buffer / all_stops)*100, 2)
