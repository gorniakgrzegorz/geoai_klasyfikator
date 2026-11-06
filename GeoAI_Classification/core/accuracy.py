# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Accuracy assessment following current good practice for thematic maps
(Congalton and Green; Olofsson et al. 2014; Stehman 2014).

A map is only as useful as your knowledge of how wrong it is. Points
are placed by a design that gives every part of the map a known chance
of being checked, each point is labelled on the raw image with the
classification hidden, and the result is read from an error matrix.

Under a stratified design small classes are sampled far more densely
than large ones, so a share of points is not a share of the map. Every
figure is therefore also reported weighted by each stratum's mapped
area, together with estimated class areas and 95% confidence intervals.

Kappa is left out on purpose; current guidance favours overall, user's
and producer's accuracy.
"""
from __future__ import annotations

import numpy as np

CONFIDENCE_Z = 1.96          # 95% confidence interval
DESIGN_SIMPLE = "simple"
DESIGN_STRATIFIED = "stratified"


# ── drawing the sample ───────────────────────────────────────────────

def simple_random_points(valid: np.ndarray, count: int,
                         seed: int = 42,
                         exclude: np.ndarray | None = None) -> np.ndarray:
    """Points placed anywhere on the map, independent of what it says.

    Returns an array of (row, col). ``exclude`` marks pixels that must
    not be drawn, which is how training objects are kept out.
    """
    usable = np.asarray(valid, dtype=bool)
    if exclude is not None:
        usable = usable & ~np.asarray(exclude, dtype=bool)
    positions = np.flatnonzero(usable)
    if positions.size == 0:
        return np.empty((0, 2), dtype=np.int64)

    rng = np.random.default_rng(seed)
    count = min(int(count), positions.size)
    picked = rng.choice(positions, size=count, replace=False)
    rows, cols = np.unravel_index(picked, usable.shape)
    return np.stack([rows, cols], axis=1)


def stratified_points(classified: np.ndarray,
                      class_values,
                      min_per_class: int = 50,
                      total: int = 200,
                      seed: int = 42,
                      exclude: np.ndarray | None = None,
                      nodata: int = 0) -> tuple:
    """A minimum number of points in every map class, the rest by area.

    Returns ``(points, strata)`` where *strata* records the map class
    each point was drawn from. The strata are the map classes at the
    time of drawing and stay with the sample afterwards, because the
    area weights depend on them (Stehman 2014).
    """
    classified = np.asarray(classified)
    blocked = np.zeros(classified.shape, dtype=bool) if exclude is None \
        else np.asarray(exclude, dtype=bool)

    counts = {}
    for value in class_values:
        counts[value] = int(np.count_nonzero(
            (classified == value) & ~blocked))
    mapped_total = sum(counts.values())
    if mapped_total == 0:
        return np.empty((0, 2), dtype=np.int64), np.empty(0, dtype=np.int64)

    rng = np.random.default_rng(seed)
    points, strata = [], []

    for value in class_values:
        available = counts[value]
        if available == 0:
            continue
        share = int(round(total * available / mapped_total))
        wanted = min(max(min_per_class, share), available)
        positions = np.flatnonzero((classified == value) & ~blocked)
        picked = rng.choice(positions, size=wanted, replace=False)
        rows, cols = np.unravel_index(picked, classified.shape)
        points.append(np.stack([rows, cols], axis=1))
        strata.append(np.full(wanted, value, dtype=np.int64))

    if not points:
        return np.empty((0, 2), dtype=np.int64), np.empty(0, dtype=np.int64)
    return np.concatenate(points), np.concatenate(strata)


# ── the error matrix ─────────────────────────────────────────────────

def error_matrix(map_classes, reference_classes, class_values) -> np.ndarray:
    """Rows are what the map says, columns what the reference says."""
    index = {value: position for position, value in enumerate(class_values)}
    size = len(class_values)
    matrix = np.zeros((size, size), dtype=np.int64)
    for predicted, observed in zip(map_classes, reference_classes):
        if predicted in index and observed in index:
            matrix[index[predicted], index[observed]] += 1
    return matrix


def counts_accuracy(matrix: np.ndarray) -> dict:
    """Accuracy straight from the point counts, with no area weighting."""
    matrix = np.asarray(matrix, dtype=np.float64)
    total = matrix.sum()
    diagonal = np.diag(matrix)
    row_totals = matrix.sum(axis=1)
    column_totals = matrix.sum(axis=0)

    with np.errstate(divide="ignore", invalid="ignore"):
        users = np.where(row_totals > 0, diagonal / row_totals, np.nan)
        producers = np.where(column_totals > 0,
                             diagonal / column_totals, np.nan)
    return {
        "overall": float(diagonal.sum() / total) if total else float("nan"),
        "users": users,
        "producers": producers,
        "n": int(total),
    }


# ── area-weighted estimates (Olofsson et al. 2014) ───────────────────

def olofsson_estimates(matrix: np.ndarray,
                       stratum_pixels,
                       pixel_area: float) -> dict:
    """Accuracy and area estimates weighted by each stratum's area.

    ``matrix`` is the error matrix with map class as rows, ``stratum_pixels``
    the mapped pixel count of each stratum in the same order, and
    ``pixel_area`` the ground area of one pixel in square metres.

    Returns area-weighted overall, user's and producer's accuracy, the
    estimated area of each class and 95% confidence intervals.
    """
    matrix = np.asarray(matrix, dtype=np.float64)
    areas = np.asarray(stratum_pixels, dtype=np.float64)
    size = len(areas)
    total_pixels = areas.sum()
    if total_pixels <= 0:
        raise ValueError(
            "The mapped area is zero, so there is nothing to estimate.")

    sample_sizes = matrix.sum(axis=1)                 # n_i
    weights = areas / total_pixels                    # W_i
    usable = sample_sizes > 0

    # p_ij: the share of the whole map in map class i and reference j
    proportions = np.zeros_like(matrix)
    proportions[usable] = (weights[usable, None]
                           * matrix[usable] / sample_sizes[usable, None])

    overall = float(np.trace(proportions))

    # user's accuracy is the share of each row that is right
    with np.errstate(divide="ignore", invalid="ignore"):
        users = np.where(usable, np.diag(matrix) / np.maximum(sample_sizes, 1),
                         np.nan)

    # estimated area share of each reference class
    estimated_share = proportions.sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        producers = np.where(estimated_share > 0,
                             np.diag(proportions) / estimated_share, np.nan)

    # ── variances ────────────────────────────────────────────────────
    # overall accuracy: variance of a stratified estimator of a mean
    overall_variance = 0.0
    for i in range(size):
        if sample_sizes[i] > 1 and np.isfinite(users[i]):
            overall_variance += (weights[i] ** 2 * users[i] * (1 - users[i])
                                 / (sample_sizes[i] - 1))

    users_ci = np.full(size, np.nan)
    for i in range(size):
        if sample_sizes[i] > 1 and np.isfinite(users[i]):
            users_ci[i] = CONFIDENCE_Z * np.sqrt(
                users[i] * (1 - users[i]) / (sample_sizes[i] - 1))

    # estimated area of each class and its interval
    share_variance = np.zeros(size)
    for j in range(size):
        total_variance = 0.0
        for i in range(size):
            if sample_sizes[i] > 1:
                rate = matrix[i, j] / sample_sizes[i]
                total_variance += (weights[i] ** 2 * rate * (1 - rate)
                                   / (sample_sizes[i] - 1))
        share_variance[j] = total_variance

    pixel_total_area = total_pixels * pixel_area
    estimated_area = estimated_share * pixel_total_area
    area_ci = CONFIDENCE_Z * np.sqrt(share_variance) * pixel_total_area
    mapped_area = areas * pixel_area

    # producer's accuracy, Olofsson et al. 2014 equation 7
    producers_ci = np.full(size, np.nan)
    estimated_pixels = estimated_share * total_pixels
    for j in range(size):
        if not np.isfinite(producers[j]) or estimated_pixels[j] <= 0:
            continue
        first = 0.0
        if sample_sizes[j] > 1 and np.isfinite(users[j]):
            first = (areas[j] ** 2 * (1 - producers[j]) ** 2
                     * users[j] * (1 - users[j]) / (sample_sizes[j] - 1))
        second = 0.0
        for i in range(size):
            if i == j or sample_sizes[i] <= 1:
                continue
            rate = matrix[i, j] / sample_sizes[i]
            second += (areas[i] ** 2 * rate * (1 - rate)
                       / (sample_sizes[i] - 1))
        variance = (first + producers[j] ** 2 * second) \
            / (estimated_pixels[j] ** 2)
        producers_ci[j] = CONFIDENCE_Z * np.sqrt(max(variance, 0.0))

    return {
        "overall": overall,
        "overall_ci": float(CONFIDENCE_Z * np.sqrt(max(overall_variance, 0.0))),
        "users": users,
        "users_ci": users_ci,
        "producers": producers,
        "producers_ci": producers_ci,
        "estimated_area": estimated_area,
        "estimated_area_ci": area_ci,
        "mapped_area": mapped_area,
        "proportions": proportions,
        "weights": weights,
        "sample_sizes": sample_sizes.astype(int),
    }


def simple_random_estimates(matrix: np.ndarray,
                            total_pixels: float,
                            pixel_area: float) -> dict:
    """Dokładności i powierzchnie dla próby prostej losowej.

    Przy losowaniu prostym każdy punkt waży tyle samo, więc udział
    powierzchni klasy to po prostu udział punktów. Wariancje liczymy
    jak dla proporcji z próby losowej, dzięki czemu także ten projekt
    daje przedziały ufności i szacowane powierzchnie.
    """
    matrix = np.asarray(matrix, dtype=np.float64)
    size = len(matrix)
    n = matrix.sum()
    if n <= 0:
        raise ValueError("The sample is empty.")

    proportions = matrix / n
    overall = float(np.trace(proportions))
    overall_ci = float(CONFIDENCE_Z * np.sqrt(
        max(overall * (1.0 - overall) / n, 0.0)))

    row_totals = matrix.sum(axis=1)
    column_totals = matrix.sum(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        users = np.where(row_totals > 0, np.diag(matrix) / row_totals,
                         np.nan)
        producers = np.where(column_totals > 0,
                             np.diag(matrix) / column_totals, np.nan)

    def przedzial(wartosc, liczba):
        if not np.isfinite(wartosc) or liczba < 2:
            return np.nan
        return CONFIDENCE_Z * np.sqrt(
            max(wartosc * (1.0 - wartosc) / (liczba - 1), 0.0))

    users_ci = np.array([przedzial(users[i], row_totals[i])
                         for i in range(size)])
    producers_ci = np.array([przedzial(producers[i], column_totals[i])
                             for i in range(size)])

    share = proportions.sum(axis=0)
    share_ci = CONFIDENCE_Z * np.sqrt(
        np.maximum(share * (1.0 - share) / n, 0.0))
    powierzchnia = total_pixels * pixel_area

    return {
        "overall": overall,
        "overall_ci": overall_ci,
        "users": users,
        "users_ci": users_ci,
        "producers": producers,
        "producers_ci": producers_ci,
        "estimated_area": share * powierzchnia,
        "estimated_area_ci": share_ci * powierzchnia,
        "mapped_area": (row_totals / n) * powierzchnia,
        "proportions": proportions,
        "weights": np.full(size, 1.0 / max(size, 1)),
        "sample_sizes": row_totals.astype(int),
    }


def assess(map_classes, reference_classes, class_values, class_names,
           stratum_pixels=None, pixel_area: float = 1.0,
           design: str = DESIGN_STRATIFIED) -> dict:
    """Everything the accuracy report needs, in one call."""
    matrix = error_matrix(map_classes, reference_classes, class_values)
    report = {
        "design": design,
        "class_values": list(class_values),
        "class_names": [class_names.get(value, str(value))
                        for value in class_values],
        "matrix": matrix,
        "counts": counts_accuracy(matrix),
        "weighted": None,
    }
    if stratum_pixels is not None and design == DESIGN_STRATIFIED:
        report["weighted"] = olofsson_estimates(matrix, stratum_pixels,
                                                pixel_area)
    elif design == DESIGN_SIMPLE and stratum_pixels is not None:
        report["weighted"] = simple_random_estimates(
            matrix, float(np.sum(stratum_pixels)), pixel_area)
    return report


def report_rows(report: dict) -> list:
    """The matrix with margins, ready to write to CSV."""
    names = report["class_names"]
    matrix = report["matrix"]
    counts = report["counts"]
    weighted = report.get("weighted")

    rows = [["map \\ reference"] + names + ["total", "user's accuracy"]]
    for index, name in enumerate(names):
        row = [name] + [int(value) for value in matrix[index]]
        row.append(int(matrix[index].sum()))
        value = (weighted["users"][index] if weighted is not None
                 else counts["users"][index])
        row.append("" if not np.isfinite(value) else round(float(value), 4))
        rows.append(row)

    rows.append(["total"] + [int(value) for value in matrix.sum(axis=0)]
                + [int(matrix.sum()), ""])

    producers = (weighted["producers"] if weighted is not None
                 else counts["producers"])
    rows.append(["producer's accuracy"]
                + ["" if not np.isfinite(value) else round(float(value), 4)
                   for value in producers] + ["", ""])
    return rows
