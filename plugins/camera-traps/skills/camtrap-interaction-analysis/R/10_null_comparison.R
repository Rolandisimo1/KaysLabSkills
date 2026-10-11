# =============================================================================
#  Part 10 -- why an earlier study of THIS system found avoidance and we do not
#
#  Swinkels et al. (2023, J Mammal 104:137-145) analysed camera-trap data from
#  Barro Colorado Island with the same focal predator (ocelot) and overlapping
#  prey, and reported significant predator avoidance: prey appeared later after
#  an ocelot passage than their null allowed (median 5.43 h observed vs
#  3.92 h null, P < 0.001), plus prey tracking in the reverse direction.
#
#  Their null (their Statistical analysis section): "within each location, we
#  shuffled the date among observations to retain the spatial pattern in local
#  and seasonal abundance of animals across the data set, while keeping time and
#  species together to retain the activity patterns of specific species."
#
#  That null preserves each camera's detection rate and each species'
#  time-of-day distribution -- but it does NOT preserve WITHIN-DAY clustering,
#  because each detection's date is reassigned independently, so a burst of
#  three agouti inside one hour is scattered across three different days.
#
#  This matters because burstiness lengthens typical waiting times at a fixed
#  rate: events pile into bursts and leave long empty stretches between them.
#  A null that removes burstiness therefore produces SHORTER waits than the
#  data, making the observed interval look long -- avoidance -- with no
#  interaction present. Figure 2c measures that burstiness directly here
#  (3.2x for agouti, 11.7x for ocelot at sub-hour gaps).
#
#  The whole-day circular shift used in R/03_null.R preserves within-day
#  structure by construction, because it moves the day index and leaves the
#  within-day offset untouched.
#
#  This module runs BOTH nulls against the SAME observed statistic on the SAME
#  data. If the date-shuffle null returns avoidance and the day-shift null does
#  not, the disagreement between the two studies is located in the null rather
#  than in the island.
# =============================================================================

suppressPackageStartupMessages({
  library(data.table); library(survival)
})

PREY_SWINKELS <- c("Central American Agouti", "Spotted Paca", "Red Brocket",
                   "White-nosed Coati", "Great Tinamou", "Common Opossum",
                   "Nine-banded Armadillo")
NONTARGET <- "Human"

#' Consecutive-event intervals from a predator detection to the next prey
#' detection, following Swinkels et al.: the interval is CENSORED when the next
#' detection is a non-target animal or another predator (a competing event) or
#' when the deployment ends, and intervals beyond `max_days` are dropped.
swinkels_intervals <- function(ev, dp, predator = "Ocelot",
                               prey = PREY_SWINKELS, max_days = 3) {
  ev <- as.data.table(ev)[order(deployment_id, timestamp)]
  dp <- as.data.table(dp)
  end <- setNames(as.numeric(dp$end_dt), dp$deployment_id)
  rbindlist(lapply(split(ev, ev$deployment_id), function(s) {
    tt <- as.numeric(s$timestamp); sp <- s$species
    i <- which(sp == predator)
    if (!length(i)) return(NULL)
    nxt <- i + 1L
    has_next <- nxt <= length(sp)
    t_next <- ifelse(has_next, tt[pmin(nxt, length(tt))],
                     end[[s$deployment_id[1]]])
    sp_next <- ifelse(has_next, sp[pmin(nxt, length(sp))], NA_character_)
    data.table(deployment_id = s$deployment_id[1],
               t_h = (t_next - tt[i]) / 3600,
               event = !is.na(sp_next) & sp_next %in% prey)
  }))[t_h > 0 & t_h <= max_days * 24][]
}

#' Their summary statistic: the rate of a fitted Weibull, expressed as the
#' constant-hazard equivalent 1 / E[T]. Reported alongside the median interval,
#' which is the quantity they quote in the text.
weibull_hazard <- function(d) {
  if (sum(d$event) < 10) return(c(hazard = NA_real_, median_h = NA_real_))
  fit <- try(survreg(Surv(t_h, event) ~ 1, data = d, dist = "weibull"),
             silent = TRUE)
  if (inherits(fit, "try-error")) return(c(hazard = NA_real_, median_h = NA_real_))
  scale_w <- exp(coef(fit)[[1]]); shape_w <- 1 / fit$scale
  c(hazard = 1 / (scale_w * gamma(1 + 1 / shape_w)),
    median_h = scale_w * log(2)^(1 / shape_w))
}

# -- null 1: Swinkels date shuffle -------------------------------------------
#' Within each camera, permute the DATE across detections while each detection
#' keeps its own time of day and species. Preserves per-camera rate, per-species
#' diel profile and seasonal date pool; destroys within-day clustering.
shuffle_dates <- function(ev) {
  d <- as.data.table(ev)[, .(deployment_id, species, timestamp)]
  d[, `:=`(date = as.Date(timestamp, tz = BCI_TZ),
           tod_s = as.numeric(timestamp) -
                   as.numeric(as.POSIXct(paste(as.Date(timestamp, tz = BCI_TZ),
                                               "00:00:00"), tz = BCI_TZ)))]
  d[, date := sample(date), by = deployment_id]
  d[, timestamp := as.POSIXct(paste(date, "00:00:00"), tz = BCI_TZ) + tod_s]
  d[order(deployment_id, timestamp), .(deployment_id, species, timestamp)]
}

# -- null 2: whole-day circular shift of the predator only -------------------
#' As R/03_null.R: shift the predator's DAY INDEX within the deployment window,
#' leaving the within-day offset untouched, so time of day AND within-day
#' clustering are both preserved exactly.
shift_predator_days <- function(ev, dp, predator = "Ocelot") {
  d <- as.data.table(ev)[, .(deployment_id, species, timestamp)]
  dp <- as.data.table(dp)[, .(deployment_id, s0 = start_dt, e0 = end_dt)]
  d <- merge(d, dp, by = "deployment_id", all.x = TRUE)
  p <- d[species == predator]
  p[, elapsed := as.numeric(difftime(timestamp, s0, units = "secs"))]
  p[, nd := floor(as.numeric(difftime(e0, s0, units = "days")))]
  p[, day_i := floor(elapsed / 86400)]
  p[, within_s := elapsed - day_i * 86400]
  off <- p[, .(o = sample.int(max(nd[1], 1L), 1L) - 1L), by = deployment_id]
  p <- merge(p, off, by = "deployment_id")
  p[, timestamp := s0 + ((day_i + o) %% pmax(nd, 1L)) * 86400 + within_s]
  rbind(d[species != predator, .(deployment_id, species, timestamp)],
        p[, .(deployment_id, species, timestamp)])[order(deployment_id, timestamp)]
}

#' Run the observed statistic against both nulls.
compare_nulls <- function(ev, dp, n_rep = 499, predator = "Ocelot",
                          prey = PREY_SWINKELS, max_days = 3, seed = 1) {
  set.seed(seed)
  obs <- weibull_hazard(swinkels_intervals(ev, dp, predator, prey, max_days))

  run <- function(fn) {
    m <- vapply(seq_len(n_rep), function(i)
      weibull_hazard(swinkels_intervals(fn(), dp, predator, prey, max_days)),
      numeric(2))
    list(hazard = m["hazard", ], median_h = m["median_h", ])
  }
  n_date  <- run(function() shuffle_dates(ev))
  n_shift <- run(function() shift_predator_days(ev, dp, predator))

  # avoidance = observed hazard LOWER than null (prey take longer to appear)
  tab <- function(nm, nl) data.table(
    null = nm,
    obs_hazard = obs[["hazard"]], null_hazard_median = median(nl$hazard, na.rm = TRUE),
    obs_median_h = obs[["median_h"]],
    null_median_h = median(nl$median_h, na.rm = TRUE),
    p_avoidance = (1 + sum(nl$hazard <= obs[["hazard"]], na.rm = TRUE)) /
                  (1 + sum(!is.na(nl$hazard))),
    n_rep_ok = sum(!is.na(nl$hazard)))
  res <- rbind(tab("Swinkels date shuffle (destroys within-day bursts)", n_date),
               tab("whole-day circular shift (preserves bursts)", n_shift))
  res[, verdict := fifelse(p_avoidance < 0.05, "AVOIDANCE (p < 0.05)", "no effect")]
  list(table = res[], nulls = list(date = n_date, shift = n_shift), obs = obs)
}
