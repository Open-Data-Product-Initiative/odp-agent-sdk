# Flight Connection Reliability Data Product

The airline partnership team maintains the Flight Connection Reliability Data
Product for monitoring transfer passenger risk across terminals. The product
identifier used by the data platform team is `flight-connection-reliability`,
and the current working version is 1.0.0.

The product combines inbound flight status, outbound flight status, minimum
connection time rules, terminal transfer times, passenger connection counts,
gate distance bands, boarding status, and missed connection outcomes. Data is
refreshed every 10 minutes for active operational flights.

Core fields include inbound flight number, outbound flight number, inbound
terminal, outbound terminal, scheduled inbound arrival, estimated inbound
arrival, outbound boarding close time, minimum connection minutes, estimated
transfer minutes, connected passenger count, connection risk level, and missed
connection count.

The owner is the Airline Partnership Data Team. Operational questions should be
sent to Airport Operations Control and airline station managers. Data quality
questions should be sent to the connection reliability steward.

Access is restricted to airport operations and airline partner teams. Data is
not for public release because it contains commercially sensitive connection
performance indicators.

