"""
.. _example_matching_aequilibrae_model:

Matching with a generic network
==================================


"""

# %%
import uuid
from os.path import join
from tempfile import gettempdir

import geopandas as gpd
import numpy as np
from aequilibrae.utils.create_example import create_example
from aequilibrae.paths import Graph

from mapmatcher import MapMatcher
from mapmatcher.examples import nauru_data

# sphinx_gallery_thumbnail_path = 'images/plot_match_from_aequilibrae_model.png'
# %%
nauru_gps = nauru_data()

# Let's see if the data has all the fields we need
nauru_gps.head()

# %%
# Since it does not, let's fix it
nauru_gps.rename(columns={"x": "longitude", "y": "latitude", "vehicle_unique_id": "trace_id"}, inplace=True)

# %%
# Let's get a Nauru example from AequilibraE and extract the link network from it
project = create_example(join(gettempdir(), uuid.uuid4().hex), "nauru")

sql = "SELECT link_id, a_node, b_node, direction, distance, Hex(ST_AsBinary(geometry)) as geom FROM links"
gdf = gpd.GeoDataFrame.from_postgis(sql, project.conn, geom_col="geom", crs=4326)
gdf.head()


# %%
# Let's build a graph with the network.
# For that, you need ta few key fields in the network: [link_id, a_node, b_node, direction]
# You also need a cost field for your graph, which is *distance* in our case


g = Graph()
g.cost = gdf["distance"].to_numpy()

g.network = gdf
g.prepare_graph(centroids=None)
g.set_graph("distance")
g.set_skimming(["distance"])
g.set_blocked_centroid_flows(False)

# %%
# let's build the map-matcher object and run it!
mmatcher = MapMatcher()
mmatcher.load_network(graph=g, links=gdf)
mmatcher.load_gps_traces(nauru_gps)

# Let's run it single-threaded
mmatcher.map_match(parallel_threads=1)

# %%
for trip in mmatcher.trips:
    if trip.success:
        break

# %%
import folium
import geopandas as gpd
import numpy as np

# %%
# Create a geometry list from the GeoDataFrame
trace = trip.trace.to_crs(4326)
geo_df_list = [[point.xy[1][0], point.xy[0][0], ts] for point, ts in zip(trace.geometry, trace.timestamp)]

result_layer = folium.FeatureGroup("Map-match result")
trace_layer = folium.FeatureGroup("GPS traces")

# Iterate through list and add a marker for each GPS ping.
i = 0
for lat, lng, ts in geo_df_list:
    trace_layer.add_child(
        folium.CircleMarker(
            location=[lat, lng],
            radius=1,
            fill=True,  # Set fill to True
            color="black",
            tooltip=str(ts),
            fill_opacity=1.0,
        )
    )

gdf = gpd.GeoDataFrame({"d": [1]}, geometry=[trip.path_shape], crs=3857).to_crs(4326).explode(ignore_index=True)
for _, rec in gdf.iterrows():
    coords = rec.geometry.xy
    coordinates = [[y, x] for x, y in zip(coords[0], coords[1])]
    folium.PolyLine(coordinates, weight=5, color="red").add_to(result_layer)

map = folium.Map(location=[np.mean(coords[1]), np.mean(coords[0])], tiles="OpenStreetMap", zoom_start=15)

result_layer.add_to(map)
trace_layer.add_to(map)
folium.LayerControl(position="bottomright").add_to(map)
map

# %%
trip.result
