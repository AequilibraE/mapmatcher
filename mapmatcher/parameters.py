import dataclasses


@dataclasses.dataclass
class geoprocessing:
    projected_crs: int = 3857  # We require a projected CRS to make sure all distance computations are correct


@dataclasses.dataclass
class data_quality:
    max_speed: float = 36.1  # in m/s
    max_speed_time: float = (
        120  # in seconds   --> time that the vehicle needs to be above the speed limit to be scraped
    )
    minimum_pings: int = 15  # Minimum number of pings that the vehicle needs to have to be considered valid
    minimum_coverage: float = 500  # Minimum diagonal of the Bounding box (m) defined by the GPS pings in the trace
    maximum_jittery: float = 1  # Maximum distance for which a vehicle can move within the same timestamp (m)


@dataclasses.dataclass
class map_matching:
    # map matching related parameters
    cost_discount: float = 0.1  # link cost reduction ratio for links likely to be used
    buffer_size: float = 20  # Buffer around the links to capture links likely used. Unit is meters
    minimum_match_quality: float = 0.99
    maximum_waypoints: int = 20
    heading_tolerance: float = 22.5  # tolerance to be used when comparing a link's direction with the link it seems to
    # be associated with


# This is the algorithm commonly used for ATRI truck GPS data. Initially developed by Pinjari et. Al and improved by
# Camargo, Hong and Livshits (2017)
@dataclasses.dataclass
class DeliveryStop:  # Time in seconds
    stopped_speed: float = 2.22  # in m/s
    min_time_stopped: float = 300  # 5*60 in seconds   --> minimum stopped time to be considered
    max_time_stopped: float = 14400  # 4*60*60 in seconds   --> maximum stopped time to be considered
    max_stop_coverage: float = 800  # in m


@dataclasses.dataclass
class Parameters:
    geoprocessing = geoprocessing()
    data_quality = data_quality()
    stop_finding = DeliveryStop()
    map_matching = map_matching()
