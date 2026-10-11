# =============================================================================
#  Part 2 -- Piece-wise exponential additive mixed model (PAMM)
#
#  Ferry et al. 2024 (MEE) reframe "does species B respond to species A" as a
#  RECURRENT event problem: model the hazard (visitation rate) of B as a smooth
#  function of time since the last occurrence of A, using every occurrence
#  rather than only the first. A piece-wise exponential model is a Poisson GAM
#  on a fine time grid with log-exposure as an offset, so the whole mgcv
#  toolbox applies -- which is what lets us add the two terms the diagnosis
#  needs: B's own self-excitation, and a cyclic time-of-day smooth.
#
#  The model set is nested on purpose. Each step removes one candidate
#  explanation for the shape seen in the original fit:
#    M0  driver smooth only                  <- reproduces the original curves
#    M1  + camera random intercept           <- detection LEVEL heterogeneity
#    M2  + time since B's own last event     <- B's self-excitation
#    M3  + cyclic time of day                <- diel mismatch
#    M4  = M3 refitted on a truncated lag range where the risk set is adequate
# =============================================================================

suppressPackageStartupMessages({
  library(data.table); library(mgcv); library(dplyr)
})

PREY_GUILD <- c("Central American Agouti", "Spotted Paca",
                "Common Opossum", "Great Tinamou")

# -- piece-wise exponential data (PED) ----------------------------------------

#' Build the piece-wise exponential grid for one driver/response pair.
#'
#' One row per (camera, time bin). `n_event` counts response events in the bin,
#' `log_exposure` is the offset, and the two elapsed-time covariates are
#' evaluated at the bin midpoint so that no bin uses information from its own
#' interior.
#'
#' Bins are uniform in CLOCK time, which is what keeps exposure constant across
#' bins. (Any sun-anchored rescaling would make per-bin exposure vary and the
#' offset would then have to be computed analytically rather than assumed.)
#'
#' @param bin_h bin width in hours.
#' @param max_lag_h keep only bins whose time-since-driver is at or below this.
build_ped <- function(events, dep, driver, response, bin_h = 1,
                      max_lag_h = 24 * 8, drop_flags = "zero_detections") {

  keep <- dep$deployment_id[!dep$qc_flag %in% drop_flags]
  ev   <- as.data.table(events)[deployment_id %in% keep]
  dp   <- as.data.table(dep)[deployment_id %in% keep]
  resp_set <- if (identical(response, "PREY_GUILD")) PREY_GUILD else response
  drv_set  <- if (identical(driver,   "PREY_GUILD")) PREY_GUILD else driver

  out <- vector("list", nrow(dp))
  for (i in seq_len(nrow(dp))) {
    cam   <- dp$deployment_id[i]
    t0    <- dp$start_dt[i]; t1 <- dp$end_dt[i]
    edges <- seq(t0, t1, by = bin_h * 3600)
    if (length(edges) < 3) next
    nb    <- length(edges) - 1L
    lo    <- edges[-length(edges)]; hi <- edges[-1]
    mid   <- lo + (hi - lo) / 2

    e_cam <- ev[deployment_id == cam]
    t_drv <- sort(e_cam[species %in% drv_set, timestamp])
    t_rsp <- sort(e_cam[species %in% resp_set, timestamp])

    # events per bin (right-open bins, so every event lands in exactly one)
    n_event <- if (length(t_rsp))
      as.integer(tabulate(findInterval(as.numeric(t_rsp), as.numeric(edges),
                                       rightmost.closed = TRUE), nbins = nb)) else
      integer(nb)

    # hours since the most recent driver event strictly before the bin midpoint
    since <- function(times, at) {
      if (!length(times)) return(rep(NA_real_, length(at)))
      k <- findInterval(as.numeric(at) - 1e-9, as.numeric(times))
      ifelse(k == 0, NA_real_, (as.numeric(at) - as.numeric(times)[pmax(k, 1)]) / 3600)
    }

    out[[i]] <- data.table(
      deployment_id = cam,
      grid          = dp$grid[i],
      bin_mid       = mid,
      n_event       = n_event,
      exposure_h    = as.numeric(difftime(hi, lo, units = "hours")),
      t_since_drv   = since(t_drv, mid),
      t_since_own   = since(t_rsp, mid),
      tod           = as.numeric(format(mid, "%H")) +
                      as.numeric(format(mid, "%M")) / 60,
      day_of_survey = as.numeric(difftime(mid, t0, units = "days"))
    )
  }
  ped <- rbindlist(out)
  ped <- ped[!is.na(t_since_drv) & t_since_drv <= max_lag_h]
  # self-term is undefined before the response species' first detection; a
  # separate indicator keeps those bins in the fit instead of discarding them
  ped[, `:=`(own_seen = as.integer(!is.na(t_since_own)),
             t_since_own_f = fifelse(is.na(t_since_own), 0, t_since_own),
             log_exposure  = log(exposure_h),
             cam = factor(deployment_id))]
  ped[]
}

# -- the nested model set -----------------------------------------------------

fit_pamm_set <- function(ped, max_lag_h_trunc = 48, k_lag = 20) {
  f <- function(form, dat)
    bam(form, family = poisson(), data = as.data.frame(dat),
        discrete = TRUE, nthreads = 4, select = FALSE)

  m0 <- f(n_event ~ offset(log_exposure) + s(t_since_drv, k = k_lag), ped)
  m1 <- f(n_event ~ offset(log_exposure) + s(t_since_drv, k = k_lag) +
            s(cam, bs = "re"), ped)
  m2 <- f(n_event ~ offset(log_exposure) + s(t_since_drv, k = k_lag) +
            s(cam, bs = "re") + s(t_since_own_f, k = k_lag, by = own_seen), ped)
  m3 <- f(n_event ~ offset(log_exposure) + s(t_since_drv, k = k_lag) +
            s(cam, bs = "re") + s(t_since_own_f, k = k_lag, by = own_seen) +
            s(tod, bs = "cc", k = 12), ped)
  pedt <- ped[t_since_drv <= max_lag_h_trunc]
  m4 <- f(n_event ~ offset(log_exposure) + s(t_since_drv, k = k_lag) +
            s(cam, bs = "re") + s(t_since_own_f, k = k_lag, by = own_seen) +
            s(tod, bs = "cc", k = 12), pedt)

  list(M0 = m0, M1 = m1, M2 = m2, M3 = m3, M4 = m4,
       ped = ped, ped_trunc = pedt)
}

#' Marginal driver-lag curve on the log-hazard scale, with a pointwise 95% band.
#' Other terms are held at reference values (self-term at its median, midday,
#' population-average camera) so curves are comparable across models.
lag_curve <- function(mod, ped, n = 200, max_lag_h = NULL) {
  hi <- max_lag_h %||% max(ped$t_since_drv)
  nd <- data.table(
    t_since_drv   = seq(min(ped$t_since_drv), hi, length.out = n),
    t_since_own_f = median(ped$t_since_own_f),
    own_seen      = 1,
    tod           = 12,
    cam           = ped$cam[1],
    log_exposure  = 0)
  trm <- unlist(lapply(mod$smooth, function(s) s$label))
  excl <- grep("cam", trm, value = TRUE)
  p <- predict(mod, newdata = as.data.frame(nd), type = "link",
               se.fit = TRUE, exclude = excl, newdata.guaranteed = FALSE)
  data.table(t_since_drv = nd$t_since_drv, fit = as.numeric(p$fit),
             lo = as.numeric(p$fit - 1.96 * p$se.fit),
             hi = as.numeric(p$fit + 1.96 * p$se.fit))
}
`%||%` <- function(a, b) if (is.null(a)) b else a

#' Risk-set / support table: how much data actually underpins each lag bin.
lag_support <- function(ped, breaks = c(0, 6, 12, 24, 48, 72, 120, 168, 192)) {
  d <- copy(ped)
  d[, lag_bin := cut(t_since_drv, breaks, right = FALSE, include.lowest = TRUE)]
  d[, .(bins = .N, camera_days = sum(exposure_h) / 24,
        events = sum(n_event), cameras = uniqueN(deployment_id)),
    by = lag_bin][order(lag_bin)]
}
