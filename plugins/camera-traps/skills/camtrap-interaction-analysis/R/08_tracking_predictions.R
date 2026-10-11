# =============================================================================
#  Part 8 -- scoring the camera data against the GPS-collar study's
#            pre-stated predictions
#
#  The companion collar study (same species, same island, Mar-Jun 2024) closed
#  with five explicit predictions about what a camera-trap analysis "should
#  show", written before this camera dataset was analysed. Two of them are
#  directly testable here and are not part of the PAMM/Hawkes work:
#
#   P2  Diel activity overlap with ocelot should reproduce the collar-derived
#       RANKING and approximately the collar values:
#         deer 0.94 > coati 0.62 > tinamou 0.60 > opossum 0.49.
#       An inverted ranking (e.g. opossum above deer) would mean the collars'
#       diel fix failure had distorted their activity profiles.
#
#   P1/P4  Station-level co-occurrence should be POSITIVE: stations that detect
#       ocelot often should detect prey often, with no systematic deficit of
#       prey at ocelot-rich stations. A negative association would contradict
#       the collar result directly and is the cleanest falsification available.
#
#  (P3, the time-to-encounter prediction, is what R/02-R/05 already test. P5,
#  the opossum daytime, is reported as new information rather than a test.)
# =============================================================================

suppressPackageStartupMessages({ library(data.table); library(dplyr) })

COLLAR_OVERLAP <- c(`Red Brocket` = 0.94, `White-nosed Coati` = 0.62,
                    `Great Tinamou` = 0.60, `Common Opossum` = 0.49)

# -- Ridout & Linkie (2009) coefficients of activity overlap ------------------
#
#  The `overlap` package cannot be installed in this environment: it Imports
#  suntools, which requires sf/GDAL/GEOS. Delta-hat-1 and delta-hat-4 are
#  therefore implemented here from the published definitions, and validated by
#  recovering a known overlap from simulated von Mises mixtures
#  (overlap_recovery_check below). Both are reported; Ridout & Linkie recommend
#  delta-4 when the smaller sample exceeds ~50, which holds for every pair here.

#' von Mises kernel density on the circle, evaluated on a grid of radians.
#'
#' Vectorised as a single matrix operation: the loop form is O(grid x n)
#' interpreted calls and makes a 999-replicate bootstrap impractical. besselI
#' can overflow for large kappa, so the normalisation is done on the log scale.
vm_density <- function(x, kappa, grid) {
  # I0(kappa) = besselI(kappa, 0, expon.scaled = TRUE) * exp(kappa), so
  #   log(2*pi*I0) = log(2*pi) + log(bs) + kappa
  # and the kernel exponent kappa*cos(d) - log(2*pi*I0) becomes
  #   kappa*(cos(d) - 1) - log(2*pi) - log(bs),
  # whose first term is <= 0 for every d. No overflow at any kappa.
  log_norm <- log(2 * pi) + log(besselI(kappa, 0, expon.scaled = TRUE))
  M <- exp(kappa * (cos(outer(grid, x, "-")) - 1) - log_norm)
  as.numeric(M %*% rep(1 / length(x), length(x)))
}

#' Taylor (2008) plug-in bandwidth: concentration for the von Mises kernel,
#' derived from the MLE concentration of the data. This is the rule Ridout &
#' Linkie cite; it is a rule of thumb, not a data-adaptive selector.
vm_bandwidth <- function(x) {
  rbar <- sqrt(mean(cos(x))^2 + mean(sin(x))^2)
  # MLE of the von Mises concentration from the mean resultant length
  kmle <- if (rbar < 0.53) 2 * rbar + rbar^3 + 5 * rbar^5 / 6
          else if (rbar < 0.85) -0.4 + 1.39 * rbar + 0.43 / (1 - rbar)
          else 1 / (rbar^3 - 4 * rbar^2 + 3 * rbar)
  n <- length(x)
  num <- 3 * n * kmle^2 * besselI(2 * kmle, 2)
  den <- 4 * sqrt(pi) * besselI(kmle, 0)^2
  max((num / den)^(2 / 5), 0.1)
}

#' Coefficients of overlap between two sets of clock times (hours, 0-24).
#'
#' delta1 = integral of min(f1, f2) over the circle, by trapezoid on `n_grid`.
#' delta4 = the two-sided mean of min(1, f_other/f_self) evaluated AT the
#'          observations, which is better behaved at larger sample sizes.
activity_overlap <- function(h1, h2, n_grid = 512) {
  x1 <- h1 / 24 * 2 * pi; x2 <- h2 / 24 * 2 * pi
  k1 <- vm_bandwidth(x1);  k2 <- vm_bandwidth(x2)
  grid <- seq(0, 2 * pi, length.out = n_grid + 1)[-(n_grid + 1)]
  f1 <- vm_density(x1, k1, grid); f2 <- vm_density(x2, k2, grid)
  d1 <- sum(pmin(f1, f2)) * (2 * pi / n_grid)

  f1_at2 <- vm_density(x1, k1, x2); f2_at2 <- vm_density(x2, k2, x2)
  f1_at1 <- vm_density(x1, k1, x1); f2_at1 <- vm_density(x2, k2, x1)
  d4 <- 0.5 * (mean(pmin(1, f2_at1 / f1_at1)) +
               mean(pmin(1, f1_at2 / f2_at2)))
  list(delta1 = d1, delta4 = d4, kappa1 = k1, kappa2 = k2,
       grid_h = grid / (2 * pi) * 24, f1 = f1, f2 = f2)
}

#' Nonparametric bootstrap CI on delta4: resample the observed times with
#' replacement and re-estimate bandwidth and overlap in each replicate.
#'
#' A SMOOTHED bootstrap (resampling from the fitted kernel and then
#' re-smoothing) was tried first and rejected: it smooths twice, so the
#' replicate distribution is biased upward by more than the interval width and
#' neither a percentile nor a basic interval contains the point estimate. The
#' plain resampling bootstrap is `overlap::bootstrap`'s default for this reason.
overlap_boot <- function(h1, h2, n_boot = 500, seed = 1, n_grid = 256) {
  set.seed(seed)
  est <- vapply(seq_len(n_boot), function(b)
    activity_overlap(sample(h1, length(h1), replace = TRUE),
                     sample(h2, length(h2), replace = TRUE),
                     n_grid = n_grid)$delta4,
    numeric(1))
  obs <- activity_overlap(h1, h2, n_grid = n_grid)$delta4
  c(lo = unname(quantile(est, 0.025)), hi = unname(quantile(est, 0.975)),
    boot_mean = mean(est), bias = mean(est) - obs, sd = sd(est))
}

#' von Mises deviates by Best & Fisher (1979) rejection sampling.
circular_vm_noise <- function(n, kappa) {
  a <- 1 + sqrt(1 + 4 * kappa^2); b <- (a - sqrt(2 * a)) / (2 * kappa)
  r <- (1 + b^2) / (2 * b)
  out <- numeric(n); i <- 0L
  while (i < n) {
    u1 <- runif(1); z <- cos(pi * u1); f <- (1 + r * z) / (r + z)
    c0 <- kappa * (r - f); u2 <- runif(1)
    if (c0 * (2 - c0) - u2 > 0 || log(c0 / u2) + 1 - c0 >= 0) {
      i <- i + 1L
      out[i] <- sign(runif(1) - 0.5) * acos(f)
    }
  }
  out
}

#' Validation: recover a known overlap between two von Mises mixtures.
#' Truth is computed by numerical integration of the TRUE densities, so this
#' checks the estimator rather than restating it.
overlap_recovery_check <- function(n = 1000, seed = 42) {
  set.seed(seed)
  truth_pdf <- function(g, mu, kap) exp(kap * cos(g - mu)) / (2 * pi * besselI(kap, 0))
  cases <- list(
    list(m1 = 2, k1 = 3, m2 = 2,   k2 = 3),      # identical -> 1
    list(m1 = 0, k1 = 3, m2 = pi,  k2 = 3),      # antiphase -> low
    list(m1 = 0, k1 = 2, m2 = 1.2, k2 = 2))      # partial
  rbindlist(lapply(cases, function(cc) {
    g <- seq(0, 2 * pi, length.out = 4001)[-4001]
    true_d <- sum(pmin(truth_pdf(g, cc$m1, cc$k1),
                       truth_pdf(g, cc$m2, cc$k2))) * (2 * pi / 4000)
    h1 <- ((cc$m1 + circular_vm_noise(n, cc$k1)) %% (2 * pi)) / (2 * pi) * 24
    h2 <- ((cc$m2 + circular_vm_noise(n, cc$k2)) %% (2 * pi)) / (2 * pi) * 24
    o <- activity_overlap(h1, h2)
    data.table(case = sprintf("mu=%.1f/%.1f kappa=%g/%g", cc$m1, cc$m2, cc$k1, cc$k2),
               true_overlap = true_d, delta1 = o$delta1, delta4 = o$delta4)
  }))[, `:=`(err1 = delta1 - true_overlap, err4 = delta4 - true_overlap)][]
}

# -- P2: activity overlap against the collar predictions ---------------------
test_p2_activity <- function(events, predator = "Ocelot",
                             prey = names(COLLAR_OVERLAP), n_boot = 500) {
  ev <- as.data.table(events)
  hp <- ev[species == predator, hour]
  rbindlist(lapply(prey, function(sp) {
    hs <- ev[species == sp, hour]
    o <- activity_overlap(hp, hs)
    b <- overlap_boot(hp, hs, n_boot = n_boot)
    data.table(prey = sp, n_prey = length(hs), n_predator = length(hp),
               camera_delta4 = o$delta4, camera_delta1 = o$delta1,
               boot_lo = b[["lo"]], boot_hi = b[["hi"]],
               collar_prediction = COLLAR_OVERLAP[[sp]])
  }))[, `:=`(difference = camera_delta4 - collar_prediction,
             collar_inside_ci = collar_prediction >= boot_lo &
                                collar_prediction <= boot_hi)][]
}

# -- P1/P4: station-level co-occurrence --------------------------------------
#
#  Detection RATES for predator and prey share the effort denominator, which
#  can induce correlation on its own. The test is therefore a quasi-Poisson GLM
#  of the prey COUNT on the predator COUNT with log-effort as an offset, so
#  effort enters once and as an offset rather than inside both variables. The
#  Spearman correlation of rates is reported alongside as a rank check only.
test_p14_cooccurrence <- function(events, dep, predator = "Ocelot",
                                  prey = names(COLLAR_OVERLAP)) {
  dp <- as.data.table(dep)[qc_flag != "zero_detections"]
  ev <- as.data.table(events)
  wide <- dcast(ev[, .N, by = .(deployment_id, species)],
                deployment_id ~ species, value.var = "N", fill = 0)
  st <- merge(dp[, .(deployment_id, placename, grid, effort_days)], wide,
              by = "deployment_id", all.x = TRUE)
  for (cl in setdiff(names(st), c("deployment_id", "placename", "grid", "effort_days")))
    st[is.na(get(cl)), (cl) := 0]

  res <- rbindlist(lapply(prey, function(sp) {
    d <- data.table(prey_n = st[[sp]], pred_n = st[[predator]],
                    eff = st$effort_days, grid = st$grid)
    m <- glm(prey_n ~ pred_n + offset(log(eff)), family = quasipoisson(), data = d)
    cf <- summary(m)$coefficients["pred_n", ]
    mg <- glm(prey_n ~ pred_n + grid + offset(log(eff)), family = quasipoisson(), data = d)
    sp_rho <- suppressWarnings(cor.test(d$prey_n / d$eff, d$pred_n / d$eff,
                                        method = "spearman"))
    data.table(prey = sp, n_stations = nrow(d),
               slope = cf[["Estimate"]], se = cf[["Std. Error"]],
               p_value = cf[["Pr(>|t|)"]],
               slope_with_grid_term = summary(mg)$coefficients["pred_n", "Estimate"],
               spearman_rho = unname(sp_rho$estimate),
               spearman_p = sp_rho$p.value)
  }))
  res[, direction := fifelse(slope > 0, "positive (co-occurrence)",
                             "negative (avoidance)")]
  list(per_species = res[], stations = st[])
}
