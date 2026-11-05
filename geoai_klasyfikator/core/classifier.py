# -*- coding: utf-8 -*-
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Learning the classes from your examples, and checking beforehand
whether the class list can be supported at all.

A Random Forest of 100 trees, each grown on a random resample of the
training objects with a random subset of features at each split, votes
on every object in the scene. The vote shares also say which objects
the model is least sure about, which is what drives the suggestion of
what to label next.

When scikit-learn is installed the plugin uses its RandomForestClassifier
with the reference settings (100 trees, seed 42, library defaults
otherwise). The forest in this module is the fallback.
"""
from __future__ import annotations

import numpy as np

from .deps import HAS_SKLEARN

N_TREES = 100
RANDOM_SEED = 42

JM_GOOD = 1.9
JM_FAIR = 1.7


# ── a small Random Forest, for when scikit-learn is absent ───────────

class _Tree:
    """One classification tree, grown on Gini impurity."""

    __slots__ = ("feature", "threshold", "left", "right", "votes")

    def __init__(self):
        self.feature = -1
        self.threshold = 0.0
        self.left = None
        self.right = None
        self.votes = None


def _gini_best_split(column: np.ndarray, classes: np.ndarray,
                     n_classes: int):
    """Best threshold on one feature, and the impurity it leaves."""
    order = np.argsort(column, kind="stable")
    values = column[order]
    labels = classes[order]
    total = len(labels)
    if total < 2:
        return None

    one_hot = np.zeros((total, n_classes), dtype=np.float64)
    one_hot[np.arange(total), labels] = 1.0
    left_counts = np.cumsum(one_hot, axis=0)[:-1]
    right_counts = left_counts[-1] + one_hot[-1] - left_counts

    left_total = left_counts.sum(axis=1)
    right_total = right_counts.sum(axis=1)
    valid = (values[:-1] < values[1:]) & (left_total > 0) & (right_total > 0)
    if not valid.any():
        return None

    left_gini = 1.0 - np.sum((left_counts / left_total[:, None]) ** 2, axis=1)
    right_gini = 1.0 - np.sum((right_counts / right_total[:, None]) ** 2,
                              axis=1)
    weighted = (left_total * left_gini + right_total * right_gini) / total
    weighted = np.where(valid, weighted, np.inf)

    position = int(np.argmin(weighted))
    if not np.isfinite(weighted[position]):
        return None
    threshold = (values[position] + values[position + 1]) / 2.0
    return threshold, float(weighted[position])


def _grow_tree(features: np.ndarray, classes: np.ndarray, n_classes: int,
               mtry: int, rng, depth: int = 0, max_depth: int = 40) -> _Tree:
    node = _Tree()
    counts = np.bincount(classes, minlength=n_classes).astype(np.float64)

    if depth >= max_depth or len(classes) < 2 or (counts > 0).sum() == 1:
        node.votes = counts / counts.sum()
        return node

    candidates = rng.choice(features.shape[1],
                            size=min(mtry, features.shape[1]),
                            replace=False)
    best = None
    for feature in candidates:
        split = _gini_best_split(features[:, feature], classes, n_classes)
        if split is None:
            continue
        threshold, impurity = split
        if best is None or impurity < best[2]:
            best = (feature, threshold, impurity)

    if best is None:
        node.votes = counts / counts.sum()
        return node

    feature, threshold, _ = best
    goes_left = features[:, feature] <= threshold
    if goes_left.all() or (~goes_left).all():
        node.votes = counts / counts.sum()
        return node

    node.feature = int(feature)
    node.threshold = float(threshold)
    node.left = _grow_tree(features[goes_left], classes[goes_left],
                           n_classes, mtry, rng, depth + 1, max_depth)
    node.right = _grow_tree(features[~goes_left], classes[~goes_left],
                            n_classes, mtry, rng, depth + 1, max_depth)
    return node


def _tree_votes(node: _Tree, features: np.ndarray) -> np.ndarray:
    """Push every row down the tree and collect the leaf distributions."""
    out = np.zeros((len(features), len(node.votes)
                    if node.votes is not None else 0))
    stack = [(node, np.arange(len(features)))]
    result = None
    while stack:
        current, rows = stack.pop()
        if len(rows) == 0:
            continue
        if current.votes is not None:
            if result is None:
                result = np.zeros((len(features), len(current.votes)))
            result[rows] = current.votes
            continue
        goes_left = features[rows, current.feature] <= current.threshold
        stack.append((current.left, rows[goes_left]))
        stack.append((current.right, rows[~goes_left]))
    return result if result is not None else out


class BuiltinRandomForest:
    """A plain Random Forest, used when scikit-learn is not installed."""

    def __init__(self, n_estimators: int = N_TREES,
                 random_state: int = RANDOM_SEED):
        self.n_estimators = int(n_estimators)
        self.random_state = int(random_state)
        self.trees = []
        self.classes_ = None

    def fit(self, features: np.ndarray, labels: np.ndarray):
        features = np.asarray(features, dtype=np.float64)
        self.classes_, encoded = np.unique(labels, return_inverse=True)
        n_classes = len(self.classes_)
        mtry = max(1, int(round(np.sqrt(features.shape[1]))))
        rng = np.random.default_rng(self.random_state)

        self.trees = []
        for _ in range(self.n_estimators):
            picked = rng.integers(0, len(encoded), len(encoded))
            self.trees.append(_grow_tree(features[picked], encoded[picked],
                                         n_classes, mtry, rng))
        return self

    def predict_proba(self, features: np.ndarray) -> np.ndarray:
        features = np.asarray(features, dtype=np.float64)
        total = np.zeros((len(features), len(self.classes_)))
        for tree in self.trees:
            total += _tree_votes(tree, features)
        return total / max(len(self.trees), 1)

    def predict(self, features: np.ndarray) -> np.ndarray:
        return self.classes_[np.argmax(self.predict_proba(features), axis=1)]


# ── training and prediction ──────────────────────────────────────────

def train(features: np.ndarray, labels: np.ndarray,
          n_estimators: int = N_TREES, seed: int = RANDOM_SEED):
    """Fit a Random Forest on the labelled objects."""
    features = np.asarray(features, dtype=np.float64)
    labels = np.asarray(labels)
    if len(np.unique(labels)) < 2:
        raise ValueError(
            "Do nauki potrzebne są przykłady co najmniej dwóch klas.")

    if HAS_SKLEARN:
        from sklearn.ensemble import RandomForestClassifier
        # n_jobs nie zmienia wyniku, tylko rozkłada drzewa na rdzenie
        model = RandomForestClassifier(n_estimators=n_estimators,
                                       random_state=seed, n_jobs=-1)
        model.fit(features, labels)
        return model
    return BuiltinRandomForest(n_estimators, seed).fit(features, labels)


def niezrownowazenie(labels) -> tuple:
    """Zwraca (najliczniejsza, najrzadsza, stosunek) dla klas uczących.

    Las losowy nie wyrównuje liczebności sam z siebie, więc klasa
    z garstką przykładów przegrywa głosowania z klasą, której naklikano
    kilkaset. Lepiej uprzedzić, niż po cichu krzywdzić.
    """
    wartosci, liczby = np.unique(np.asarray(labels), return_counts=True)
    if len(wartosci) < 2:
        return None, None, 1.0
    najwiecej, najmniej = int(np.argmax(liczby)), int(np.argmin(liczby))
    return (str(wartosci[najwiecej]), str(wartosci[najmniej]),
            float(liczby[najwiecej]) / max(float(liczby[najmniej]), 1.0))


def predict(model, features: np.ndarray) -> tuple:
    """Return ``(labels, confidence)`` for every row.

    Confidence is the winning class's share of the vote, which is what
    the suggestion of what to label next sorts on.
    """
    features = np.asarray(features, dtype=np.float64)
    probabilities = model.predict_proba(features)
    winners = np.argmax(probabilities, axis=1)
    classes = np.asarray(model.classes_)
    return classes[winners], probabilities[np.arange(len(winners)), winners]


def least_certain(model, features: np.ndarray, limit: int = 20) -> np.ndarray:
    """Row indices the forest is least sure about, least certain first."""
    _, confidence = predict(model, features)
    return np.argsort(confidence)[:limit]


def feature_importance(model, names) -> list:
    """Feature names with their share of the forest's decisions."""
    values = getattr(model, "feature_importances_", None)
    if values is None:
        return []
    pairs = sorted(zip(names, np.asarray(values, dtype=float)),
                   key=lambda item: -item[1])
    return pairs


# ── class separability ───────────────────────────────────────────────

def _shrunk_covariance(block: np.ndarray) -> np.ndarray:
    """Covariance with Ledoit-Wolf shrinkage towards a diagonal.

    With dozens of features and a few hundred samples the plain
    covariance is close to singular, and a distance computed from it
    saturates. Shrinking it towards a scaled identity keeps the
    estimate usable.
    """
    n_samples, n_features = block.shape
    if n_samples < 2:
        return np.eye(n_features)
    centred = block - block.mean(axis=0)
    sample = centred.T @ centred / n_samples

    mu = np.trace(sample) / n_features
    target = mu * np.eye(n_features)
    delta = np.sum((sample - target) ** 2) / n_features
    beta = np.sum([np.sum((np.outer(row, row) - sample) ** 2)
                   for row in centred]) / (n_features * n_samples ** 2)
    shrink = 0.0 if delta <= 0 else min(1.0, max(0.0, beta / delta))
    return (1.0 - shrink) * sample + shrink * target


def _bhattacharyya_1d(a: np.ndarray, b: np.ndarray) -> float:
    """Bhattacharyya distance between two sets of numbers."""
    if len(a) < 2 or len(b) < 2:
        return 0.0
    mean_a, mean_b = float(np.mean(a)), float(np.mean(b))
    var_a = float(np.var(a, ddof=1)) + 1e-12
    var_b = float(np.var(b, ddof=1)) + 1e-12
    first = 0.125 * (mean_a - mean_b) ** 2 * 2.0 / (var_a + var_b)
    second = 0.5 * np.log((var_a + var_b) / 2.0 / np.sqrt(var_a * var_b))
    return float(max(first + second, 0.0))


def _jm_from_bhattacharyya(distance: float) -> float:
    return float(2.0 * (1.0 - np.exp(-distance)))


def _best_direction(block_a: np.ndarray, block_b: np.ndarray) -> np.ndarray:
    """Fisher's direction: the line along which the two classes separate."""
    pooled = (_shrunk_covariance(block_a) * len(block_a)
              + _shrunk_covariance(block_b) * len(block_b)) \
        / (len(block_a) + len(block_b))
    difference = block_a.mean(axis=0) - block_b.mean(axis=0)
    try:
        direction = np.linalg.solve(
            pooled + 1e-9 * np.eye(len(pooled)), difference)
    except np.linalg.LinAlgError:
        direction = difference
    norm = np.linalg.norm(direction)
    return direction / norm if norm > 0 else difference


def pair_separability(block_a: np.ndarray, block_b: np.ndarray,
                      folds: int = 5, seed: int = RANDOM_SEED) -> float:
    """Cross-validated Jeffries-Matusita distance for one pair.

    The separating direction is found on part of the samples and the
    distance is measured on the rest. Measured in the full feature
    space instead, the distance reads 2.00 for nearly every pair, even
    for a class split against itself, and so cannot point out a weak
    pair.
    """
    if len(block_a) < 4 or len(block_b) < 4:
        return _jm_from_bhattacharyya(
            _bhattacharyya_1d(block_a @ _best_direction(block_a, block_b),
                              block_b @ _best_direction(block_a, block_b)))

    rng = np.random.default_rng(seed)
    order_a = rng.permutation(len(block_a))
    order_b = rng.permutation(len(block_b))
    folds = max(2, min(folds, len(block_a) // 2, len(block_b) // 2))
    scores = []

    for fold in range(folds):
        test_a = order_a[fold::folds]
        test_b = order_b[fold::folds]
        train_a = np.setdiff1d(order_a, test_a)
        train_b = np.setdiff1d(order_b, test_b)
        if min(len(train_a), len(train_b), len(test_a), len(test_b)) < 2:
            continue
        direction = _best_direction(block_a[train_a], block_b[train_b])
        scores.append(_jm_from_bhattacharyya(_bhattacharyya_1d(
            block_a[test_a] @ direction, block_b[test_b] @ direction)))

    return float(np.mean(scores)) if scores else 0.0


def leading_features(block_a: np.ndarray, block_b: np.ndarray,
                     names, limit: int = 5) -> list:
    """Which single features separate this pair best."""
    scores = []
    for index, name in enumerate(names):
        distance = _bhattacharyya_1d(block_a[:, index], block_b[:, index])
        scores.append((name, _jm_from_bhattacharyya(distance)))
    scores.sort(key=lambda item: -item[1])
    return scores[:limit]


def separability_report(features: np.ndarray, labels: np.ndarray,
                        names, class_names=None) -> dict:
    """The pairwise table, the closest pairs and why they are close."""
    features = np.asarray(features, dtype=np.float64)
    labels = np.asarray(labels)
    classes = list(dict.fromkeys(labels.tolist()))
    if class_names is None:
        class_names = {value: str(value) for value in classes}

    blocks = {value: features[labels == value] for value in classes}
    table = {}
    pairs = []

    for i, first in enumerate(classes):
        for second in classes[i + 1:]:
            score = pair_separability(blocks[first], blocks[second])
            table[(first, second)] = score
            pairs.append({
                "a": class_names.get(first, str(first)),
                "b": class_names.get(second, str(second)),
                "jm": score,
                "verdict": ("good" if score >= JM_GOOD
                            else "fair" if score >= JM_FAIR else "poor"),
                "leading": leading_features(blocks[first], blocks[second],
                                            names),
            })

    pairs.sort(key=lambda item: item["jm"])
    sizes = {class_names.get(value, str(value)): int(len(blocks[value]))
             for value in classes}
    return {"table": table, "pairs": pairs, "sample_sizes": sizes,
            "n_features": features.shape[1],
            "classes": [class_names.get(value, str(value))
                        for value in classes]}
