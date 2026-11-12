"""An application whose listener reads every request before routing.

Nothing here answers a request: the kernel scans the package for the one
listener the isolation tests watch, and the tests declare the routes.
"""
