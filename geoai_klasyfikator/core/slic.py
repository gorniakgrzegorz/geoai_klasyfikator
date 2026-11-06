# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
SLIC segmentation (Achanta et al. 2012).

k-means on five numbers per pixel: the three CIELAB colour channels and
the pixel's x and y position, with the distance

    D = sqrt( d_colour^2 + (d_space / S)^2 * m^2 )

where S is the seed spacing and m the compactness. CIELAB is used
because equal distances in it look like equal colour differences.

When scikit-image is installed the plugin calls its SLIC instead, with
the same parameters, so that results match the reference implementation.
The code below is the fallback and follows the same algorithm.
"""
from __future__ import annotations

import numpy as np

from .deps import HAS_SCIPY, HAS_SKIMAGE

DEFAULT_COMPACTNESS = 0.15
DEFAULT_SIGMA = 2.5
MAX_ITERATIONS = 10


# ── colour ───────────────────────────────────────────────────────────

def rgb_to_lab(rgb: np.ndarray) -> np.ndarray:
    """Convert an sRGB image in 0..1 to CIELAB (D65, 2 degree observer)."""
    rgb = np.asarray(rgb, dtype=np.float64)

    # sRGB companding
    linear = np.where(rgb <= 0.04045,
                      rgb / 12.92,
                      ((rgb + 0.055) / 1.055) ** 2.4)

    # linear RGB to XYZ
    matrix = np.array([
        [0.412453, 0.357580, 0.180423],
        [0.212671, 0.715160, 0.072169],
        [0.019334, 0.119193, 0.950227],
    ])
    xyz = linear @ matrix.T

    # white point D65
    white = np.array([0.950456, 1.0, 1.088754])
    xyz = xyz / white

    epsilon = 216.0 / 24389.0
    kappa = 24389.0 / 27.0
    f = np.where(xyz > epsilon,
                 np.cbrt(np.maximum(xyz, 1e-12)),
                 (kappa * xyz + 16.0) / 116.0)

    lab = np.empty_like(xyz)
    lab[..., 0] = 116.0 * f[..., 1] - 16.0
    lab[..., 1] = 500.0 * (f[..., 0] - f[..., 1])
    lab[..., 2] = 200.0 * (f[..., 1] - f[..., 2])
    return lab


# ── smoothing ────────────────────────────────────────────────────────

def _gaussian_kernel(sigma: float) -> np.ndarray:
    radius = max(1, int(round(3.0 * sigma)))
    x = np.arange(-radius, radius + 1, dtype=np.float64)
    kernel = np.exp(-(x ** 2) / (2.0 * sigma ** 2))
    return kernel / kernel.sum()


def gaussian_blur(image: np.ndarray, sigma: float) -> np.ndarray:
    """Separable Gaussian blur, applied to each band."""
    if sigma <= 0:
        return np.asarray(image, dtype=np.float64)

    if HAS_SCIPY:
        from scipy.ndimage import gaussian_filter
        out = np.asarray(image, dtype=np.float64).copy()
        for band in range(out.shape[2]):
            out[..., band] = gaussian_filter(out[..., band], sigma,
                                             mode="nearest")
        return out

    kernel = _gaussian_kernel(sigma)
    radius = len(kernel) // 2
    out = np.asarray(image, dtype=np.float64)

    for axis in (0, 1):
        padded = np.pad(
            out,
            [(radius, radius) if a == axis else (0, 0)
             for a in range(out.ndim)],
            mode="edge")
        accumulated = np.zeros_like(out)
        for offset, weight in enumerate(kernel):
            if axis == 0:
                accumulated += weight * padded[offset:offset + out.shape[0]]
            else:
                accumulated += weight * padded[:, offset:offset + out.shape[1]]
        out = accumulated
    return out


# ── the segmentation itself ──────────────────────────────────────────

def _seed_grid(height: int, width: int, n_segments: int):
    """Regular seed positions and their spacing S."""
    spacing = max(2.0, np.sqrt(height * width / float(n_segments)))
    rows = np.arange(spacing / 2.0, height, spacing)
    cols = np.arange(spacing / 2.0, width, spacing)
    grid_r, grid_c = np.meshgrid(rows, cols, indexing="ij")
    seeds = np.stack([grid_r.ravel(), grid_c.ravel()], axis=1)
    return seeds, spacing


def _enforce_connectivity(labels: np.ndarray, min_size: int) -> np.ndarray:
    """Make every label one connected piece; absorb slivers.

    A breadth-first flood fill walks each connected run of one label.
    Runs smaller than *min_size* take the label of the neighbour they
    were reached from, which is how the reference implementation keeps
    segments whole.
    """
    height, width = labels.shape
    out = np.full(labels.shape, -1, dtype=np.int64)
    neighbours = ((-1, 0), (1, 0), (0, -1), (0, 1))
    next_label = 0
    adjacent_label = 0

    queue = np.empty(height * width, dtype=np.int64)

    for start_row in range(height):
        for start_col in range(width):
            if out[start_row, start_col] >= 0 or labels[start_row, start_col] < 0:
                continue

            source = labels[start_row, start_col]
            out[start_row, start_col] = next_label
            queue[0] = start_row * width + start_col
            count = 1
            head = 0

            # a label to fall back on if this piece turns out to be tiny
            found_adjacent = False

            while head < count:
                flat = queue[head]
                head += 1
                row, col = divmod(int(flat), width)
                for d_row, d_col in neighbours:
                    n_row, n_col = row + d_row, col + d_col
                    if not (0 <= n_row < height and 0 <= n_col < width):
                        continue
                    if labels[n_row, n_col] != source:
                        if not found_adjacent and out[n_row, n_col] >= 0:
                            adjacent_label = out[n_row, n_col]
                            found_adjacent = True
                        continue
                    if out[n_row, n_col] >= 0:
                        continue
                    out[n_row, n_col] = next_label
                    queue[count] = n_row * width + n_col
                    count += 1

            if count < min_size and found_adjacent:
                out[np.where(out == next_label)] = adjacent_label
            else:
                next_label += 1

    return out


def slic_segments(rgb: np.ndarray,
                  n_segments: int,
                  compactness: float = DEFAULT_COMPACTNESS,
                  sigma: float = DEFAULT_SIGMA,
                  mask: np.ndarray | None = None,
                  prefer_skimage: bool = True,
                  progress=None) -> np.ndarray:
    """Split *rgb* into roughly *n_segments* objects.

    ``rgb`` is a float array in 0..1 of shape (rows, cols, 3).
    ``mask`` marks the pixels to segment (True = inside).
    ``progress`` is an optional callable(fraction 0..1), called by the
    built-in implementation so the interface can stay responsive.
    Returns an int32 label image, 1..N, with 0 for pixels left out.
    """
    rgb = np.asarray(rgb, dtype=np.float64)
    if rgb.ndim != 3 or rgb.shape[2] < 3:
        raise ValueError(
            "Podział na obiekty wymaga zdjęcia trójkanałowego (RGB).")
    rgb = rgb[..., :3]
    height, width = rgb.shape[:2]

    if mask is not None:
        mask = np.asarray(mask, dtype=bool)
        if mask.shape != (height, width):
            raise ValueError(
                "Maska musi mieć taki sam rozmiar jak zdjęcie.")

    if prefer_skimage and HAS_SKIMAGE:
        from skimage.segmentation import slic as skimage_slic
        kwargs = dict(n_segments=int(n_segments),
                      compactness=float(compactness),
                      sigma=float(sigma),
                      start_label=1,
                      enforce_connectivity=True,
                      convert2lab=True,
                      channel_axis=-1)
        if mask is not None:
            kwargs["mask"] = mask
        labels = skimage_slic(rgb, **kwargs).astype(np.int32)
        if mask is not None:
            labels[~mask] = 0
        return labels

    return _slic_builtin(rgb, n_segments, compactness, sigma, mask,
                         progress)


def _fill_unassigned(labels: np.ndarray,
                     mask: np.ndarray | None) -> np.ndarray:
    """Give any pixel the clustering missed the label of a neighbour.

    A few pixels can end up outside every search window when centres
    drift. Growing the existing labels into them keeps the segmentation
    gap-free, which everything downstream assumes.
    """
    inside = np.ones(labels.shape, dtype=bool) if mask is None else mask
    missing = inside & (labels < 0)
    guard = 0
    while missing.any() and guard < 64:
        guard += 1
        filled = labels.copy()
        for shift, axis in ((1, 0), (-1, 0), (1, 1), (-1, 1)):
            donor = np.roll(labels, shift, axis=axis)
            if axis == 0:
                if shift == 1:
                    donor[0, :] = -1
                else:
                    donor[-1, :] = -1
            else:
                if shift == 1:
                    donor[:, 0] = -1
                else:
                    donor[:, -1] = -1
            take = missing & (filled < 0) & (donor >= 0)
            filled[take] = donor[take]
        if np.array_equal(filled, labels):
            break
        labels = filled
        missing = inside & (labels < 0)
    return labels


def _slic_builtin(rgb, n_segments, compactness, sigma, mask,
                  progress=None):
    height, width = rgb.shape[:2]
    smoothed = gaussian_blur(rgb, sigma)
    lab = rgb_to_lab(np.clip(smoothed, 0.0, 1.0))

    seeds, spacing = _seed_grid(height, width, n_segments)
    rows = np.clip(np.round(seeds[:, 0]).astype(int), 0, height - 1)
    cols = np.clip(np.round(seeds[:, 1]).astype(int), 0, width - 1)

    if mask is not None:
        keep = mask[rows, cols]
        if not keep.any():
            raise ValueError(
                "Żaden punkt startowy nie trafił w obszar z danymi.")
        rows, cols = rows[keep], cols[keep]
        seeds = seeds[keep]      # punkty startowe muszą zostać zgodne

    centres_colour = lab[rows, cols].astype(np.float64)
    centres_rc = np.stack([rows, cols], axis=1).astype(np.float64)
    n_centres = len(rows)

    grid_r = np.arange(height, dtype=np.float64)[:, None]
    grid_c = np.arange(width, dtype=np.float64)[None, :]

    labels = np.full((height, width), -1, dtype=np.int64)
    distances = np.full((height, width), np.inf, dtype=np.float64)
    window = int(np.ceil(spacing))
    factor = (compactness ** 2) / (spacing ** 2)

    # meldunek co ok. 2 proc. jednej iteracji: pasek postępu się rusza,
    # a QGIS nie wygląda na zawieszony
    co_ile = max(1, n_centres // 50)
    for iteration in range(MAX_ITERATIONS):
        distances[:] = np.inf
        labels[:] = -1

        for index in range(n_centres):
            if progress is not None and index % co_ile == 0:
                progress((iteration + index / n_centres) / MAX_ITERATIONS)
            centre_r, centre_c = centres_rc[index]
            r0 = max(0, int(centre_r) - window)
            r1 = min(height, int(centre_r) + window + 1)
            c0 = max(0, int(centre_c) - window)
            c1 = min(width, int(centre_c) + window + 1)
            if r0 >= r1 or c0 >= c1:
                continue

            patch = lab[r0:r1, c0:c1]
            colour_distance = np.sum(
                (patch - centres_colour[index]) ** 2, axis=2)
            space_distance = ((grid_r[r0:r1] - centre_r) ** 2
                              + (grid_c[:, c0:c1] - centre_c) ** 2)
            total = colour_distance + space_distance * factor

            current = distances[r0:r1, c0:c1]
            better = total < current
            if mask is not None:
                better &= mask[r0:r1, c0:c1]
            current[better] = total[better]
            labels[r0:r1, c0:c1][better] = index

        # move each centre to the mean of its pixels
        valid = labels >= 0
        flat_labels = labels[valid]
        counts = np.bincount(flat_labels, minlength=n_centres)
        safe = np.maximum(counts, 1)
        for channel in range(3):
            centres_colour[:, channel] = np.bincount(
                flat_labels, weights=lab[..., channel][valid],
                minlength=n_centres) / safe
        rr, cc = np.nonzero(valid)
        centres_rc[:, 0] = np.bincount(flat_labels, weights=rr,
                                       minlength=n_centres) / safe
        centres_rc[:, 1] = np.bincount(flat_labels, weights=cc,
                                       minlength=n_centres) / safe
        empty = counts == 0
        if empty.any():
            centres_rc[empty] = seeds[empty]

    labels = _fill_unassigned(labels, mask)
    if mask is not None:
        labels[~mask] = -1

    # scikit-image absorbs pieces below half the nominal segment size
    nominal = (height * width) / float(max(n_segments, 1))
    min_size = max(1, int(0.5 * nominal))
    connected = _enforce_connectivity(labels, min_size)

    out = np.zeros((height, width), dtype=np.int32)
    inside = connected >= 0
    if inside.any():
        unique, renumbered = np.unique(connected[inside], return_inverse=True)
        out[inside] = (renumbered + 1).astype(np.int32)
    return out
