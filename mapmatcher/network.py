import geopandas as gpd
import numpy as np
from aequilibrae import Graph

from mapmatcher.parameters import Parameters


class Network:
    """
    Creates the properties for the outputs.

    .. code-block:: python

        >>> from mapmatcher.network import Network

        >>> network = Network(graph, links, nodes, parameters)

    """

    def __init__(self, graph: Graph, links: gpd.GeoDataFrame, nodes: gpd.GeoDataFrame, parameters: Parameters):
        """
        :Arguments:
            **graph** (:obj:`aequilibrae.graph.Graph`): AequilibraE graph

            **links** (:obj:`gpd.GeoDataFrame`): GeoDataFrame containing the network links

            **nodes** (:obj:`gpd.GeoDataFrame`): GeoDataFrame containing the network nodes

            **parameters** (:obj:`Parameters`): Map-Matching parameters.

        """
        self._speed_field = ""
        self._pars = parameters
        self.graph = graph
        self._orig_crs = links.crs
        self.links = links if links.index.name == "link_id" else links.set_index("link_id", drop=True)
        self.links.to_crs(parameters.geoprocessing.projected_crs, inplace=True)
        self.nodes = nodes if nodes.index.name == "node_id" else nodes.set_index("node_id", drop=True)
        self.nodes.to_crs(parameters.geoprocessing.projected_crs, inplace=True)

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
        self.graph.set_graph("distance")

    def reset_graph(self):
        """Resets the current graph."""
        self.graph.prepare_graph(self.graph.centroids)
        self.graph.set_graph("distance")
