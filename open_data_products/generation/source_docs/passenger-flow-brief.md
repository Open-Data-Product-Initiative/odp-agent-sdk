# Passenger Flow and Queue Data Product

The terminal planning team maintains the Passenger Flow and Queue Data Product
for internal airport operations analytics. The product identifier used by the
data platform team is `passenger-flow-queue`, and the current working version is
1.0.0.

The product combines passenger counting sensors, security checkpoint queue
measurements, boarding pass scan events, transfer desk timestamps, and terminal
zone occupancy records. Data is refreshed every 15 minutes during operating
hours and every hour overnight.

Core fields include terminal, zone, checkpoint, queue length band, estimated wait
minutes, passenger count, boarding pass scan count, transfer desk wait minutes,
occupancy threshold status, observation timestamp, and sensor confidence score.

The owner is the Terminal Planning Analytics Team. Operational questions should
be sent to the terminal duty manager, while data quality questions should be
sent to the passenger flow data steward.

Access is restricted to airport operations, security operations, and airline
partner teams with a terminal performance role. The product is not public
because it can reveal operational capacity and passenger movement patterns.

