#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
GeoAI Klasyfikator — uruchamianie z wiersza poleceń.

    python geoai.py sprawdz
    python geoai.py ucz --zdjecie proba.tif --probki przyklady.gpkg
    python geoai.py klasyfikuj --folder ./zdjecia --model model.geoai

© Grzegorz Górniak
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from geoai_cli.main import main    # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
