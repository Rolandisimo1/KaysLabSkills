# =============================================================================
#  Part 7 -- interval structure: risk sets and self-clustering
#
#  These are the model-free diagnostics. They decide, before any smooth is
#  fitted, how much of the lag axis is actually supported by data and how much
#  of the short-lag structure is each species' own clustering.
# =============================================================================

suppressPackageStartupMessages({ library(data.table) })

#' Time from each driver event to the next response event at the same camera,
#' with ADMINISTRATIVE CENSORING at the deployment end.
#'
#' The censoring matters: an interval that never closes because the camera
#' stopped recording is not evidence of a long waiting time. Treating it as
#' "infinite" inflates the apparent risk set at long lags. `time_h` is the
#' observed lag when one exists and the remaining observation time otherwise,
#' so #{time_h > t} is the number of intervals genuinely still under
#' observation at lag t.
lag_table <- function(events, dep, driver, response,
                      drop_flags = "zero_detections") {
  keep <- dep$deployment_id[!dep$qc_flag %in% drop_flags]
  ev <- as.data.table(events)[deployment_id %in% keep]
  resp <- if (identical(response, "PREY_GUILD")) PREY_GUILD else response
  drv  <- if (identical(driver,   "PREY_GUILD")) PREY_GUILD else driver

  rbindlist(lapply(split(ev, ev$deployment_id), function(s) {
    dt <- sort(as.numeric(s[species %in% drv,  timestamp]))
    tt <- sort(as.numeric(s[species %in% resp, timestamp]))
    if (!length(dt)) return(NULL)
    end <- as.numeric(s$end_dt[1])
    k   <- findInterval(dt, tt, left.open = FALSE)  # #{tt <= dt}
    nxt <- ifelse(k < length(tt), tt[pmin(k + 1L, length(tt))], NA_real_)
    lag_h <- (nxt - dt) / 3600
    data.table(deployment_id = s$deployment_id[1],
               lag_h = lag_h,
               censor_h = (end - dt) / 3600,
               observed = !is.na(lag_h))
  }))[, time_h := fifelse(observed, lag_h, censor_h)][]
}

#' Observed share of short self-intervals against a Poisson process fitted at
#' each camera's own rate. Using the per-camera rate for the null removes
#' between-camera rate heterogeneity as an explanation, so what is left is
#' genuine within-camera clustering.
burst_table <- function(events, dep, species_list,
                        cuts = c(1, 3, 6, 12, 24), min_events = 5,
                        drop_flags = "zero_detections") {
  keep <- dep$deployment_id[!dep$qc_flag %in% drop_flags]
  ev <- as.data.table(events)[deployment_id %in% keep]
  dp <- as.data.table(dep)[deployment_id %in% keep]

  rbindlist(lapply(species_list, function(sp) {
    rows <- rbindlist(lapply(split(ev, ev$deployment_id), function(s) {
      t <- sort(as.numeric(s[species == sp, timestamp]))
      if (length(t) < min_events) return(NULL)
      dur_h <- dp[deployment_id == s$deployment_id[1], effort_days] * 24
      rate  <- length(t) / dur_h
      gaps  <- diff(t) / 3600
      data.table(cut = cuts,
                 obs = vapply(cuts, function(c1) mean(gaps <= c1), numeric(1)),
                 exp = 1 - exp(-rate * cuts),
                 n   = length(gaps))
    }))
    if (!nrow(rows)) return(NULL)
    rows[, .(species = sp, n_intervals = sum(n),
             obs_share = sum(obs * n) / sum(n),
             poisson_exp = sum(exp * n) / sum(n)), by = cut]
  }))[, ratio := obs_share / poisson_exp][]
}

#' Add a night indicator to a PED, for the diel-composition panel.
add_night_flag <- function(ped, lat = 9.152, lon = -79.847) {
  sw <- solar_window(ped$bin_mid, rep(lat, nrow(ped)), rep(lon, nrow(ped)))
  ped <- copy(as.data.table(ped))
  ped[, is_night_bin := tod < sw$sunrise | tod > sw$sunset][]
}
