Conceptual documentation
========================

The following sections present the MapMatcher documentation. The API reference can be found
:ref:`here <api_references>`.

Network data
------------

Three pieces of network data are required by **MapMatcher**

1. A Set of GPS traces in either CSV or GeoDataFrame formats
2. An AequilibraE Graph
3. A GeoPandas GeoDataFrame with all **links** in the graph
4. A GeoPandas GeoDataFrame with all **nodes** in the graph

GPS data
--------

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
4. timestamp (*date-time format*): timestamp for the data file


The following fields can also be used, but are optional:

1. heading (*float*): Direction (degrees [0,359]) the vehicle was heading when ping was registered
2. speed (*float*): Speed the vehicle was traveling at when ping happened

Data Quality
------------

Before map-matching a GPS trace, a series of data quality assurances are performed.

Data jitter
+++++++++++

MapMatcher is designed to work with time stamps at the 1s resolution, and it 
may happen that a single GPS trace have multiple records at the same instant
but at slightly different positions. Since a single GPS device cannot be 
in two places at the same time, there is data quality parameter to control for
the maximum *jitter* acceptable in the model, which defaults to zero.
The parameter can be changed before any data is loaded into the MapMatcher
instance (to 2.5 meters, for example).

.. code-block:: python

    >>> from mapmatcher import MapMatcher

    >>> matcher = Mapmatcher()
    >>> matcher.parameters.data_quality.maximum_jittery = 2.5

Algorithms
----------

Map-matching
++++++++++++

Mapmatcher's  map-matching algorithm does not rely on the computation of stops, but rather attempts
to reproduce the trace's route by computing routes between the initial and final links where the the
GPS trace was recorded and progressively adding waypoints on missed sedments of the route as needed.


Stop Finding
++++++++++++

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

Parallelization
---------------
Map-matching (for cold data) is an embarrassingly parallel problem. However, no advanced parallelization has been 
implemented so far. The path computation part of the algorithm DOES release the GIL, so threading might be worth pursuing.
Contributions on this issue are welcome.
