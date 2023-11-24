import pandas as pd


def check_lines_aligned(trace: pd.DataFrame, tolerance) -> pd.DataFrame:
    # If checking the tolerance interval will make the angle bleed the [0,360] interval, we have to fix it

    cols = ["net_link_az", "tangent_bearing"]
    df = trace.assign(
        abs_diff=abs(trace.net_link_az - trace.tangent_bearing),
        reverse_diff=(trace[cols].max(axis=1) - trace[cols].min(axis=1) + tolerance) % 360,
        aligned=0,
    )

    # Comparison 1
    df.loc[df.abs_diff <= tolerance, "aligned"] = 1

    # Comparison 2
    df.loc[(df.abs_diff >= 180 - tolerance) & ((df.abs_diff <= 180 + tolerance)), "aligned"] = 1

    # Comparison 3
    df.loc[df.reverse_diff <= tolerance, "aligned"] = 1

    return df[["aligned"]]
