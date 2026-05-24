# Airport Operations Performance Data Product

The airport operations team maintains the Airport Operations Performance Data
Product for internal operational analytics. The product identifier used by the
data platform team is `airport-operations-performance`, and the current working
version is 1.0.0.

The product combines operational events from the airport operational database,
the flight information display system, gate management records, baggage belt
events, and aircraft stand allocation logs. The data is refreshed every hour and
is considered production ready for internal use by the airport operations
control center, airline station managers, and terminal planning analysts.

Core fields include flight number, scheduled departure time, actual departure
time, scheduled arrival time, actual arrival time, terminal, gate, aircraft
stand, baggage belt, delay reason code, turnaround start time, turnaround end
time, passenger load band, and handling agent.

The owner is the Airport Data Platform Team. Operational questions should be
sent to Airport Operations Control, while data quality questions should be sent
to the platform steward for airport events.

Access is restricted to airport and airline partner teams with an operational
need. Data is not intended for public release because it can reveal sensitive
operational patterns.

