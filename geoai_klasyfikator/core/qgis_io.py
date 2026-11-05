# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Everything that touches QGIS and GDAL: reading rasters onto a working
grid, turning segments into a vector layer, and writing the finished
map out as a GeoTIFF with a style QGIS picks up by itself.
"""
from __future__ import annotations

import contextlib
import os

import numpy as np
from osgeo import gdal, ogr, osr
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsRasterLayer,
    QgsVectorLayer,
)

gdal.UseExceptions()

# Jeden piksel siatki roboczej kosztuje ok. 100 bajtów we wszystkich
# pośrednich tablicach razem (RGB float64, Lab, etykiety, cechy),
# więc 15 Mpx to już ok. 1,5 GB. Wyżej QGIS zwykle pada, zanim
# zdążymy zgłosić brak pamięci.
MAX_WORKING_PIXELS = 15_000_000
OSTRZEZENIE_PIKSELE = 6_000_000


class RasterGrid:
    """An image read onto one working grid, with its georeferencing."""

    def __init__(self, array, transform, crs_wkt, mask, pixel_size,
                 source_path=""):
        self.array = array              # (rows, cols, bands) float 0..1
        self.transform = transform      # GDAL geotransform
        self.crs_wkt = crs_wkt
        self.mask = mask                # True where there is data
        self.pixel_size = pixel_size    # ground size of one pixel
        self.source_path = source_path

    @property
    def shape(self):
        return self.array.shape[:2]

    def crs(self) -> QgsCoordinateReferenceSystem:
        return QgsCoordinateReferenceSystem.fromWkt(self.crs_wkt)

    def pixel_to_map(self, rows, cols):
        """Centre coordinates of the given pixels."""
        origin_x, size_x, _, origin_y, _, size_y = self.transform
        x = origin_x + (np.asarray(cols) + 0.5) * size_x
        y = origin_y + (np.asarray(rows) + 0.5) * size_y
        return x, y

    def map_to_pixel(self, x, y):
        """Pixel the given map coordinates fall in."""
        origin_x, size_x, _, origin_y, _, size_y = self.transform
        col = int(np.floor((x - origin_x) / size_x))
        row = int(np.floor((y - origin_y) / size_y))
        return row, col


def _layer_path(layer) -> str:
    """The file behind a raster layer, if there is one."""
    if isinstance(layer, str):
        return layer
    source = layer.source()
    return source.split("|")[0]


def native_pixel_size(path: str) -> float:
    dataset = gdal.Open(path)
    if dataset is None:
        raise ValueError(
            f"Nie udało się otworzyć pliku: {path}")
    transform = dataset.GetGeoTransform()
    rozmiar = float(abs(transform[1]))
    dataset = None          # zwalniamy uchwyt, inaczej Windows blokuje plik
    return rozmiar


def read_rgb(layer, target_pixel_size: float = 0.0,
             extent=None) -> RasterGrid:
    """Read the first three bands onto a working grid, scaled to 0..1.

    ``target_pixel_size`` resamples the image; 0 keeps the file's own
    resolution. ``extent`` is an optional (xmin, ymin, xmax, ymax) in
    the raster's own coordinates, which is how "process this extent
    only" works.
    """
    path = _layer_path(layer)
    dataset = gdal.Open(path)
    if dataset is None:
        raise ValueError(
            f"Nie udało się otworzyć pliku: {path}")
    if dataset.RasterCount < 3:
        raise ValueError(
            "Potrzebne jest zdjęcie trójkanałowe (RGB), a wskazany "
            f"raster ma {dataset.RasterCount} kanał(y). Wybierz "
            "ortomozaikę albo zdjęcie lotnicze w kolorze.")

    transform = dataset.GetGeoTransform()
    native = abs(transform[1])
    offset_x, offset_y = 0, 0
    width, height = dataset.RasterXSize, dataset.RasterYSize

    if extent is not None:
        xmin, ymin, xmax, ymax = extent
        offset_x = max(0, int((xmin - transform[0]) / transform[1]))
        offset_y = max(0, int((ymax - transform[3]) / transform[5]))
        end_x = min(width, int(np.ceil((xmax - transform[0]) / transform[1])))
        end_y = min(height, int(np.ceil((ymin - transform[3]) / transform[5])))
        width, height = max(1, end_x - offset_x), max(1, end_y - offset_y)

    scale = 1.0 if target_pixel_size <= 0 else native / target_pixel_size
    out_width = max(1, int(round(width * scale)))
    out_height = max(1, int(round(height * scale)))

    if out_width * out_height > MAX_WORKING_PIXELS:
        raise MemoryError(
            f"Siatka robocza {out_width} na {out_height} pikseli nie "
            f"zmieści się w pamięci komputera.")

    bands = []
    for index in range(1, 4):
        band = dataset.GetRasterBand(index)
        # przy zgrubianiu uśredniamy piksele; najbliższy sąsiad
        # wprowadzałby aliasing i sztucznie podbijał zmienność koloru
        # oraz kontrast faktury
        data = band.ReadAsArray(
            offset_x, offset_y, width, height, out_width, out_height,
            resample_alg=(gdal.GRIORA_Average if scale < 1.0
                          else gdal.GRIORA_NearestNeighbour)
        ).astype(np.float32)
        bands.append(data)
    array = np.stack(bands, axis=2)

    # scale to 0..1 by the band's data type, so that 8-bit and 16-bit
    # imagery behave the same
    data_type = dataset.GetRasterBand(1).DataType
    maximum = {gdal.GDT_Byte: 255.0, gdal.GDT_UInt16: 65535.0,
               gdal.GDT_Int16: 32767.0}.get(data_type, None)
    if maximum is None:
        finite = array[np.isfinite(array)]
        maximum = float(finite.max()) if finite.size else 1.0
        maximum = maximum if maximum > 1.5 else 1.0
    array = np.clip(array / maximum, 0.0, 1.0)

    mask = np.ones((out_height, out_width), dtype=bool)
    first = dataset.GetRasterBand(1)
    nodata = first.GetNoDataValue()
    if nodata is not None:
        mask &= ~np.all(np.isclose(array * maximum, nodata), axis=2)
    mask_band = first.GetMaskBand()
    if mask_band is not None:
        # not every file carries a usable mask band; when it cannot be
        # read we simply fall back to the nodata value and the
        # black-corner test below
        with contextlib.suppress(Exception):
            mask_data = mask_band.ReadAsArray(offset_x, offset_y, width,
                                              height, out_width, out_height)
            if mask_data is not None:
                mask &= mask_data > 0
    # rotated mosaics leave black corners that are not flagged
    mask &= ~np.all(array <= 0.0, axis=2)

    working_pixel = native / scale
    new_transform = (
        transform[0] + offset_x * transform[1],
        transform[1] / scale, 0.0,
        transform[3] + offset_y * transform[5],
        0.0, transform[5] / scale)

    projection = dataset.GetProjection()
    dataset = None
    return RasterGrid(array, new_transform, projection, mask,
                      float(abs(working_pixel)), path)


def read_dsm_like(layer, grid: RasterGrid,
                  ostrzezenia=None) -> np.ndarray:
    """Read a surface model onto the same grid as *grid*.

    The surface model may have its own pixel size and extent; it is
    placed by its coordinates, which is why the two files need not
    match.
    """
    if ostrzezenia is None:
        ostrzezenia = []
    path = _layer_path(layer)
    source = gdal.Open(path)
    if source is None:
        raise ValueError(
            f"Nie udało się otworzyć pliku: {path}")

    height, width = grid.shape
    origin_x, size_x, _, origin_y, _, size_y = grid.transform
    bounds = (origin_x, origin_y + height * size_y,
              origin_x + width * size_x, origin_y)

    zrodlowe_nodata = source.GetRasterBand(1).GetNoDataValue()
    BRAK = -3.0e38
    # gdal.Warp (w odróżnieniu od ReprojectImage) respektuje nodata
    # źródła, więc wartości wypełniacza nie wmieszają się w prawdziwe
    # wysokości przy interpolacji na brzegach dziur
    target = gdal.Warp(
        "", source, format="MEM", outputBounds=bounds,
        width=width, height=height, dstSRS=grid.crs_wkt,
        resampleAlg=gdal.GRA_Bilinear,
        srcNodata=zrodlowe_nodata, dstNodata=BRAK)
    if target is None:
        raise ValueError(
            "Nie udało się dopasować modelu wysokości do zdjęcia.")

    band = target.GetRasterBand(1)
    out = band.ReadAsArray().astype(np.float64)
    source = None
    target = None

    # poza nodata odrzucamy też wartości nierealne dla wysokości
    missing = (~np.isfinite(out)) | (out <= BRAK / 2.0) \
        | (np.abs(out) > 1.0e6)
    if missing.all():
        raise ValueError(
            "Model wysokości nie pokrywa się ze zdjęciem. Sprawdź, czy "
            "oba pliki obejmują ten sam teren i mają ten sam układ "
            "współrzędnych.")
    if missing.any():
        udzial = float(missing.mean())
        out[missing] = np.median(out[~missing])
        if udzial > 0.02:
            ostrzezenia.append(
                "Model wysokości nie pokrywa {0:.0f} procent zdjęcia; "
                "te miejsca wypełniono medianą, więc wysokość nad "
                "gruntem jest tam zmyślona.".format(udzial * 100))
    return out


# ── writing results ──────────────────────────────────────────────────

def write_classified_tif(path: str, classified: np.ndarray,
                         grid: RasterGrid, class_names, class_colours):
    """Write the map as a single-band GeoTIFF with its colours attached.

    Value 0 is no data and 1.. are the classes in list order, which is
    the same convention the reference implementation exports.
    """
    height, width = classified.shape
    driver = gdal.GetDriverByName("GTiff")
    dataset = driver.Create(path, width, height, 1, gdal.GDT_Byte,
                            options=["COMPRESS=LZW", "TILED=YES"])
    dataset.SetGeoTransform(grid.transform)
    dataset.SetProjection(grid.crs_wkt)

    band = dataset.GetRasterBand(1)
    band.WriteArray(np.clip(classified, 0, 255).astype(np.uint8))
    band.SetNoDataValue(0)

    table = gdal.ColorTable()
    table.SetColorEntry(0, (0, 0, 0, 0))
    for index, colour in enumerate(class_colours, start=1):
        table.SetColorEntry(index, (colour.red(), colour.green(),
                                    colour.blue(), 255))
    band.SetRasterColorTable(table)
    band.SetRasterColorInterpretation(gdal.GCI_PaletteIndex)
    # category names are a convenience; older GDAL builds refuse them
    with contextlib.suppress(Exception):
        band.SetCategoryNames([""] + list(class_names))

    dataset.FlushCache()
    dataset = None

    _write_qml(os.path.splitext(path)[0] + ".qml", class_names, class_colours)
    return path


def _write_qml(path: str, class_names, class_colours):
    """A QGIS style file so the exported map opens already coloured."""
    entries = "\n".join(
        f'        <paletteEntry value="{index}" alpha="255" '
        f'label="{_escape(name)}" '
        f'color="{colour.name()}"/>'
        for index, (name, colour)
        in enumerate(zip(class_names, class_colours), start=1))

    content = f"""<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.22" styleCategories="AllStyleCategories">
  <pipe>
    <rasterrenderer type="paletted" band="1" opacity="1" alphaBand="-1">
      <colorPalette>
{entries}
      </colorPalette>
    </rasterrenderer>
  </pipe>
  <blendMode>0</blendMode>
</qgis>
"""
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)


def _escape(text: str) -> str:
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ── segments as a vector layer ───────────────────────────────────────

def polygonize_segments(labels: np.ndarray, grid: RasterGrid,
                        layer_name: str = "Segments") -> QgsVectorLayer:
    """Turn the label image into polygons, one per object.

    The result is a memory layer with a ``segment_id`` field; the
    plugin then adds the measurements and the class columns to it, so
    the whole session is visible in the attribute table.
    """
    height, width = labels.shape
    driver = gdal.GetDriverByName("MEM")
    source = driver.Create("", width, height, 1, gdal.GDT_Int32)
    source.SetGeoTransform(grid.transform)
    source.SetProjection(grid.crs_wkt)
    band = source.GetRasterBand(1)
    band.WriteArray(labels.astype(np.int32))
    band.SetNoDataValue(0)

    memory_driver = ogr.GetDriverByName("Memory")
    vector = memory_driver.CreateDataSource("segments")
    spatial_reference = osr.SpatialReference()
    if grid.crs_wkt:
        spatial_reference.ImportFromWkt(grid.crs_wkt)
    ogr_layer = vector.CreateLayer("segments", spatial_reference,
                                   ogr.wkbPolygon)
    field = ogr.FieldDefn("segment_id", ogr.OFTInteger)
    ogr_layer.CreateField(field)

    gdal.Polygonize(band, band.GetMaskBand(), ogr_layer, 0, [])

    authid = ""
    crs = grid.crs()
    if crs.isValid():
        authid = crs.authid()
    uri = f"Polygon?crs={authid}" if authid else "Polygon"
    out = QgsVectorLayer(uri, layer_name, "memory")

    from qgis.core import QgsFeature, QgsGeometry
    from .compat import make_field

    provider = out.dataProvider()
    provider.addAttributes([make_field("segment_id", "int")])
    out.updateFields()

    features = []
    for ogr_feature in ogr_layer:
        geometry = ogr_feature.GetGeometryRef()
        if geometry is None:
            continue
        feature = QgsFeature(out.fields())
        feature.setGeometry(QgsGeometry.fromWkt(geometry.ExportToWkt()))
        feature.setAttribute("segment_id",
                             int(ogr_feature.GetField("segment_id")))
        features.append(feature)
    provider.addFeatures(features)
    out.updateExtents()

    source = None
    vector = None
    return out


def load_as_layer(path: str, name: str) -> QgsRasterLayer:
    """Open a written GeoTIFF as a QGIS layer."""
    layer = QgsRasterLayer(path, name)
    return layer if layer.isValid() else None
