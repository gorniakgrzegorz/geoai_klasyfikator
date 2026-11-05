# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Two steps that run after the objects have been classified.

**Greenness refinement.** An object-based map is only as fine as its
objects: a strip of grass between two bare beds can be narrower than
any object and is absorbed into it. The objects still decide what kind
of land an area is, but for two classes you choose, each pixel then
decides which of the two it is from its greenness. Every other class
stays exactly as the objects decided.

**Minimum mapping unit.** A sieve absorbs connected patches of one
class smaller than a threshold into the class around them, which sets
a smallest mapped patch without blurring real boundaries.
"""
from __future__ import annotations

import numpy as np

from .deps import HAS_SCIPY

MODE_WHOLE = "whole"      # a green object turns over only as a whole
MODE_PIXEL = "pixel"      # every pixel decides for itself
DEFAULT_WINDOW = 3
WHOLE_SEGMENT_SHARE = 0.25


def excess_green(rgb: np.ndarray) -> np.ndarray:
    """ExG = 2g - r - b on colours scaled to sum to one.

    The same index as the ``exg_mean`` feature, so the cutoff taken
    from the training samples means the same thing here.
    """
    rgb = np.asarray(rgb, dtype=np.float64)
    total = rgb[..., 0] + rgb[..., 1] + rgb[..., 2]
    total = np.where(total <= 0, 1e-9, total)
    red = rgb[..., 0] / total
    green = rgb[..., 1] / total
    blue = rgb[..., 2] / total
    return 2.0 * green - red - blue


def smooth(array: np.ndarray, window: int = DEFAULT_WINDOW) -> np.ndarray:
    """Average over a small square, so single pixels do not flicker."""
    window = max(1, int(window))
    if window <= 1:
        return array
    if HAS_SCIPY:
        from scipy.ndimage import uniform_filter
        return uniform_filter(array, size=window, mode="nearest")

    radius = window // 2
    out = array.astype(np.float64)
    for axis in (0, 1):
        padded = np.pad(out, [(radius, radius) if a == axis else (0, 0)
                              for a in range(2)], mode="edge")
        total = np.zeros_like(out)
        for offset in range(2 * radius + 1):
            if axis == 0:
                total += padded[offset:offset + out.shape[0], :]
            else:
                total += padded[:, offset:offset + out.shape[1]]
        out = total / (2 * radius + 1)
    return out


def cutoff_from_samples(green_values: np.ndarray,
                        other_values: np.ndarray) -> float:
    """The ExG value that best separates the two classes' samples.

    Thresholds are tried across the combined range and the one with the
    best balance of the two classes correctly placed wins, so a class
    with far more samples cannot drag the cutoff to its own side.
    """
    green_values = np.asarray(green_values, dtype=np.float64)
    other_values = np.asarray(other_values, dtype=np.float64)
    if green_values.size == 0 or other_values.size == 0:
        return 0.0

    low = float(min(green_values.min(), other_values.min()))
    high = float(max(green_values.max(), other_values.max()))
    if high <= low:
        return low

    candidates = np.linspace(low, high, 256)
    green_rate = (green_values[None, :] > candidates[:, None]).mean(axis=1)
    other_rate = (other_values[None, :] <= candidates[:, None]).mean(axis=1)
    balance = (green_rate + other_rate) / 2.0
    return float(candidates[int(np.argmax(balance))])


def refine_by_greenness(classified: np.ndarray,
                        rgb: np.ndarray,
                        labels: np.ndarray,
                        green_class: int,
                        other_class: int,
                        cutoff: float,
                        window: int = DEFAULT_WINDOW,
                        mode: str = MODE_WHOLE) -> tuple:
    """Re-decide two classes pixel by pixel from greenness.

    Returns ``(refined_map, moved_to_green, moved_to_other)``.
    """
    classified = np.asarray(classified)
    greenness = smooth(excess_green(rgb), window)
    reads_green = greenness > cutoff

    out = classified.copy()
    is_green = classified == green_class
    is_other = classified == other_class

    # In both modes, pixels of the other class that read green become
    # the green class one by one. This is what brings out thin strips.
    to_green = is_other & reads_green
    out[to_green] = green_class

    if mode == MODE_PIXEL:
        to_other = is_green & ~reads_green
        out[to_other] = other_class
        return out, int(to_green.sum()), int(to_other.sum())

    # MODE_WHOLE: a green object turns over only as a whole, and only
    # when little of it reads green, so patchy or dying grass stays
    # solid instead of being punched full of holes.
    to_other = np.zeros(classified.shape, dtype=bool)
    green_labels = np.unique(labels[is_green])
    green_labels = green_labels[green_labels > 0]
    if green_labels.size:
        flat_labels = labels[is_green].astype(np.int64)
        maximum = int(labels.max())
        counts = np.bincount(flat_labels, minlength=maximum + 1)
        green_counts = np.bincount(flat_labels,
                                   weights=reads_green[is_green].astype(float),
                                   minlength=maximum + 1)
        share = np.divide(green_counts, np.maximum(counts, 1))
        turning = np.zeros(maximum + 1, dtype=bool)
        turning[green_labels] = share[green_labels] < WHOLE_SEGMENT_SHARE
        to_other = is_green & turning[labels]
        out[to_other] = other_class

    return out, int(to_green.sum()), int(to_other.sum())


# ── minimum mapping unit ─────────────────────────────────────────────

def sieve(classified: np.ndarray, min_pixels: int,
          nodata: int = 0) -> np.ndarray:
    """Absorb patches smaller than *min_pixels* into their surroundings."""
    if min_pixels <= 0:
        return classified

    try:
        return _sieve_gdal(classified, min_pixels, nodata)
    except Exception:
        return _sieve_builtin(classified, min_pixels, nodata)


def _sieve_gdal(classified: np.ndarray, min_pixels: int,
                nodata: int) -> np.ndarray:
    """GDAL's own sieve filter, the same one QGIS exposes."""
    from osgeo import gdal

    driver = gdal.GetDriverByName("MEM")
    height, width = classified.shape
    dataset = driver.Create("", width, height, 1, gdal.GDT_Int32)
    band = dataset.GetRasterBand(1)
    band.WriteArray(classified.astype(np.int32))
    band.SetNoDataValue(float(nodata))
    gdal.SieveFilter(band, None, band, int(min_pixels), 4)
    out = band.ReadAsArray()
    dataset = None
    return out.astype(classified.dtype)


def _sieve_builtin(classified: np.ndarray, min_pixels: int,
                   nodata: int) -> np.ndarray:
    """Connected patches below the threshold take their neighbour's class."""
    out = classified.copy()
    values = np.unique(classified)
    values = values[values != nodata]

    for value in values:
        mask = out == value
        if not mask.any():
            continue
        pieces, count = _connected_components(mask)
        if count == 0:
            continue
        sizes = np.bincount(pieces.ravel())
        small = np.nonzero(sizes[1:] < min_pixels)[0] + 1
        for piece in small:
            where = pieces == piece
            neighbour = _majority_neighbour(out, where, value, nodata)
            if neighbour is not None:
                out[where] = neighbour
    return out


def _connected_components(mask: np.ndarray) -> tuple:
    if HAS_SCIPY:
        from scipy.ndimage import label as scipy_label
        pieces, count = scipy_label(mask)
        return pieces, int(count)

    height, width = mask.shape
    pieces = np.zeros(mask.shape, dtype=np.int32)
    current = 0
    for start_row in range(height):
        for start_col in range(width):
            if not mask[start_row, start_col] or pieces[start_row, start_col]:
                continue
            current += 1
            stack = [(start_row, start_col)]
            pieces[start_row, start_col] = current
            while stack:
                row, col = stack.pop()
                for d_row, d_col in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n_row, n_col = row + d_row, col + d_col
                    if 0 <= n_row < height and 0 <= n_col < width \
                            and mask[n_row, n_col] \
                            and not pieces[n_row, n_col]:
                        pieces[n_row, n_col] = current
                        stack.append((n_row, n_col))
    return pieces, current


def _majority_neighbour(array: np.ndarray, where: np.ndarray,
                        own_value: int, nodata: int):
    """The class that most surrounds a patch."""
    grown = np.zeros(array.shape, dtype=bool)
    for shift, axis in ((1, 0), (-1, 0), (1, 1), (-1, 1)):
        grown |= np.roll(where, shift, axis=axis)
    ring = grown & ~where
    neighbours = array[ring]
    neighbours = neighbours[(neighbours != own_value)
                            & (neighbours != nodata)]
    if neighbours.size == 0:
        return None
    values, counts = np.unique(neighbours, return_counts=True)
    return values[int(np.argmax(counts))]


def pixels_to_area(pixels: int, pixel_size: float) -> float:
    """Convert a pixel count to square metres."""
    return float(pixels) * (pixel_size ** 2)


def area_to_pixels(area: float, pixel_size: float) -> int:
    """Convert square metres to a pixel count."""
    if pixel_size <= 0:
        return 0
    return int(round(area / (pixel_size ** 2)))
