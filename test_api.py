#!/usr/bin/env python3
"""
Simple test script to verify UK Police API connectivity
"""
import httpx
from time import sleep

API_BASE_URL = "https://data.police.uk/api/crimes-street/all-crime"

# Small London area test
test_polygon = "51.7,-0.5:51.7,0.3:51.3,0.3:51.3,-0.5"

# Try multiple dates (API may have limited recent data)
test_dates = ["2023-12", "2023-11", "2023-10", "2023-06", "2023-01"]

print("Testing UK Police API connectivity...")
print(f"URL: {API_BASE_URL}")
print(f"Polygon: {test_polygon}")
print("=" * 60)

for test_date in test_dates:
    print(f"\nTrying date: {test_date}")
    print("-" * 60)

    try:
        params = {
            "date": test_date,
            "poly": test_polygon
        }

        response = httpx.get(API_BASE_URL, params=params, timeout=30.0)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            crime_count = len(data)
            print(f"✓ SUCCESS! Found {crime_count} crimes")

            if crime_count > 0:
                print(f"\nSample crime data:")
                sample = data[0]
                print(f"  Category: {sample.get('category')}")
                print(f"  Location: {sample.get('location', {}).get('street', {}).get('name')}")
                print(f"  Month: {sample.get('month')}")
                print(f"\n✓ API is working! Use date: {test_date}")
                break
        elif response.status_code == 503:
            print(f"✗ Service unavailable (503) - API might be down temporarily")
        elif response.status_code == 404:
            print(f"✗ Data not found (404) - date may not have data available")
        else:
            print(f"✗ ERROR: {response.status_code}")
            print(f"Response: {response.text[:200]}")

    except Exception as e:
        print(f"✗ EXCEPTION: {e}")

    sleep(1)  # Rate limit between attempts

print("\n" + "=" * 60)
print("API test complete!")
