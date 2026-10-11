# =============================================================================
#  Part 5 -- multivariate Hawkes process (MHP)
#
#  Model (Nicvert et al. 2024 Ecology, following Lambert et al. 2018 JCGS).
#  For species i at camera l the conditional intensity is
#
#     lambda_i^l(t) = ( nu_i  +  sum_j sum_k  alpha^k_{j->i} *
#                       N_j^l[ t - k*delta , t - (k-1)*delta ) )_+
#
#  i.e. a constant background rate nu_i plus a PIECEWISE-CONSTANT interaction
#  function f_{j->i} evaluated on K bins of width delta. alpha^k_{j->i} is the
#  average number of species-i occurrences gained (positive) or suppressed
#  (negative) per species-j occurrence, k bins later. Unlike a classical Hawkes
#  process the alphas may be NEGATIVE, which is what lets the model express
#  avoidance as well as attraction.
#
#  Two things about this formulation matter for our data and are stated up front:
#   * nu_i is a single CONSTANT per species. There is no time-of-day term
#     anywhere in the model. The authors flag this as a limitation and as future
#     work. With a nocturnal predator and diurnal prey, diel rhythm is therefore
#     an uncontrolled confound -- which is why every fit below is accompanied by
#     a circular-shift null that preserves time of day exactly (Part 3).
#   * f_{i->i} (self-excitation) is estimated as a function SEPARATE from
#     f_{j->i} (cross-excitation). That separation is structural here, whereas in
#     the PAMM it has to be added by hand. It is the reason the model is worth
#     fitting at all given the diel limitation.
#
#  ESTIMATION. The reference implementation (UnitEvents) is not on CRAN and was
#  not reachable from this environment, so the estimator is implemented here from
#  the paper's equations and VALIDATED by parameter recovery on simulated data
#  (see hawkes_recovery_check()). It is a weighted-LASSO penalised least-squares
#  fit: with c^l(t) = (1, {N_j^l[t-k*delta, t-(k-1)*delta)}_{j,k}) the contrast is
#
#     gamma(beta) = -2 beta' b_i + beta' G beta ,
#     b_i = sum_l sum_{T in N_i^l} c^l(T-) ,   G = sum_l integral c^l(t) c^l(t)' dt
#
#  minimised subject to an L1 penalty with Bernstein-type data-driven weights
#  (Hansen/Reynaud-Bouret). G depends only on the driver counts, so it is
#  computed once and reused for every response species.
# =============================================================================

suppressPackageStartupMessages({ library(data.table) })

#' Design pieces for one camera: G contribution and per-species b contributions.
#'
#' c^l(t) is piecewise constant and changes only at times T + k*delta, so the
#' integral is an exact finite sum over those breakpoints -- no discretisation.
#' The first K*delta of each deployment is dropped (burn-in): the count windows
#' there would reach back before the camera was recording, where no data exists.
hawkes_design_one <- function(times_by_sp, t_start, t_end, species, K, delta_h) {
  S  <- length(species)
  M  <- 1L + S * K
  dsec <- delta_h * 3600
  burn <- t_start + K * dsec
  if (t_end <= burn) return(NULL)

  # Count matrix C: one row per evaluation time, columns (1, {N_j[.,.]}_{j,k}).
  # Built with findInterval on the sorted event times, so each window count is a
  # binary search rather than a scan. cnt(x) = #{events strictly before x},
  # hence N_j[t-k*d, t-(k-1)*d) = cnt(t-(k-1)*d) - cnt(t-k*d), which excludes an
  # event at exactly t -- required, since the intensity is left-continuous.
  cmat <- function(tt) {
    C <- matrix(0, length(tt), M); C[, 1] <- 1
    for (s in seq_len(S)) {
      ts <- times_by_sp[[s]]
      if (!length(ts)) next
      # #{events strictly before x}. left.open=TRUE is load-bearing: an epsilon
      # offset (x - 1e-9) is invisible at POSIX-second magnitudes (~1.7e9, where
      # machine epsilon is ~4e-7), so every event would count ITSELF in its own
      # k=1 window and the self-excitation term would absorb the event count.
      cum <- function(x) findInterval(x, ts, left.open = TRUE)
      up <- cum(tt)                              # k = 1 upper edge is t itself
      for (k in seq_len(K)) {
        dn <- cum(tt - k * dsec)
        C[, 1L + (s - 1L) * K + k] <- up - dn
        up <- dn
      }
    }
    C
  }

  all_t <- unlist(times_by_sp, use.names = FALSE)
  bp <- c(burn, t_end, as.numeric(outer(all_t, (0:K) * dsec, "+")))
  bp <- sort(unique(bp[bp >= burn & bp <= t_end]))
  if (length(bp) < 2) return(NULL)

  lo <- bp[-length(bp)]; hi <- bp[-1]
  w  <- (hi - lo) / 3600                        # hours, so rates are per hour
  ok <- w > 0
  Cm <- cmat((lo[ok] + hi[ok]) / 2)
  G  <- crossprod(Cm, Cm * w[ok])

  b <- matrix(0, M, S)
  for (s in seq_len(S)) {
    ts <- times_by_sp[[s]]
    ts <- ts[ts >= burn & ts <= t_end]
    if (length(ts)) b[, s] <- colSums(cmat(ts))
  }
  list(G = G, b = b, dur_h = as.numeric(t_end - burn) / 3600)
}

#' Assemble the design across cameras.
hawkes_design <- function(events, dep, species, K = 6, delta_h = 6,
                          drop_flags = "zero_detections", jitter_ties = TRUE,
                          seed = 1) {
  set.seed(seed)
  sp_keep <- species
  ev <- as.data.table(events)[species %in% sp_keep]
  keep <- dep$deployment_id[!dep$qc_flag %in% drop_flags]
  ev <- ev[deployment_id %in% keep]
  dp <- as.data.table(dep)[deployment_id %in% keep]

  # The model disallows two species occurring at the same instant. 180 such ties
  # exist here; jitter them by up to +/- 1 min, as the paper does.
  if (jitter_ties) {
    ev[, tie := .N > 1, by = .(deployment_id, timestamp)]
    n_tie <- sum(ev$tie)
    if (n_tie) ev[tie == TRUE,
                  timestamp := timestamp + runif(.N, -60, 60)]
    ev[, tie := NULL]
  } else n_tie <- 0L

  S <- length(species); M <- 1L + S * K
  G <- matrix(0, M, M); b <- matrix(0, M, S); dur <- 0
  for (i in seq_len(nrow(dp))) {
    cam <- dp$deployment_id[i]
    e   <- ev[deployment_id == cam]
    tbs <- lapply(species, function(s) sort(as.numeric(e[species == s, timestamp])))
    one <- hawkes_design_one(tbs, as.numeric(dp$start_dt[i]),
                             as.numeric(dp$end_dt[i]), species, K, delta_h)
    if (is.null(one)) next
    G <- G + one$G; b <- b + one$b; dur <- dur + one$dur_h
  }
  dimnames(b) <- list(NULL, species)
  list(G = G, b = b, species = species, K = K, delta_h = delta_h,
       total_hours = dur, n_ties_jittered = n_tie,
       par_names = c("nu", paste0(rep(species, each = K), "_k", seq_len(K))))
}

#' Weighted-LASSO minimiser of  -2 b'beta + beta'G beta + 2 d'|beta|
#' by cyclic coordinate descent. The background rate (coordinate 1) is not
#' penalised: shrinking it toward zero would be nonsensical.
lasso_ls <- function(G, b, d, max_iter = 5000, tol = 1e-10) {
  M <- length(b); beta <- numeric(M); dg <- diag(G)
  d[1] <- 0
  for (it in seq_len(max_iter)) {
    delta_max <- 0
    for (m in seq_len(M)) {
      if (dg[m] <= 0) { beta[m] <- 0; next }
      r <- b[m] - sum(G[m, ] * beta) + G[m, m] * beta[m]
      new <- sign(r) * max(abs(r) - d[m], 0) / dg[m]
      delta_max <- max(delta_max, abs(new - beta[m]))
      beta[m] <- new
    }
    if (delta_max < tol) break
  }
  beta
}

#' Bernstein-type data-driven penalty weights (Hansen et al. / Reynaud-Bouret).
#' V is the observed quadratic variation of each coordinate; gamma scales the
#' whole penalty and is the paper's tuning constant (they use 0.5).
penalty_weights <- function(G, b_i, V_i, sup_i, M, gamma = 0.5) {
  lg <- log(max(M, 2))
  gamma * (sqrt(2 * V_i * lg) + sup_i * lg / 3)
}

#' Fit the MHP: one weighted-LASSO solve per response species.
hawkes_fit <- function(design, gamma = 0.5) {
  G <- design$G; b <- design$b
  S <- length(design$species); K <- design$K; M <- nrow(G)
  # quadratic-variation proxy and sup-norm per coordinate, from the diagonal of
  # G scaled to the event counts: V_m ~ sum over events of c_m^2
  res <- matrix(NA_real_, M, S,
                dimnames = list(design$par_names, design$species))
  for (s in seq_len(S)) {
    V   <- pmax(b[, s], 0)                       # counts are non-negative
    sup <- pmax(sqrt(pmax(diag(G), 0) / max(design$total_hours, 1)), 1)
    d   <- penalty_weights(G, b[, s], V, sup, M, gamma)
    res[, s] <- lasso_ls(G, b[, s], d)
  }
  # tidy: alpha^k_{j->i}
  alpha <- CJ(k = seq_len(K), driver = design$species, response = design$species,
              sorted = FALSE)
  alpha[, value := mapply(function(kk, jj, ii)
    res[1L + (match(jj, design$species) - 1L) * K + kk, ii], k, driver, response)]
  list(coef = res, alpha = alpha[], nu = res[1, ],
       species = design$species, K = K, delta_h = design$delta_h,
       gamma = gamma)
}

# -- simulation + recovery check ----------------------------------------------

#' Simulate an MHP by Ogata thinning on one "camera" of length T_h hours.
hawkes_simulate <- function(nu, alpha, K, delta_h, T_h, seed = NULL) {
  if (!is.null(seed)) set.seed(seed)
  S <- length(nu); dsec <- delta_h
  times <- vector("list", S); for (s in seq_len(S)) times[[s]] <- numeric(0)
  lam <- function(t) {
    out <- nu
    for (j in seq_len(S)) {
      tj <- times[[j]]
      if (!length(tj)) next
      for (k in seq_len(K)) {
        n <- sum(tj >= t - k * dsec & tj < t - (k - 1) * dsec)
        if (n) out <- out + alpha[k, j, ] * n
      }
    }
    pmax(out, 0)
  }
  lam_max <- sum(nu) + sum(pmax(alpha, 0)) * 6
  t <- 0
  while (t < T_h) {
    t <- t + rexp(1, lam_max)
    if (t >= T_h) break
    l <- lam(t)
    if (runif(1) < sum(l) / lam_max) {
      s <- sample.int(S, 1, prob = l / sum(l))
      times[[s]] <- c(times[[s]], t)
    }
  }
  times
}

#' Parameter-recovery check. Simulates a 2-species process with a known
#' attraction and a known repulsion, fits with the estimator above, and returns
#' true vs recovered interaction functions.
hawkes_recovery_check <- function(n_cam = 25, T_h = 24 * 400, K = 4,
                                  delta_h = 6, gamma = 0.5, seed = 42) {
  set.seed(seed)
  S <- 2; sp <- c("A", "B")
  nu <- c(A = 0.02, B = 0.01)                     # per hour
  alpha <- array(0, dim = c(K, S, S))             # [k, driver, response]
  alpha[1, 1, 2] <-  0.010                        # A attracts B, first bin
  alpha[2, 1, 2] <-  0.005
  alpha[1, 2, 1] <- -0.004                        # B repels A, first bin
  alpha[1, 1, 1] <-  0.008                        # A self-excites

  sim <- lapply(seq_len(n_cam), function(i)
    hawkes_simulate(nu, alpha, K, delta_h, T_h))

  ev <- rbindlist(lapply(seq_along(sim), function(i) {
    rbindlist(lapply(seq_len(S), function(s) {
      if (!length(sim[[i]][[s]])) return(NULL)
      data.table(deployment_id = paste0("SIM", i), species = sp[s],
                 timestamp = as.POSIXct("2024-01-01", tz = "UTC") +
                             sim[[i]][[s]] * 3600)
    }))
  }))
  dp <- data.table(deployment_id = paste0("SIM", seq_len(n_cam)),
                   start_dt = as.POSIXct("2024-01-01", tz = "UTC"),
                   end_dt = as.POSIXct("2024-01-01", tz = "UTC") + T_h * 3600,
                   qc_flag = "ok")

  des <- hawkes_design(ev, dp, sp, K = K, delta_h = delta_h, jitter_ties = TRUE)
  fit <- hawkes_fit(des, gamma = gamma)

  truth <- CJ(k = seq_len(K), driver = sp, response = sp, sorted = FALSE)
  truth[, true_value := mapply(function(kk, jj, ii)
    alpha[kk, match(jj, sp), match(ii, sp)], k, driver, response)]
  out <- merge(fit$alpha, truth, by = c("k", "driver", "response"))
  out <- out[order(driver, response, k)]

  # Guards. These are what make a re-implementation usable instead of merely
  # plausible: the estimator must recover the background rates, put the right
  # sign on every non-zero interaction, and leave the true zeros at zero.
  nz <- out[true_value != 0]; zs <- out[true_value == 0]
  checks <- c(
    nu_within_25pct = all(abs(fit$nu - nu) / nu < 0.25),
    signs_correct   = all(sign(nz$value) == sign(nz$true_value)),
    zeros_small     = max(abs(zs$value)) < 0.1 * min(abs(nz$true_value)),
    magnitude_ok    = all(abs(nz$value - nz$true_value) <
                          0.5 * abs(nz$true_value) + 1e-4))
  if (!all(checks))
    warning("Hawkes estimator failed recovery: ",
            paste(names(checks)[!checks], collapse = ", "))

  list(comparison = out, checks = checks,
       nu_true = nu, nu_hat = fit$nu, n_events = nrow(ev), fit = fit)
}

# -- null reference for the interaction functions -----------------------------

#' Shift EVERY species independently by its own whole-day offset at every
#' camera. Whole-day shifts leave each species' time-of-day distribution and its
#' own within-day event structure untouched -- so the SELF interaction functions
#' f_{i->i} are preserved by construction and the CROSS functions f_{j->i} lose
#' all alignment. That asymmetry is exactly what we want: it gives a null band
#' for the cross terms while holding the self terms fixed, which is the one
#' comparison the MHP cannot make internally because it has no diel term.
shift_all_species <- function(events, dep) {
  ev <- as.data.table(events)
  dp <- as.data.table(dep)[, .(deployment_id, start_dt, end_dt)]
  d  <- merge(ev, dp, by = "deployment_id", suffixes = c("", ".dep"))
  d[, n_days := floor(as.numeric(difftime(end_dt.dep, start_dt.dep, units = "days")))]
  d[, elapsed_s := as.numeric(difftime(timestamp, start_dt.dep, units = "secs"))]
  d[, day_i    := floor(elapsed_s / 86400)]
  d[, within_s := elapsed_s - day_i * 86400]
  # one offset per (camera, species)
  d[, off := sample.int(max(pmax(n_days, 2L) - 1L, 1L), 1L),
    by = .(deployment_id, species)]
  d[, new_day   := (day_i + off) %% pmax(n_days, 1L)]
  d[, timestamp := start_dt.dep + new_day * 86400 + within_s]
  d[, names(ev), with = FALSE][order(deployment_id, timestamp)]
}

#' Observed fit plus a null distribution for every interaction function.
hawkes_with_null <- function(events, dep, species, K = 6, delta_h = 6,
                             gamma = 0.5, n_rep = 199, seed = 11) {
  des <- hawkes_design(events, dep, species, K = K, delta_h = delta_h)
  obs <- hawkes_fit(des, gamma = gamma)

  set.seed(seed)
  reps <- vector("list", n_rep)
  for (i in seq_len(n_rep)) {
    evn <- shift_all_species(events, dep)
    dn  <- hawkes_design(evn, dep, species, K = K, delta_h = delta_h,
                         seed = 1000 + i)
    reps[[i]] <- hawkes_fit(dn, gamma = gamma)$alpha[, rep := i]
  }
  nulls <- rbindlist(reps)

  band <- nulls[, .(null_lo = quantile(value, .025, names = FALSE),
                    null_hi = quantile(value, .975, names = FALSE),
                    null_med = median(value),
                    prop_nonzero = mean(value != 0)),
                by = .(k, driver, response)]

  res <- merge(obs$alpha, band, by = c("k", "driver", "response"))
  res[, `:=`(is_self = driver == response,
             outside_null = value < null_lo | value > null_hi)]
  list(design = des, fit = obs, alpha = res[order(driver, response, k)],
       nulls = nulls, n_rep = n_rep, K = K, delta_h = delta_h, gamma = gamma)
}

