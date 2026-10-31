"""sentinel-llm boundary.

This package is the *only* place Claude credentials belong.
It must never import Schwab tokens, place orders, or hold BrokerClient
instances with live credentials. Communication with sentinel-core is via
the local queue documented in ``queue.py`` + JSON schemas under ``schemas/``.
"""
