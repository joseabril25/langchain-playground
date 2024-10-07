import logging
import psycopg2
import json
from psycopg2.extras import execute_values

def geometry_to_wkt(geometry):
    if geometry['type'] == 'Polygon':
        coordinates = geometry['coordinates']
        return f"POLYGON(({','.join([' '.join(map(str, point)) for point in coordinates[0]])}))"
    elif geometry['type'] == 'MultiPolygon':
        polygons = []
        for poly in geometry['coordinates']:
            polygons.append(f"(({','.join([' '.join(map(str, point)) for point in poly[0]])}))")
        return f"MULTIPOLYGON({','.join(polygons)})"
    else:
        raise ValueError(f"Unsupported geometry type: {geometry['type']}")

def insert_road_construction_data(connection_string, geojson_file_path):
    try:
        with open(geojson_file_path, 'r') as file:
            data = json.load(file)
        
        features = data['features']
        
        conn = psycopg2.connect(connection_string)
        cur = conn.cursor()
        
        batch_size = 100  # Adjust this value based on your data size and system capabilities
        total_inserted = 0
        
        for i in range(0, len(features), batch_size):
            batch = features[i:i+batch_size]
            values = []
            
            for index, feature in enumerate(batch):
                try:
                    properties = feature['properties']
                    geometry = feature['geometry']
                    
                    wkt = geometry_to_wkt(geometry)
                    logging.debug(f"Feature {i+index} WKT: {wkt[:100]}...")  # Log first 100 characters of WKT
                    
                    values.append((
                        properties.get('WorksiteCode'),
                        properties.get('WorksiteName'),
                        properties.get('ProjectName'),
                        properties.get('Status'),
                        properties.get('WorksiteType'),
                        properties.get('Shape__Area'),
                        properties.get('Shape__Length'),
                        properties.get('PrincipalOrganisation'),
                        properties.get('ProjectStartDate'),
                        properties.get('ProjectEndDate'),
                        properties.get('WorkStartDate'),
                        properties.get('WorkCompletionDate'),
                        properties.get('WorkStatus'),
                        wkt
                    ))
                except Exception as e:
                    logging.error(f"Error processing feature {i+index}: {str(e)}")
            
            if values:
                try:
                    execute_values(cur, """
                        INSERT INTO road_construction 
                        (worksite_code, worksite_name, project_name, status, worksite_type, 
                         shape_area, shape_length, principal_organisation, project_start_date, 
                         project_end_date, work_start_date, work_completion_date, work_status, geom)
                        VALUES %s
                    """, values, template="(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, ST_GeomFromText(%s, 4326))")
                    
                    conn.commit()
                    total_inserted += len(values)
                    logging.info(f"Inserted batch of {len(values)} records. Total inserted: {total_inserted}")
                except Exception as e:
                    conn.rollback()
                    logging.error(f"Error inserting batch: {str(e)}")
                    # Optionally, you could try to insert records one by one here
            else:
                logging.warning(f"No valid records in batch {i//batch_size + 1}")
        
        print(f"Total inserted records: {total_inserted}")
        
        cur.close()
        conn.close()
    except Exception as e:
        logging.exception(f"An error occurred: {str(e)}")

# Don't forget to update the create_road_construction_table function to allow for MultiPolygon:
def create_road_construction_table(connection_string):
    conn = psycopg2.connect(connection_string)
    cur = conn.cursor()
    
    # Enable PostGIS extension if not already enabled
    cur.execute("CREATE EXTENSION IF NOT EXISTS postgis;")

    # Create table with PostGIS geometry that allows for both Polygon and MultiPolygon
    cur.execute("""
    CREATE TABLE IF NOT EXISTS road_construction (
        id SERIAL PRIMARY KEY,
        worksite_code VARCHAR(50),
        worksite_name VARCHAR(255),
        project_name VARCHAR(255),
        status VARCHAR(50),
        worksite_type VARCHAR(100),
        shape_area FLOAT,
        shape_length FLOAT,
        principal_organisation VARCHAR(255),
        project_start_date TIMESTAMP,
        project_end_date TIMESTAMP,
        work_start_date TIMESTAMP,
        work_completion_date TIMESTAMP,
        work_status VARCHAR(50),
        geom GEOMETRY(GEOMETRY, 4326)
    );
    
    CREATE INDEX IF NOT EXISTS idx_road_construction_geom ON road_construction USING GIST (geom);
    """)
    
    conn.commit()
    logging.debug("Table 'road_construction' created or already exists.")
    
    cur.close()
    conn.close()

def test_insertion(connection_string, test_lat, test_lon):
    conn = psycopg2.connect(connection_string)
    cur = conn.cursor()
    
    # Check the total number of records
    cur.execute("SELECT COUNT(*) FROM road_construction")
    count = cur.fetchone()[0]
    logging.debug(f"Total records in road_construction table: {count}")
    
    # Retrieve and display a sample record
    cur.execute("SELECT worksite_name, ST_AsText(geom) FROM road_construction LIMIT 1")
    sample = cur.fetchone()
    if sample:
        logging.debug(f"Sample record - Worksite Name: {sample[0]}")
        logging.debug(f"Geometry: {sample[1][:100]}...")  # Printing first 100 characters of geometry
    
    # Check for construction at the given coordinates
    cur.execute("""
        SELECT worksite_name, project_name, status, work_status, 
               ST_Distance(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography) AS distance
        FROM road_construction
        WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography, 100)
        ORDER BY distance
        LIMIT 1;
    """, (test_lon, test_lat, test_lon, test_lat))
    
    nearby_construction = cur.fetchone()
    if nearby_construction:
        print(f"\nConstruction found near coordinates ({test_lat}, {test_lon}):")
        print(f"Worksite Name: {nearby_construction[0]}")
        print(f"Project Name: {nearby_construction[1]}")
        print(f"Status: {nearby_construction[2]}")
        print(f"Work Status: {nearby_construction[3]}")
        print(f"Distance: {nearby_construction[4]:.2f} meters")
    else:
        print(f"\nNo construction found within 100 meters of coordinates ({test_lat}, {test_lon})")
    
    cur.close()
    conn.close()

# Example usage
if __name__ == "__main__":
    connection_string = ""
    geojson_file_path = "Roadworks.geojson"  # Replace with your actual file path
    
    # create_road_construction_table(connection_string)
    # insert_road_construction_data(connection_string, geojson_file_path)

    test_lat, test_lon = -36.883379917376402, 174.706054955572  # Example coordinates
    test_insertion(connection_string, test_lat, test_lon)