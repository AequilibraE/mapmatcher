Concepts
========

The following sections present the MapMatcher documentation. The API reference can be found
:ref:`here <api_references>`.

Map-matching
------------

Mapmatcher's map-matching algorithm does not rely on the computation of stops, but rather attempts
to reproduce the trace's route by computing routes between the initial and final links where the the
GPS trace was recorded and progressively adding waypoints on segments/nodes on the links associated
with sequences of GPS pings that are not covered with the path found for the prevailing set of waypoints.


Algorithm parameters
++++++++++++++++++++

The map-matching algorithm implemented in *mapmatcher* has 5 built-in parameters that can be tuned
for a particular application, and their default values and purses are presented below:

.. code-block:: python

    >>> from mapmatcher.parameters import Parameters
    >>>
    >>> par = Parameters()
    >>> par.map_matching.cost_discount: float = 0.1  # link cost reduction ratio for links likely to be used
    >>> par.map_matching.buffer_size: float = 50  # Buffer around the links to capture links likely used. Unit is meters
    >>> par.map_matching.minimum_match_quality: float = 0.99 # *match_quality* expected to be matched
    >>> par.map_matching.maximum_waypoints: int = 20 # Number of middle waypoints added in the algorithm
    >>> par.map_matching.heading_tolerance: float = 22.5  # tolerance to be used when comparing a link's direction with the link it seems to be associated with

Further to these parameters, the user

Quality measures
++++++++++++++++

There are three quality measures produces automatically during the map-matching
process, and they are listed below:

* match_quality_raw: Share of the GPS pings that within the defined buffer distance from the map-matched path result

* match_quality: Similar to the *match_quality_raw* above, but only considers GPS pings that have at least one network link closer than the buffer distance

* middle_points_required: The number of waypoints required to reproduce the final path

Stop Finding
------------

The delivery stop algorithm is commonly used for the ATRI truck GPS data.
It was initially developed by *Pinjari et al.* and improved by :ref:`Camargo, Hong, and Livshits (2017) <citation>`.

.. code-block:: python

    >>> from mapmatcher.parameters import Parameters
    >>> 
    >>> par = Parameters()
    >>> par.stop_finding.stopped_speed: float = 2.22  # in m/s
    >>> par.stop_finding.min_time_stopped: float = 300  # 5*60 in seconds   --> minimum stopped time to be considered
    >>> par.stop_finding.max_stop_coverage: float = 800  # in m

The values above are the default premises, which can be summarized as follows:

* If the travel speed between records is smaller than 8 km/h (2.2 m/s) the vehicle is considered stopped;
* If the travel distance between stops is smaller than 800 metres, these stops are assumed to be only one;
* If the time stopped is shorter than 5 minutes (300 seconds), one assumes the stop to be at normal traffic speed;


Network data
------------

Three pieces of network data are required by **MapMatcher**

1. A Set of GPS traces in either CSV or GeoDataFrame formats
2. An AequilibraE Graph
3. A GeoPandas GeoDataFrame with all **links** in the graph
4. A GeoPandas GeoDataFrame with all **nodes** in the graph


GPS data requirements
---------------------

To be able to perform map-matching, MapMatcher requires the following information:

When using a CSV file
+++++++++++++++++++++

1. trace_id (*int*)
2. latitude (*float*)
3. longitude (*float*)
4. timestamp (*date-time format*): timestamp for the data file

.. note::

    When loading GPS data from CSV files, the GPS pings coordinate system must **always** be 4326.

When using a Geopandas GeoDataFrame
+++++++++++++++++++++++++++++++++++

1. trace_id (*int*)
2. timestamp (*date-time format*): timestamp for the data file


The following fields can also be used, but are optional:

1. heading (*float*): Direction (degrees [0,359]) the vehicle was heading when ping was registered
2. speed (*float*): Speed the vehicle was traveling at when ping happened

Data Quality
------------

Before map-matching a GPS trace, a series of data quality assurances are performed.

The first two parameters are the more straightforward ones, and specify the minimum
number of GPS pings and the minimum area covered by all records when measuring
all straight lines between every two consecutive pings, which is called *coverage*
within the package.

.. code-block:: python

    >>> from mapmatcher import MapMatcher

    >>> matcher = Mapmatcher()
    >>> matcher.parameters.data_quality.minimum_pings: int = 15  # Minimum number of pings that the vehicle needs to have to be considered valid
    >>> matcher.parameters.data_quality.minimum_coverage: float = 500  # Minimum diagonal of the Bounding box (m) defined by the GPS pings in the trace

The second set of parameters involves vehicle speeds, and it is designed to flag GPS traces
that present speeds that are unrealistic and that are sustained for a long period of time.
To this effect, there is a parameter for the maximum speed considered reasonable (default to 36.1m/s, or
130km/h or 81.25 mph), and a second for the amount of time that these high speeds would have to be
sustained for in order for the GPS trace to be considered problematic.

.. code-block:: python

    >>> from mapmatcher import MapMatcher

    >>> matcher = Mapmatcher()

    >>> matcher.parameters.data_quality.max_speed: float = 36.1  # in m/s
    >>> matcher.parameters.data_quality.max_speed_time = 120  # in seconds   --> time that the vehicle needs to be above the speed limit to be scraped

The last parameter (data *jittery*) is less straightforward to define, and it
is designed to capture large inconsistencies with coordinates and timestamps in the data.

MapMatcher is designed to work with time stamps at the 1s resolution, and it
may happen that a single GPS trace have multiple records at the same instant
but at slightly different positions. Since a single GPS device cannot be
in two places at the same time, there is data quality parameter to control for
the maximum *jitter* acceptable in the model, which defaults to zero.
The parameter can be changed before any data is loaded into the MapMatcher
instance (to 1 meter, for example).

.. code-block:: python

    >>> from mapmatcher import MapMatcher

    >>> matcher = Mapmatcher()
    >>> matcher.parameters.data_quality.maximum_jittery = 1.0 # 1m is the default value


It is possible, however, to circumvent all data quality parameters without changing them
by just setting **ignore_errors = True** in the map-match method call, as shown below.

.. code-block:: python

    >>> from mapmatcher import MapMatcher

    >>> matcher = Mapmatcher()
    >>> matcher.load_network(graph, links, nodes)
    >>> matcher.load_gps_traces(gps_traces)
    >>> matcher.map_match(ignore_errors=True)

Parallelization
---------------
Map-matching (for cold data) is an embarrassingly parallel problem. To take advantage of this characteristic, the
map-matcher has been implemented with support for parallelization through the Python multi-processing package. There
is very little that can be done here

