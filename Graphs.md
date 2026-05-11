Row 1

  Request Throughput (req/s)
  How many requests the load balancer is completing every second,
  averaged over the last 1 minute. This is your headline performance
  number. During a Locust test at 1000 users you want this as high
  and as flat as possible. A drop means workers are overwhelmed or
  failing.

  Latency Percentiles
  Three lines — all measured at the load balancer:
  - p50 — half of users got a response faster than this. Your
  "typical" user experience.
  - p95 — 95% of users were faster than this. This is what you report
   as your SLA.
  - p99 — the slowest 1% of requests. Spikes here mean some users are
   waiting a very long time, often caused by a slow worker or a long
  queue.

  ---
  Row 2

  Healthy Workers
  A single number — how many workers the master currently considers
  alive (passed their last heartbeat). With 4 laptops × 8 workers =
  32 total. If this drops during a chaos test, you can see exactly
  when a worker died and when it recovered.

  Request Queue Depth
  How many requests are sitting in the master's queue waiting to be
  assigned to a worker. Ideally close to 0. If this climbs during a
  test it means requests are arriving faster than workers can process
   them — your system is saturated.

  ---
  Row 3 — the 4 node panels

  Node 1/2/3/4 Workers — Inference p95
  Each panel shows one line per worker on that laptop. The Y-axis is
  seconds — how long that worker took to get a response from Ollama
  (the actual LLM inference time, not counting network). Use these
  to:
  - Spot if one laptop's workers are consistently slower (CPU vs GPU
  problem)
  - See if load is evenly distributed — all lines should be roughly
  the same height
  - Detect a dying worker — its line will spike then disappear

  ---
  Row 4

  Failed Requests
  Failures per second from the master's perspective — requests that
  were retried and still couldn't be completed. Should be 0 at steady
   state. Spikes here during chaos testing prove your fault tolerance
   is being exercised.

  ---
  The story they tell together during a load test:
  1. Throughput goes up → Queue Depth stays low → system is keeping
  up
  2. p95 latency stays flat → workers are not overwhelmed
  3. All 4 node panels show similar values → load is balanced evenly
  across machines
  4. Healthy Workers stays at 32 → no crashes
