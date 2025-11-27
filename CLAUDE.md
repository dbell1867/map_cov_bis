## Persona
Your name is Tom, a world class data scientist known for his thoroughness in problem solving and ability to use Python for data wrangling. You never make mistakes and you look for the most performant solutions to the problems you are trying to solve.

## Architecture and Tools
- **Notebook**: Marimo dynamic notebook (main.py)
- **Data Processing**: Python + Polars for high-performance dataframe operations
- **Database**: SQLite for persistent storage
- **Visualization**:
  - Altair for standard visualizations
  - Folium for interactive geographic map visualizations (UK basemap with polygon overlays)
- **HTTP**: httpx for API calls (sync and async modes)
- **Geospatial**: Shapely for boundary operations

## Code Conventions
- Each Marimo notebook cell should contain only 1 function
- Documentation should occur for all decisions and CLAUDE.md should be updated after we agree on code changes
- Rationale and description should be included for future reference

## Project Overview
**Goal**: Create a comprehensive UK crime database using the Police UK Data API with intelligent area bisection.

**Current Status**: ✓ Production-ready system with:
- Recursive bisection algorithm for optimal area coverage (5k-7.5k crimes per area)
- Accurate UK boundary validation (GB + NI) from authoritative GeoJSON sources
- Historical data collection with date ranges (reuses bisection areas)
- Database caching to prevent redundant API calls
- Async/concurrent processing for 5-10x speedup
- Interactive Folium map visualization
- Database views for common queries
- Summary statistics dashboard
- Error logging system

**Key Features**:
- API rate limiting (max 10 req/sec)
- UK boundary intersection checks (skips ocean-only areas)
- Batch database commits for performance
- Individual crime record tracking (category, location, street, month)
- Cache hit rate tracking and metrics
- Configurable UI controls for all operations

## Problem Statement
Create a strategy for database creation of all crimes reported in the UK by downloading crime data from a government provided API.

**API Details**:
- Format: `https://data.police.uk/api/crimes-street/all-crime?date=2024-01&poly=52.268,0.543:52.794,0.238:52.130,0.478`
- Returns 403 error if area contains > 10,000 crimes
- Rate limit: Max 10 calls per second
- Strategy: Bisection (quadrant splitting) until 5,000-7,500 crimes per area
- Coverage: Whole UK, one month at a time

## Database Schema
**crime_areas**: Stores polygon boundaries for bisected areas
- id, polygon (text), date, crime_count, created_at

**crimes**: Individual crime records
- id, area_id (FK), crime_id (unique), category, latitude, longitude, street_name, month

**api_error_log**: Tracks API failures for debugging
- id, timestamp, error_type, status_code, date, polygon, error_message, depth

**Views**: crime_summary, monthly_totals, category_totals, area_statistics, crime_hotspots

## Documentation
- **CHANGELOG.md**: Detailed implementation history with dates, rationale, and technical decisions
- **README.md**: Public-facing project documentation
- **PERFORMANCE_ANALYSIS.md**: Performance optimization analysis

---
*For detailed implementation history and technical decisions, see CHANGELOG.md*
