# Performance Analysis: UK Crime Data Full Analysis

## Current Performance Bottlenecks

### 1. **Sequential API Calls** ⚠️ CRITICAL BOTTLENECK
**Impact**: Highest performance cost
**Current Implementation**:
- One API call at a time in recursive function (main.py:340)
- 0.1s delay between each call (10 calls/second max)
- Recursive algorithm waits for each call to complete before proceeding

**Estimated Time for Full UK**:
- Full UK area requires ~500-1000 API calls (estimated)
- At 10 calls/second: **50-100 seconds minimum**
- With recursion overhead and processing: **2-3 minutes minimum**
- Actual time likely higher due to deep recursion in high-crime areas

**Example**: London alone might require 100+ calls at depth 5-7 recursion
- Sequential: 10 seconds
- Parallel (10 concurrent): 1-2 seconds

---

### 2. **Database Operations** ⚠️ MODERATE BOTTLENECK
**Impact**: Moderate performance cost
**Current Implementation**:
- `conn.commit()` after EVERY insert (main.py:376, 392)
- Synchronous writes block the recursive function
- Database I/O happens hundreds of times

**Estimated Time Cost**:
- ~1-5ms per commit
- 500 areas × 3ms = **1.5 seconds**

**Better Approach**: Batch commits at the end

---

### 3. **No Result Caching** ⚠️ MODERATE BOTTLENECK
**Impact**: Wasted API calls on reruns
**Current Implementation**:
- No check if area/date already processed
- Rerunning same date re-fetches all data
- `INSERT OR IGNORE` silently skips duplicates but API call still made

**Estimated Waste**:
- Rerunning same date: 100% wasted calls
- Interrupted run resumed: Repeats all previous work

---

### 4. **Synchronous HTTP Requests** ⚠️ HIGH BOTTLENECK
**Impact**: Cannot utilize concurrent requests
**Current Implementation**:
- Uses synchronous `httpx.get()` (main.py:282)
- Cannot make parallel requests to API
- API allows 10 calls/second, but we only use 1 at a time

**Potential Speedup**: **10x faster** with async/parallel requests

---

### 5. **Initial Boundary Fetch** ⚠️ LOW BOTTLENECK
**Impact**: One-time 3-4 second delay
**Current Implementation**:
- Fetches GB (2.5 MB) + NI (17.7 MB) on every notebook load
- ~3-4 seconds startup time
- Re-fetches even if boundary unchanged

**Better Approach**: Cache to disk, load from file

---

## Performance Optimization Strategies

### HIGH IMPACT OPTIMIZATIONS

#### 1. **Async/Parallel API Calls** 🚀 **10x SPEEDUP**
```python
import asyncio
import httpx

async def fetch_crimes_async(client, polygon_coords, date):
    polygon_str = format_polygon(polygon_coords)
    params = {"date": date, "poly": polygon_str}
    response = await client.get(API_BASE_URL, params=params)
    if response.status_code == 200:
        data = response.json()
        return 200, data, len(data)
    return response.status_code, None, 0

async def process_area_async(north, south, east, west, date, semaphore):
    """Process with semaphore limiting to 10 concurrent requests"""
    async with semaphore:
        # Check boundary intersection first
        # Make async API call
        # Return results without blocking other calls
        pass

async def process_full_uk(date):
    semaphore = asyncio.Semaphore(10)  # Max 10 concurrent requests
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Process multiple areas concurrently
        tasks = []
        # Create tasks for initial grid
        results = await asyncio.gather(*tasks)
```

**Benefits**:
- 10x faster: Use full API rate limit (10 concurrent calls)
- Better resource utilization
- Reduces total time from 100s to 10s

---

#### 2. **Database Result Caching** 🚀 **Avoids Duplicate Work**
```python
def check_area_cached(cursor, polygon_str, date):
    """Check if area already processed for this date"""
    cursor.execute(
        "SELECT crime_count FROM crime_areas WHERE polygon = ? AND date = ?",
        (polygon_str, date)
    )
    result = cursor.fetchone()
    return result[0] if result else None

def process_area(north, south, east, west, date, ...):
    polygon_coords = bounds_to_polygon(north, south, east, west)
    polygon_str = ":".join([f"{lat},{lon}" for lat, lon in polygon_coords])

    # Check cache first
    cached_count = check_area_cached(cursor, polygon_str, date)
    if cached_count is not None:
        print(f"Using cached result: {cached_count} crimes")
        return [(polygon_coords, cached_count)]

    # Otherwise fetch from API
    status_code, data, crime_count = fetch_crimes(polygon_coords, date)
    # ... rest of logic
```

**Benefits**:
- Resume interrupted runs without re-fetching
- Instant results for previously processed areas
- Saves API quota

---

#### 3. **Batch Database Commits** 🚀 **3-5x FASTER DB OPS**
```python
def process_area(north, south, east, west, date, results_buffer, ...):
    """Collect results in buffer instead of immediate commit"""
    # ... processing logic ...

    if crime_count >= TARGET_MIN_CRIMES:
        # Add to buffer instead of immediate commit
        results_buffer.append((polygon_str, crime_count, date))

        # Batch commit every 50 inserts
        if len(results_buffer) >= 50:
            cursor.executemany(
                "INSERT OR IGNORE INTO crime_areas (polygon, crime_count, date) VALUES (?, ?, ?)",
                results_buffer
            )
            conn.commit()
            results_buffer.clear()

# After all processing
cursor.executemany(...)  # Final batch
conn.commit()
```

**Benefits**:
- Reduces I/O from 500 commits to 10-20 batch commits
- 3-5x faster database operations
- Maintains data integrity with periodic commits

---

#### 4. **Smart Initial Grid** 🚀 **Reduces API Calls by 30-50%**
```python
def generate_initial_grid(uk_bounds, target_grid_size=0.5):
    """
    Start with pre-calculated grid instead of single large box.
    Grid size chosen to likely hit target range in urban areas.
    """
    north, south = uk_bounds["north"], uk_bounds["south"]
    east, west = uk_bounds["east"], uk_bounds["west"]

    lat_steps = int((north - south) / target_grid_size) + 1
    lon_steps = int((east - west) / target_grid_size) + 1

    grid_cells = []
    for i in range(lat_steps):
        for j in range(lon_steps):
            cell_north = min(north, south + (i + 1) * target_grid_size)
            cell_south = south + i * target_grid_size
            cell_east = min(east, west + (j + 1) * target_grid_size)
            cell_west = west + j * target_grid_size

            # Only include cells that intersect UK
            cell_box = box(cell_west, cell_south, cell_east, cell_north)
            if cell_box.intersects(uk_boundary_polygon):
                grid_cells.append((cell_north, cell_south, cell_east, cell_west))

    return grid_cells
```

**Benefits**:
- Start at reasonable granularity instead of recursing from full UK
- Fewer recursion levels needed
- 30-50% fewer total API calls
- Better parallelization (more initial tasks)

---

### MEDIUM IMPACT OPTIMIZATIONS

#### 5. **Cached Boundary Data** 💾 **Saves 3-4 seconds per run**
```python
from pathlib import Path
import pickle

def load_uk_boundary():
    cache_path = Path("uk_boundary_cache.pkl")

    # Try loading from cache first
    if cache_path.exists():
        with open(cache_path, "rb") as f:
            return pickle.load(f)

    # Otherwise fetch and cache
    uk_boundary_polygon = fetch_boundary_from_github()

    with open(cache_path, "wb") as f:
        pickle.dump(uk_boundary_polygon, f)

    return uk_boundary_polygon
```

---

#### 6. **Progress Persistence & Resume** 💾 **Avoid Lost Work**
```python
def save_progress(processed_areas, filename="progress.json"):
    """Save list of completed areas to resume later"""
    with open(filename, "w") as f:
        json.dump(processed_areas, f)

def load_progress(filename="progress.json"):
    """Load previously processed areas"""
    if Path(filename).exists():
        with open(filename, "r") as f:
            return set(json.load(f))
    return set()
```

---

### LOW IMPACT OPTIMIZATIONS

#### 7. **Optimize Intersection Checks**
- Use `area_box.intersects()` is already efficient
- Could pre-compute intersection for grid cells
- Minimal impact (~0.1ms per check)

#### 8. **Reduce Logging Verbosity**
- Console I/O adds small overhead
- Use logging levels (INFO/DEBUG)
- Batch status updates instead of per-area

---

## Recommended Implementation Priority

### Phase 1: Quick Wins (1-2 hours)
1. ✅ Add database result caching (check before API call)
2. ✅ Implement batch database commits
3. ✅ Cache boundary data to disk

**Expected Speedup**: 2-3x for reruns, 1.5x for fresh runs

---

### Phase 2: Async Rewrite (4-6 hours)
1. ✅ Convert to async/await with asyncio
2. ✅ Use httpx.AsyncClient
3. ✅ Implement semaphore-based rate limiting (10 concurrent)
4. ✅ Add progress persistence

**Expected Speedup**: 10x total (100s → 10s for full UK)

---

### Phase 3: Advanced Optimizations (2-4 hours)
1. ✅ Implement smart initial grid
2. ✅ Add intelligent retry logic
3. ✅ Optimize recursion with breadth-first approach

**Expected Speedup**: 15-20x total from baseline

---

## Estimated Performance After Optimizations

### Current Performance (Sequential)
- Full UK: **~100-150 seconds** (1.5-2.5 minutes)
- 500-1000 API calls
- Sequential processing

### After Phase 1 (Caching + Batching)
- Fresh run: **~70-100 seconds**
- Rerun same date: **~1 second** (cached)
- 25-30% improvement

### After Phase 2 (Async/Parallel)
- Fresh run: **~10-15 seconds** ⚡
- 10x parallel speedup
- 90% improvement

### After Phase 3 (Smart Grid + Optimizations)
- Fresh run: **~5-8 seconds** ⚡⚡
- Fewer API calls needed
- 95% improvement from baseline

---

## Trade-offs & Considerations

### Async Implementation Complexity
- **Pro**: 10x speedup
- **Con**: More complex code, harder to debug
- **Con**: Marimo reactive model may need adjustment

### API Rate Limiting Risk
- **Pro**: Faster processing
- **Con**: Could hit rate limits if not careful
- **Mitigation**: Proper semaphore limiting + exponential backoff

### Memory Usage
- **Pro**: Batch operations more efficient
- **Con**: Storing results buffer uses more memory
- **Impact**: Minimal (500 areas × 200 bytes = 100KB)

### Database Locking
- **Pro**: Batch commits faster
- **Con**: Less frequent commits = more data loss if crash
- **Mitigation**: Periodic commits (every 50 areas) + final commit

---

## Next Steps

1. **Quick win**: Implement Phase 1 optimizations (2-3x speedup, low risk)
2. **Measure**: Add timing instrumentation to confirm bottlenecks
3. **Test**: Run medium area (South East England) before full UK
4. **Async**: If satisfied with Phase 1, proceed to async rewrite

Would you like me to implement any of these optimizations?
