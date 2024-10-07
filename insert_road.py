import psycopg2
import json
from psycopg2.extras import execute_values

def create_table_if_not_exists(connection_string):
    conn = psycopg2.connect(connection_string)
    cur = conn.cursor()
    
    # Enable PostGIS extension if not already enabled
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # Check if table exists
    cur.execute("""
    SELECT EXISTS (
        SELECT FROM information_schema.tables 
        WHERE table_name = 'road_segments'
    );
    """)
    table_exists = cur.fetchone()[0]
    
    if not table_exists:
        # Create table with PostGIS geometry
        cur.execute("""
        CREATE TABLE road_segments (
            id SERIAL PRIMARY KEY,
            ramm_road_id INTEGER,
            road_name VARCHAR(255),
            shape_length FLOAT,
            speed_limit INTEGER,
            geom GEOMETRY(LINESTRING, 4326)
        );
        
        CREATE INDEX idx_road_segments_geom ON road_segments USING GIST (geom);
        """)
        conn.commit()
        print("Table 'road_segments' created successfully.")
    else:
        print("Table 'road_segments' already exists.")
    
    cur.close()
    conn.close()

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
    for index, feature in enumerate(features):
        try:
            properties = feature['properties']
            geometry = feature['geometry']
            
            if geometry['type'] != 'LineString':
                raise ValueError(f"Unsupported geometry type: {geometry['type']}")
            
            speed_limit = properties.get('ns_speed_limit', '0')
            speed_limit = int(speed_limit) if isinstance(speed_limit, str) and speed_limit.isdigit() else 0
            
            coordinates = geometry['coordinates']
            linestring = f"LINESTRING({','.join([f'{lon} {lat}' for lon, lat in coordinates])})"
            
            values.append((
                properties.get('road_id', 0),
                properties.get('road_name', ''),
                properties.get('Shape__Length', 0.0),
                speed_limit,
                linestring
            ))
        except KeyError as e:
            print(f"Warning: Skipping record {index} due to missing key: {e}")
        except ValueError as e:
            print(f"Warning: Skipping record {index} due to value error: {e}")
        except Exception as e:
            print(f"Warning: Skipping record {index} due to unexpected error: {e}")
    
    # Perform batch insert
    try:
        execute_values(cur, """
            INSERT INTO road_segments 
            (ramm_road_id, road_name, shape_length, speed_limit, geom) 
            VALUES %s
        """, [(v[0], v[1], v[2], v[3], f"ST_GeomFromText('{v[4]}', 4326)") for v in values])
        
        conn.commit()
        print(f"Successfully inserted {len(values)} road segments.")
    except Exception as e:
        conn.rollback()
        print(f"Error during batch insert: {e}")
        # If batch insert fails, try inserting records one by one
        print("Attempting to insert records individually...")
        for v in values:
            try:
                cur.execute("""
                    INSERT INTO road_segments 
                    (ramm_road_id, road_name, shape_length, speed_limit, geom) 
                    VALUES (%s, %s, %s, %s, ST_GeomFromText(%s, 4326))
                """, (v[0], v[1], v[2], v[3], v[4]))
                conn.commit()
                print(f"Successfully inserted road segment: {v[1]}")
            except Exception as e:
                conn.rollback()
                print(f"Error inserting road segment {v[1]}: {e}")
    
    cur.close()
    conn.close()
    
    print(f"Inserted {len(values)} road segments.")

def query_nearest_road(connection_string, lat, lon):
    conn = psycopg2.connect(connection_string)
    cur = conn.cursor()
    
    cur.execute("""
    SELECT 
        road_name, 
        speed_limit, 
        ST_Distance(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4326)) AS distance
    FROM road_segments
    ORDER BY geom <-> ST_SetSRID(ST_MakePoint(%s, %s), 4326)
    LIMIT 1;
    """, (lon, lat, lon, lat))
    
    result = cur.fetchone()
    cur.close()
    conn.close()
    
    return result

def test_insertion_and_query(connection_string, test_lat, test_lon):
    print("\nTesting data insertion and querying:")
    nearest_road = query_nearest_road(connection_string, test_lat, test_lon)
    if nearest_road:
        print(f"Nearest road: {nearest_road[0]}, Speed limit: {nearest_road[1]} kph, Distance: {nearest_road[2]:.2f} meters")
    else:
        print("No road found")

#usage
if __name__ == "__main__":
    connection_string = ""
    geojson_file_path = "Speed_Limits.geojson"  # Replace with your actual file path
    
    # Create table if it doesn't exist
    create_table_if_not_exists(connection_string)
    
    # Insert data from GeoJSON file
    # insert_road_data(connection_string, geojson_file_path)
    
    # Test the insertion and querying
    test_lat, test_lon = -36.758110, 174.729309  # Example coordinates
    test_insertion_and_query(connection_string, test_lat, test_lon)