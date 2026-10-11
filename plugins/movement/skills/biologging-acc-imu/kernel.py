"""Helpers for animal-borne accelerometer / IMU data. See SKILL.md."""

import numpy as np
import pandas as pd

MIN_SAMPLES = 6
STATIC_WINDOW_S = 1.0
MIN_BURSTS_FOR_FIT = 200
GPS_SENSOR_ID = 653
ACC_SENSOR_ID = 2365683


def epoch_seconds(ts):
    """Seconds since the Unix epoch, independent of the index's time unit.

    DatetimeIndex.asi8 returns int64 in the index's OWN unit: nanoseconds for
    pd.date_range, but MICROseconds for timestamps that have been through a
    Parquet round-trip. Dividing asi8 by 1e9 unconditionally is wrong by 1000x
    on exactly the data that comes back from disk, and it fails silently -- solar
    events land decades away from the timestamps and every row is discarded as
    unbracketed. Synthetic checks built with date_range will not catch it.
    """
    return pd.DatetimeIndex(ts).as_unit("ns").asi8 / 1e9


def burst_metrics(raw, freq, n_axes=3):
    """Mean VeDBA and ODBA of one burst payload ('x y z x y z ...' string).

    Returns (vedba, odba, n_samples), both nan when the burst is too short to
    estimate a static component. VeDBA first because it is the default metric:
    it is the rotation-invariant one, unchanged if the tag sits at a different
    angle on the collar, whereas ODBA's L1 sum depends on how a given
    acceleration vector is distributed across the axes.

      VeDBA = mean over samples of sqrt(dx^2 + dy^2 + dz^2)
      ODBA  = mean over samples of (|dx| + |dy| + |dz|)

    Bounded by VeDBA <= ODBA <= sqrt(3) * VeDBA, so on one tag the two are
    near-perfectly monotonically related and a classification built on either
    agrees with the other on ~99.8% of bursts; expect a VeDBA threshold about
    two thirds of the ODBA one. Parses tolerantly: a malformed tail costs that
    burst, not the whole chunk.
    """
    if not isinstance(raw, str):
        return np.nan, np.nan, 0
    try:
        v = np.fromstring(raw, sep=" ")
        if v.size == 0:
            raise ValueError("empty")
    except Exception:
        vals = []
        for tok in raw.split():
            try:
                vals.append(float(tok))
            except ValueError:
                break
        if not vals:
            return np.nan, np.nan, 0
        v = np.asarray(vals, float)
    n = v.size // n_axes
    if n < MIN_SAMPLES:
        return np.nan, np.nan, n
    a = v[:n * n_axes].reshape(n, n_axes).astype(float)
    w = max(int(round(STATIC_WINDOW_S * float(freq))), 1)
    if w >= n:
        static = a.mean(axis=0, keepdims=True)
    else:
        kern = np.ones(w) / w
        static = np.column_stack([np.convolve(a[:, j], kern, mode="same")
                                  for j in range(n_axes)])
        static = static / np.convolve(np.ones(n), kern, mode="same")[:, None]
    dyn = a - static
    return (float(np.sqrt((dyn ** 2).sum(axis=1)).mean()),
            float(np.abs(dyn).sum(axis=1).mean()), n)


def bursts_to_metrics(df, raw_col="eobs_accelerations_raw",
                      freq_col="eobs_acceleration_sampling_frequency_per_axis",
                      axes_col="eobs_acceleration_axes", default_freq=10.0):
    """Reduce a frame of Movebank burst rows to (vedba, odba, n_samples) arrays.

    Fetch acceleration in MONTHLY time windows and write each window to disk
    before moving on. Raw burst payloads are large, and a fetch that accumulates
    several months of them in memory before writing will slow to a crawl and can
    exhaust RAM on a single large study; per-window files also make the job
    resumable after a dropped connection, which is common on long pulls.
    """
    freq = pd.to_numeric(df[freq_col], errors="coerce").fillna(default_freq).to_numpy()
    if axes_col in df.columns:
        nax = df[axes_col].fillna("XYZ").astype(str).str.len().to_numpy()
    else:
        nax = np.full(len(df), 3)
    ve = np.empty(len(df))
    od = np.empty(len(df))
    ns = np.empty(len(df), dtype=int)
    for i, (raw, f, k_) in enumerate(zip(df[raw_col].to_numpy(), freq, nax)):
        ve[i], od[i], ns[i] = burst_metrics(raw, f, int(k_) if k_ in (1, 2, 3) else 3)
    return ve, od, ns


def classify_two_state(metric, group, random_state=0, max_fit=60000):
    """Two-state Gaussian mixture on log(metric), fitted per GROUP.

    Pass SPECIES as `group` for a species-level threshold, which is the default
    recommendation: reportable, transferable to a new animal without refitting,
    and measured to agree with per-animal thresholds on 96.9% of bursts across
    96 animals of 7 species. Pass individual ids instead only when the mode
    separation is too small to pool (see below).

    Returns (active, fitted, info): booleans per row, plus a dict per group of
    {cut, mu_rest, mu_active, sep_d, n}. `cut` is the log-scale threshold, so
    exp(cut) is the threshold in the metric's own units. `sep_d` is the
    standardised distance between the two component means.

    CHECK sep_d BEFORE TRUSTING A POOLED CUT. Above about 3 the modes barely
    overlap and pooling is safe even though per-animal boundaries may span a
    factor of ten. Below about 1 the two states are not resolved at all; between
    those, fit per individual instead.

    Do not normalise each animal by its own median and apply a group-level
    multiplier: the median sits at a different position relative to the two
    modes depending on the animal's duty cycle, so it injects the between-animal
    variation it appears to remove.
    """
    from sklearn.mixture import GaussianMixture
    metric = np.asarray(metric, float)
    group = np.asarray(group)
    active = np.zeros(metric.size, dtype=bool)
    fitted = np.zeros(metric.size, dtype=bool)
    info = {}
    good = np.isfinite(metric) & (metric > 0)
    rng = np.random.default_rng(random_state)
    for gval in pd.unique(group):
        m = (group == gval) & good
        if m.sum() < MIN_BURSTS_FOR_FIT:
            continue
        lx = np.log(metric[m])
        fit_x = lx if lx.size <= max_fit else lx[rng.choice(lx.size, max_fit, replace=False)]
        gm = GaussianMixture(n_components=2, random_state=random_state,
                             n_init=3).fit(fit_x.reshape(-1, 1))
        o = np.argsort(gm.means_.ravel())
        mu = gm.means_.ravel()[o]
        sd = np.sqrt(gm.covariances_.ravel()[o])
        grid = np.linspace(mu[0] - 3 * sd[0], mu[1] + 3 * sd[1], 4000)
        post = gm.predict_proba(grid.reshape(-1, 1))[:, o[1]]
        cut = float(grid[np.argmin(np.abs(post - 0.5))])
        active[m] = lx > cut
        fitted[m] = True
        info[gval] = dict(cut=cut, threshold=float(np.exp(cut)),
                          mu_rest=float(mu[0]), mu_active=float(mu[1]),
                          sep_d=float((mu[1] - mu[0]) / np.sqrt((sd[0] ** 2 + sd[1] ** 2) / 2)),
                          n=int(m.sum()))
    return active, fitted, info


def solar_events(ts_utc, lat, lon):
    """Sunrise and sunset in UTC hours past midnight of each timestamp's date.

    NOAA algorithm. Values may fall outside [0, 24) when the event lands on an
    adjacent UTC date; that is intentional. Returns
    (sunrise_h, sunset_h, polar_day, polar_night). Validated to within 5 min
    of published times from 51N to the equator at both solstices.
    """
    ts = pd.DatetimeIndex(ts_utc)
    lat = np.asarray(lat, float)
    lon = np.asarray(lon, float)
    jd_mid = epoch_seconds(ts.normalize()) / 86400.0 + 2440587.5
    # solar terms count from the Julian day NUMBER, which begins at noon, so
    # they take jd_mid + 0.5 while the conversion back to hours takes jd_mid.
    # Using one for both puts sunrise and sunset exactly 12 h out and still
    # leaves solar noon correct, so a transit check alone will not catch it.
    J = ((jd_mid + 0.5) - 2451545.0 + 0.0008) - lon / 360.0
    M = np.radians((357.5291 + 0.98560028 * J) % 360)
    C = 1.9148 * np.sin(M) + 0.0200 * np.sin(2 * M) + 0.0003 * np.sin(3 * M)
    lam = np.radians((np.degrees(M) + C + 180 + 102.9372) % 360)
    Jtr = 2451545.0 + J + 0.0053 * np.sin(M) - 0.0069 * np.sin(2 * lam)
    decl = np.arcsin(np.sin(lam) * np.sin(np.radians(23.4397)))
    cosw = ((np.sin(np.radians(-0.833)) - np.sin(np.radians(lat)) * np.sin(decl))
            / (np.cos(np.radians(lat)) * np.cos(decl)))
    w = np.arccos(np.clip(cosw, -1.0, 1.0))
    return ((Jtr - np.degrees(w) / 360.0 - jd_mid) * 24.0,
            (Jtr + np.degrees(w) / 360.0 - jd_mid) * 24.0,
            cosw < -1.0, cosw > 1.0)


def event_epochs(ts_utc, lat, lon, day_offsets=(-2, -1, 0, 1, 2)):
    """Absolute epoch seconds of sunrise/sunset on several adjacent dates.

    Returns (sunrise, sunset, polar), each (n_timestamps, n_offsets). Absolute
    epochs rather than hours-past-midnight are what makes the bracketing in
    sun_anchored_time correct at every longitude: a sunset whose UTC hour
    exceeds 24 simply lands on the next calendar day.
    """
    ts = pd.DatetimeIndex(ts_utc)
    SR, SS, POL = [], [], []
    for k in day_offsets:
        tk = ts + pd.Timedelta(days=int(k))
        midnight = epoch_seconds(tk.normalize())
        sr_h, ss_h, pday, pnight = solar_events(tk, lat, lon)
        SR.append(midnight + sr_h * 3600.0)
        SS.append(midnight + ss_h * 3600.0)
        POL.append(pday | pnight)
    return np.column_stack(SR), np.column_stack(SS), np.column_stack(POL)


def sun_anchored_time(ts_utc, lat, lon):
    """Map UTC timestamps to sun-anchored time: 0 sunrise, 12 sunset, 24 sunrise.

    Each timestamp is bracketed by the most recent solar event at or before it
    and the next one after it, on ABSOLUTE epoch seconds. Day and night are each
    rescaled to 12 units, so an hour of sun-anchored time is not an hour of clock
    time; any count model over these bins needs a matching effort offset.

    Do not implement this by comparing UTC hour-of-date against a sunset in
    hours past that midnight: wherever sunset falls after 00:00 UTC (any
    western-hemisphere longitude) that sunset exceeds 24, the daytime branch
    cannot reach 12, and real late-afternoon samples are pushed into the night
    branch leaving whole stretches of the curve exactly empty. Anchor checks
    still pass in that state. Verify COVERAGE instead: uniform sampling in clock
    time must give a sun-anchored histogram with no empty bins (see
    effort_by_bin).

    Returns (sun_time, valid); valid is False at polar day or night.
    """
    ts = pd.DatetimeIndex(ts_utc)
    t = epoch_seconds(ts)
    SR, SS, POL = event_epochs(ts, lat, lon)
    last_sr = np.where(SR <= t[:, None], SR, -np.inf).max(axis=1)
    last_ss = np.where(SS <= t[:, None], SS, -np.inf).max(axis=1)
    next_sr = np.where(SR > t[:, None], SR, np.inf).min(axis=1)
    next_ss = np.where(SS > t[:, None], SS, np.inf).min(axis=1)
    with np.errstate(invalid="ignore", divide="ignore"):
        day = 12.0 * (t - last_sr) / (next_ss - last_sr)
        night = 12.0 + 12.0 * (t - last_ss) / (next_sr - last_ss)
    out = np.where(last_sr > last_ss, day, night)
    ok = (np.isfinite(last_sr) & np.isfinite(last_ss) & np.isfinite(next_sr)
          & np.isfinite(next_ss) & ~POL.any(axis=1) & np.isfinite(out)
          & (out >= 0) & (out < 24))
    return np.mod(out, 24.0), ok


def effort_by_bin(sun_time, n_bins=24):
    """Relative sampling effort per sun-anchored bin, 1.0 = uniform.

    Check this before taking a maximum of any diel curve: a zero means the
    bin is unsampled, not that activity was zero there.
    """
    b = np.clip((np.asarray(sun_time) / (24.0 / n_bins)).astype(int), 0, n_bins - 1)
    c = np.bincount(b, minlength=n_bins).astype(float)
    return c / c.sum() * n_bins
