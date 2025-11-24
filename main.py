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
    return Polygon, box, folium, httpx, mo, sleep, sqlite3, unary_union


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
    API_BASE_URL = "https://data.police.uk/api/crimes-street/all-crime"
    MAX_CALLS_PER_SECOND = 10
    TARGET_MIN_CRIMES = 5000
    TARGET_MAX_CRIMES = 7500
    MAX_CRIMES_LIMIT = 10000
    DB_PATH = "uk_crime_data.db"
    return API_BASE_URL, DB_PATH, TARGET_MAX_CRIMES, TARGET_MIN_CRIMES


@app.cell
def uk_boundaries(Polygon, httpx, unary_union):
    """
    UK mainland approximate boundaries.
    Fetches accurate UK boundary from public GeoJSON source.
    """
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

    # Fetch accurate UK boundary from UK-GeoJSON repository
    # This includes Great Britain (England, Scotland, Wales) + Northern Ireland
    try:
        print("Fetching UK boundary data...")

        # Fetch Great Britain (England, Scotland, Wales)
        gb_url = "https://raw.githubusercontent.com/martinjc/UK-GeoJSON/master/json/administrative/gb/lad.json"
        print("  - Fetching Great Britain boundaries...")
        gb_response = httpx.get(gb_url, timeout=30.0)

        # Fetch Northern Ireland
        ni_url = "https://raw.githubusercontent.com/martinjc/UK-GeoJSON/master/json/administrative/ni/lgd.json"
        print("  - Fetching Northern Ireland boundaries...")
        ni_response = httpx.get(ni_url, timeout=30.0)

        if gb_response.status_code == 200 and ni_response.status_code == 200:
            # Extract polygons from Great Britain data
            gb_data = gb_response.json()
            polygons = []

            for feature in gb_data['features']:
                geom = feature['geometry']
                if geom['type'] == 'Polygon':
                    coords = geom['coordinates'][0]
                    polygons.append(Polygon(coords))
                elif geom['type'] == 'MultiPolygon':
                    for poly_coords in geom['coordinates']:
                        polygons.append(Polygon(poly_coords[0]))

            gb_count = len(polygons)
            print(f"  ✓ Loaded {gb_count} Great Britain boundaries")

            # Extract polygons from Northern Ireland data
            ni_data = ni_response.json()

            for feature in ni_data['features']:
                geom = feature['geometry']
                if geom['type'] == 'Polygon':
                    coords = geom['coordinates'][0]
                    polygons.append(Polygon(coords))
                elif geom['type'] == 'MultiPolygon':
                    for poly_coords in geom['coordinates']:
                        polygons.append(Polygon(poly_coords[0]))

            ni_count = len(polygons) - gb_count
            print(f"  ✓ Loaded {ni_count} Northern Ireland boundaries")

            # Merge all polygons into one boundary
            uk_boundary_polygon = unary_union(polygons)
            print(f"✓ Total: {len(polygons)} UK administrative boundaries (GB + NI)")

        else:
            raise Exception(f"Failed to fetch UK boundary: GB={gb_response.status_code}, NI={ni_response.status_code}")

    except Exception as e:
        print(f"⚠ Could not fetch UK boundary: {e}")
        print("Using simplified fallback boundary...")

        # Fallback: simplified boundary including Northern Ireland
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
        uk_boundary_polygon = unary_union([gb_poly, ni_poly])
        print(f"  ✓ Using fallback boundary (includes Northern Ireland)")
    return UK_BOUNDS, UK_FULL_BOUNDS, uk_boundary_polygon


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
            location_type TEXT,
            latitude REAL,
            longitude REAL,
            street_name TEXT,
            outcome_status TEXT,
            month TEXT,
            FOREIGN KEY (area_id) REFERENCES crime_areas(id)
        )
    """)

    conn.commit()
    return conn, cursor


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
    conn,
    cursor,
    fetch_crimes,
    split_bounds_quad,
    uk_boundary_polygon,
):
    def process_area(north, south, east, west, date, api_call_counter, depth=0, max_depth=15):
        """
        Recursively process an area using bisection strategy.

        Args:
            north, south, east, west: Bounding box coordinates
            date: Date string in YYYY-MM format
            api_call_counter: List with single element to track total API calls
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

        # Convert bounds to polygon and fetch crime data
        polygon_coords = bounds_to_polygon(north, south, east, west)
        print(f"{indent}Depth {depth}: Checking area ({north:.3f}, {south:.3f}, {east:.3f}, {west:.3f})")

        status_code, data, crime_count = fetch_crimes(polygon_coords, date)

        # Increment API call counter
        api_call_counter[0] += 1

        # Handle different status codes
        if status_code == 403 or status_code == 503:
            # 403: Too many crimes (>10,000)
            # 503: Service unavailable (might be due to area size)
            # Both cases: try splitting into smaller areas
            error_msg = "too many crimes" if status_code == 403 else "service unavailable"
            print(f"{indent}  -> {status_code} Error ({error_msg}), splitting into 4 quadrants")
            quadrants = split_bounds_quad(north, south, east, west)
            for quad in quadrants:
                results.extend(process_area(*quad, date, api_call_counter, depth + 1, max_depth))

        elif status_code == 200:
            # Success - check if crime count is in target range
            print(f"{indent}  -> {crime_count} crimes found")

            if crime_count > TARGET_MAX_CRIMES:
                # Too many crimes, split into 4 quadrants
                print(f"{indent}  -> Above target ({TARGET_MAX_CRIMES}), splitting")
                quadrants = split_bounds_quad(north, south, east, west)
                for quad in quadrants:
                    results.extend(process_area(*quad, date, api_call_counter, depth + 1, max_depth))

            elif crime_count >= TARGET_MIN_CRIMES:
                # Perfect range! Save to database
                print(f"{indent}  -> ✓ In target range ({TARGET_MIN_CRIMES}-{TARGET_MAX_CRIMES}), saving")
                polygon_str = ":".join([f"{lat},{lon}" for lat, lon in polygon_coords])

                try:
                    cursor.execute(
                        """INSERT OR IGNORE INTO crime_areas (polygon, crime_count, date)
                           VALUES (?, ?, ?)""",
                        (polygon_str, crime_count, date)
                    )
                    conn.commit()
                    results.append((polygon_coords, crime_count))
                except Exception as e:
                    print(f"{indent}  -> Error saving to DB: {e}")

            else:
                # Too few crimes, but save anyway for completeness
                print(f"{indent}  -> Below target ({TARGET_MIN_CRIMES}), saving anyway")
                polygon_str = ":".join([f"{lat},{lon}" for lat, lon in polygon_coords])

                try:
                    cursor.execute(
                        """INSERT OR IGNORE INTO crime_areas (polygon, crime_count, date)
                           VALUES (?, ?, ?)""",
                        (polygon_str, crime_count, date)
                    )
                    conn.commit()
                    results.append((polygon_coords, crime_count))
                except Exception as e:
                    print(f"{indent}  -> Error saving to DB: {e}")

        else:
            # Other errors (500, timeout, etc.)
            # For robustness, try splitting these too (might be area-size related)
            print(f"{indent}  -> Error {status_code}, trying to split anyway")
            quadrants = split_bounds_quad(north, south, east, west)
            for quad in quadrants:
                results.extend(process_area(*quad, date, api_call_counter, depth + 1, max_depth))

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

    display = mo.vstack([
        mo.md(f"""
        ### Ready to Execute

        **Date**: {test_date.value}
        **Area**: {area_labels.get(test_area.value, test_area.value)}

        Click the button below to start the bisection algorithm.
        """),
        run_button
    ])
    return display, run_button


@app.cell
def show_execute_controls(display):
    display
    return


@app.cell
def run_bisection_process(
    process_area,
    run_button,
    selected_bounds,
    test_date,
):
    run_button  # Create dependency

    if run_button.value:
        print("Starting bisection algorithm...")
        print(f"Date: {test_date.value}")
        print(f"Bounds: {selected_bounds}")
        print("-" * 60)

        # Initialize API call counter (using list so it's mutable across recursion)
        api_call_counter = [0]

        results = process_area(
            north=selected_bounds["north"],
            south=selected_bounds["south"],
            east=selected_bounds["east"],
            west=selected_bounds["west"],
            date=test_date.value,
            api_call_counter=api_call_counter,
        )

        print("-" * 60)
        print(f"Completed! Found {len(results)} areas in target range.")
        print(f"Total API calls made: {api_call_counter[0]}")
        bisection_results = results
        total_api_calls = api_call_counter[0]
    else:
        bisection_results = []
        total_api_calls = 0
    return bisection_results, total_api_calls


@app.cell
def visualize_results(
    bisection_results,
    folium,
    mo,
    show_boundaries,
    total_api_calls,
    uk_boundary_polygon,
):
    if len(bisection_results) == 0:
        output = mo.md("**No results yet.** Run the bisection algorithm to see visualizations.")
    else:
        # Calculate center point for map
        all_lats = [coord[0] for coords, _ in bisection_results for coord in coords]
        all_lons = [coord[1] for coords, _ in bisection_results for coord in coords]

        center_lat = (max(all_lats) + min(all_lats)) / 2
        center_lon = (max(all_lons) + min(all_lons)) / 2

        # Create folium map centered on data
        m = folium.Map(
            location=[center_lat, center_lon],
            zoom_start=8,
            tiles='OpenStreetMap'
        )

        # Conditionally add UK boundary polygon in red (reference outline)
        if show_boundaries.value:
            # Handle both Polygon and MultiPolygon types
            if uk_boundary_polygon.geom_type == 'Polygon':
                # Single polygon - extract exterior coordinates
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
                ).add_to(m)
            else:
                # MultiPolygon - iterate through all constituent polygons
                for geomi in uk_boundary_polygon.geoms:
                    uk_boundary_coords_list = list(geomi.exterior.coords)
                    uk_boundary_latlon = [[lat, lon] for lon, lat in uk_boundary_coords_list]

                    folium.Polygon(
                        locations=uk_boundary_latlon,
                        color='red',
                        weight=3,
                        fill=False,
                        opacity=0.8,
                        popup='UK Boundary (excludes Republic of Ireland)',
                        tooltip='UK Territory Boundary'
                    ).add_to(m)

        # Calculate crime counts for statistics
        crime_counts = [count for _, count in bisection_results]
        min_crimes = min(crime_counts)
        max_crimes = max(crime_counts)

        # Uniform styling for all polygons
        POLYGON_COLOR = '#3388ff'      # Blue border
        POLYGON_FILL_COLOR = '#3388ff' # Blue fill
        POLYGON_OPACITY = 0.3          # 30% fill opacity
        POLYGON_WEIGHT = 2             # 2px border width

        # Add each bisected area as a polygon
        for idx, (polygon_coords, crime_count) in enumerate(bisection_results):
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
            ).add_to(m)

        # Display statistics
        total_crimes = sum(crime_counts)
        avg_crimes = total_crimes / len(crime_counts)

        stats = mo.md(f"""
        ### Results Summary

        - **Total Areas**: {len(bisection_results)}
        - **Total Crimes**: {total_crimes:,}
        - **Average Crimes per Area**: {avg_crimes:.0f}
        - **Min Crimes**: {min_crimes}
        - **Max Crimes**: {max_crimes}
        - **API Calls Made**: {total_api_calls}

        **Map**: Blue polygons show bisected areas. Click for details, hover for quick stats.
        """)

        output = mo.vstack([stats, mo.Html(m._repr_html_())])
    return (output,)


@app.cell
def _(output):

    output
    return


if __name__ == "__main__":
    app.run()
