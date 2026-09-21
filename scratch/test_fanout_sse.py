import time
from backend import stream_travel_agent

def test_fanout_sse():
    start = time.time()
    query = "5 days in Tokyo with flights and hotels, budget 150000 INR"
    print(f"Running query: {query}")
    event_count = 0
    for chunk in stream_travel_agent(query):
        event_count += 1
        lines = chunk.strip().split("\n")
        event_name = lines[0] if len(lines) > 0 else ""
        print(f"[{round(time.time() - start, 2)}s] {event_name}")
        if "event: interrupt" in chunk or "event: complete" in chunk:
            print("Received terminal event!")
            break
    
    elapsed = round(time.time() - start, 2)
    print(f"Total time taken: {elapsed} seconds! Total SSE chunks: {event_count}")

if __name__ == "__main__":
    test_fanout_sse()
