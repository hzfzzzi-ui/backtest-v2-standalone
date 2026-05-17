from __future__ import annotations

import numpy as np
import pandas as pd

from backend.core.engine_vector.rolling_state import (
    rolling_max_1d,
    rolling_mean_1d,
    rolling_mean_matrix_streaming,
    rolling_min_1d,
)


def test_streaming_rolling_mean_matches_pandas() -> None:
    values = np.array([1.0, 2.0, np.nan, 4.0, 5.0, 6.0])

    actual = rolling_mean_1d(values, 2)
    expected = pd.Series(values).rolling(2, min_periods=2).mean().to_numpy(dtype=float)

    np.testing.assert_allclose(actual, expected, equal_nan=True)


def test_streaming_rolling_extremes_match_pandas() -> None:
    values = np.array([3.0, 2.0, 5.0, np.nan, 4.0, 1.0])

    np.testing.assert_allclose(
        rolling_max_1d(values, 3),
        pd.Series(values).rolling(3, min_periods=3).max().to_numpy(dtype=float),
        equal_nan=True,
    )
    np.testing.assert_allclose(
        rolling_min_1d(values, 3),
        pd.Series(values).rolling(3, min_periods=3).min().to_numpy(dtype=float),
        equal_nan=True,
    )


def test_streaming_rolling_mean_matrix_matches_pandas() -> None:
    values = np.array(
        [
            [1.0, 10.0],
            [2.0, 11.0],
            [3.0, np.nan],
            [4.0, 13.0],
        ]
    )

    actual = rolling_mean_matrix_streaming(values, 2)
    expected = pd.DataFrame(values).rolling(2, min_periods=2).mean().to_numpy(dtype=float)

    np.testing.assert_allclose(actual, expected, equal_nan=True)
