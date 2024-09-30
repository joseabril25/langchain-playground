import psycopg2
import json
import re
from psycopg2.extras import execute_values

def create_table_if_not_exists(connection_string):
    conn = psycopg2.connect(connection_string)
    cur = conn.cursor()
    
    # Check if table exists
    cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'road_segments'
    );
    """)
    table_exists = cur.fetchone()[0]
    
    if not table_exists:
        # Create table
        cur.execute("""
        CREATE TABLE road_segments (
            id SERIAL PRIMARY KEY,
            ramm_road_id INTEGER,
            road_name VARCHAR(255),
            shape_length FLOAT,
            speed_limit INTEGER,
            coordinates JSONB
        );
        
        CREATE INDEX idx_road_segments_coordinates ON road_segments USING GIN (coordinates);
        
        -- Function to calculate distance between two points (in degrees)
        CREATE OR REPLACE FUNCTION calculate_distance(
            lon1 FLOAT, lat1 FLOAT,
            lon2 FLOAT, lat2 FLOAT
        ) RETURNS FLOAT AS $$
        BEGIN
            RETURN SQRT(POW(lon2 - lon1, 2) + POW(lat2 - lat1, 2));
        END;
        $$ LANGUAGE plpgsql;
        
        -- Function to find the minimum distance from a point to a line segment
        CREATE OR REPLACE FUNCTION min_distance_to_segment(
            point_lon FLOAT, point_lat FLOAT,
            segment JSONB
        ) RETURNS FLOAT AS $$
        DECLARE
            start_point JSONB;
            end_point JSONB;
            dist FLOAT;
        BEGIN
            start_point := segment->0;
            end_point := segment->1;
            
            dist := calculate_distance(
                point_lon, point_lat,
                (start_point->>0)::FLOAT, (start_point->>1)::FLOAT
            );
            
            dist := LEAST(dist, calculate_distance(
                point_lon, point_lat,
                (end_point->>0)::FLOAT, (end_point->>1)::FLOAT
            ));
            
            RETURN dist;
        END;
        $$ LANGUAGE plpgsql;
        """)
        conn.commit()
        print("Table 'road_segments' created successfully.")
    else:
        print("Table 'road_segments' already exists.")
    
    cur.close()
    conn.close()

def parse_speed_limit(speed_limit_str):
    # Remove any non-digit characters
    digits = re.findall(r'\d+', speed_limit_str)
    if not digits:
        return None
    # If there's a range, take the higher value
    return int(max(digits))

def insert_road_data(connection_string, geojson_file_path):
    # Read GeoJSON file
    with open(geojson_file_path, 'r') as file:
        data = json.load(file)
    
    # Extract features
    features = data['features']
    
    conn = psycopg2.connect(connection_string)
    cur = conn.cursor()
    
    # Prepare the data for batch insert
    values = []
    for feature in features:
        try:
            speed_limit_str = feature['properties']['ns_speed_limit']
            speed_limit = parse_speed_limit(speed_limit_str)
            
            if speed_limit is None:
                print(f"Warning: Unable to parse speed limit '{speed_limit_str}'. Skipping this record.")
                continue
            
            values.append((
                feature['properties']['road_id'],
                feature['properties']['road_name'],
                feature['properties']['Shape__Length'],
                speed_limit,
                json.dumps(feature['geometry']['coordinates'])
            ))
        except KeyError as e:
            print(f"Warning: Skipping a record due to missing key: {e}")
        except Exception as e:
            print(f"Warning: Skipping a record due to unexpected error: {e}")
    
    # Perform batch insert
    execute_values(cur, """
        INSERT INTO road_segments 
        (ramm_road_id, road_name, shape_length, speed_limit, coordinates) 
        VALUES %s
    """, values)
    
    conn.commit()
    cur.close()
    conn.close()
    
    print(f"Inserted {len(values)} road segments.")

def query_nearest_road(connection_string, lat, lon):
    conn = psycopg2.connect(connection_string)
    cur = conn.cursor()
    
    cur.execute("""
    WITH point_distances AS (
        SELECT 
            id, 
            road_name, 
            speed_limit,
            MIN(min_distance_to_segment(%s, %s, segment)) AS min_distance
        FROM road_segments,
             jsonb_array_elements(coordinates) WITH ORDINALITY AS coords(segment, idx)
        GROUP BY id, road_name, speed_limit
    )
    SELECT road_name, speed_limit, min_distance
    FROM point_distances
    ORDER BY min_distance
    LIMIT 1;
    """, (lon, lat))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    return result

#usage
if __name__ == "__main__":
    connection_string = ""
    geojson_file_path = "Speed_Limits.geojson"  # Replace with your actual file path
    
    # Create table if it doesn't exist
    create_table_if_not_exists(connection_string)
    
    # Insert data from GeoJSON file
    insert_road_data(connection_string, geojson_file_path)
    
    # Querying nearest road
    lat, lon = -36.78, 174.55  # Example coordinates
    nearest_road = query_nearest_road(connection_string, lat, lon)
    if nearest_road:
        print(f"Nearest road: {nearest_road[0]}, Speed limit: {nearest_road[1]} kph, Distance: {nearest_road[2]}")
    else:
        print("No road found")