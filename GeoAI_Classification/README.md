# GeoAI Classification

A QGIS plugin that makes a **land cover map** from a drone image or an
aerial photo and tells you straight away how good that map is.

It does not classify single pixels. It cuts the image into **objects**
(pieces of a field, a roof, a tree crown), measures each of them and
learns from your examples what is what.

This is the English edition of
[GeoAI Klasyfikator](https://plugins.qgis.org/plugins/geoai_klasyfikator/).
Both editions are built from the same code and give the same results;
only the user interface language differs.

**Author:** Grzegorz Górniak (gorniakgrzegorz@gmail.com)
**Licence:** GPL-3.0-or-later
**Requires:** QGIS 3.22 or newer and nothing else
**Guide:** <https://gorniakgrzegorz.github.io/geoai_klasyfikator/en/>

---

## Why objects and not pixels

A single pixel tells you only its colour. An object also has texture,
shape, height and surroundings, and the map does not come out littered
with single specks.

## Four steps

| Step | What happens |
|---|---|
| 1 · Image and objects | load the raster and an optional DSM, SLIC segmentation, 19 or 24 features measured |
| 2 · Classes and examples | add classes and click examples of each on the map |
| 3 · Training and map | class separability check, Random Forest, refinements, GeoTIFF export |
| 4 · Accuracy assessment | point sampling, blind labelling, error matrix and areas with confidence intervals |

## What the plugin measures

| Group | Features |
|---|---|
| Colour (7) | mean and variability of R, G, B, and brightness |
| Vegetation indices (3) | ExG greenness, VARI, NGRDI, computed on chromatic coordinates, so a leaf in shade and in sun look alike |
| GLCM texture (4) | contrast, homogeneity, energy, entropy |
| Shape (4) | area, perimeter, circularity, convexity |
| Context (1) | brightness relative to neighbours |
| Height from DSM (5) | mean, variability, slope, height relative to neighbours, height above ground |

Ordinary drone cameras do not record near infrared, so **there is no
NDVI here**. It is replaced by visible-band indices, texture, shape and
height.

## Installation

1. In QGIS: Plugins, Manage and Install Plugins
2. Search for "GeoAI Classification" and click **Install Plugin**
3. A **GeoAI Classification** button appears on the toolbar

Plugin page: <https://plugins.qgis.org/plugins/GeoAI_Classification/>.
Without internet access: the **Install from ZIP** tab and the file
`GeoAI_Classification.zip`.

### Faster on large images (optional)

The plugin works with nothing else installed. If you add two libraries,
segmentation and training run much faster:

```
python -m pip install scikit-image scikit-learn
```

Type the command in **OSGeo4W Shell** (Start menu, QGIS folder), then
restart QGIS. If it fails, run the shell as administrator.

## Three tips that decide the result

1. **Match the object size to the narrowest thing** you want to show on
   the map, not to what covers most of the image.
2. **Spread the examples over the whole image** and show every variant
   of a class: both lush grass and dry grass.
3. **Correcting the map is the method, not a failure.** The first map is
   never good. Review it, write down the kinds of errors, add a few
   examples of each kind and repeat. Two or three rounds bring the most.

## Accuracy assessment

Here the plugin does something QGIS lacks. It draws check points (never
on objects used for training), you label them by looking at the image
alone, and you get:

- the error matrix,
- user's and producer's accuracy for each class,
- **area-weighted** overall accuracy,
- **estimated class areas with 95 per cent confidence intervals**.

With stratified sampling the share of points is not the share of area,
so a publication should cite the area-weighted figures and the
estimated areas, not the areas read directly from the map (Olofsson et
al., 2014; Stehman, 2014). The kappa coefficient is deliberately not
computed.

## What stays in the project

- **GeoAI objects**: a polygon layer; its attribute table holds all
  measured features, the column `train_class` (your examples) and
  `map_class` (the result).
- **GeoAI check points**: points with the label from the image
  (`ref_class`), the class from the map and the sampling stratum.
- A saved **GeoTIFF** with a `.qml` style file next to it.

## Source

This folder is generated from the Polish plugin by
`narzedzia/wersja_angielska.py` in the
[repository](https://github.com/gorniakgrzegorz/geoai_klasyfikator).
Report problems in the
[issue tracker](https://github.com/gorniakgrzegorz/geoai_klasyfikator/issues).

## How to cite

Górniak, G. GeoAI Klasyfikator: object-based land cover classification
of drone and satellite imagery. Zenodo.
<https://doi.org/10.5281/zenodo.24005560>
