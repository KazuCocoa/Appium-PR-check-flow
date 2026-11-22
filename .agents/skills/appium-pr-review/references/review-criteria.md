# Appium PR review criteria

Use selectively; do not claim an area is verified unless relevant code was inspected.

- W3C WebDriver protocol behavior and error shapes.
- Appium server routing, remote/loopback bindings, Host validation and CORS.
- SSRF, DNS rebinding, WebSocket upgrade routing, direct connect boundaries.
- CLI defaults, config schema, backwards compatibility and upgrade paths.
- Version compatibility between core, drivers, plugins and clients.
- Concurrency, teardown, retry behavior and resource cleanup.
- Tests: which changed scenarios are covered, what is untested, whether a
  test was only mentioned by the author or independently executed.
- PR review scope: version/head SHA, changed-file completeness and patch truncation.

A reviewer should report a concrete defect with a file/line anchor only when
the implementation supports that claim. Otherwise describe it as a follow-up
question or an evidence gap, not as a confirmed finding.
