from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


def _save(fig, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return str(path)


def plot_missing_values(df, chart_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(8, 4))
    df.isna().sum().sort_values(ascending=False).plot(kind="bar", ax=ax, color="#27667b")
    ax.set_title("Missing values by variable")
    return _save(fig, chart_dir / "missing_values.png")


def plot_coefficients(result: dict, chart_dir: Path) -> str:
    values = {k: v for k, v in result.get("coefficients", {}).items() if k != "Intercept"}
    fig, ax = plt.subplots(figsize=(8, max(3, len(values) * .35)))
    ax.barh(list(values), list(values.values()), color="#d17b46")
    ax.axvline(0, color="#333", linewidth=.8)
    ax.set_title("Estimated coefficients")
    return _save(fig, chart_dir / "coefficients.png")


def plot_group_trends(df, outcome: str, treat: str, time: str, chart_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(8, 4))
    df.groupby([time, treat])[outcome].mean().unstack().plot(ax=ax)
    ax.set_title("Outcome trends by group")
    return _save(fig, chart_dir / "group_trends.png")


def plot_event_study_placeholder(chart_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(8, 4)); ax.text(.5, .5, "Event study diagnostic placeholder", ha="center"); return _save(fig, chart_dir / "event_study.png")


def plot_psm_balance_placeholder(chart_dir: Path) -> str:
    fig, ax = plt.subplots(figsize=(8, 4)); ax.text(.5, .5, "PSM balance diagnostic placeholder", ha="center"); return _save(fig, chart_dir / "psm_balance.png")


def plot_parallel_trends(df, spec: dict, chart_dir: Path) -> tuple[str, list[str]]:
    warnings = [] if (df[spec["time"]] < int(spec["policy_time"])).any() else ["缺少政策前数据"]
    fig, ax = plt.subplots(figsize=(8, 4))
    df.groupby([spec["time"], spec["treat"]])[spec["outcome"]].mean().unstack().plot(ax=ax)
    ax.axvline(int(spec["policy_time"]), linestyle="--", color="#d17b46")
    ax.set_title("Parallel trends diagnostic")
    return _save(fig, chart_dir / "parallel_trends.png"), warnings


def plot_event_study_results(result: dict, chart_dir: Path) -> str:
    rows = sorted(result["relative_time_results"], key=lambda row: row["relative_time"])
    x, y = [row["relative_time"] for row in rows], [row["coef"] for row in rows]
    low, high = [row["ci_low"] for row in rows], [row["ci_high"] for row in rows]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.errorbar(x, y, yerr=[[v - l for v, l in zip(y, low)], [h - v for v, h in zip(y, high)]], fmt="o-", color="#27667b")
    ax.axhline(0, color="#333", linewidth=.8); ax.axvline(0, linestyle="--", color="#d17b46")
    ax.set_title("Event study estimates")
    return _save(fig, chart_dir / "event_study_results.png")
