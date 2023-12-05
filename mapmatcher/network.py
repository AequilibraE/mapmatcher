import geopandas as gpd
import numpy as np
import pandas as pd
from aequilibrae import Graph

from mapmatcher.linebearing import bearing_for_lines
from mapmatcher.parameters import Parameters


class Network:
    """
    Creates the properties for the outputs.

    .. code-block:: python

        >>> from mapmatcher.network import Network

        >>> network = Network(graph, links, parameters)

    """

    def __init__(self, graph: Graph, links: gpd.GeoDataFrame, parameters: Parameters):
        """
        :Arguments:
            **graph** (:obj:`aequilibrae.graph.Graph`): AequilibraE graph

            **links** (:obj:`gpd.GeoDataFrame`): GeoDataFrame containing the network links

            **parameters** (:obj:`Parameters`): Map-Matching parameters.

        """
        self._speed_field = ""
        self._pars = parameters
        self.graph = graph
        self._orig_crs = links.crs
        self.__graph_cost = np.array(self.graph.cost, copy=True)

        links = links.to_crs(parameters.geoprocessing.projected_crs)
        if links._geometry_column_name != "geometry":
            links.rename_geometry("geometry", inplace=True)

        self.links = links if links.index.name == "link_id" else links.set_index("link_id", drop=True)

        if "a_node" not in self.links:
            self.links = self.links.join(
                pd.DataFrame(graph.network[["link_id", "a_node", "b_node"]]).set_index(["link_id"])
            )
        self.links = self.links.merge(bearing_for_lines(self.links), on="link_id")
        self.links.set_index("link_id", inplace=True)

    @property
    def has_speed(self) -> bool:
        """Returns `True` if there is a speed field, otherwise it returns `False`."""
        return len(self._speed_field) > 0

    def set_speed_field(self, speed_field: str):
        """Sets the speed field, if it exists."""
        if speed_field not in self.links:
            raise ValueError("Speed field NOT in the links table")
        self._speed_field = speed_field

    def discount_graph(self, links: np.ndarray):
        """Updates the costs for each link in the graph."""
        self.graph.graph.loc[self.graph.graph.link_id.isin(links), "distance"] *= self._pars.map_matching.cost_discount
        self.graph.cost = self.graph.graph.distance.to_numpy()

    def reset_graph(self):
        """Resets the current graph."""
        self.graph.graph.loc[:, "distance"] = self.__graph_cost
