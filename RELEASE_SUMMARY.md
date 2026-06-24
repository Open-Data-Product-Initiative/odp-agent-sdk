# Release Summary: 0.3.2

## Portfolio Refresh Fixes

- Fixed a major normal `portfolio refresh` delta bug so changed source files
  are detected from saved `path + sha256` source state, and model output from a
  changed lane cannot duplicate unchanged objectives, use cases, signals, or
  products.
