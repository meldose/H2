#!/usr/bin/env python3
"""Bend the right elbow forward by +2 degrees, then return.

Use --degrees for a positive bend up to 10 degrees. Read-only unless
--execute is supplied; robot mode and feedback checks remain active.
"""
from h2_motion_common import main

if __name__ == "__main__":
    raise SystemExit(main("right_elbow"))
