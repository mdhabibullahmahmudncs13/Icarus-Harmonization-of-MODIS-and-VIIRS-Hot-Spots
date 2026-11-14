"""Fire-news search: a Hyperbrowser-backed agent that finds sourced reports.

:mod:`src.news.agent` owns query building, strict date/region filtering, the
per-``(date, region)`` cache and the satellite cross-check;
:mod:`src.news.hyperbrowser` is the thin HTTP client for the two Hyperbrowser
web APIs the agent uses (search and fetch). Neither module is imported by the
scientific pipeline, and nothing here writes detections.
"""
