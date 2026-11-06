# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
The object fingerprint: 19 measurements from RGB, 24 with a surface
model. These numbers, not the image, are what the classifier learns
from.

    Colour (7)      r/g/b mean and standard deviation, brightness
    Indices (3)     Excess Green, VARI, NGRDI on chromatic coordinates
    Texture (4)     GLCM contrast, homogeneity, energy, entropy
    Shape (4)       area, perimeter, circularity, convexity
    Context (1)     brightness against touching objects
    Height (5)      DSM mean and spread, slope, height against
                    neighbours, height above ground

Segments are drawn on the working grid, but colour and texture may be
read from a finer grid, which is how the reference implementation keeps
crown-sized objects while measuring texture on full detail.
"""
from __future__ import annotations

import numpy as np

from .deps import HAS_SCIPY

GREY_LEVELS = 15
DIRECTIONS = ((0, 1), (-1, 1), (-1, 0), (-1, -1))   # 0, 45, 90, 135 st.
MIN_TEXTURE_PIXELS = 16
GROUND_BLOCK_M = 1.0
GROUND_OPENING_M = 40.0

COLOUR_FEATURES = ["r_mean", "g_mean", "b_mean",
                   "r_std", "g_std", "b_std", "brightness_mean"]
INDEX_FEATURES = ["exg_mean", "vari_mean", "ngrdi_mean"]
TEXTURE_FEATURES = ["contrast", "homogeneity", "energy", "entropy"]
SHAPE_FEATURES = ["area", "perimeter", "circularity", "convexity"]
CONTEXT_FEATURES = ["brightness_rel_neighbors"]
DSM_FEATURES = ["dsm_mean", "dsm_std", "slope_mean",
                "dsm_rel_neighbors", "hag_mean"]

BASE_FEATURES = (COLOUR_FEATURES + INDEX_FEATURES + TEXTURE_FEATURES
                 + SHAPE_FEATURES + CONTEXT_FEATURES)
ALL_FEATURES = BASE_FEATURES + DSM_FEATURES


def feature_names(with_dsm: bool) -> list:
    return list(ALL_FEATURES) if with_dsm else list(BASE_FEATURES)


# ── helpers ──────────────────────────────────────────────────────────

def _segment_ids(labels: np.ndarray) -> np.ndarray:
    ids = np.unique(labels)
    return ids[ids > 0]


def _grouped_mean(values: np.ndarray, flat_labels: np.ndarray,
                  counts: np.ndarray) -> np.ndarray:
    total = np.bincount(flat_labels, weights=values,
                        minlength=len(counts) + 1)[1:]
    return total / np.maximum(counts, 1)


def luminance(rgb: np.ndarray) -> np.ndarray:
    """Rec. 601 luminance, the grey the texture measures work on."""
    return (0.299 * rgb[..., 0] + 0.587 * rgb[..., 1]
            + 0.114 * rgb[..., 2])


# ── colour, indices ──────────────────────────────────────────────────

def colour_features(rgb: np.ndarray, labels: np.ndarray,
                    n_segments: int) -> dict:
    """Means, spreads, brightness and the three vegetation indices."""
    inside = labels > 0
    flat_labels = labels[inside].astype(np.int64)
    counts = np.bincount(flat_labels, minlength=n_segments + 1)[1:]
    safe = np.maximum(counts, 1)

    out = {}
    bands = {}
    for index, name in enumerate("rgb"):
        values = rgb[..., index][inside].astype(np.float64)
        bands[name] = values
        mean = np.bincount(flat_labels, weights=values,
                           minlength=n_segments + 1)[1:] / safe
        mean_square = np.bincount(flat_labels, weights=values ** 2,
                                  minlength=n_segments + 1)[1:] / safe
        out[f"{name}_mean"] = mean
        out[f"{name}_std"] = np.sqrt(np.maximum(mean_square - mean ** 2, 0.0))

    brightness = (bands["r"] + bands["g"] + bands["b"]) / 3.0
    out["brightness_mean"] = np.bincount(
        flat_labels, weights=brightness, minlength=n_segments + 1)[1:] / safe

    # chromatic coordinates: each band over the sum, so that a shaded
    # leaf and a sunlit leaf score alike
    total = bands["r"] + bands["g"] + bands["b"]
    total = np.where(total <= 0, 1e-9, total)
    red, green, blue = (bands["r"] / total, bands["g"] / total,
                        bands["b"] / total)

    exg = 2.0 * green - red - blue
    vari_denominator = green + red - blue
    vari = np.where(np.abs(vari_denominator) < 1e-9, 0.0,
                    (green - red) / np.where(np.abs(vari_denominator) < 1e-9,
                                             1.0, vari_denominator))
    ngrdi_denominator = green + red
    ngrdi = np.where(ngrdi_denominator < 1e-9, 0.0,
                     (green - red) / np.where(ngrdi_denominator < 1e-9,
                                              1.0, ngrdi_denominator))

    for name, values in (("exg_mean", exg), ("vari_mean", vari),
                         ("ngrdi_mean", ngrdi)):
        out[name] = np.bincount(flat_labels, weights=values,
                                minlength=n_segments + 1)[1:] / safe
    return out


# ── texture ──────────────────────────────────────────────────────────

def _glcm_for_patch(levels: np.ndarray) -> tuple:
    """Co-occurrence measures for one object.

    *levels* holds 1..GREY_LEVELS inside the object and 0 outside;
    pairs touching a 0 are dropped and the matrix is renormalised, so
    only pairs inside the object count. Pairs are one pixel apart at
    0, 45, 90 and 135 degrees, counted symmetrically.
    """
    size = GREY_LEVELS + 1
    contrast = []
    homogeneity = []
    energy = []
    entropy_values = []

    offsets = DIRECTIONS
    rows, cols = levels.shape
    index_i, index_j = np.mgrid[1:size, 1:size]
    difference = (index_i - index_j).astype(np.float64)

    for d_row, d_col in offsets:
        r0_a, r1_a = max(0, -d_row), rows - max(0, d_row)
        c0_a, c1_a = max(0, -d_col), cols - max(0, d_col)
        if r1_a <= r0_a or c1_a <= c0_a:
            continue
        first = levels[r0_a:r1_a, c0_a:c1_a]
        second = levels[r0_a + d_row:r1_a + d_row,
                        c0_a + d_col:c1_a + d_col]

        valid = (first > 0) & (second > 0)
        if not valid.any():
            continue
        a = first[valid].astype(np.int64)
        b = second[valid].astype(np.int64)

        matrix = np.bincount(a * size + b, minlength=size * size)
        matrix = matrix.reshape(size, size).astype(np.float64)
        matrix = matrix + matrix.T          # symmetric
        matrix = matrix[1:, 1:]             # drop the outside level
        total = matrix.sum()
        if total <= 0:
            continue
        matrix /= total                     # renormalise

        contrast.append(float(np.sum(matrix * difference ** 2)))
        homogeneity.append(
            float(np.sum(matrix / (1.0 + difference ** 2))))
        energy.append(float(np.sum(matrix ** 2)))
        non_zero = matrix[matrix > 0]
        entropy_values.append(float(-np.sum(non_zero * np.log2(non_zero))))

    if not contrast:
        return 0.0, 1.0, 1.0, 0.0
    # entropia idzie w skali sumy po czterech kierunkach (tak jak w
    # implementacji wzorcowej), ale liczona jako średnia razy cztery,
    # żeby wąski obiekt, dla którego część kierunków nie ma par, nie
    # dostawał sztucznie niższej wartości z powodu samego kształtu
    return (float(np.mean(contrast)), float(np.mean(homogeneity)),
            float(np.mean(energy)),
            float(np.mean(entropy_values)) * len(DIRECTIONS))


def texture_features(rgb: np.ndarray, labels: np.ndarray,
                     n_segments: int, progress=None) -> dict:
    """GLCM texture for every object, on the grid the image is given on."""
    grey = luminance(rgb.astype(np.float64))
    finite = grey[np.isfinite(grey)]
    low, high = (float(finite.min()), float(finite.max())) \
        if finite.size else (0.0, 1.0)
    if high <= low:
        high = low + 1.0

    # one global quantisation, so that contrast is comparable between
    # objects; level 0 stays free to mark pixels outside the object
    scaled = (grey - low) / (high - low)
    quantised = np.clip(
        (scaled * (GREY_LEVELS - 1)).round().astype(np.int16) + 1,
        1, GREY_LEVELS)

    contrast = np.zeros(n_segments, dtype=np.float64)
    homogeneity = np.ones(n_segments, dtype=np.float64)
    energy = np.ones(n_segments, dtype=np.float64)
    entropy = np.zeros(n_segments, dtype=np.float64)

    slices = _bounding_boxes(labels, n_segments)
    for position, (segment_id, box) in enumerate(slices.items()):
        row_slice, col_slice = box
        window = labels[row_slice, col_slice]
        patch = np.where(window == segment_id,
                         quantised[row_slice, col_slice], 0).astype(np.int16)
        if int((patch > 0).sum()) < MIN_TEXTURE_PIXELS:
            continue        # too small to say anything: neutral values
        values = _glcm_for_patch(patch)
        index = segment_id - 1
        contrast[index], homogeneity[index] = values[0], values[1]
        energy[index], entropy[index] = values[2], values[3]
        if progress is not None and position % 500 == 0:
            progress(position, len(slices))

    return {"contrast": contrast, "homogeneity": homogeneity,
            "energy": energy, "entropy": entropy}


def _bounding_boxes(labels: np.ndarray, n_segments: int) -> dict:
    """The smallest window holding each segment."""
    if HAS_SCIPY:
        from scipy.ndimage import find_objects
        found = find_objects(labels.astype(np.int32))
        return {index + 1: box for index, box in enumerate(found)
                if box is not None}

    boxes = {}
    rows, cols = np.nonzero(labels > 0)
    ids = labels[rows, cols]
    order = np.argsort(ids, kind="stable")
    ids, rows, cols = ids[order], rows[order], cols[order]
    starts = np.searchsorted(ids, np.arange(1, n_segments + 1), "left")
    ends = np.searchsorted(ids, np.arange(1, n_segments + 1), "right")
    for segment_id, (start, end) in enumerate(zip(starts, ends), start=1):
        if end <= start:
            continue
        boxes[segment_id] = (slice(rows[start:end].min(),
                                   rows[start:end].max() + 1),
                             slice(cols[start:end].min(),
                                   cols[start:end].max() + 1))
    return boxes


# ── shape ────────────────────────────────────────────────────────────

def _convex_hull_area(rows: np.ndarray, cols: np.ndarray) -> float:
    """Area of the convex hull of a set of pixel centres."""
    # the hull is taken over the pixel corners, not their centres:
    # the hull of centres loses half a pixel all round, which would
    # make a plain square look more convex than it can be
    centres = np.stack([cols, rows], axis=1).astype(np.float64)
    offsets = np.array([[-0.5, -0.5], [0.5, -0.5],
                        [-0.5, 0.5], [0.5, 0.5]])
    points = (centres[:, None, :] + offsets[None, :, :]).reshape(-1, 2)
    if len(points) < 3:
        return float(len(centres))

    if HAS_SCIPY:
        from scipy.spatial import ConvexHull, QhullError
        try:
            return float(ConvexHull(points).volume)
        except (QhullError, ValueError):
            return float(len(centres))

    # monotone chain, then the shoelace formula
    order = np.lexsort((points[:, 1], points[:, 0]))
    ordered = points[order]

    def half(sequence):
        stack = []
        for point in sequence:
            while len(stack) >= 2:
                (x1, y1), (x2, y2) = stack[-2], stack[-1]
                cross = ((x2 - x1) * (point[1] - y1)
                         - (y2 - y1) * (point[0] - x1))
                if cross <= 0:
                    stack.pop()
                else:
                    break
            stack.append(tuple(point))
        return stack

    hull = half(ordered)[:-1] + half(ordered[::-1])[:-1]
    if len(hull) < 3:
        return float(len(centres))
    hull_array = np.array(hull)
    x, y = hull_array[:, 0], hull_array[:, 1]
    return float(0.5 * abs(np.dot(x, np.roll(y, -1))
                           - np.dot(y, np.roll(x, -1))))


def _crofton_perimeter(mask: np.ndarray) -> float:
    """Perimeter of a binary shape, estimated the unbiased way.

    Counting pixel edges turns a circle into a staircase and
    overestimates its outline by about 27%. The Crofton estimate counts
    how often four families of parallel lines enter the shape and
    weights them by their spacing, which gives the right answer for a
    disc as well as for a rectangle.
    """
    padded = np.pad(mask, 1, constant_values=False)
    horizontal = np.count_nonzero(padded[:, :-1] != padded[:, 1:])
    vertical = np.count_nonzero(padded[:-1, :] != padded[1:, :])
    diagonal_a = np.count_nonzero(padded[:-1, :-1] != padded[1:, 1:])
    diagonal_b = np.count_nonzero(padded[:-1, 1:] != padded[1:, :-1])

    straight = (horizontal + vertical) / 2.0
    diagonal = (diagonal_a + diagonal_b) / 2.0
    return float(np.pi / 4.0 * (straight + diagonal / np.sqrt(2.0)))


def shape_features(labels: np.ndarray, n_segments: int,
                   pixel_size: float) -> dict:
    """Area and perimeter on the ground, plus two dimensionless shapes."""
    area_pixels = np.bincount(labels.ravel(),
                              minlength=n_segments + 1)[1:].astype(np.float64)
    perimeter_pixels = np.zeros(n_segments, dtype=np.float64)
    convexity = np.ones(n_segments, dtype=np.float64)

    boxes = _bounding_boxes(labels, n_segments)
    for segment_id, (row_slice, col_slice) in boxes.items():
        window = labels[row_slice, col_slice] == segment_id
        index = segment_id - 1
        perimeter_pixels[index] = _crofton_perimeter(window)

        rows, cols = np.nonzero(window)
        count = float(window.sum())
        hull_area = _convex_hull_area(rows, cols)
        convexity[index] = (min(1.0, count / hull_area)
                            if hull_area > 0 else 1.0)

    area = area_pixels * (pixel_size ** 2)
    perimeter = perimeter_pixels * pixel_size

    circularity = np.where(
        perimeter > 0, 4.0 * np.pi * area / np.maximum(perimeter ** 2, 1e-12),
        0.0)
    circularity = np.clip(circularity, 0.0, 1.5)

    return {"area": area, "perimeter": perimeter,
            "circularity": circularity, "convexity": convexity}


# ── context ──────────────────────────────────────────────────────────

def adjacency_pairs(labels: np.ndarray) -> np.ndarray:
    """Unique pairs of segments that share a border."""
    pairs = []
    for axis in (0, 1):
        if axis == 0:
            first, second = labels[:-1, :], labels[1:, :]
        else:
            first, second = labels[:, :-1], labels[:, 1:]
        differs = (first != second) & (first > 0) & (second > 0)
        if differs.any():
            pairs.append(np.stack([first[differs], second[differs]], axis=1))
    if not pairs:
        return np.empty((0, 2), dtype=np.int64)
    stacked = np.concatenate(pairs).astype(np.int64)
    stacked.sort(axis=1)
    return np.unique(stacked, axis=0)


def relative_to_neighbours(values: np.ndarray,
                           pairs: np.ndarray,
                           n_segments: int) -> np.ndarray:
    """Each object's value minus the mean of the objects it touches."""
    if len(pairs) == 0:
        return np.zeros(n_segments, dtype=np.float64)

    both = np.concatenate([pairs, pairs[:, ::-1]])
    totals = np.bincount(both[:, 0], weights=values[both[:, 1] - 1],
                         minlength=n_segments + 1)[1:]
    counts = np.bincount(both[:, 0], minlength=n_segments + 1)[1:]
    neighbour_mean = np.where(counts > 0, totals / np.maximum(counts, 1),
                              values)
    return values - neighbour_mean


# ── height ───────────────────────────────────────────────────────────

def _minimum_filter(array: np.ndarray, size: int) -> np.ndarray:
    if HAS_SCIPY:
        from scipy.ndimage import minimum_filter
        return minimum_filter(array, size=size, mode="nearest")
    return _sliding_extreme(array, size, np.minimum)


def _maximum_filter(array: np.ndarray, size: int) -> np.ndarray:
    if HAS_SCIPY:
        from scipy.ndimage import maximum_filter
        return maximum_filter(array, size=size, mode="nearest")
    return _sliding_extreme(array, size, np.maximum)


def _sliding_extreme(array: np.ndarray, size: int, operation) -> np.ndarray:
    """Separable moving minimum or maximum, edges held at the border."""
    radius = max(1, size // 2)
    out = array
    for axis in (0, 1):
        padded = np.pad(out, [(radius, radius) if a == axis else (0, 0)
                              for a in range(2)], mode="edge")
        accumulated = None
        for offset in range(2 * radius + 1):
            if axis == 0:
                window = padded[offset:offset + out.shape[0], :]
            else:
                window = padded[:, offset:offset + out.shape[1]]
            accumulated = window if accumulated is None \
                else operation(accumulated, window)
        out = accumulated
    return out


def ground_surface(dsm: np.ndarray, pixel_size: float) -> np.ndarray:
    """Estimate the ground from the surface model alone.

    The lowest value in each metre-wide block, then a morphological
    opening over 40 m (a moving minimum followed by a moving maximum)
    that removes anything narrower than 40 m, such as crowns and
    buildings. Under closed canopy wider than that the estimate rides
    up on the canopy, which is the usual limit of this approach.
    """
    block = max(1, int(round(GROUND_BLOCK_M / max(pixel_size, 1e-6))))
    opening = max(3, int(round(GROUND_OPENING_M / max(pixel_size, 1e-6))))

    # On a small extent the 40 m window can be wider than the image
    # itself, which would flatten the estimate onto the scene mean and
    # swallow real height. Keep it inside the picture.
    limit = max(3, min(dsm.shape) // 2)
    opening = min(opening, limit)
    block = min(block, max(1, opening // 2))

    lowest = _minimum_filter(dsm, block) if block > 1 else dsm
    eroded = _minimum_filter(lowest, opening)
    opened = _maximum_filter(eroded, opening)

    smoothing = max(3, min(opening // 4, 25))
    if HAS_SCIPY:
        from scipy.ndimage import uniform_filter
        return uniform_filter(opened, size=smoothing, mode="nearest")
    return _box_mean(opened, smoothing)


def _box_mean(array: np.ndarray, size: int) -> np.ndarray:
    """Separable moving average, used when SciPy is not available."""
    radius = max(1, size // 2)
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


def slope_degrees(dsm: np.ndarray, pixel_size: float) -> np.ndarray:
    """Slope of the surface model, in degrees."""
    gradient_rows, gradient_cols = np.gradient(dsm, max(pixel_size, 1e-6))
    return np.degrees(np.arctan(
        np.sqrt(gradient_rows ** 2 + gradient_cols ** 2)))


def dsm_features(dsm: np.ndarray, labels: np.ndarray, n_segments: int,
                 pixel_size: float, pairs: np.ndarray) -> dict:
    """The five height measurements."""
    inside = labels > 0
    flat_labels = labels[inside].astype(np.int64)
    counts = np.bincount(flat_labels, minlength=n_segments + 1)[1:]
    safe = np.maximum(counts, 1)

    heights = dsm[inside].astype(np.float64)
    mean = np.bincount(flat_labels, weights=heights,
                       minlength=n_segments + 1)[1:] / safe
    mean_square = np.bincount(flat_labels, weights=heights ** 2,
                              minlength=n_segments + 1)[1:] / safe
    spread = np.sqrt(np.maximum(mean_square - mean ** 2, 0.0))

    slope = slope_degrees(dsm, pixel_size)[inside]
    slope_mean = np.bincount(flat_labels, weights=slope,
                             minlength=n_segments + 1)[1:] / safe

    above = (dsm - ground_surface(dsm, pixel_size))[inside]
    hag = np.bincount(flat_labels, weights=above,
                      minlength=n_segments + 1)[1:] / safe

    return {"dsm_mean": mean, "dsm_std": spread, "slope_mean": slope_mean,
            "dsm_rel_neighbors": relative_to_neighbours(mean, pairs,
                                                        n_segments),
            "hag_mean": hag}


# ── everything together ──────────────────────────────────────────────

def compute_features(rgb: np.ndarray,
                     labels: np.ndarray,
                     pixel_size: float,
                     dsm: np.ndarray | None = None,
                     fine_rgb: np.ndarray | None = None,
                     progress=None) -> tuple:
    """Measure every object.

    ``rgb`` is the working-grid image in 0..1, ``labels`` the segment
    ids (1..N, 0 outside). ``fine_rgb`` is an optional finer version of
    the same scene; when given, colour and texture are read from it
    while shape, context and height stay on the working grid.

    Returns ``(ids, matrix, names)`` where *matrix* has one row per
    object in the order of *ids*.
    """
    ids = _segment_ids(labels)
    if ids.size == 0:
        raise ValueError(
            "Segmentation produced no objects. Check that the image is "
            "not empty and that the working resolution is not too "
            "coarse.")
    n_segments = int(ids.max())

    def step(message, fraction):
        if progress is not None:
            progress(message, fraction)

    step("Measuring colour...", 0.05)
    if fine_rgb is not None and fine_rgb.shape[:2] != labels.shape:
        fine_labels = _upsample_labels(labels, fine_rgb.shape[:2])
        colour = colour_features(fine_rgb, fine_labels, n_segments)
        step("Measuring texture on the fine grid...", 0.25)
        texture = texture_features(fine_rgb, fine_labels, n_segments)
    else:
        colour = colour_features(rgb, labels, n_segments)
        step("Measuring texture...", 0.25)
        texture = texture_features(rgb, labels, n_segments)

    step("Measuring shape...", 0.60)
    shape = shape_features(labels, n_segments, pixel_size)

    step("Comparing each object with its neighbours...", 0.75)
    pairs = adjacency_pairs(labels)
    context = {"brightness_rel_neighbors": relative_to_neighbours(
        colour["brightness_mean"], pairs, n_segments)}

    blocks = [colour, texture, shape, context]
    names = list(BASE_FEATURES)

    if dsm is not None:
        step("Measuring height...", 0.85)
        blocks.append(dsm_features(dsm, labels, n_segments, pixel_size,
                                   pairs))
        names = list(ALL_FEATURES)

    merged = {}
    for block in blocks:
        merged.update(block)

    keep = ids - 1
    matrix = np.column_stack([merged[name][keep] for name in names])
    matrix = np.nan_to_num(matrix, nan=0.0, posinf=0.0, neginf=0.0)
    step("Features ready.", 1.0)
    return ids, matrix, names


def _upsample_labels(labels: np.ndarray, shape: tuple) -> np.ndarray:
    """Nearest-neighbour upsampling of the label image to a finer grid."""
    rows = (np.arange(shape[0]) * labels.shape[0] / shape[0]).astype(int)
    cols = (np.arange(shape[1]) * labels.shape[1] / shape[1]).astype(int)
    rows = np.clip(rows, 0, labels.shape[0] - 1)
    cols = np.clip(cols, 0, labels.shape[1] - 1)
    return labels[rows[:, None], cols[None, :]]
