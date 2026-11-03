"""Post-hoc comparison of frozen probe artifacts; no generation or LLM runs.

Distances use the original ten bounded descriptors, with no fitted scaling.
Worlds, not transitions, are the units. Metrics are descriptive.
"""
from pathlib import Path
import csv
import hashlib
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent
RESEARCH = ROOT.parent
INPUTS = {}
FEATURES = ['autonomous_change', 'driven_change', 'turnover', 'growth', 'shrink',
            'action_effect', 'delayed_effect', 'persistent_effect',
            'stochastic_difference', 'observation_aliasing']
LABELS = ['Автономные изменения', 'Изменения при действиях', 'Доля изменённых клеток',
          'Рост занятой площади', 'Убывание занятой площади', 'Эффект вмешательства',
          'Отложенный эффект', 'Сохраняющийся эффект', 'Различие между seed',
          'Неоднозначность наблюдения']

def read(relative):
    p = RESEARCH / relative
    raw = p.read_bytes()
    INPUTS[str(p.relative_to(RESEARCH))] = hashlib.sha256(raw).hexdigest()
    return json.loads(raw)

def load_group(folder, names):
    rows = [read(f'{folder}/{n}.json') for n in names]
    assert all(r['valid'] for r in rows)
    x = np.array([[r['features'][f] for f in FEATURES] for r in rows])
    assert np.isfinite(x).all() and ((x >= 0) & (x <= 1)).all()
    return x

def distances(x, y):
    return abs(x[:, None] - y[None, :]).mean(axis=2)

def within(x):
    d = distances(x, x)
    return float(d.sum() / (len(x) * (len(x) - 1)))

def stats(x):
    return dict(n=len(x), min=float(np.min(x)), median=float(np.median(x)),
                max=float(np.max(x)), mean=float(np.mean(x)))

def energy_test(x, y):
    # Unbiased energy statistic, L1 distance; descriptive fixed-pool label test.
    # L1 energy mainly captures marginal distributions, not all joint dependence.
    z = np.concatenate([x, y]); d = distances(z, z); n = len(x); m = len(y)
    def statistic(a, b):
        return (2 * d[np.ix_(a, b)].mean()
                - d[np.ix_(a, a)].sum() / (n * (n - 1))
                - d[np.ix_(b, b)].sum() / (m * (m - 1)))
    observed = statistic(np.arange(n), np.arange(n, n + m))
    rng = np.random.default_rng(20261103)
    null = []
    for _ in range(4999):
        p = rng.permutation(n + m); null.append(statistic(p[:n], p[n:]))
    return {'unbiased_energy_L1': float(observed),
            'permutation_p': float((1 + np.count_nonzero(np.array(null) >= observed)) / 5000),
            'permutations': 4999}
