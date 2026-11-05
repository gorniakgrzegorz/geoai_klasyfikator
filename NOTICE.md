# GeoAI Klasyfikator — nota prawna

Copyright (C) 2026 Grzegorz Górniak <gorniakgrzegorz@gmail.com>

This program is free software: you can redistribute it and/or modify it
under the terms of the GNU General Public License as published by the
Free Software Foundation, either version 3 of the License, or (at your
option) any later version. See `LICENSE` for the full text.

This program is distributed in the hope that it will be useful, but
WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.

## Methods

The algorithms are published science and are implemented here from the
papers:

- Achanta, R., et al. (2012). SLIC superpixels compared to
  state-of-the-art superpixel methods. *IEEE TPAMI*, 34(11), 2274-2282.
- Haralick, R. M., Shanmugam, K., & Dinstein, I. (1973). Textural
  features for image classification. *IEEE Trans. SMC*, 3(6), 610-621.
- Woebbecke, D. M., et al. (1995). Color indices for weed
  identification. *Trans. ASAE*, 38(1), 259-269.
- Breiman, L. (2001). Random forests. *Machine Learning*, 45(1), 5-32.
- Belgiu, M., & Drăguţ, L. (2016). Random forest in remote sensing.
  *ISPRS J. Photogramm. Remote Sens.*, 114, 24-31.
- Blaschke, T. (2010). Object based image analysis for remote sensing.
  *ISPRS J. Photogramm. Remote Sens.*, 65(1), 2-16.
- Olofsson, P., et al. (2014). Good practices for estimating area and
  assessing accuracy of land change. *Remote Sens. Environ.*, 148,
  42-57.
- Stehman, S. V. (2014). Estimating area and map accuracy for
  stratified random sampling when the strata are different from the map
  classes. *Int. J. Remote Sens.*, 35(13), 4923-4939.
- Congalton, R. G., & Green, K. (2019). *Assessing the accuracy of
  remotely sensed data* (3rd ed.). CRC Press.

## Optional dependencies

scikit-image and scikit-learn are not bundled and not required. When
they are present in the QGIS Python environment the plugin calls them
for SLIC and the Random Forest; otherwise it uses the implementations
in `core/slic.py` and `core/classifier.py`. Both libraries are under
BSD-3-Clause licences and are installed separately by the user.
