"""
.. _example_matching_aequilibrae_model:

Matching with an AequilibraE Model
==================================


"""

# %%
import uuid
from os.path import join
from tempfile import gettempdir

from aequilibrae.utils.create_example import create_example
from mapmatcher.examples import nauru_data
from mapmatcher import MapMatcher

# sphinx_gallery_thumbnail_path = 'images/plot_match_from_aequilibrae_model.png'
# %%
nauru_gps = nauru_data()

# Let's see if the data has all the fields we need
nauru_gps.head()

# %%
# Since it does not, let's fix it
nauru_gps.rename(columns={"x": "longitude", "y": "latitude", "vehicle_unique_id": "trace_id"}, inplace=True)

# %%
# We get our AequilibraE model for Nauru and create the map-mather from this model
# We also need to provide the transportation mode we want to consider for the
# map-matching
project = create_example(join(gettempdir(), uuid.uuid4().hex), "nauru")
mmatcher = MapMatcher.from_aequilibrae(project, "c")

# %%
# let's add the GPS data to the map-matcher and run it!
mmatcher.load_gps_traces(nauru_gps)
mmatcher.execute()

# %%
for trip in mmatcher.trips:
    if trip.success:
        break

# %%
import folium
import numpy as np
import geopandas as gpd

# %%
# Create a geometry list from the GeoDataFrame
trace = trip.trace.to_crs(4326)
geo_df_list = [[point.xy[1][0], point.xy[0][0], ts] for point, ts in zip(trace.geometry, trace.timestamp)]

result_layer = folium.FeatureGroup("Map-match result")
trace_layer = folium.FeatureGroup("GPS traces")

# Iterate through list and add a marker for each GPS ping.
i = 0
for lat, lng, ts in geo_df_list:
    trace_layer.add_child(folium.CircleMarker(location=[lat, lng], radius=1,
                                              fill=True,  # Set fill to True
                                              color='black',
                                              tooltip=str(ts),
                                              fill_opacity=1.0))

gdf = gpd.GeoDataFrame({"d": [1]}, geometry=[trip.path_shape], crs=3857).to_crs(4326).explode(ignore_index=True)
for _, rec in gdf.iterrows():
    coords = rec.geometry.xy
    coordinates = [[y, x] for x, y in zip(coords[0], coords[1])]
    folium.PolyLine(coordinates, weight=5, color="red").add_to(result_layer)

map = folium.Map(location=[np.mean(coords[1]), np.mean(coords[0])], tiles="OpenStreetMap", zoom_start=15)

result_layer.add_to(map)
trace_layer.add_to(map)
folium.LayerControl(position='bottomright').add_to(map)
map

# %%
trip.result
