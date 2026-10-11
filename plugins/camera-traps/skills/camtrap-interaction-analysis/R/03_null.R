# =============================================================================
#  Part 3 -- circular-shift null
#
#  The decisive test. Everything up to here asks whether a term changes the
#  fitted curve; this asks whether the curve is distinguishable from one fitted
#  to data with NO cross-species timing in it at all.
#
#  Design: within each camera, shift the DRIVER's event times by a random WHOLE
#  number of days and wrap inside the deployment window. This preserves
#    - the driver's detection rate at that camera,
#    - the driver's time-of-day distribution (exactly -- whole-day shifts),
#    - the driver's own burst/self-clustering structure within a day,
#    - the response process completely untouched,
#    - camera-level heterogeneity in both species,
#  and destroys only the alignment between the two species' event times. So a
#  driver-lag curve that survives is cross-species timing; one that the null
#  reproduces is an artifact of rate, clock, and clustering.
#
#  Effect size is the RANGE of the fitted driver smooth on the log-hazard scale
#  over the fitted lag window -- the same quantity for observed and null fits.
#  artifact_ratio = median(null range) / observed range. Ratios near or above 1
#  mean the observed curve is uninterpretable (convention from camera-trap-qc).
# =============================================================================

suppressPackageStartupMessages({ library(data.table); library(mgcv) })

#' Circularly shift one species' event times within each camera by whole days.
shift_driver <- function(events, dep, driver, rng) {
  ev  <- as.data.table(events)
  dp  <- as.data.table(dep)[, .(deployment_id, start_dt, end_dt)]
  drv_set <- if (identical(driver, "PREY_GUILD")) PREY_GUILD else driver

  d <- merge(ev[species %in% drv_set], dp, by = "deployment_id",
             suffixes = c("", ".dep"))
  span_days <- as.numeric(difftime(d$end_dt.dep, d$start_dt.dep, units = "days"))
  cams <- unique(d$deployment_id)
  off  <- setNames(
    vapply(cams, function(c1) {
      n <- floor(max(span_days[d$deployment_id == c1]))
      if (n < 3) 0 else sample.int(n - 1L, 1L)
    }, numeric(1)), cams)

  # Shift the DAY INDEX, keeping the within-day offset untouched. Wrapping on the
  # raw elapsed time instead would break exact time-of-day preservation, because
  # deployment spans are not whole numbers of days.
  d[, elapsed_s := as.numeric(difftime(timestamp, start_dt.dep, units = "secs"))]
  d[, n_days    := floor(as.numeric(difftime(end_dt.dep, start_dt.dep, units = "days")))]
  d[, day_i     := floor(elapsed_s / 86400)]
  d[, within_s  := elapsed_s - day_i * 86400]
  d[, new_day   := (day_i + off[deployment_id]) %% pmax(n_days, 1L)]
  d[, timestamp := start_dt.dep + new_day * 86400 + within_s]
  # derived time fields must follow the shifted timestamp, not the original
  d[, hour := clock_hour(timestamp)]
  sw <- solar_window(d$timestamp, d$latitude, d$longitude)
  d[, `:=`(sunrise_h = sw$sunrise, sunset_h = sw$sunset)]
  d[, is_night := hour < sunrise_h | hour > sunset_h]
  d[, days_since_start := as.numeric(difftime(timestamp, start_dt, units = "days"))]

  rbind(ev[!species %in% drv_set],
        d[, names(ev), with = FALSE])[order(deployment_id, timestamp)]
}

#' Range of the fitted driver smooth on the log-hazard scale.
driver_range <- function(mod, ped, n = 200) {
  cur <- lag_curve(mod, ped, n = n)
  diff(range(cur$fit))
}

#' Observed-vs-null comparison for one driver/response pair.
#' Only the full model (M4-equivalent: camera RE + self-term + cyclic time of
#' day, truncated lag range) is refitted per replicate -- that is the model the
#' inference would be based on.
null_test <- function(events, dep, driver, response, n_rep = 199,
                      bin_h = 1, max_lag_h = 48, k_lag = 20, seed = 1) {
  set.seed(seed)
  fit_one <- function(ev) {
    p <- build_ped(ev, dep, driver, response, bin_h = bin_h, max_lag_h = max_lag_h)
    m <- bam(n_event ~ offset(log_exposure) + s(t_since_drv, k = k_lag) +
               s(cam, bs = "re") + s(t_since_own_f, k = k_lag, by = own_seen) +
               s(tod, bs = "cc", k = 12),
             family = poisson(), data = as.data.frame(p),
             discrete = TRUE, nthreads = 4)
    list(range = driver_range(m, p),
         p = summary(m)$s.table["s(t_since_drv)", "p-value"],
         edf = summary(m)$s.table["s(t_since_drv)", "edf"])
  }

  obs <- fit_one(events)
  nulls <- vector("list", n_rep)
  for (i in seq_len(n_rep)) {
    nulls[[i]] <- tryCatch(fit_one(shift_driver(events, dep, driver)),
                           error = function(e) list(range = NA_real_, p = NA_real_,
                                                    edf = NA_real_))
  }
  nr <- vapply(nulls, `[[`, numeric(1), "range")
  np <- vapply(nulls, `[[`, numeric(1), "p")

  list(driver = driver, response = paste(response, collapse = "+"),
       observed_range = obs$range, observed_p = obs$p, observed_edf = obs$edf,
       null_range_median = median(nr, na.rm = TRUE),
       null_range_q95 = quantile(nr, .95, na.rm = TRUE, names = FALSE),
       artifact_ratio = median(nr, na.rm = TRUE) / obs$range,
       p_vs_null = (1 + sum(nr >= obs$range, na.rm = TRUE)) / (1 + sum(!is.na(nr))),
       null_p_below_05 = mean(np < .05, na.rm = TRUE),
       n_rep_ok = sum(!is.na(nr)), null_ranges = nr)
}
