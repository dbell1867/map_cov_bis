# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "altair==6.0.0",
#     "httpx==0.28.1",
#     "polars==1.35.2",
#     "pyarrow==22.0.0",
#     "folium==0.20.0",
#     "shapely==2.1.2",
# ]
# ///

import marimo

__generated_with = "0.18.0"
app = marimo.App(width="medium")


@app.cell
def imports():
    import marimo as mo
    import polars as pl
    import altair as alt
    import httpx
    import sqlite3
    from pathlib import Path
    from datetime import datetime
    from time import sleep
    import folium
    from shapely.geometry import Polygon, box
    from shapely.ops import unary_union
    return (
        Path,
        Polygon,
        box,
        folium,
        httpx,
        mo,
        pl,
        sleep,
        sqlite3,
        unary_union,
    )


@app.cell
def configuration(mo):
    mo.md("""
    # UK Crime Data Analysis

    ## Configuration
    This notebook implements a bisection strategy to download UK crime data from the Police API.

    **API Constraints:**
    - Max 10,000 crimes per request (returns 403 if exceeded)
    - Max 10 calls per second
    - Target: 5,000-7,500 crimes per area
    """)
    return


@app.cell
def api_config():
    """API configuration constants."""
    API_BASE_URL = "https://data.police.uk/api/crimes-street/all-crime"
    MAX_CALLS_PER_SECOND = 10
    TARGET_MIN_CRIMES = 5000
    TARGET_MAX_CRIMES = 7500
    MAX_CRIMES_LIMIT = 10000
    DB_PATH = "uk_crime_data.db"
    return API_BASE_URL, DB_PATH, TARGET_MAX_CRIMES, TARGET_MIN_CRIMES


@app.cell
def uk_boundary_constants():
    """Define UK boundary box constants."""
    # England mainland bounds (lat, lon)
    UK_BOUNDS = {
        "north": 55.8,
        "south": 49.0,
        "east": 1.8,
        "west": -5.7
    }

    # Full UK including Scotland, Wales, Northern Ireland
    UK_FULL_BOUNDS = {
        "north": 60.86,
        "south": 49.00,
        "east": 1.76,
        "west": -8.18
    }
    return UK_BOUNDS, UK_FULL_BOUNDS


@app.cell
def boundary_cache_functions(Path):
    """Functions for loading and saving boundary cache."""
    import pickle

    def load_boundary_from_cache():
        """Load UK boundary from disk cache. Returns polygon or None."""
        cache_path = Path("uk_boundary_cache.pkl")
        if cache_path.exists():
            try:
                print("Loading UK boundary from cache...")
                with open(cache_path, "rb") as f:
                    boundary = pickle.load(f)
                print("✓ Loaded UK boundary from cache (instant)")
                return boundary
            except Exception as e:
                print(f"⚠ Cache load failed: {e}, will fetch fresh data...")
                return None
        return None

    def save_boundary_to_cache(boundary):
        """Save UK boundary polygon to disk cache."""
        cache_path = Path("uk_boundary_cache.pkl")
        try:
            with open(cache_path, "wb") as f:
                pickle.dump(boundary, f)
            print(f"✓ Saved boundary to cache: {cache_path}")
        except Exception as e:
            print(f"⚠ Could not save cache: {e}")
    return load_boundary_from_cache, save_boundary_to_cache


@app.cell
def boundary_geojson_functions(Polygon):
    """Functions for parsing GeoJSON boundary data."""
    def extract_polygons_from_geojson(geojson_data):
        """Extract polygon geometries from GeoJSON FeatureCollection."""
        polygons = []
        for feature in geojson_data['features']:
            geom = feature['geometry']
            if geom['type'] == 'Polygon':
                coords = geom['coordinates'][0]
                polygons.append(Polygon(coords))
            elif geom['type'] == 'MultiPolygon':
                for poly_coords in geom['coordinates']:
                    polygons.append(Polygon(poly_coords[0]))
        return polygons
    return (extract_polygons_from_geojson,)


@app.cell
def fetch_uk_boundary_from_github(
    extract_polygons_from_geojson,
    httpx,
    unary_union,
):
    """Fetch UK boundary data from GitHub GeoJSON repository."""
    def fetch_boundary():
        """Fetch and merge GB + NI boundaries. Returns polygon or None."""
        try:
            print("Fetching UK boundary data from GitHub...")

            # Fetch Great Britain (England, Scotland, Wales)
            gb_url = "https://raw.githubusercontent.com/martinjc/UK-GeoJSON/master/json/administrative/gb/lad.json"
            print("  - Fetching Great Britain boundaries...")
            gb_response = httpx.get(gb_url, timeout=30.0)

            # Fetch Northern Ireland
            ni_url = "https://raw.githubusercontent.com/martinjc/UK-GeoJSON/master/json/administrative/ni/lgd.json"
            print("  - Fetching Northern Ireland boundaries...")
            ni_response = httpx.get(ni_url, timeout=30.0)

            if gb_response.status_code != 200 or ni_response.status_code != 200:
                raise Exception(f"Failed to fetch: GB={gb_response.status_code}, NI={ni_response.status_code}")

            # Extract polygons from both datasets
            gb_polygons = extract_polygons_from_geojson(gb_response.json())
            print(f"  ✓ Loaded {len(gb_polygons)} Great Britain boundaries")

            ni_polygons = extract_polygons_from_geojson(ni_response.json())
            print(f"  ✓ Loaded {len(ni_polygons)} Northern Ireland boundaries")

            # Merge all polygons
            all_polygons = gb_polygons + ni_polygons
            boundary = unary_union(all_polygons)
            print(f"✓ Total: {len(all_polygons)} UK administrative boundaries (GB + NI)")

            return boundary

        except Exception as e:
            print(f"⚠ Could not fetch UK boundary: {e}")
            return None
    return (fetch_boundary,)


@app.cell
def create_fallback_boundary(Polygon, unary_union):
    """Create simplified fallback boundary when fetch fails."""
    def get_fallback_boundary():
        """Returns simplified UK boundary polygon."""
        print("Using simplified fallback boundary...")

        # Main GB boundary (England, Scotland, Wales)
        gb_boundary_coords = [
            (-5.7, 50.0), (-4.0, 50.2), (-2.0, 50.7), (0.5, 51.0), (1.8, 51.5),
            (1.5, 52.5), (0.5, 53.5), (-0.5, 54.0), (-1.5, 55.0),
            (-2.0, 56.0), (-2.5, 57.5), (-3.0, 58.5), (-3.5, 59.0), (-4.0, 60.0),
            (-5.0, 60.5), (-6.0, 60.0), (-7.0, 59.0), (-7.5, 58.0), (-7.0, 57.0),
            (-6.5, 56.5), (-6.0, 56.0), (-6.5, 55.5), (-6.0, 55.2),
            (-5.0, 55.5), (-5.0, 54.5), (-4.5, 54.0), (-5.5, 52.5), (-5.0, 52.0),
            (-4.5, 51.5), (-5.5, 51.0), (-5.7, 50.5), (-5.7, 50.0)
        ]

        # Northern Ireland boundary (approximate)
        ni_boundary_coords = [
            (-8.18, 54.0), (-8.0, 54.4), (-7.5, 54.9), (-7.0, 55.2),
            (-6.5, 55.3), (-6.0, 55.3), (-5.4, 55.0), (-5.4, 54.5),
            (-5.8, 54.2), (-6.5, 54.0), (-7.5, 54.0), (-8.18, 54.0)
        ]

        # Create MultiPolygon for both regions
        gb_poly = Polygon(gb_boundary_coords)
        ni_poly = Polygon(ni_boundary_coords)
        boundary = unary_union([gb_poly, ni_poly])
        print(f"  ✓ Using fallback boundary (includes Northern Ireland)")

        return boundary
    return (get_fallback_boundary,)


@app.cell
def uk_boundaries(
    fetch_boundary,
    get_fallback_boundary,
    load_boundary_from_cache,
    save_boundary_to_cache,
):
    """
    Main function to get UK boundary polygon with caching.
    Tries cache first, then GitHub fetch, then fallback.
    """
    # Try loading from cache
    uk_boundary_polygon = load_boundary_from_cache()

    # If cache failed, fetch from GitHub
    if uk_boundary_polygon is None:
        uk_boundary_polygon = fetch_boundary()

        # Save to cache if fetch succeeded
        if uk_boundary_polygon is not None:
            save_boundary_to_cache(uk_boundary_polygon)

    # If fetch also failed, use fallback
    if uk_boundary_polygon is None:
        uk_boundary_polygon = get_fallback_boundary()
    return (uk_boundary_polygon,)


@app.cell
def database_setup(DB_PATH, sqlite3):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Create table for storing area polygons that meet our criteria
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crime_areas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            polygon TEXT NOT NULL,
            crime_count INTEGER NOT NULL,
            date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(polygon, date)
        )
    """)

    # Create table for storing actual crime data
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crimes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            area_id INTEGER,
            crime_id TEXT UNIQUE,
            category TEXT,
            latitude REAL,
            longitude REAL,
            street_name TEXT,
            month TEXT,
            FOREIGN KEY (area_id) REFERENCES crime_areas(id)
        )
    """)

    conn.commit()
    return conn, cursor


@app.cell
def cache_functions(cursor):
    def check_area_cached(polygon_str, date):
        """
        Check if area already processed for this date.
        Returns crime_count if cached, None otherwise.
        """
        cursor.execute(
            "SELECT crime_count FROM crime_areas WHERE polygon = ? AND date = ?",
            (polygon_str, date)
        )
        result = cursor.fetchone()
        return result[0] if result else None

    def get_cache_stats(date):
        """Get statistics about cached areas for a date."""
        cursor.execute(
            "SELECT COUNT(*), SUM(crime_count) FROM crime_areas WHERE date = ?",
            (date,)
        )
        result = cursor.fetchone()
        return {"areas": result[0] or 0, "total_crimes": result[1] or 0}
    return (check_area_cached,)


@app.cell
def crime_insertion_functions(conn, cursor):
    def insert_crimes_batch(area_id, crimes_data):
        """
        Insert individual crime records into the crimes table.

        Args:
            area_id: The area_id from crime_areas table
            crimes_data: List of crime dictionaries from API response

        Returns:
            Number of crimes inserted (may be less than total if duplicates exist)
        """
        if not crimes_data:
            return 0

        # Prepare batch insert data
        crime_records = []
        for crime in crimes_data:
            # Extract data from API response
            crime_id = crime.get('id', None)
            if crime_id is None:
                # Skip crimes without ID
                continue

            category = crime.get('category', '')
            location = crime.get('location', {})
            latitude = location.get('latitude')
            longitude = location.get('longitude')
            street_name = location.get('street', {}).get('name', '')
            month = crime.get('month', '')

            # Convert latitude/longitude to float (they come as strings)
            try:
                latitude = float(latitude) if latitude else None
                longitude = float(longitude) if longitude else None
            except (ValueError, TypeError):
                latitude = None
                longitude = None

            crime_records.append((
                area_id,
                crime_id,
                category,
                latitude,
                longitude,
                street_name,
                month
            ))

        # Batch insert with INSERT OR IGNORE to handle duplicates
        try:
            cursor.executemany(
                """INSERT OR IGNORE INTO crimes
                   (area_id, crime_id, category, latitude, longitude, street_name, month)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                crime_records
            )
            conn.commit()
            return len(crime_records)
        except Exception as e:
            print(f"    ⚠ Error inserting crimes: {e}")
            return 0
    return (insert_crimes_batch,)


@app.cell
def polygon_helper_functions():
    def format_polygon(coords):
        """
        Format list of (lat, lon) tuples into API polygon string.
        Example: [(52.268, 0.543), (52.794, 0.238)] -> "52.268,0.543:52.794,0.238"
        """
        return ":".join([f"{lat},{lon}" for lat, lon in coords])

    def bounds_to_polygon(north, south, east, west):
        """
        Convert bounding box to polygon coordinates (4 corners, clockwise from NW).
        Returns list of (lat, lon) tuples.
        """
        return [
            (north, west),  # NW
            (north, east),  # NE
            (south, east),  # SE
            (south, west),  # SW
        ]

    def split_bounds_horizontal(north, south, east, west):
        """
        Split a bounding box horizontally (east-west).
        Returns two bounding boxes: (north1, south1, east1, west1), (north2, south2, east2, west2)
        """
        mid_lat = (north + south) / 2
        box1 = (north, mid_lat, east, west)  # Northern half
        box2 = (mid_lat, south, east, west)  # Southern half
        return box1, box2

    def split_bounds_vertical(north, south, east, west):
        """
        Split a bounding box vertically (north-south).
        Returns two bounding boxes.
        """
        mid_lon = (east + west) / 2
        box1 = (north, south, east, mid_lon)  # Eastern half
        box2 = (north, south, mid_lon, west)  # Western half
        return box1, box2

    def split_bounds_quad(north, south, east, west):
        """
        Split a bounding box into 4 quadrants.
        Returns list of 4 bounding boxes.
        """
        mid_lat = (north + south) / 2
        mid_lon = (east + west) / 2

        return [
            (north, mid_lat, east, mid_lon),      # NE
            (north, mid_lat, mid_lon, west),      # NW
            (mid_lat, south, east, mid_lon),      # SE
            (mid_lat, south, mid_lon, west),      # SW
        ]
    return bounds_to_polygon, format_polygon, split_bounds_quad


@app.cell
def api_functions(API_BASE_URL, format_polygon, httpx, sleep):
    def fetch_crimes(polygon_coords, date, rate_limit_delay=0.1):
        """
        Fetch crime data for a given polygon and date.
        Returns (status_code, data, crime_count)
        """

        polygon_str = format_polygon(polygon_coords)
        params = {
            "date": date,
            "poly": polygon_str
        }

        sleep(rate_limit_delay)  # Rate limiting

        try:
            response = httpx.get(API_BASE_URL, params=params, timeout=30.0)
            if response.status_code == 200:
                data = response.json()
                return 200, data, len(data)
            else:
                return response.status_code, None, 0
        except Exception as e:
            return 500, str(e), 0
    return (fetch_crimes,)


@app.cell
def bisection_algorithm(
    TARGET_MAX_CRIMES,
    TARGET_MIN_CRIMES,
    bounds_to_polygon,
    box,
    check_area_cached,
    conn,
    cursor,
    fetch_crimes,
    insert_crimes_batch,
    split_bounds_quad,
    uk_boundary_polygon,
):
    def process_area(north, south, east, west, date, api_call_counter, results_buffer, cache_hits, depth=0, max_depth=15):
        """
        Recursively process an area using bisection strategy.

        Args:
            north, south, east, west: Bounding box coordinates
            date: Date string in YYYY-MM format
            api_call_counter: List with single element to track total API calls
            results_buffer: List to collect results for batch commit
            cache_hits: List with single element to track cache hits
            depth: Current recursion depth
            max_depth: Maximum recursion depth to prevent infinite loops

        Returns:
            List of tuples: [(polygon_coords, crime_count), ...]
        """
        results = []

        # Prevent infinite recursion
        if depth > max_depth:
            print(f"Max depth {max_depth} reached, stopping recursion")
            return results

        indent = "  " * depth

        # Create a box for this area (west, south, east, north)
        area_box = box(west, south, east, north)

        # Check if this area intersects with UK boundary
        if not area_box.intersects(uk_boundary_polygon):
            print(f"{indent}Depth {depth}: Area ({north:.3f}, {south:.3f}, {east:.3f}, {west:.3f}) - Skipping (no UK land)")
            return results

        # Convert bounds to polygon
        polygon_coords = bounds_to_polygon(north, south, east, west)
        polygon_str = ":".join([f"{lat},{lon}" for lat, lon in polygon_coords])

        # Check cache before making API call
        cached_count = check_area_cached(polygon_str, date)
        if cached_count is not None:
            cache_hits[0] += 1
            print(f"{indent}Depth {depth}: Area ({north:.3f}, {south:.3f}, {east:.3f}, {west:.3f}) - ✓ CACHED ({cached_count} crimes)")
            results.append((polygon_coords, cached_count))
            return results

        # Not cached, fetch from API
        print(f"{indent}Depth {depth}: Checking area ({north:.3f}, {south:.3f}, {east:.3f}, {west:.3f})")
        status_code, data, crime_count = fetch_crimes(polygon_coords, date)

        # Increment API call counter
        api_call_counter[0] += 1

        # Handle different status codes
        if status_code == 503:
            # 503: Service unavailable (crimes > 10000)
            error_msg = "too many crimes" if status_code == 503 else "area size too large"
            print(f"{indent}  -> {status_code} Error ({error_msg}), splitting into 4 quadrants")
            quadrants = split_bounds_quad(north, south, east, west)
            for quad in quadrants:
                results.extend(process_area(*quad, date, api_call_counter, results_buffer, cache_hits, depth + 1, max_depth))

        elif status_code == 200:
            # Success - check if crime count is in target range
            print(f"{indent}  -> {crime_count} crimes found")

            if crime_count > TARGET_MAX_CRIMES:
                # Too many crimes, split into 4 quadrants
                print(f"{indent}  -> Above target ({TARGET_MAX_CRIMES}), splitting")
                quadrants = split_bounds_quad(north, south, east, west)
                for quad in quadrants:
                    results.extend(process_area(*quad, date, api_call_counter, results_buffer, cache_hits, depth + 1, max_depth))

            elif crime_count >= TARGET_MIN_CRIMES:
                # Perfect range! Save area and crimes immediately
                print(f"{indent}  -> ✓ In target range ({TARGET_MIN_CRIMES}-{TARGET_MAX_CRIMES}), saving area and crimes")

                try:
                    # Insert area (or ignore if exists)
                    cursor.execute(
                        """INSERT OR IGNORE INTO crime_areas (polygon, crime_count, date)
                           VALUES (?, ?, ?)""",
                        (polygon_str, crime_count, date)
                    )

                    # Get the area_id (either newly inserted or existing)
                    cursor.execute(
                        """SELECT id FROM crime_areas WHERE polygon = ? AND date = ?""",
                        (polygon_str, date)
                    )
                    area_id = cursor.fetchone()[0]

                    # Insert individual crimes
                    crimes_inserted = insert_crimes_batch(area_id, data)
                    print(f"{indent}  -> ✓ Saved area_id={area_id}, inserted {crimes_inserted} individual crimes")

                    conn.commit()
                    results.append((polygon_coords, crime_count))

                except Exception as e:
                    print(f"{indent}  -> ⚠ Error saving area/crimes: {e}")

            else:
                # Too few crimes, but save anyway for completeness
                print(f"{indent}  -> Below target ({TARGET_MIN_CRIMES}), saving area and crimes")

                try:
                    # Insert area (or ignore if exists)
                    cursor.execute(
                        """INSERT OR IGNORE INTO crime_areas (polygon, crime_count, date)
                           VALUES (?, ?, ?)""",
                        (polygon_str, crime_count, date)
                    )

                    # Get the area_id
                    cursor.execute(
                        """SELECT id FROM crime_areas WHERE polygon = ? AND date = ?""",
                        (polygon_str, date)
                    )
                    area_id = cursor.fetchone()[0]

                    # Insert individual crimes
                    crimes_inserted = insert_crimes_batch(area_id, data)
                    print(f"{indent}  -> ✓ Saved area_id={area_id}, inserted {crimes_inserted} individual crimes")

                    conn.commit()
                    results.append((polygon_coords, crime_count))

                except Exception as e:
                    print(f"{indent}  -> ⚠ Error saving area/crimes: {e}")

        else:
            # Other errors (500, timeout, etc.)
            # For robustness, try splitting these too (might be area-size related)
            print(f"{indent}  -> Error {status_code}, trying to split anyway")
            quadrants = split_bounds_quad(north, south, east, west)
            for quad in quadrants:
                results.extend(process_area(*quad, date, api_call_counter, results_buffer, cache_hits, depth + 1, max_depth))

        return results
    return (process_area,)


@app.cell
def test_execution_controls(mo):
    # Create date input
    test_date = mo.ui.text(value="2024-01", label="Date (YYYY-MM)")

    # Create test area selector
    test_area = mo.ui.dropdown(
        options=["small", "medium", "large", "full"],
        value="small",
        label="Test Area Size"
    )

    # Create boundary display toggle
    show_boundaries = mo.ui.checkbox(
        value=True,
        label="Show UK boundary on map"
    )

    mo.vstack([
        mo.md("""
        ## Execution Controls

        Test the bisection algorithm on a small area before running on the entire UK.
        """),
        test_date,
        test_area,
        show_boundaries
    ])
    return show_boundaries, test_area, test_date


@app.cell
def test_area_bounds(UK_BOUNDS, UK_FULL_BOUNDS, test_area):
    # Define test areas
    test_areas = {
        "small": {  # London area
            "north": 51.7,
            "south": 51.3,
            "east": 0.3,
            "west": -0.5
        },
        "medium": {  # South East England
            "north": 52.0,
            "south": 50.5,
            "east": 1.5,
            "west": -1.5
        },
        "large": UK_BOUNDS,        # England mainland
        "full": UK_FULL_BOUNDS     # Full UK (England, Scotland, Wales, N. Ireland)
    }

    selected_bounds = test_areas[test_area.value]
    return (selected_bounds,)


@app.cell
def execute_bisection(mo, test_area, test_date):
    area_labels = {
        "small": "Small Test (London area)",
        "medium": "Medium Test (South East England)",
        "large": "Large Test (England mainland)",
        "full": "Full UK (England, Scotland, Wales, Northern Ireland)"
    }

    run_button = mo.ui.run_button(label="Run Bisection Algorithm")

    bisection_display = mo.vstack([
        mo.md(f"""
        ### Ready to Execute

        **Date**: {test_date.value}
        **Area**: {area_labels.get(test_area.value, test_area.value)}

        Click the button below to start the bisection algorithm.
        """),
        run_button
    ])
    return bisection_display, run_button


@app.cell
def show_execute_controls(bisection_display):
    bisection_display
    return


@app.cell
def bisection_execution_helpers():
    """Helper functions for bisection execution."""
    def initialize_counters():
        """Initialize counter lists for bisection algorithm."""
        return {
            'api_call_counter': [0],
            'cache_hits': [0],
            'results_buffer': []
        }

    def print_bisection_header(date, bounds):
        """Print header for bisection execution."""
        print("Starting bisection algorithm (with caching & individual crime tracking)...")
        print(f"Date: {date}")
        print(f"Bounds: {bounds}")
        print("-" * 60)

    def print_bisection_summary(results, api_calls, cache_hits):
        """Print summary statistics after bisection completes."""
        print("-" * 60)
        print(f"Completed! Found {len(results)} areas in target range.")
        print(f"Total API calls made: {api_calls}")
        print(f"Cache hits: {cache_hits} (avoided {cache_hits} API calls)")

        if api_calls + cache_hits > 0:
            cache_rate = cache_hits / (api_calls + cache_hits) * 100
            print(f"Cache hit rate: {cache_rate:.1f}%")
    return initialize_counters, print_bisection_header, print_bisection_summary


@app.cell
def bisection_executor_function():
    """Wrapper for bisection execution logic."""
    def execute_bisection_algorithm(process_area, selected_bounds, test_date, counters):
        """
        Execute the bisection algorithm with given parameters.

        Args:
            process_area: The bisection algorithm function
            selected_bounds: Dictionary with north, south, east, west keys
            test_date: Date string in YYYY-MM format
            counters: Dictionary with api_call_counter, cache_hits, results_buffer

        Returns:
            List of (polygon_coords, crime_count) tuples
        """
        results = process_area(
            north=selected_bounds["north"],
            south=selected_bounds["south"],
            east=selected_bounds["east"],
            west=selected_bounds["west"],
            date=test_date,
            api_call_counter=counters['api_call_counter'],
            results_buffer=counters['results_buffer'],
            cache_hits=counters['cache_hits'],
        )
        return results
    return (execute_bisection_algorithm,)


@app.cell
def run_bisection_process(
    execute_bisection_algorithm,
    initialize_counters,
    print_bisection_header,
    print_bisection_summary,
    process_area,
    run_button,
    selected_bounds,
    test_date,
):
    """Main orchestrator for bisection execution."""
    run_button  # Create dependency

    if run_button.value:
        # Initialize
        counters = initialize_counters()

        # Print header
        print_bisection_header(test_date.value, selected_bounds)

        # Execute bisection
        results = execute_bisection_algorithm(
            process_area,
            selected_bounds,
            test_date.value,
            counters
        )

        # Print summary
        print_bisection_summary(
            results,
            counters['api_call_counter'][0],
            counters['cache_hits'][0]
        )

        # Store results
        bisection_results = results
        total_api_calls = counters['api_call_counter'][0]
        total_cache_hits = counters['cache_hits'][0]
    else:
        bisection_results = []
        total_api_calls = 0
        total_cache_hits = 0
    return bisection_results, total_api_calls, total_cache_hits


@app.cell
def map_helper_functions(folium):
    """Helper functions for map creation and manipulation."""
    def calculate_map_center(bisection_results):
        """Calculate center point from bisection results."""
        all_lats = [coord[0] for coords, _ in bisection_results for coord in coords]
        all_lons = [coord[1] for coords, _ in bisection_results for coord in coords]
        center_lat = (max(all_lats) + min(all_lats)) / 2
        center_lon = (max(all_lons) + min(all_lons)) / 2
        return center_lat, center_lon

    def create_base_map(center_lat, center_lon, zoom_start=8):
        """Create a folium map centered on given coordinates."""
        return folium.Map(
            location=[center_lat, center_lon],
            zoom_start=zoom_start,
            tiles='OpenStreetMap'
        )
    return calculate_map_center, create_base_map


@app.cell
def boundary_rendering_functions(folium):
    """Functions for rendering UK boundary on map."""
    def add_uk_boundary_to_map(map_obj, uk_boundary_polygon):
        """
        Add UK boundary polygon to folium map.

        Args:
            map_obj: Folium map object
            uk_boundary_polygon: Shapely Polygon or MultiPolygon
        """
        if uk_boundary_polygon.geom_type == 'Polygon':
            # Single polygon
            uk_boundary_coords_list = list(uk_boundary_polygon.exterior.coords)
            uk_boundary_latlon = [[lat, lon] for lon, lat in uk_boundary_coords_list]

            folium.Polygon(
                locations=uk_boundary_latlon,
                color='red',
                weight=3,
                fill=False,
                opacity=0.8,
                popup='UK Boundary (excludes Republic of Ireland)',
                tooltip='UK Territory Boundary'
            ).add_to(map_obj)
        else:
            # MultiPolygon - iterate through all constituent polygons
            for geom in uk_boundary_polygon.geoms:
                uk_boundary_coords_list = list(geom.exterior.coords)
                uk_boundary_latlon = [[lat, lon] for lon, lat in uk_boundary_coords_list]

                folium.Polygon(
                    locations=uk_boundary_latlon,
                    color='red',
                    weight=3,
                    fill=False,
                    opacity=0.8,
                    popup='UK Boundary (excludes Republic of Ireland)',
                    tooltip='UK Territory Boundary'
                ).add_to(map_obj)
    return (add_uk_boundary_to_map,)


@app.cell
def area_rendering_functions(folium):
    """Functions for rendering bisected areas on map."""
    # Polygon styling constants
    POLYGON_COLOR = '#3388ff'      # Blue border
    POLYGON_FILL_COLOR = '#3388ff' # Blue fill
    POLYGON_OPACITY = 0.3          # 30% fill opacity
    POLYGON_WEIGHT = 2             # 2px border width

    def add_area_polygons_to_map(map_obj, bisection_results):
        """
        Add bisected area polygons to folium map.

        Args:
            map_obj: Folium map object
            bisection_results: List of (polygon_coords, crime_count) tuples
        """
        # Start enumeration at 1 to match database area_id
        for idx, (polygon_coords, crime_count) in enumerate(bisection_results, start=1):
            # Convert to list of [lat, lon] for folium
            locations = [[lat, lon] for lat, lon in polygon_coords]

            # Add polygon to map with uniform styling
            folium.Polygon(
                locations=locations,
                color=POLYGON_COLOR,
                weight=POLYGON_WEIGHT,
                fill=True,
                fillColor=POLYGON_FILL_COLOR,
                fillOpacity=POLYGON_OPACITY,
                popup=folium.Popup(
                    f"<b>Area {idx}</b><br>"
                    f"Crimes: {crime_count:,}<br>"
                    f"Bounds:<br>"
                    f"N: {max([c[0] for c in polygon_coords]):.4f}<br>"
                    f"S: {min([c[0] for c in polygon_coords]):.4f}<br>"
                    f"E: {max([c[1] for c in polygon_coords]):.4f}<br>"
                    f"W: {min([c[1] for c in polygon_coords]):.4f}",
                    max_width=300
                ),
                tooltip=f"Area {idx}: {crime_count:,} crimes"
            ).add_to(map_obj)
    return (add_area_polygons_to_map,)


@app.cell
def statistics_functions():
    """Functions for calculating and formatting statistics."""
    def calculate_crime_statistics(bisection_results):
        """Calculate statistics from bisection results."""
        crime_counts = [count for _, count in bisection_results]
        return {
            'crime_counts': crime_counts,
            'total_crimes': sum(crime_counts),
            'avg_crimes': sum(crime_counts) / len(crime_counts),
            'min_crimes': min(crime_counts),
            'max_crimes': max(crime_counts),
            'total_areas': len(bisection_results)
        }

    def format_statistics_markdown(stats, total_api_calls, total_cache_hits):
        """Format statistics as markdown string."""
        total_checks = total_api_calls + total_cache_hits
        cache_rate = (total_cache_hits / total_checks * 100) if total_checks > 0 else 0

        return f"""
        ### Results Summary

        - **Total Areas**: {stats['total_areas']}
        - **Total Crimes**: {stats['total_crimes']:,}
        - **Average Crimes per Area**: {stats['avg_crimes']:.0f}
        - **Min Crimes**: {stats['min_crimes']}
        - **Max Crimes**: {stats['max_crimes']}
        - **API Calls Made**: {total_api_calls}
        - **Cache Hits**: {total_cache_hits} ({cache_rate:.1f}% cache hit rate)

        **Map**: Blue polygons show bisected areas. Click for details, hover for quick stats.
        """
    return calculate_crime_statistics, format_statistics_markdown


@app.cell
def visualize_results(
    add_area_polygons_to_map,
    add_uk_boundary_to_map,
    bisection_results,
    calculate_crime_statistics,
    calculate_map_center,
    create_base_map,
    format_statistics_markdown,
    mo,
    show_boundaries,
    total_api_calls,
    total_cache_hits,
    uk_boundary_polygon,
):
    """Main visualization orchestrator function."""
    if len(bisection_results) == 0:
        output = mo.md("**No results yet.** Run the bisection algorithm to see visualizations.")
    else:
        # Create map
        center_lat, center_lon = calculate_map_center(bisection_results)
        m = create_base_map(center_lat, center_lon)

        # Add UK boundary if requested
        if show_boundaries.value:
            add_uk_boundary_to_map(m, uk_boundary_polygon)

        # Add area polygons
        add_area_polygons_to_map(m, bisection_results)

        # Calculate and format statistics
        stats = calculate_crime_statistics(bisection_results)
        stats_md = format_statistics_markdown(stats, total_api_calls, total_cache_hits)

        # Combine into output
        output = mo.vstack([mo.md(stats_md), mo.Html(m._repr_html_())])
    return (output,)


@app.cell
def _(output):

    output
    return


@app.cell
def _(conn, pl):
    df_chk = pl.read_database("SELECT * FROM crime_areas", conn)
    return (df_chk,)


@app.cell
def _(df_chk):
    df_chk
    return


@app.cell
def crimes_data(conn, pl):
    """Query individual crimes data from the crimes table."""
    df_crimes = pl.read_database(
        """SELECT c.*, ca.date, ca.crime_count as area_crime_count
           FROM crimes c
           LEFT JOIN crime_areas ca ON c.area_id = ca.id
           ORDER BY c.id DESC
           LIMIT 1000""",
        conn
    )
    return (df_crimes,)


@app.cell
def _(df_crimes):
    df_crimes
    return


@app.cell
def _():
    return


app._unparsable_cell(
    r"""
    \"> There is still an issue witht he visualize_results cell
    \"\"Functions for loading existing areas and processing historical data.\"\"\"
    def load_existing_areas(base_date=None):
        \"\"\"
        Load existing area polygons from the database.

        Args:
            base_date: Optional date to filter areas (YYYY-MM format)
                      If None, loads all unique polygons

        Returns:
            List of tuples: [(area_id, polygon_str, base_crime_count), ...]
        \"\"\"
        if base_date:
            cursor.execute(
                \"\"\"SELECT id, polygon, crime_count
                   FROM crime_areas
                   WHERE date = ?
                   ORDER BY id\"\"\",
                (base_date,)
            )
        else:
            # Get unique polygons (take first occurrence of each)
            cursor.execute(
                \"\"\"SELECT id, polygon, crime_count
                   FROM crime_areas
                   GROUP BY polygon
                   ORDER BY id\"\"\"
            )

        areas = cursor.fetchall()
        return areas

    def generate_month_range(start_date, end_date):
        \"\"\"
        Generate list of months between start_date and end_date (inclusive).

        Args:
            start_date: Start date in YYYY-MM format
            end_date: End date in YYYY-MM format

        Returns:
            List of date strings: ['2024-01', '2024-02', ...]
        \"\"\"
        start_year, start_month = map(int, start_date.split('-'))
        end_year, end_month = map(int, end_date.split('-'))

        months = []
        current_year = start_year
        current_month = start_month

        while (current_year < end_year) or (current_year == end_year and current_month <= end_month):
            months.append(f\"{current_year:04d}-{current_month:02d}\")
            current_month += 1
            if current_month > 12:
                current_month = 1
                current_year += 1

        return months
    """,
    name="historical_data_functions"
)


@app.cell
def historical_crime_fetcher(conn, cursor, fetch_crimes, insert_crimes_batch):
    """Fetch historical crime data for existing areas."""
    def fetch_historical_crimes(areas, date, progress_callback=None):
        """
        Fetch crimes for all areas for a specific date.

        Args:
            areas: List of (area_id, polygon_str, crime_count) tuples
            date: Date string in YYYY-MM format
            progress_callback: Optional function to call with progress updates

        Returns:
            Dictionary with statistics
        """
        total_areas = len(areas)
        successful = 0
        failed = 0
        total_crimes_inserted = 0

        for idx, (area_id, polygon_str, _) in enumerate(areas, start=1):
            # Convert polygon string back to coords for API
            # Format: "lat1,lon1:lat2,lon2:..."
            polygon_coords = []
            for pair in polygon_str.split(':'):
                lat, lon = pair.split(',')
                polygon_coords.append((float(lat), float(lon)))

            # Fetch crimes from API
            status_code, data, crime_count = fetch_crimes(polygon_coords, date)

            if status_code == 200:
                # Check if this area/date already exists in crime_areas
                cursor.execute(
                    """SELECT id FROM crime_areas
                       WHERE polygon = ? AND date = ?""",
                    (polygon_str, date)
                )
                result = cursor.fetchone()

                if result:
                    # Area/date exists, use existing area_id
                    existing_area_id = result[0]
                    area_id_to_use = existing_area_id
                else:
                    # Insert new area/date record
                    cursor.execute(
                        """INSERT INTO crime_areas (polygon, crime_count, date)
                           VALUES (?, ?, ?)""",
                        (polygon_str, crime_count, date)
                    )
                    area_id_to_use = cursor.lastrowid

                # Insert individual crimes
                crimes_inserted = insert_crimes_batch(area_id_to_use, data)
                total_crimes_inserted += crimes_inserted
                successful += 1

                conn.commit()

                if progress_callback:
                    progress_callback(idx, total_areas, area_id, crime_count, crimes_inserted)
            else:
                failed += 1
                if progress_callback:
                    progress_callback(idx, total_areas, area_id, 0, 0, error=status_code)

        return {
            'total_areas': total_areas,
            'successful': successful,
            'failed': failed,
            'total_crimes': total_crimes_inserted
        }
    return (fetch_historical_crimes,)


@app.cell
def historical_ui_controls(mo):
    """UI controls for historical data collection."""

    historical_start_date = mo.ui.text(
        value="2024-01",
        label="Start Date (YYYY-MM)"
    )

    historical_end_date = mo.ui.text(
        value="2024-01",
        label="End Date (YYYY-MM)"
    )

    base_date_for_areas = mo.ui.text(
        value="2024-01",
        label="Base Date (areas to use)"
    )

    historical_run_button = mo.ui.run_button(
        label="Fetch Historical Crime Data"
    )

    historical_display = mo.vstack([
        mo.md("""
        ## Historical Data Collection

        Use existing areas from the database to fetch crime data for multiple months.

        **Instructions:**
        1. **Base Date**: The date of the bisection run (which areas to use)
        2. **Start Date**: First month to fetch
        3. **End Date**: Last month to fetch (inclusive)
        4. Click "Fetch Historical Crime Data" to begin

        **Note**: This will fetch crimes for ALL areas for each month in the range.
        """),
        base_date_for_areas,
        historical_start_date,
        historical_end_date,
        historical_run_button
    ])
    return (
        base_date_for_areas,
        historical_display,
        historical_end_date,
        historical_run_button,
        historical_start_date,
    )


@app.cell
def show_historical_controls(historical_display):
    historical_display
    return


@app.cell
def run_historical_collection(
    base_date_for_areas,
    fetch_historical_crimes,
    generate_month_range,
    historical_end_date,
    historical_run_button,
    historical_start_date,
    load_existing_areas,
):
    """Execute historical data collection."""
    historical_run_button  # Create dependency

    if historical_run_button.value:
        print("=" * 70)
        print("HISTORICAL CRIME DATA COLLECTION")
        print("=" * 70)

        # Load existing areas
        print(f"\nLoading areas from base date: {base_date_for_areas.value}")
        areas = load_existing_areas(base_date_for_areas.value)
        print(f"✓ Loaded {len(areas)} areas")

        if len(areas) == 0:
            print("⚠ No areas found! Run bisection algorithm first.")
        else:
            # Generate date range
            print(f"\nGenerating date range: {historical_start_date.value} to {historical_end_date.value}")
            months = generate_month_range(
                historical_start_date.value,
                historical_end_date.value
            )
            print(f"✓ Will process {len(months)} month(s): {', '.join(months)}")

            # Process each month
            total_stats = {
                'months_processed': 0,
                'total_crimes': 0,
                'total_api_calls': 0
            }

            for month in months:
                print(f"\n{'─' * 70}")
                print(f"Processing: {month}")
                print(f"{'─' * 70}")

                def progress(idx, total, area_id, crime_count, crimes_inserted, error=None):
                    if error:
                        print(f"  [{idx}/{total}] Area {area_id} - ⚠ Error {error}")
                    else:
                        print(f"  [{idx}/{total}] Area {area_id} - {crime_count} crimes, {crimes_inserted} inserted")

                month_stats = fetch_historical_crimes(areas, month, progress)

                print(f"\n✓ {month} Complete:")
                print(f"  - Successful: {month_stats['successful']}/{month_stats['total_areas']}")
                print(f"  - Failed: {month_stats['failed']}")
                print(f"  - Total crimes inserted: {month_stats['total_crimes']:,}")

                total_stats['months_processed'] += 1
                total_stats['total_crimes'] += month_stats['total_crimes']
                total_stats['total_api_calls'] += month_stats['total_areas']

            print(f"\n{'═' * 70}")
            print("COLLECTION COMPLETE")
            print(f"{'═' * 70}")
            print(f"Months processed: {total_stats['months_processed']}")
            print(f"Total API calls: {total_stats['total_api_calls']:,}")
            print(f"Total crimes inserted: {total_stats['total_crimes']:,}")
            print(f"{'═' * 70}")

            historical_stats = total_stats
    else:
        historical_stats = None
    return


if __name__ == "__main__":
    app.run()
