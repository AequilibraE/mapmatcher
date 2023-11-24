import numpy as np
import pandas as pd

from mapmatcher.utils import check_lines_aligned


def test_check_lines_aligned():
    for threshold in range(5, 50, 5):
        for diff in [50, 310, 130, 240]:
            df = pd.DataFrame({"net_link_az": np.arange(360), "tangent_bearing": (np.arange(360) + diff) % 360})

            res = check_lines_aligned(df, threshold)
            assert np.sum(res.aligned) == 0

    for threshold in range(5, 50, 5):
        for diff in range(1, threshold + 1):
            df = pd.DataFrame({"net_link_az": np.arange(360), "tangent_bearing": (np.arange(360) + diff) % 360})

            res = check_lines_aligned(df, threshold)
            assert np.sum(res.aligned) == df.shape[0]

    for threshold in range(5, 50, 5):
        for diff in range(1, threshold + 1):
            df = pd.DataFrame({"net_link_az": np.arange(360), "tangent_bearing": (180 + np.arange(360) + diff) % 360})

            res = check_lines_aligned(df, threshold)
            assert np.sum(res.aligned) == df.shape[0]
