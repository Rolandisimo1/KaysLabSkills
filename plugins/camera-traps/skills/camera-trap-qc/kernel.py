"""Helpers for camera-trap QC. See SKILL.md for what each check is for."""
import numpy as np
import pandas as pd

DIURNAL_SENTINEL = "Eastern Gray Squirrel"
NOCTURNAL_SENTINEL = "Northern Raccoon"

# Sentinel groups that work outside North America. Validated on a 128.6M-row
# global Wildlife Insights export: 8.4% of diurnal-group detections and 92.4%
# of nocturnal-group detections fell at night (project medians 4.2% / 96.8%).
GLOBAL_DIURNAL = {"genus": ["Sciurus"], "class": ["Aves"],
                  "exclude_order": ["Strigiformes", "Caprimulgiformes"]}
GLOBAL_NOCTURNAL = {"genus": ["Didelphis", "Genetta", "Rattus"],
                    "order": ["Strigiformes"], "binomial": ["Procyon lotor"]}


def sentinel_mask(df, kind="diurnal", genus_col="genus", class_col="class",
                  order_col="order", binomial_col="sp_binomial"):
    """Boolean mask selecting global diurnal or nocturnal sentinel rows.

    Used to screen timestamp storage and camera clocks on exports that reach
    beyond North America, where the single-species sentinels above do not occur.
    Run BOTH masks: a clock error inverts the two groups together, while an
    unusual site moves only one, and that difference is the whole diagnostic.
    Returns a mask; the caller supplies night_fraction() per project.
    """
    spec = GLOBAL_DIURNAL if kind == "diurnal" else GLOBAL_NOCTURNAL
    cols = {c: df[c].astype(str) if c in df.columns else None
            for c in (genus_col, class_col, order_col, binomial_col)}
    m = pd.Series(False, index=df.index)
    if cols[genus_col] is not None and spec.get("genus"):
        m |= cols[genus_col].isin(spec["genus"])
    if cols[order_col] is not None and spec.get("order"):
        m |= cols[order_col].isin(spec["order"])
    if cols[binomial_col] is not None and spec.get("binomial"):
        m |= cols[binomial_col].isin(spec["binomial"])
    if cols[class_col] is not None and spec.get("class"):
        birds = cols[class_col].isin(spec["class"])
        if cols[order_col] is not None and spec.get("exclude_order"):
            birds &= ~cols[order_col].isin(spec["exclude_order"])
        m |= birds
    return m


def site_timezone(lat, lon):
    """IANA time zone at a coordinate. Requires `timezonefinder`."""
    from timezonefinder import TimezoneFinder
    global _TF
    try:
        _TF
    except NameError:
        _TF = TimezoneFinder()
    return _TF.timezone_at(lat=float(lat), lng=float(lon))


def utc_offsets(timestamps, latitude, longitude):
    """UTC offset in hours for each timestamp, honouring the real zone and DST."""
    from zoneinfo import ZoneInfo
    ts = pd.DatetimeIndex(pd.to_datetime(timestamps))
    # Callers sometimes parse with utc=True, which yields a tz-AWARE index that
    # cannot be localized. These are wall-clock readings regardless of any suffix,
    # so strip the tz rather than convert (converting would shift the clock).
    if ts.tz is not None:
        ts = ts.tz_localize(None)
    lat = np.asarray(latitude, dtype=float)
    lon = np.asarray(longitude, dtype=float)
    zones = np.array([site_timezone(a, o) for a, o in zip(lat, lon)], dtype=object)
    out = np.full(len(ts), np.nan)
    for z in pd.unique(zones):
        if z is None:
            continue
        m = zones == z
        # The hour repeated at the DST fall-back is genuinely ambiguous: resolve to
        # standard time and skip forward over the spring-gap hour. A one-hour error on
        # those rare records is far smaller than the zone-wide bias this removes.
        loc = pd.DatetimeIndex(ts[m]).tz_localize(
            ZoneInfo(z), ambiguous=False, nonexistent="shift_forward")
        out[m] = np.array([o.total_seconds() / 3600.0
                           for o in loc.map(lambda x: x.utcoffset())])
    return out


def solar_window(timestamps, latitude, longitude):
    """Sunrise/sunset in LOCAL CLOCK hours -- the units camera timestamps use.

    WHY THIS SIGNATURE. An earlier version took (day_of_year, latitude) and returned
    SOLAR sunrise, which was then compared against CLOCK timestamps. That is wrong by
    two compounding terms: the site's longitude offset within its time zone (up to an
    hour, largest at zone edges) and daylight saving (another hour). Combined bias
    reached ~1 h, which made ordinary crepuscular activity at western-edge sites read
    as nocturnal and produced false 'broken camera' flags. Longitude is therefore
    REQUIRED, and the zone comes from the IANA database rather than round(lon/15),
    because US zone borders follow state lines and Arizona does not observe DST.

    Validated against published sunrise/sunset at 9 sites spanning 4 zones: worst
    error 14 min (versus ~60 min for the solar-time version).

    Returns (sunrise, sunset) as arrays of local clock hours.
    """
    ts = pd.DatetimeIndex(pd.to_datetime(timestamps))
    if ts.tz is not None:
        ts = ts.tz_localize(None)
    lat_deg = np.asarray(latitude, dtype=float)
    lon = np.asarray(longitude, dtype=float)
    lat = np.radians(lat_deg)
    doy = ts.dayofyear.values.astype(float)
    gamma = 2 * np.pi * (doy - 1) / 365.0
    # equation of time (minutes) -- kept, unlike the old version
    eqt = 229.18 * (0.000075 + 0.001868 * np.cos(gamma) - 0.032077 * np.sin(gamma)
                    - 0.014615 * np.cos(2 * gamma) - 0.040849 * np.sin(2 * gamma))
    declin = (0.006918 - 0.399912 * np.cos(gamma) + 0.070257 * np.sin(gamma)
              - 0.006758 * np.cos(2 * gamma) + 0.000907 * np.sin(2 * gamma)
              - 0.002697 * np.cos(3 * gamma) + 0.00148 * np.sin(3 * gamma))
    cos_h = np.clip((np.cos(np.radians(90.833)) / (np.cos(lat) * np.cos(declin))
                     - np.tan(lat) * np.tan(declin)), -1, 1)
    half = np.degrees(np.arccos(cos_h)) / 15.0
    noon = 12.0 - lon / 15.0 - eqt / 60.0 + utc_offsets(ts, lat_deg, lon)
    return noon - half, noon + half


def night_fraction(timestamps, latitude, longitude):
    """Share of detections outside the local-clock sunrise-sunset window."""
    ts = pd.DatetimeIndex(pd.to_datetime(timestamps))
    h = ts.hour.values + ts.minute.values / 60.0 + ts.second.values / 3600.0
    sr, ss = solar_window(ts, latitude, longitude)
    return float(np.mean((h < sr) | (h >= ss)))


def is_night(timestamps, latitude, longitude):
    """Boolean night flag per timestamp, in local clock time."""
    ts = pd.DatetimeIndex(pd.to_datetime(timestamps))
    h = ts.hour.values + ts.minute.values / 60.0 + ts.second.values / 3600.0
    sr, ss = solar_window(ts, latitude, longitude)
    return (h < sr) | (h >= ss)


def classify_project_timezone(df, time_col="timestamp", lat_col="latitude",
                              lon_col="longitude", project_col="project_id",
                              species_col="common_name", min_n=60,
                              night_threshold=0.20):
    """Flag projects whose timestamps are stored as UTC rather than local time.

    Pass detections of the DIURNAL sentinel species only, or a frame containing
    it -- rows for other species are dropped. One row per detection.
    Returns a DataFrame indexed by project with night fractions as-stored and
    after a longitude-implied shift, plus an `is_utc` verdict.
    """
    d = df[df[species_col] == DIURNAL_SENTINEL] if species_col in df.columns else df
    d = d.dropna(subset=[time_col, lat_col, lon_col])
    out = []
    for proj, g in d.groupby(project_col):
        if len(g) < min_n:
            continue
        ts = pd.DatetimeIndex(pd.to_datetime(g[time_col]))
        sr, ss = solar_window(ts, g[lat_col], g[lon_col])
        h = ts.hour.values + ts.minute.values / 60.0
        asis = float(np.mean((h < sr) | (h >= ss)))
        # A project storing UTC is corrected by ADDING its own UTC offset (negative
        # in North America). Use the real offset, not round(lon/15): zone borders
        # follow state lines and Arizona skips DST.
        h2 = (h + utc_offsets(ts, g[lat_col], g[lon_col])) % 24
        shifted = float(np.mean((h2 < sr) | (h2 >= ss)))
        out.append((proj, len(g), asis, shifted,
                    bool(asis > night_threshold and shifted < asis)))
    return pd.DataFrame(out, columns=[project_col, "n", "night_asis",
                                      "night_shifted", "is_utc"]).set_index(project_col)


def flag_clock_errors(df, time_col="timestamp", lat_col="latitude",
                      lon_col="longitude", unit_col="deployment_id",
                      species_col="common_name", min_n=15, min_n_check=10):
    """Per-deployment clock-error verdicts using two sentinel species.

    Run AFTER any project-level timezone correction. Both sentinels inverted in
    the same unit is the clock-error signature; only the diurnal one inverted
    points at misidentification instead.
    """
    rows = []
    for unit, g in df.groupby(unit_col):
        sq = g[g[species_col] == DIURNAL_SENTINEL]
        rc = g[g[species_col] == NOCTURNAL_SENTINEL]
        if len(sq) < min_n:
            continue
        sq_night = night_fraction(sq[time_col], sq[lat_col], sq[lon_col])
        rc_night = (night_fraction(rc[time_col], rc[lat_col], rc[lon_col])
                    if len(rc) >= min_n_check else np.nan)
        sq_bad = sq_night > 0.45
        rc_bad = (not np.isnan(rc_night)) and rc_night < 0.55
        if sq_bad and rc_bad:
            verdict = "clock error - both sentinels inverted"
        elif sq_bad and not np.isnan(rc_night):
            verdict = "diurnal sentinel odd only - suspect misidentification"
        elif sq_bad:
            verdict = "diurnal sentinel odd, nocturnal untestable - review"
        elif rc_bad:
            verdict = "nocturnal sentinel odd only - review"
        else:
            verdict = "ok"
        rows.append((unit, len(sq), sq_night, len(rc), rc_night, verdict))
    return pd.DataFrame(rows, columns=[unit_col, "n_diurnal", "diurnal_night_frac",
                                       "n_nocturnal", "nocturnal_night_frac", "verdict"])


def best_offset(timestamps, latitude, longitude, candidates=None):
    """Integer-hour offset that minimises diurnal-sentinel nocturnality.

    DIAGNOSTIC ONLY -- never a correction. Searching 25 candidate shifts and keeping
    the best ALWAYS improves fit, including on cameras known to be fine: on 1,142
    cameras in arrays that passed the array-level check, a non-zero offset "improved"
    fit by >50% for 44.5% of them (versus 60.7% on suspect arrays -- only 1.4x
    enrichment, so this cannot identify individual cameras). Fitting an offset so a
    camera matches the species mean assumes the answer and erases genuinely unusual
    sites. Use the species-ORDERING test (`flag_clock_errors`) to detect a candidate,
    then require evidence from OUTSIDE the diel data before acting: the Jan-1 reset
    signature, timestamps outside the recorded deployment window, a structurally
    impossible detection gap, or a human looking at the photograph. Prefer dropping
    a confirmed-bad camera to shifting it.
    """
    if candidates is None:
        candidates = range(-12, 13)
    ts = pd.DatetimeIndex(pd.to_datetime(timestamps))
    sr, ss = solar_window(ts, latitude, longitude)
    h0 = ts.hour.values + ts.minute.values / 60.0
    best, best_off = 1.0, 0
    for off in candidates:
        h = (h0 + off) % 24
        nf = float(np.mean((h < sr) | (h >= ss)))
        if nf < best:
            best, best_off = nf, off
    return best_off, best


def array_extent_km(lat, lon, max_points=300, seed=0):
    """Max pairwise great-circle distance (km) within one array."""
    la = np.radians(np.asarray(lat, dtype=float))
    lo = np.radians(np.asarray(lon, dtype=float))
    if la.size < 2:
        return 0.0
    if la.size > max_points:
        idx = np.random.default_rng(seed).choice(la.size, max_points, replace=False)
        la, lo = la[idx], lo[idx]
    dla = la[:, None] - la[None, :]
    dlo = lo[:, None] - lo[None, :]
    a = np.sin(dla / 2) ** 2 + np.cos(la)[:, None] * np.cos(la)[None, :] * np.sin(dlo / 2) ** 2
    return float(6371 * 2 * np.arcsin(np.sqrt(np.clip(a, 0, 1))).max())


def cluster_by_distance(lat, lon, threshold_km=25.0, method="complete"):
    """Cluster camera locations so no cluster exceeds threshold_km across.

    Complete linkage guarantees the bound; single linkage chains through
    intermediate cameras and can exceed it badly.
    """
    from scipy.cluster.hierarchy import fcluster, linkage
    from scipy.spatial.distance import pdist
    la = np.radians(np.asarray(lat, dtype=float))
    lo = np.radians(np.asarray(lon, dtype=float))
    if la.size < 2:
        return np.ones(la.size, dtype=int)
    xyz = np.c_[np.cos(la) * np.cos(lo), np.cos(la) * np.sin(lo), np.sin(la)] * 6371
    return fcluster(linkage(pdist(xyz), method=method), t=threshold_km,
                    criterion="distance")


def find_repeated_sites(df, lat_col="latitude", lon_col="longitude",
                        project_col="project_id", unit_col="deployment_id",
                        precision=3):
    """Locations sampled in more than one project/year -- sample-size inflation."""
    d = df.copy()
    d["_loc"] = (d[lat_col].round(precision).astype(str) + "_"
                 + d[lon_col].round(precision).astype(str))
    g = d.groupby("_loc").agg(n_projects=(project_col, "nunique"),
                              n_deployments=(unit_col, "size"))
    return g[g.n_projects > 1].sort_values("n_deployments", ascending=False)


def suntime_effort_ratio(effort_by_bin):
    """Within-unit max/min per-bin effort. Should be 1.0 in clock time; is not
    in sun-anchored time. Values above ~1.1 mean the offset matters."""
    e = np.asarray(effort_by_bin, dtype=float)
    e = e[np.isfinite(e) & (e > 0)]
    return float(e.max() / e.min()) if e.size else np.nan


def redeployment_gaps(df, lat_col="latitude", lon_col="longitude", start_col="start_date",
                      end_col="end_date", unit_col="deployment_id", precision=4):
    """Gap in days between consecutive deployments at each location.

    Returns one row per consecutive pair with `gap_days`. Plot a histogram of it:
    a mode near zero is back-to-back records needing merging (Case A), a mode
    near 365 is annual re-survey (Case B). Negative gaps are overlapping
    deployments and need resolving by hand.
    """
    d = df.copy()
    d[start_col] = pd.to_datetime(d[start_col], errors="coerce", utc=True)
    d[end_col] = pd.to_datetime(d[end_col], errors="coerce", utc=True)
    d = d.dropna(subset=[start_col, end_col, lat_col, lon_col])
    d["_loc"] = (d[lat_col].round(precision).astype(str) + "_"
                 + d[lon_col].round(precision).astype(str))
    d = d.sort_values(["_loc", start_col])
    d["prev_end"] = d.groupby("_loc")[end_col].shift(1)
    d["prev_unit"] = d.groupby("_loc")[unit_col].shift(1)
    d["gap_days"] = (d[start_col] - d["prev_end"]).dt.days
    return d[d.gap_days.notna()][["_loc", unit_col, "prev_unit", start_col, end_col,
                                  "prev_end", "gap_days"]]


def merge_back_to_back(df, max_gap_days=7, lat_col="latitude", lon_col="longitude",
                       start_col="start_date", end_col="end_date",
                       unit_col="deployment_id", effort_col=None, precision=4):
    """Collapse consecutive deployments at one location separated by <= max_gap_days.

    Case A of SKILL.md section 3: one continuous survey split across records.
    Returns the frame with a `merge_group` column; group and aggregate on it
    (min start, max end, summed effort). Does NOT merge annual repeats.
    """
    d = df.copy()
    d[start_col] = pd.to_datetime(d[start_col], errors="coerce", utc=True)
    d[end_col] = pd.to_datetime(d[end_col], errors="coerce", utc=True)
    d["_loc"] = (d[lat_col].round(precision).astype(str) + "_"
                 + d[lon_col].round(precision).astype(str))
    d = d.sort_values(["_loc", start_col])
    gap = (d[start_col] - d.groupby("_loc")[end_col].shift(1)).dt.days
    new_block = (gap.isna()) | (gap > max_gap_days)
    d["merge_group"] = (d["_loc"] + "#"
                        + new_block.groupby(d["_loc"]).cumsum().astype(str))
    return d


def plot_qc_panels(df, lat_col="latitude", lon_col="longitude", start_col="start_date",
                   end_col="end_date", project_col="project_id",
                   subproject_col="subproject_name", unit_col="deployment_id",
                   figsize=(13, 9.2)):
    """The four QC plots of SKILL.md section 0. Returns (fig, axes_dict).

    Read them for DEFECTS: points outside the study region, impossible dates,
    subproject bars spanning years. Axes are never clipped to the expected
    range -- that would hide the outliers this exists to surface.
    """
    import matplotlib.pyplot as plt
    d = df.copy()
    d[start_col] = pd.to_datetime(d[start_col], errors="coerce", utc=True)
    d[end_col] = pd.to_datetime(d[end_col], errors="coerce", utc=True)
    d = d.dropna(subset=[start_col, end_col, lat_col, lon_col])
    fig = plt.figure(figsize=figsize)
    gs = fig.add_gridspec(3, 2, height_ratios=[1.15, .85, 1.15], hspace=.58, wspace=.22)
    axes = {}

    ax = fig.add_subplot(gs[0, 0]); axes["map"] = ax
    ax.scatter(d[lon_col], d[lat_col], s=2.2, alpha=.32, lw=0)
    ax.set_xlabel("Longitude"); ax.set_ylabel("Latitude")
    ax.set_title(f"a  {len(d):,} deployments, {d[project_col].nunique()} projects", loc="left")

    ax = fig.add_subplot(gs[0, 1]); axes["gaps"] = ax
    g = redeployment_gaps(d, lat_col, lon_col, start_col, end_col, unit_col)
    if len(g):
        ax.hist(g.gap_days.clip(-10, 800), bins=70)
    ax.set_xlabel("Gap between consecutive deployments at one location (days)")
    ax.set_ylabel("Number of pairs"); ax.set_title("b  Redeployment gaps", loc="left")

    ax = fig.add_subplot(gs[1, :]); axes["effort"] = ax
    months = []
    for s_, e_ in zip(d[start_col], d[end_col]):
        if e_ >= s_:
            months.extend(pd.period_range(s_, e_, freq="M"))
    if months:
        eff = pd.Series(months).value_counts().sort_index()
        ax.fill_between([p.to_timestamp() for p in eff.index], eff.values, alpha=.75)
    ax.set_ylabel("Active camera-months")
    ax.set_title("c  Effort over time (full range, unclipped)", loc="left")

    ax = fig.add_subplot(gs[2, :]); axes["timeline"] = ax
    key = (d[project_col].astype(str) + " :: " + d[subproject_col].fillna("(none)").astype(str)
           if subproject_col in d.columns else d[project_col].astype(str))
    sp = d.assign(_k=key).groupby("_k").agg(s=(start_col, "min"), e=(end_col, "max"),
                                            n=(unit_col, "size")).sort_values("s")
    spans = (sp.e - sp.s).dt.days
    ax.barh(np.arange(len(sp)), list(spans), left=list(sp.s), height=1.0,
            color=np.where(spans.values > 730, "#c0392b", "#2c6e8f"), alpha=.75, lw=0)
    ax.set_yticks([]); ax.set_xlabel("Date"); ax.set_ylabel(f"{len(sp)} subprojects")
    ax.set_title(f"d  Subproject spans — red = over 2 years "
                 f"({int((spans > 730).sum())} of {len(sp)})", loc="left")
    ax.invert_yaxis()
    return fig, axes


DIURNAL_SENTINELS = ["Eastern Gray Squirrel", "Eastern Fox Squirrel",
                     "Eastern Chipmunk", "Wild Turkey"]
NOCTURNAL_SENTINELS = ["Northern Raccoon", "Virginia Opossum", "Striped Skunk"]


def segment_clock_errors(df, unit_col="deployment_id", time_col="timestamp",
                         lat_col="latitude", lon_col="longitude",
                         species_col="common_name",
                         sentinels=None, night_threshold=0.5, min_per_day=3):
    """Find WHICH DAYS of each deployment look clock-shifted.

    Partial shifts are the common case -- a clock breaks or is corrected
    mid-deployment -- so a whole-deployment verdict is wrong for most affected
    cameras. Returns one row per contiguous run of days with `is_bad`.

    Screening only. A flagged segment is a CANDIDATE; confirm with images,
    a structurally impossible detection gap, or the Jan-1 reset signature
    before excluding or correcting anything.
    """
    sent = sentinels or DIURNAL_SENTINELS
    d = df[df[species_col].isin(sent)].copy()
    d[time_col] = pd.to_datetime(d[time_col], errors="coerce", utc=True)
    d = d.dropna(subset=[time_col, lat_col, lon_col])
    if not len(d):
        return pd.DataFrame(columns=[unit_col, "start", "end", "n", "is_bad"])
    hours = d[time_col].dt.hour + d[time_col].dt.minute / 60
    sr, ss = solar_window(d[time_col], d[lat_col], d[lon_col])
    d["_night"] = (hours.values < sr) | (hours.values >= ss)
    d["_day"] = d[time_col].dt.floor("D")
    out = []
    for unit, g in d.groupby(unit_col):
        daily = g.groupby("_day")._night.agg(["mean", "size"])
        daily = daily[daily["size"] >= min_per_day]
        if not len(daily):
            continue
        daily["bad"] = daily["mean"] > night_threshold
        daily["blk"] = (daily.bad != daily.bad.shift()).cumsum()
        for _, s in daily.groupby("blk"):
            out.append({unit_col: unit, "start": s.index.min().date(),
                        "end": s.index.max().date(), "n": int(s["size"].sum()),
                        "is_bad": bool(s.bad.iloc[0])})
    return pd.DataFrame(out)


def dead_window(df, unit_col="deployment_id", time_col="timestamp",
                species_col="common_name", sentinels=None, min_n=15):
    """Hours of day with ZERO detections of diurnal sentinel species.

    A long dead window is the strongest purely-statistical evidence of a broken
    clock: no animal community produces a 9-hour gap in squirrel and turkey
    activity. Compare against working cameras at the same site.

    CAUTION: compute this per camera. Pooling a broken camera with working
    siblings fills the window and hides the signature -- a mistake made and
    caught in the reference analysis.
    """
    sent = sentinels or DIURNAL_SENTINELS
    d = df[df[species_col].isin(sent)].copy()
    d[time_col] = pd.to_datetime(d[time_col], errors="coerce", utc=True)
    d = d.dropna(subset=[time_col])
    rows = []
    for unit, g in d.groupby(unit_col):
        if len(g) < min_n:
            continue
        present = set(g[time_col].dt.hour)
        dead = [h for h in range(24) if h not in present]
        runs, cur = [], []
        for h in list(range(24)) + list(range(24)):     # wrap midnight
            if h in dead:
                cur.append(h)
            elif cur:
                runs.append(len(cur)); cur = []
        rows.append({unit_col: unit, "n": len(g), "n_dead_hours": len(dead),
                     "longest_dead_run": max(runs) if runs else 0,
                     "dead_hours": dead})
    return pd.DataFrame(rows).sort_values("longest_dead_run", ascending=False)


def reset_signature(df, unit_col="deployment_id", time_col="timestamp"):
    """Deployments whose FIRST record is 1 January -- the classic camera reset.

    Presence is strong evidence of a fault. Absence is only weak evidence of
    health: in the reference dataset just 15 of 26,778 deployments showed it,
    and none of 29 independently-flagged clock candidates did.
    """
    d = df.copy()
    d[time_col] = pd.to_datetime(d[time_col], errors="coerce", utc=True)
    first = d.dropna(subset=[time_col]).groupby(unit_col)[time_col].min()
    jan1 = first[(first.dt.month == 1) & (first.dt.day == 1)]
    return pd.DataFrame({unit_col: jan1.index, "first_timestamp": jan1.values,
                         "at_midnight": (jan1.dt.hour == 0).values})


def verification_images(df, segments, unit_col="deployment_id", time_col="timestamp",
                        lat_col="latitude", lon_col="longitude",
                        species_col="common_name",
                        sentinels=None, per_segment=2):
    """Pick images for a human to check, FROM INSIDE flagged segments.

    Each returned row is a strictly diurnal species timestamped at night, chosen
    far from twilight so the photo is unambiguous. Dark frame -> the clock is
    wrong; daylight frame -> the flag is wrong.

    Sampling from the whole deployment instead of the flagged segment is how you
    hand someone the one clean week of an 8-week-shifted camera and get a false
    all-clear.
    """
    sent = sentinels or DIURNAL_SENTINELS
    d = df[df[species_col].isin(sent)].copy()
    d[time_col] = pd.to_datetime(d[time_col], errors="coerce", utc=True)
    d = d.dropna(subset=[time_col, lat_col])
    hours = d[time_col].dt.hour + d[time_col].dt.minute / 60
    sr, ss = solar_window(d[time_col], d[lat_col], d[lon_col])
    d["_hour"], d["_sr"], d["_ss"] = hours.values, sr, ss
    d["_night"] = (hours.values < sr) | (hours.values >= ss)
    rows = []
    for _, seg in segments[segments.is_bad].iterrows():
        w = d[(d[unit_col] == seg[unit_col]) & d._night
              & (d[time_col].dt.date >= seg["start"]) & (d[time_col].dt.date <= seg["end"])]
        if not len(w):
            continue
        w = w.assign(margin=np.minimum((w._hour - w._sr).abs(), (w._hour - w._ss).abs()))
        for _, x in w.nlargest(per_segment, "margin").iterrows():
            rows.append({unit_col: seg[unit_col], "segment_start": seg["start"],
                         "segment_end": seg["end"], "species": x[species_col],
                         "timestamp": x[time_col].strftime("%Y-%m-%d %H:%M:%S"),
                         "hours_from_twilight": round(float(x["margin"]), 1)})
    return pd.DataFrame(rows)


def collapse_sequences(df, response="events", dep_col="deployment_id",
                       seq_col="sequence_id", species_col="common_name",
                       group_col="group_size", time_col="start_time"):
    """Collapse the age/sex rows that share a sequence_id into one row per event.

    A sequence carries one row per (species x age x sex) class, so sequence_id is
    NOT a unique key. Which collapse is correct depends on the response:

      response="events"    -> one row per (deployment, sequence, species).
                              Use for diel activity, occupancy, detection events.
      response="abundance" -> same rows, but group_size SUMMED across the age/sex
                              classes. Use whenever counts of ANIMALS matter;
                              deduplicating instead silently drops individuals
                              (2.2% of animals in the reference dataset).

    Returns a DataFrame with an added n_class_rows column recording how many
    age/sex rows were folded in, so the collapse is auditable.
    """
    if response not in ("events", "abundance"):
        raise ValueError("response must be 'events' or 'abundance'")
    keys = [dep_col, seq_col, species_col]
    missing = [k for k in keys if k not in df.columns]
    if missing:
        raise KeyError(f"missing columns: {missing}")
    g = df.groupby(keys, dropna=False)
    out = g.head(1).copy()
    out = out.set_index(keys)
    out["n_class_rows"] = g.size()
    if response == "abundance":
        if group_col not in df.columns:
            raise KeyError(f"{group_col} not in columns; cannot sum abundance")
        out[group_col] = g[group_col].sum()
    return out.reset_index()


def sequence_class_audit(df, seq_col="sequence_id", species_col="common_name",
                         age_col="age", sex_col="sex", group_col="group_size"):
    """Report how sequences are split across species and age/sex classes.

    Run this before choosing a collapse rule. Returns a dict with the number of
    multi-row sequences, how many are multi-SPECIES versus same-species-split,
    how many groups vary by age or sex, and the fraction of animals that a naive
    deduplication would discard.
    """
    import numpy as np
    n_rows = len(df)
    sizes = df.groupby(seq_col).size()
    multi = sizes[sizes > 1].index
    sub = df[df[seq_col].isin(multi)]
    nsp = sub.groupby(seq_col)[species_col].nunique()
    res = {"rows": int(n_rows),
           "distinct_sequence_ids": int(df[seq_col].nunique()),
           "multi_row_sequences": int(len(multi)),
           "multi_species": int((nsp > 1).sum()),
           "same_species_split": int((nsp == 1).sum())}
    for col, name in ((age_col, "groups_varying_age"), (sex_col, "groups_varying_sex")):
        if col in df.columns:
            res[name] = int(sub.groupby([seq_col, species_col])[col].nunique().gt(1).sum())
    if group_col in df.columns:
        keys = [seq_col, species_col]
        summed = df.groupby(keys)[group_col].sum()
        first = df.groupby(keys)[group_col].first()
        lost = float((summed - first).sum())
        total = float(summed.sum())
        res["animals_lost_if_deduplicated"] = int(lost)
        res["pct_animals_lost_if_deduplicated"] = round(100 * lost / total, 2) if total else np.nan
    return res
