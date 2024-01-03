import logging
import traceback
from math import sqrt
from time import perf_counter
from typing import Optional

import geopandas as gpd
import numpy as np
import pandas as pd
from aequilibrae.paths.results import PathResults
from shapely.geometry import LineString
from shapely.ops import substring

from mapmatcher.linebearing import bearing_for_gps
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

    def __init__(self, gps_trace: gpd.GeoDataFrame, parameters: Parameters, network: Network):
        # Fields necessary for running the algorithm
        """
        :Arguments:
            **gps_trace** (:obj:`gpd.GeoDataFrame`): GeoDataFrame containing the vehicle GPS traces.

            **parameters** (:obj:`Parameters`): Map-Matching parameters.

            **network** (:obj:`mapmatcher.network.Network`): MapMatcher Network object.

        """

        self.__coverage = -1
        self.__candidate_links = np.array([])
        self.__map_matched = 0
        self.id = -1

        self.parameters = parameters
        self.stops: Optional[gpd.GeoDataFrame] = None
        self._waypoints: Optional[gpd.GeoDataFrame] = None
        self.warnings = []
        self.__geo_path = LineString([])
        self.__mm_results = pd.DataFrame([], columns=["links", "direction", "milepost"])
        self._unmatchable = gpd.GeoDataFrame(
            pd.DataFrame(
                [],
                columns=[
                    "ping_id",
                    "trace_id",
                    "timestamp",
                    "position",
                    "geometry",
                ],
            )
        )
        self.network = network
        self._err = ["Data not loaded yet"]
        self.middle_waypoints_required = 0
        self.mm_time = 0
        self.__match_quality = -1

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
                return

        try:
            self.__map_match()
        except Exception as e:
            self._err = [f"Critical failures. {traceback.print_exc()}"]
            logging.getLogger("mapmatcher").critical(e.args)
            print(e)

    def __map_match(self):
        if not self._waypoints.shape[0]:
            return

        self.mm_time = -perf_counter()
        self.network.reset_graph()
        self.network.discount_graph(self.__candidate_links)
        res = PathResults()
        res.prepare(self.network.graph)

        par = self.parameters.map_matching
        pos = 0
        curr_match_quality = 0
        for waypoint_count in range(par.maximum_waypoints + 1):
            wpnts = self._waypoints.stop_node[self._waypoints.is_waypoint > 0].to_list()
            links = []
            directions = []
            mileposts = []
            for start, end in zip(wpnts[:-1], wpnts[1:]):
                res.reset()
                if start == end:
                    continue
                res.compute_path(start, end, early_exit=True)
                if res.path is None:
                    continue
                links.extend(list(res.path))
                directions.extend(list(res.path_link_directions))
                mileposts.extend(list(res.milepost[1:] + pos))
                pos = mileposts[-1]
            self.__mm_results = pd.DataFrame({"links": links, "direction": directions, "milepost": mileposts})
            if self.match_quality >= par.minimum_match_quality:
                self.__reset()
                break

            corr = -1 if curr_match_quality == self.match_quality else 1
            # It means that the latest waypoint did not improve anything, so we can get rid of it
            self._waypoints.loc[self._waypoints.is_waypoint == 2, "is_waypoint"] = corr
            curr_match_quality = self.match_quality

            self.__reset()
            self.__add_waypoint()
            self.middle_waypoints_required = waypoint_count
        self._waypoints.loc[self._waypoints.is_waypoint == 2, "stop_node"] = 1
        self.mm_time += perf_counter()
        self.__map_matched = 1
        _ = self.match_quality

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
            links = self.network.links.loc[self.__mm_results.links.to_numpy(), :].reset_index()

            geo_data = []
            points = self._waypoints[self._waypoints.ping_is_covered.astype(int) == 1].geometry
            for (i_d, rec), direction in zip(links.iterrows(), self.__mm_results.direction.to_numpy()):
                geo = rec.geometry.coords if direction > 0 else rec.geometry.coords[::-1]
                found_line = True
                if points.shape[0]:
                    if i_d == 0:
                        geo_ = LineString(geo)
                        geo_ = substring(geo_, geo_.project(points.values[0]), geo_.length)
                        if geo_.length == 0:
                            found_line = False
                        geo = geo_.coords
                    if i_d == links.shape[0] - 1 and found_line:
                        geo_ = LineString(geo)
                        geo_ = substring(geo_, 0, geo_.project(points.values[-1]))
                        geo = geo_.coords
                        if geo_.length == 0:
                            found_line = False
                if found_line:
                    geo_data.extend(list(geo))
            self.__geo_path = LineString(geo_data)
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

    def __pre_process(self):
        dqp = self.parameters.data_quality
        self._err = []

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
            self._err.append(f"Vehicle with only {self.trace.shape[0]} pings. Minimum is {dqp.minimum_pings}")

        if self.coverage < dqp.minimum_coverage:
            self._err.append(f"Vehicle covers only {self.coverage:,.2} m. Minimum is {dqp.minimum_coverage}")

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
                self._err.append(f"Data is jittery. Same timestamp {np.max(jitter):,.2} m apart.")

            self.trace.drop_duplicates(subset=["ping_posix_time"], inplace=True, keep="first")

            if self.trace.shape[0] < dqp.minimum_pings:
                self._err.append(f"Vehicle with only {self.trace.shape[0]} pings. Minimum is {dqp.minimum_pings}")
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
                self._err.append(f"Max speed surpassed for {w} seconds")

        # Adds the GPS pings sequence
        self.trace = self.trace.assign(ping_sequence=np.arange(1, self.trace.shape[0] + 1))

        # Adds information on all the
        self._waypoints = self.trace.sjoin_nearest(self.network.links.reset_index(), distance_col="dist_near_link")
        bf = self.parameters.map_matching.buffer_size
        outside = self._waypoints[self._waypoints.dist_near_link > bf]
        self._waypoints = self._waypoints[self._waypoints.dist_near_link <= bf]
        if self._waypoints.shape[0] < dqp.minimum_pings:
            pings = self.trace.shape[0]
            minp = self._waypoints.shape[0]
            self._err.append(f"Vehicle has {pings} pings, but only {minp} within {bf}m from any network link")
        else:
            self.__network_links()
            if len(self._waypoints.stop_node.unique()) < 2:
                self._err.append("All valid GPS ping map to a single point in the network")

        if self.parameters.map_matching.keep_ping_classification and outside.shape[0] > 0:
            outside = outside.assign(position="middle")
            outside.loc[outside.ping_id < self._waypoints.ping_id.min(), "position"] = "before start"
            outside.loc[outside.ping_id > self._waypoints.ping_id.max(), "position"] = "after end"
            self._unmatchable = gpd.GeoDataFrame(
                outside[["ping_id", "trace_id", "timestamp", "position"]], geometry=outside.geometry, crs=self.trace.crs
            )

    def compute_stops(self):
        """Compute stops."""

        raise NotImplementedError("Not implemented yet. Package supports map-matching only for now")

    def __network_links(self):
        if self.__candidate_links.shape[0] > 0:
            return

        # Now we get the first/last links
        wpnts = self._waypoints
        wpnts = wpnts[
            ["ping_id", "timestamp", "link_id", "a_node", "b_node", "net_link_az", "tangent_bearing", "dist_near_link"]
        ]
        wpnts = wpnts.assign(is_waypoint=0, stop_node=wpnts.b_node, ping_is_covered=0)
        wpnts = gpd.GeoDataFrame(wpnts, geometry=self.trace.geometry, crs=self.trace.crs)

        abs_diff = (wpnts.tangent_bearing - wpnts.net_link_az).abs()
        wpnts.loc[abs_diff < 90, "stop_node"] = wpnts.a_node[abs_diff < 90]
        wpnts.loc[(-abs_diff + 360).abs() < 90, "stop_node"] = wpnts.a_node[(-abs_diff + 360).abs() < 90]
        wpnts.iloc[[0, -1], wpnts.columns.get_loc("is_waypoint")] = 1

        col_loc = wpnts.columns.get_loc("stop_node")
        if wpnts.link_id.unique().shape[0] > 1:
            # For the last ping we actually want the TO node
            if wpnts.stop_node.iloc[0] == wpnts.b_node.iloc[0]:
                wpnts.iloc[0, col_loc] = wpnts.a_node.iloc[0]
            else:
                wpnts.iloc[0, col_loc] = wpnts.b_node.iloc[0]
        else:
            a_node = wpnts.a_node.values[0]
            b_node = wpnts.b_node.values[0]
            a_geo = wpnts.geometry.values[0]
            b_geo = wpnts.geometry.values[-1]
            link_geo = self.network.links.loc[wpnts.link_id.values[0]].geometry
            if link_geo.project(a_geo) < link_geo.project(b_geo):
                wpnts.iloc[0, col_loc] = a_node
                wpnts.iloc[-1, col_loc] = b_node
            else:
                wpnts.iloc[0, col_loc] = b_node
                wpnts.iloc[-1, col_loc] = a_node

        self._waypoints = wpnts
        self.__candidate_links = list(wpnts.link_id.unique())

    def __add_waypoint(self):
        stop_nodes = self._waypoints[self._waypoints.is_waypoint == 1].stop_node.values
        df = self._waypoints.loc[~self._waypoints.ping_is_covered, :]
        df = df.loc[df.is_waypoint == 0, :]
        df = df.assign(is_start=df.ping_id != 1 + df.ping_id.shift(1), is_end=df.ping_id != df.ping_id.shift(-1) - 1)
        missed_time = df.timestamp[df.is_end].values - df.timestamp[df.is_start].values
        ping_id = 0
        for i in range(1, missed_time.shape[0] + 1):
            worst_segment = np.argsort(missed_time)[-i]
            frm = df[df.is_start].iloc[worst_segment].ping_id
            end = df[df.is_end].iloc[worst_segment].ping_id

            # We will get the most frequent candidate stop node among our candidates to add as our next stop
            candidates = self._waypoints[(self._waypoints.ping_id >= frm) & (self._waypoints.ping_id <= end)]
            candidates = candidates[~candidates.stop_node.isin(stop_nodes)]
            if candidates.shape[0] == 0:
                continue
            stop_node = np.argmax(np.bincount(candidates.stop_node.to_numpy()))
            ping_id = candidates[candidates.stop_node == stop_node].ping_id.values[0]

            # ping_id = frm + floor((end - frm) / 2)
            if self._waypoints.loc[self._waypoints.ping_id == ping_id, "is_waypoint"].values[0] == 0:
                break
        self._waypoints.loc[self._waypoints.ping_id == ping_id, "is_waypoint"] = 2

    @property
    def match_quality(self):
        """Assesses the map-matching quality. Returns the percentage of GPS pings close to the map-matched trip."""
        if self.__match_quality < 0:
            buffer = self.parameters.map_matching.buffer_size
            self._waypoints.loc[:, "ping_is_covered"] = self._waypoints.intersects(self.path_shape.buffer(buffer))[:]
            self.__match_quality = min(1.0, self._waypoints.ping_is_covered.sum() / self._waypoints.shape[0])
        return self.__match_quality

    @property
    def distance_ratio(self):
        return self.path_shape.length / self.trace.trace_segment_dist.sum()

    @property
    def match_quality_raw(self):
        _ = self.match_quality
        return min(1.0, self._waypoints.ping_is_covered.sum() / max(self.trace.shape[0], 1))

    def __reset(self):
        self.__match_quality = -1
        self.__geo_path = LineString([])
