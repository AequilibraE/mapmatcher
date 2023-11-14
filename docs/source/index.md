(home)=
# MapMatcher

The Python **MapMatcher** package is yet another Python package designed to 
map-match GPS traces onto a network.

The main difference between this package and other existing solutions is that it 
is built around [AequilibraE](https://www.aequilibrae.com), adding a powerful resource
to its ecosystem.

Following on the AequilibraE ethos, however, one does not need an AequilibraE model 
to use **MapMatcher** to map-match GPS traces to a bespoke link network.

# Examples

Examples on MapMatcher application can be found in this 

```{toctree}
---
numbered: 2
maxdepth: 2
---
_auto_examples/index
```

# Documentation

The following sections present MapMatcher documentation. The API reference can be found 
[here](source/api_reference.md).

## Network data

Three pieces of network data are required by **MapMatcher**

1. An AequilibraE Graph
2. A GeoPandas GeoDataFrame with all **links** in the graph
3. A GeoPandas GeoDataFrame with all **nodes** in the graph

## GPS data

To be able to perform map-matching, MapMatcher requires the following information:

1. trace_id (*int*)
2. latitude (*float*)
3. longitude (*float*)
4. timestamp (*date-time format*): timestamp for the data file

The following fields can also be used, but are optional:

1. heading (*float*): Direction (degrees [0,359]) the vehicle was heading when ping was registered
2. speed (*float*): Speed the vehicle was traveling at when ping happened

> When loading GPS data from CSV files, the GPS pings coordinate system must **always** be 4326.

## Data Quality

Before map-matching a GPS trace, a series of data quality assurances are performed.

### Data jitter

MapMatcher is designed to work with time stamps at the 1s resolution, and it 
may happen that a single GPS trace have multiple records at the same instant
but at slightly different positions. Since a single GPS device cannot be 
in two places at the same time, there is data quality parameter to control for
the maximum *jitter* acceptable in the model, which defaults to zero.
The parameter can be changed before any data is loaded into the MapMatcher
instance (to 2.5 meters, for example).

```python
from mapmatcher import MapMatcher

matcher = Mapmatcher()
matcher.parameters.data_quality.maximum_jittery = 2.5
```

## Algorithms

### Stop Finding

It is necessary to identify the vehicle's stops to reconstruct the route.

MapMatcher holds two different stop finding algorithms.

#### 1. Delivery Stop

The delivery stop algorithm is commonly used for the ATRI truck GPS data.
It was initially developed by Pinjari et al. ()[^1] and improved by [Camargo, Hong, and Livshits (2017)](#citing).

[^1]: Add reference

```python
from mapmatcher.parameters import Parameters

par = Parameters()
par.stop_algorithm = "delivery_stop"
```

The algorithm presents the following default premises:

* If the travel speed between records is smaller than 8 km/h (2.2 m/s) the vehicle is considered stopped;
* If the travel distance between stops is smaller than 800 metres, these stops are assumed to be only one;
* If the time stopped is shorter than 5 minutes (300 seconds), one assumes the stop to be at normal traffic speed;
* The maximum stopped time to be considered are 4 hours (14,400 seconds).

#### 2. Maximum Space

The maximum space algorithm limits the maximum time and distance (great circle distance, measured in metres) 
between consecutive pings.

```python
from mapmatcher.parameters import Parameters

par = Parameters()
par.stop_algorithm = "maximum_space"
```

## Path Reconstruction

After identifying the stops and the links more likely used links, MapMatcher can reconstruct the vehicle's route.

## Parallelization

Map-matching (for cold data) is an embarrassingly parallel problem. However, no advanced parallelization has been 
implemented so far. The path computation part of the algorithm DOES release the GIL, so threading might be worth pursuing.
Contributions on this issue are welcome.

# Citing

Case you use MapMatcher, please cite:

> P. Camargo, S. Hong, and V. Livshits, ‘Expanding the Uses of Truck GPS Data in Freight Modeling and Planning Activities’, 
> Transportation Research Record, vol. 2646, no. 1, pp. 68–76, Jan. 2017, [doi: 10.3141/2646-08](https://journals.sagepub.com/doi/abs/10.3141/2646-08).