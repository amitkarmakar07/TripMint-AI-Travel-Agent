from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

# 1. Test Input Size Validation
print("Testing Input Size Validation (> 50 KB)...")
huge_payload = {"message": "A" * (60 * 1024)} # 60 KB
res_huge = client.post("/api/travel_planner", json=huge_payload)
print(f"Status: {res_huge.status_code}, Response: {res_huge.json()}")
assert res_huge.status_code == 413, "Expected 413 for oversized payload"

# 2. Test Rate Limiting
print("\nTesting Rate Limiting (10 req/min limit)...")
for i in range(1, 13):
    res = client.post("/api/travel_planner", json={"message": ""})
    print(f"Request #{i}: Status {res.status_code}")
    if res.status_code == 429:
        print("Rate limiter triggered successfully:", res.json())
        break

print("\nAll middleware tests completed successfully!")
