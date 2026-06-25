# Release Summary: 0.3.2

## Portfolio Refresh Fixes

- Fixed a major normal `portfolio refresh` delta bug so changed source files
  are detected from saved `path + sha256` source state, and model output from a
  changed lane cannot duplicate unchanged objectives, use cases, signals, or
  products.
- Added a real fullscreen graph workspace control for generated portfolio HTML
  so crowded graph views can be explored with the canvas, inspector, filters,
  and legend expanded beyond the normal tab area.
