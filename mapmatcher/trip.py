import logging
from math import sqrt
from time import perf_counter
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
from aequilibrae.paths.results import PathResults
from scipy import stats
from shapely.geometry import LineString
from shapely.ops import linemerge

from mapmatcher.linebearing import bearing_for_gps
from mapmatcher.network import Network
from .parameters import Parameters
from .utils import check_lines_aligned


class Trip:
    """Builds the path a vehicle did.

    .. code-block:: python

        >>> from mapmatcher.trip import Trip

        >>> trip = Trip(gps_trace, parameters, network)
        >>> trip.map_match()

        >>> trip.result.plot()

    """

    def __init__(self, gps_trace: gpd.GeoDataFrame, parameters: Parameters, network: Network):
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
        self.__waypoints: Optional[gpd.GeoDataFrame] = None
        self.warnings = []
        self.__geo_path = LineString([])
        self.__mm_results = pd.DataFrame([], columns=["links", "direction", "milepost"])
        self.network = network
        self._err = "Data not loaded yet"
        self.middle_waypoints_required = 0
        self.mm_time = 0
        self.__match_quality = -1
        self.__excluded_pings = -1

        # Creates the properties for the outputs
        self.trace = gps_trace.to_crs(parameters.geoprocessing.projected_crs)
        self.__pre_process()
        self.__reset()

        # Indicators to show if we have the optional fields in the data

    def map_match(self, ignore_errors=False):
        """
        Performs map-matching.

        :Arguments:
            **ignore_errors** (:obj:`bool`):

        """
        if self.has_error:
            if not ignore_errors:
                logging.getLogger("mapmatcher").warning(
                    f"Cannot map-match trace id {self.id} due to : {self._err}. You can also try to ignore errors"
                )
                return

        # TODO: reset_graph takes a LOT of time because of the rebuilding of the graph. We need to hack the change of
        #       the cost field to avoid this insanity

        self.mm_time = -perf_counter()
        self.network.reset_graph()
        self.network.discount_graph(self.candidate_links)
        res = PathResults()
        res.prepare(self.network.graph)

        par = self.parameters.map_matching
        pos = 0
        for waypoint_count in range(par.maximum_waypoints + 1):
            wpnts = self.__waypoints.stop_node[self.__waypoints.is_waypoint == 1].to_list()
            links = []
            directions = []
            mileposts = []
            for start, end in zip(wpnts[:-1], wpnts[1:]):
                if start == end:
                    continue
                res.compute_path(start, end)
                if res.path is None:
                    continue
                links.extend(list(res.path))
                directions.extend(list(res.path_link_directions))
                mileposts.extend(list(res.milepost[1:] + pos))
                pos = mileposts[-1]
                res.reset()
            self.__mm_results = pd.DataFrame({"links": links, "direction": directions, "milepost": mileposts})
            if self.match_quality >= par.minimum_match_quality:
                break
            self.__reset()
            self.__add_waypoint()
            self.middle_waypoints_required = waypoint_count
        self.mm_time += perf_counter()
        self.__map_matched = 1

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
        return len(self._err) > 0

    @property
    def candidate_links(self) -> np.ndarray:
        """Returns an array containing the candidate links."""
        self.__network_links()
        return self.__candidate_links

    def __pre_process(self):
        dqp = self.parameters.data_quality
        self._err = ""

        if "trace_id" not in self.trace:
            raise ValueError("Trace does not have field trace_id")

        if len(self.trace.trace_id.unique()) > 1:
            raise ValueError("trace_id is not unique")

        self.trace.sort_values("timestamp", inplace=True)
        self.trace = self.trace.assign(tangent_bearing=bearing_for_gps(self.trace))

        self.id = self.trace.trace_id.values[0]

        self.trace.sort_values(by=["timestamp"], inplace=True)
        self.trace.reset_index(drop=True, inplace=True)
        # Check number of pings
        if self.trace.shape[0] < dqp.minimum_pings:
            self._err = f"Vehicle with only {self.trace.shape[0]} pings. Minimum is {dqp.minimum_pings}"

        if self.coverage < dqp.minimum_coverage:
            self._err += f"  Vehicle covers only {self.coverage:,.2} m. Minimum is {dqp.minimum_coverage}"

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
            if np.max(jitter) > dqp.maximum_jittery:
                self._err += f"  Data is jittery. Same timestamp {np.max(jitter):,.2} m apart."

            self.trace.drop_duplicates(subset=["ping_posix_time"], inplace=True, keep="first")

            if self.trace.shape[0] < dqp.minimum_pings:
                self._err += f"   Vehicle with only {self.trace.shape[0]} pings. Minimum is {dqp.minimum_pings}"
        # Create data quality fields
        dist = self.trace.distance(self.trace.shift(1))
        ttime = (self.trace["timestamp"] - self.trace["timestamp"].shift(1)).dt.seconds.astype(float)
        speed = dist / ttime
        speed[0] = 0
        self.trace = self.trace.assign(
            trace_segment_dist=dist.fillna(0),
            trace_segment_traveled_time=ttime.fillna(0),
            trace_segment_speed=speed.fillna(-1),
            ping_id=np.arange(self.trace.shape[0]) + 1,
        )

        # Verify data quality
        w = int(self.trace.trace_segment_traveled_time[self.trace.trace_segment_speed > dqp.max_speed].sum())
        if w > dqp.max_speed_time:
            # If there is evidence of speeding for longer than tolerated, we will see if it happens continuously
            too_fast = self.trace.groupby(self.trace.trace_segment_speed > dqp.max_speed)[
                "trace_segment_traveled_time"
            ].cumsum()
            if too_fast.max() > dqp.max_speed_time:
                self._err += f"  Max speed surpassed for {w} seconds"

        # Adds the GPS pings sequence
        self.trace = self.trace.assign(ping_sequence=np.arange(1, self.trace.shape[0] + 1))

    def compute_stops(self):
        """Compute stops."""

        raise NotImplementedError("Not implemented yet. Package supports map-matching only for now")

    def __network_links(self):
        if self.__candidate_links.shape[0] > 0:
            return
        pars = self.parameters.map_matching
        cand = self.network.links.sjoin_nearest(self.trace, distance_col="ping_dist", max_distance=pars.buffer_size)

        # Remove candidates that are above the allowed speed
        if self.network.has_speed:
            cand = cand[cand[self.network._speed_field] >= cand.trace_segment_speed]

        cand_acceptable = check_lines_aligned(cand, pars.heading_tolerance)
        filtered = cand.loc[cand[cand_acceptable.aligned == 1].index, :]

        filtered = filtered.loc[filtered.groupby(["ping_sequence"]).ping_dist.idxmin()]

        self.__candidate_links = filtered.index.to_numpy()

        # Now we get the first/last links
        wpnts = self.trace.sjoin_nearest(self.network.links, distance_col="dist_near_link")
        wpnts = wpnts[["ping_id", "timestamp", "a_node", "b_node", "net_link_az", "tangent_bearing", "dist_near_link"]]
        wpnts = wpnts.assign(is_waypoint=0, stop_node=wpnts.a_node, ping_is_covered=0)
        wpnts = gpd.GeoDataFrame(wpnts, geometry=self.trace.geometry, crs=self.trace.crs)

        wpnts.loc[abs(wpnts.tangent_bearing - wpnts.net_link_az) > 90, "stop_node"] = wpnts.b_node[
            abs(wpnts.tangent_bearing - wpnts.net_link_az) > 90
        ]
        wpnts.iloc[[0, -1], wpnts.columns.get_loc("is_waypoint")] = 1

        # For the last ping we actually want the TO node
        if wpnts.stop_node.iloc[-1] == wpnts.b_node.iloc[-1]:
            wpnts.iloc[-1, wpnts.columns.get_loc("stop_node")] = wpnts.a_node.iloc[-1]
        else:
            wpnts.iloc[-1, wpnts.columns.get_loc("stop_node")] = wpnts.b_node.iloc[-1]

        self.__waypoints = wpnts

    def __add_waypoint(self):
        stop_nodes = self.__waypoints[self.__waypoints.is_waypoint == 1].stop_node.values
        df = self.__waypoints.loc[~self.__waypoints.ping_is_covered, :]
        df = df.loc[df.is_waypoint == 0, :]
        df = df.assign(is_start=df.ping_id != 1 + df.ping_id.shift(1), is_end=df.ping_id != df.ping_id.shift(-1) - 1)
        missed_time = df.timestamp[df.is_end].values - df.timestamp[df.is_start].values
        ping_id = 0
        for i in range(1, missed_time.shape[0] + 1):
            worst_segment = np.argsort(missed_time)[-i]
            frm = df[df.is_start].iloc[worst_segment].ping_id
            end = df[df.is_end].iloc[worst_segment].ping_id

            # We will get the most frequent candidate stop node among our candidates to add as our next stop
            candidates = self.__waypoints[(self.__waypoints.ping_id >= frm) & (self.__waypoints.ping_id <= end)]
            candidates = candidates[~candidates.stop_node.isin(stop_nodes)]
            if candidates.shape[0] == 0:
                continue
            stop_node = stats.mode(candidates.stop_node.to_numpy())[0]
            ping_id = candidates[candidates.stop_node == stop_node].ping_id.values[0]

            # ping_id = frm + floor((end - frm) / 2)
            if self.__waypoints.loc[self.__waypoints.ping_id == ping_id, "is_waypoint"].values[0] == 0:
                break
        self.__waypoints.loc[self.__waypoints.ping_id == ping_id, "is_waypoint"] = 1

    @property
    def match_quality(self):
        """Assesses the map-matching quality. Returns the percentage of GPS pings close to the map-matched trip."""
        if self.__match_quality < 0:
            buffer = self.parameters.map_matching.buffer_size
            self.__waypoints.loc[:, "ping_is_covered"] = self.__waypoints.intersects(self.path_shape.buffer(buffer))[:]
            self._debug = self.__waypoints
            self.__match_quality = min(
                1.0, self.__waypoints.ping_is_covered.sum() / max(self.trace.shape[0] - self.excluded_pings, 1)
            )
        return self.__match_quality

    @property
    def match_quality_raw(self):
        _ = self.match_quality
        return min(1.0, self.__waypoints.ping_is_covered.sum() / max(self.trace.shape[0], 1))

    @property
    def excluded_pings(self):
        if self.__excluded_pings < 0:
            buffer = self.parameters.map_matching.buffer_size
            too_far_to_count = self.__waypoints[~self.__waypoints.ping_is_covered]
            too_far_to_count = too_far_to_count[too_far_to_count.dist_near_link > buffer]
            self.__excluded_pings = too_far_to_count.shape[0]
        return self.__excluded_pings

    def __reset(self):
        self.__match_quality = -1
        self.__geo_path = LineString([])
        self.__excluded_pings = -1
