# Geo profile

Only a regional Dagestan extract is allowed. Its URL and SHA-256 checksum are
provided outside Git. Flatnode is intentionally not configured.

Run `geo-import` only while worker, beat, `geo`, and `ops` are stopped. On the
4 GB VPS, `geo-import` and `ops` must never run together. After import, stop the
maintenance profile and start the `geo` query profile.

The full import and three-city address review are release-readiness work, not
evidence that G6 is complete.
