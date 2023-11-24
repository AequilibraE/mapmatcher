# API Reference

This page contains the API References for the existing functions in MapMatcher.

## 1. Class Trip
Builds the path a vehicle did.

### **Arguments**
*gps_trace* (`gpd.GeoDataFrame`): GeoDataFrame containing the vehicle GPS traces.

*parameters* (`Parameters`): Map-Matching parameters.

*network* (`Network`): MapMatcher Network object.

*stops* (`Optional[gpd.GeoDataFrame] = None`): 

```python
from mapmatcher.trip import Trip

trip = Trip(gps_trace, parameters, network)
trip.map_match()

trip.result.plot()
```

### **Methods:**

#### `map_match(ignore_errors=False)`
Performs map-matching

#### `compute_stops()`
Compute stops.

### **Properties**

#### `success`
Indicates the success of the map-matching procedure. If it succeeded, it returns `1`, otherwise returns `0`.

#### `path_shape`
Returns the `shapely.LineString` that represents the map-matched path.

#### `result`
Returns a GeoDataFrame containing the network links selected in map-matching.

#### `coverage`
Returns the distance (in metres) between the bounds of the geometries that represent the path.

#### `has_error`
Indicates the presence of errors during the map-matching process. 
Returns `True` if there are any errors, otherwise, it returns `False`.

#### `candidate_links`
Returns an array containing the candidate links.

## 2. Class Network
Builds the network to be used in the project.

### **Arguments**
*graph* (`aequilibrae.graph.Graph`): AequilibraE graph

*links* (`gpd.GeoDataFrame`): GeoDataFrame containing the network links

*nodes* (`gpd.GeoDataFrame`): GeoDataFrame containing the network nodes

*parameters* (`Parameters`): Map-Matching parameters.

```python
from mapmatcher.network import Network

network = Network(graph, links, nodes, parameters)
```

### **Methods:**

#### `set_speed_field(speed_field: str)`
Sets the speed field, if it exists.

#### `discount_graph(links: np.ndarray)`
Updates the costs for each link in the graph.

#### `reset_graph()`
Resets the current graph.

### **Properties**

#### `has_speed`
Returns `True` if there is a speed field, otherwise it returns `False`.

## 3. Class MapMatcher
Performs map-matching.

```python
from mapmatcher import MapMatcher

matcher = MapMatcher.from_aequilibrae(project, "c")
mmatcher.load_gps_traces(nauru_gps)
mmatcher.map_match()

``` 
### **Methods:**

#### `from_aequilibrae(proj: aequilibrae.Project, mode: str)`

#### `set_output_folder(output_folder: str)`
Sets the name of the output folder.

#### `set_stop_algorithm(stop_algorithm)`
Sets the stop algorithm.

#### `load_network(graph: Graph, links: gpd.GeoDataFrame, nodes: Optional[gpd.GeoDataFrame])`
Loads the project network.

#### `load_gps_traces(gps_traces: Union[gpd.GeoDataFrame, PathLike], crs: Optional[int])`
Loads the GPS traces to the map-matcher.

#### `load_stops(stops: Union[gpd.GeoDataFrame, PathLike])`
Loads the stops.

#### `map_match()`
Executes map-matching.