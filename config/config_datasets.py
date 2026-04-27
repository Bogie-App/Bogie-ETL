# La configuration est séparée de la logique
PIPELINE_CONFIG = {
    'stops': ['stop_id', 'stop_name', 'stop_desc', 'stop_lat', 'stop_lon'],
    'routes': ['route_id', 'route_short_name',  'route_long_name', 'route_type'],
    'trips': ['route_id', 'service_id', 'trip_id', 'direction_id'],
    'stop_times': ['trip_id', 'arrival_time', 'departure_time', 'stop_id', 'stop_sequence'],
    'calendar': ['service_id', 'date']
}


# === df_stops === 
# stop_id 
# stop_name
# stop_desc
# stop_lat
# stop_lon	

# === df_routes ===
# route_id
# route_short_name
# route_long_name
# route_type

# === df_trips ===
# route_id
# service_id
# trip_id
# direction_id

# === df_stop_times ===
# trip_id
# arrival_time
# departure_time
# stop_id
# stop_sequence

# === df_calendar ===
# service_id
# date  