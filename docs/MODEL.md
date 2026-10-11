# The Model

This document describes exactly what the simulator computes: the equations, the parameters, the interventions, the numerical method, and the summary metrics. It also lists the assumptions behind them and the limits of what the results mean.

> **This is an educational simulation, not a forecast.** It shows how epidemics behave in an idealized population. It has not been fitted to data from any real outbreak, and its numbers should not be used to predict real cases, plan health services, or make medical decisions.

---

## 1. Compartments

Every person is in exactly one compartment at any time. The compartments hold real numbers (for example, 12.4 people) rather than whole people.

| Symbol | Compartment | Meaning |
|---|---|---|
| S | Susceptible | Can be infected |
| E | Exposed (SEIR only) | Infected but not yet infectious: the latent period |
| I | Infected | Infected and infectious |
| R | Recovered | Recovered and permanently immune |
| V | Vaccinated | Vaccinated on day 0 and not (yet) infected; see §4 |

The population is closed, so the total never changes: **S + E + I + R + V = N** on every day. In the SIR model, E is always 0.

## 2. Equations

### SIR

```
dS/dt = −β · S · I / N
dI/dt =  β · S · I / N − γ · I
dR/dt =  γ · I
```

### SEIR

```
dS/dt = −β · S · I / N
dE/dt =  β · S · I / N − σ · E
dI/dt =  σ · E − γ · I
dR/dt =  γ · I
```

Both models share one simulation engine. The only difference is where a new infection goes: straight to I (SIR) or to E first (SEIR).

With a leaky vaccine, V is also infected (§4), adding a term `m · β · V · I / N` that flows out of V and into I (SIR) or E (SEIR). When contact reduction is active, β is replaced by `β · (1 − r)` (§5).

### Parameters

| Symbol | Meaning | Unit | App control | Default |
|---|---|---|---|---|
| N | Total population | people | Population | 10,000 |
| I₀ | Infectious on day 0 (E₀ = R₀ = 0) | people | Initially infected | 10 |
| β | Transmission rate: new infections caused per infectious person per day, in a fully susceptible population | 1/day | Infection rate β | 0.357 (from R₀ = 2.5 and D = 7 days) |
| γ | Recovery rate | 1/day | Recovery rate γ | 0.143 (1 / 7 days) |
| σ | Progression rate from E to I | 1/day | Mean latent period (days), as σ = 1 / period | 5 days (σ = 0.2) |
| — | Simulation length | days | Days to simulate (10–730) | 365 |
| k | Euler steps per day (§6) | — | Simulation steps per day | 4 |

The app opens in **SEIR** mode and takes the disease as **R₀ and mean infectious period D** (defaults R₀ = 2.5, D = 7 days). It converts them with γ = 1/D and β = R₀ · γ. The disease can instead be entered as the rates β and γ; switching between the two input modes converts the current values, rounded to the slider steps. The default interventions are 30% vaccination coverage at 90% effectiveness (all-or-nothing) and a 30% contact reduction from day 14, never lifted. These defaults are illustrative: chosen to show a clear outbreak and clear differences between scenarios, not to describe any real disease. The R₀ slider runs from 0.5 to 20 and the β slider from 0.01 to 3 per day, so every preset below fits.

### Disease presets

The **Disease preset** menu fills in R₀ and the mean infectious and latent periods with rounded values typical of published estimates. It does not change the model (SIR or SEIR), the population, or the interventions. SIR ignores the latent period. Moving any disease slider afterwards sets the menu back to **Custom**.

| Preset | R₀ | Published R₀ estimates | Infectious period D | Latent period |
|---|---|---|---|---|
| COVID-19 (original strain, 2020) | 2.5 | about 2–3.5 | 5 days | 3 days |
| COVID-19 (Delta variant, 2021) | 5 | about 3–8 | 5 days | 2 days |
| Seasonal influenza | 1.3 | about 1.2–1.4 | 4 days | 2 days |
| 1918 pandemic influenza | 2 | about 1.5–3 | 4 days | 2 days |
| Measles | 15 | about 12–18 | 5 days | 8 days |
| Chickenpox | 10 | about 7–12 | 7 days | 14 days |

R₀ values follow Liu et al. (2020) and Liu & Rocklöv (2021) for COVID-19, Biggerstaff et al. (2014) for influenza, and Anderson & May (1991) and Keeling & Rohani (2008) for measles and chickenpox. The periods are rounded values of the kind used in teaching models. They are not fitted to data. Keep in mind:

- Published estimates vary by place, time, and method. One number cannot describe a disease.
- The model still applies its own assumptions (§10). It has no deaths, which matters for the 1918 influenza. Everyone starts susceptible, but real seasonal influenza meets partial prior immunity. People mix equally, and waiting times are exponential, so the presets show how each disease behaves *in this model*. They are not predictions.
- High-R₀ presets (measles, Delta) need more steps per day to stay within the step-error tolerance (§6). The status area says when.

### Mean periods and exponential waiting times

γ and σ are rates: each day, a fraction γ of infected people recover and a fraction σ of exposed people become infectious. This assumes the time a person spends in I (or E) follows an **exponential distribution**, with mean infectious period **1/γ** and mean latent period **1/σ**.

The exponential distribution is "memoryless": someone who has been infectious for a week is exactly as likely to recover tomorrow as someone infected yesterday. Real latent and infectious periods are more tightly clustered around their average. The model therefore lets a few people leave a stage almost at once and lets a few stay far longer than is realistic. The averages are right, but the spread is not.

**Latent period vs. incubation period:** the *latent* period (infected → infectious) is what E models. The *incubation* period (infected → symptoms) is a different quantity. The model has no symptoms, so the app's control is labeled "mean latent period".

## 3. Reproduction numbers

**Basic reproduction number** R₀ = β / γ: the average number of people one infectious person infects in a fully susceptible population. It is β new infections per day times 1/γ days of being infectious. If γ = 0, R₀ is infinite.

R₀ is the **same in SIR and SEIR**. The latent stage delays when someone becomes infectious but does not change how long they stay infectious, because the model has no deaths during E.

**Effective reproduction number at day 0**, shown as "Rₑ at day 0":

```
Rₑ(0) = R₀ · c(0) · (S₀ + m · V₀) / N
```

Here m is the susceptibility of vaccinated people (§4), and c(0) is the contact multiplier at time 0: (1 − r) if a contact reduction is active on day 0, otherwise 1. This is the value **at day 0 only**. Rₑ falls as people are infected, rises if a contact reduction is lifted, and does not include a contact reduction that starts later.

**What Rₑ < 1 means.** On average, each infected person causes fewer than one new infection, so each "generation" of cases is smaller than the one before and the outbreak dies out. Summing those shrinking generations gives a bound that the tests check: total new infections ≤ I₀ · Rₑ / (1 − Rₑ).

Rₑ < 1 does **not** guarantee that the number of people in E + I or I falls on every single day. In SIR, I does fall from day 0 when Rₑ(0) < 1 and no intervention changes later. In SEIR, I could rise temporarily if many people started in E, and E + I can change direction once a time-limited intervention ends.

**Final size.** With no interventions, an SIR or SEIR epidemic that runs to completion leaves S∞ susceptible people, where

```
S∞ / N = (S₀ / N) · exp(−R₀ · (1 − S∞ / N))
```

(Kermack & McKendrick, 1927, with nobody recovered at the start). The latent period does not appear: E changes **when** people are infected, not **how many** are eventually infected. The tests check the simulator against this equation.

## 4. Vaccination

Vaccination happens once, at day 0, to the initially susceptible people (N − I₀). **Coverage c** is the fraction vaccinated. What **effectiveness e** means depends on the vaccine model.

| Vaccine model | Meaning of e | At day 0 | Susceptibility m of V |
|---|---|---|---|
| **All-or-nothing** (default) | Fraction of vaccinated people who become fully immune | V₀ = c · e · S₀. The c · (1 − e) · S₀ vaccine failures stay in S. | 0 (V is never infected) |
| **Leaky** | Reduction in each vaccinated person's chance of infection per contact | V₀ = c · S₀ | 1 − e |

- With e = 100%, the two models give identical results.
- With the same c and e, both give the same Rₑ(0). Over time they diverge, because a leaky vaccine allows **breakthrough infections**.
- What V counts differs by model. Under all-or-nothing, V holds only the protected people. Under leaky, V holds every vaccinated person not yet infected, so the V line falls as breakthroughs happen.
- Assumptions: protection starts immediately and never wanes; vaccination does not change how infectious a breakthrough case is; nobody is vaccinated after day 0.

## 5. Contact reduction

Contact reduction represents distancing, masking, or other non-pharmaceutical interventions. Since β is roughly (contacts per day) × (chance a contact transmits), reducing either one scales β:

```
β(t) = β · (1 − r)   if start_day ≤ t < end_day
β(t) = β             otherwise
```

- **r** is the reduction (0–90% in the app). The end day is optional; without one, the reduction is never lifted. The end day itself is unrestricted.
- In the simulation, each Euler step uses the multiplier at the time the step starts (§6).
- A permanent reduction starting on day 0 is exactly the same as running with a lower β.
- **Rebound:** if restrictions lift while most people are still susceptible, Rₑ jumps back up and infections grow again. Lifting a reduction early mostly delays the epidemic rather than preventing it.

## 6. Numerical method

The equations describe continuous change. The simulator approximates them with the **forward Euler method**: it computes each flow's current rate, assumes that rate stays constant for a short step of length Δt = 1/k days, and advances. For SEIR, one step is:

```
new infections   = β(t) · I · S / N · Δt          capped at S
breakthroughs    = β(t) · I · m · V / N · Δt      capped at V
progressions     = σ · E · Δt                     capped at E
recoveries       = γ · I · Δt                     capped at I

S ← S − new infections
V ← V − breakthroughs
E ← E + new infections + breakthroughs − progressions
I ← I + progressions − recoveries
R ← R + recoveries
```

- **Simultaneous update.** All flows in a step are computed from the state at the start of the step and then applied together, so the order of the update lines does not change the result.
- **Caps keep compartments nonnegative.** With large rates or large steps, a flow could otherwise take more people than a compartment holds. Each compartment has only one outflow, so capping that flow at the compartment's size is enough. The caps rarely trigger with realistic settings and small steps.
- **Conservation.** Every flow leaves one compartment and enters another, so S + E + I + R + V = N holds exactly, up to floating-point rounding (tested to 10⁻⁹ · N), even when a cap triggers.
- **Daily output.** Results are recorded once per day (after k steps), from day 0 to the last day.

**Accuracy.** Forward Euler is a first-order method: its error shrinks roughly in proportion to Δt. Euler overestimates the final epidemic size slightly. Measured against the final-size equation (§3), with N = 1,000 and I₀ = 1:

| R₀ (β, γ) | 1 step/day | 4 steps/day | 10 steps/day |
|---|---|---|---|
| 3.0 (0.3, 0.1) | +0.66% | +0.16% | +0.06% |
| 2.0 (0.5, 0.25) | +1.85% | +0.44% | +0.18% |
| 1.67 (0.05, 0.03) | +0.18% | +0.05% | +0.02% |

The app offers 1, 4, 10, 20, and 50 steps per day. The default is **4**. **1 step per day** is the legacy setting: it reproduces the original version of this app exactly, which a regression test checks.

The final size is the most forgiving measure. The **shape and timing** of the curve need smaller steps when rates are fast. Measured as the largest daily difference in I from a near-exact run (800 steps per day), relative to the peak:

| Disease | 1 step/day | 4 | 10 | 20 | 50 |
|---|---|---|---|---|---|
| β = 0.05, γ = 0.03 (Phase 1 defaults) | 1.5% | 0.4% | 0.1% | 0.1% | 0.0% |
| β = 0.5, γ = 0.03 (rate sliders at maximum) | 28% | 7.5% | 3.0% | 1.5% | 0.6% |
| R₀ = 4, infectious period 1 day | 105% | 49% | 22% | 10% | 3.8% |
| SEIR example (β = 0.3, γ = 0.1, 5-day latent period) | 7.5% | 1.8% | 0.7% | 0.4% | 0.1% |
| SEIR app defaults, no intervention (R₀ = 2.5, 7-day infectious, 5-day latent, N = 10,000, I₀ = 10, 365 days) | 8.7% | 2.1% | 0.8% | 0.4% | 0.2% |

**Estimating the error while the app runs: step doubling.** Because Euler's error is roughly proportional to Δt, halving the step roughly halves the error. The app therefore re-runs every scenario with twice the steps per day and compares:

```
estimated error ≈ 2 × max over days |I_k(t) − I_2k(t)| ÷ peak of I_2k
```

The app always shows this estimate (the largest across the four scenarios) in its status area. If it exceeds **5%**, the status becomes a warning with the approximate number of steps needed (k × error ÷ 5%, rounded up to an offered setting). The estimate matches the true error closely while no cap is triggering. When caps trigger (very fast rates at few steps), it tends to overestimate, so the warning errs on the side of caution.

## 7. Summary metrics

Each scenario reports the following, computed from its daily results (days 0 to D, which is n = D + 1 values).

### Epidemiological metrics

| Metric | Formula | Interpretation and limitations |
|---|---|---|
| Peak infected | max over days of I | The largest number infectious on any recorded day. A peak between daily samples is not seen. |
| Peak day | first day on which I equals its maximum | When the peak happens. If I only falls, the peak day is 0. |
| New infections | (S₀ − S_D) + (V₀ − V_D) | Infections that happen **during** the simulation. Every infection moves someone out of S or V, so this counts them exactly, including people still in E at the end. |
| Cumulative infections | E₀ + I₀ + new infections | Everyone infected at any point, **including** the initially infected. (E₀ is always 0 in this app.) |
| Attack rate | cumulative infections ÷ N | The fraction of the **whole population** ever infected. The denominator is N, not the number initially susceptible. Vaccinated people are included in N, so vaccination lowers the attack rate partly by making people immune. |
| Infections averted (by last day) | baseline new infections − scenario new infections | Compared with the "No intervention" scenario. All scenarios start with the same I₀, so it is the same whether new or cumulative infections are used. **It counts only infections up to the last simulated day.** An intervention that merely delays infections (such as a contact reduction lifted later) can look far more effective in a short run than over the whole epidemic. For example, with R₀ = 3 and a 50% reduction for the first 40 days, a 60-day run shows about 465 infections averted, but a run long enough for the epidemic to finish shows about 3. The app warns whenever any scenario is still infected at the end. |
| R₀, Rₑ at day 0 | §3 | Rₑ(0) is a snapshot at day 0, not over the whole run. |
| Still infected at end | E_D + I_D ≥ 1 person | If true, the simulation ended before the epidemic did, so infection totals and infections averted are **incomplete**: run more days to see the final size. It does not say whether infections are growing or shrinking. The 1-person threshold is needed because compartments approach 0 without ever reaching it. In this deterministic model, a flag of false does not strictly rule out later regrowth from a fraction of a person if Rₑ is above 1 (for example, right after a contact reduction ends). |

### Descriptive statistics of the infected curve

These summarize the **daily infected counts I₀, I₁, …, I_D** as a set of n = D + 1 numbers.

| Statistic | Formula | Interpretation |
|---|---|---|
| Mean infected | x̄ = (Σ Iₜ) / n | The average number infectious on a simulated day. Mean × n approximates total "person-days" of infection. |
| Median infected | the middle value of the sorted Iₜ (average of the two middle values when n is even) | Half of the simulated days had more people infected than this, half fewer. It is usually well below the mean, because an epidemic curve has a few very high days and many low ones (right-skewed). |
| SD infected | σ = √( Σ (Iₜ − x̄)² / n ) | How far the daily counts typically are from their mean: how "peaked" versus flat the curve is. |

**Why the SD divides by n, not n − 1.** In statistics classes, the sample SD divides by n − 1 to correct for estimating a population's spread from a sample. Here the simulated days are not a sample from anything: they are the complete set of values being described. So the population formula (divide by n) is used.

**What these statistics do not mean.** The model is **deterministic**: the same inputs always give exactly the same curve. There is no random sampling and no measurement error, so:

- the SD is **not** a measure of uncertainty and does not give a confidence interval or a margin of error;
- differences between scenarios are not "statistically significant" or "non-significant." They are exact consequences of the inputs, and no hypothesis test applies;
- all four statistics depend on the chosen number of days. Extending the run with days of near-zero infections lowers the mean, median, and SD without anything about the epidemic changing. Compare scenarios only at the same run length (the app always does).

Measuring real uncertainty would need a **stochastic** model run many times. That is planned for Phase 5 (see ROADMAP.md).

## 8. Scenarios

The app runs four scenarios that share the same population, run length, steps per day, and disease parameters. Only the interventions differ:

1. **No intervention:** the baseline
2. **Vaccination only:** the chosen vaccination settings
3. **Contact reduction only:** the chosen contact reduction settings
4. **Vaccination + contact reduction:** both. This is exactly the user's chosen settings and is the scenario drawn in the main chart.

## 9. How the app presents results

The dashboard displays the quantities defined above without changing them. A few presentation rules affect how they look:

- **Status area.** Above the tabs, the app always shows the step-doubling error estimate (§6) and whether every scenario's outbreak is over by the last day ("Still infected at end", §7), naming any scenario that is not.
- **Three kinds of numbers.** The app separates (1) **model results**, which are deterministic; (2) **numerical error**, the estimated gap between the Euler approximation and the exact solution of the equations (§6), which says nothing about whether the equations are realistic; and (3) **statistical uncertainty**, from chance or uncertain parameters, which this model does **not** measure (§7).
- **Logarithmic y-axis.** Zero has no position on a log axis. On log charts, daily values below **0.01 people**, including zeros, are left out (the line has a gap there), and the chart states how many values were left out. Linear charts draw every value and start at 0.
- **Statistics tab.** The mean and median are drawn as reference lines on the infected curve. A box plot shows each scenario's daily infected counts (median, quartiles, mean, and unusually high days). These describe one deterministic curve across simulated days, not uncertainty across possible outbreaks (§7).
- **Colors and line patterns.** Each compartment and each scenario has a fixed color and line pattern, so a series looks the same on every chart and can be identified without color.
- **CSV downloads.** Daily results in long format with columns `scenario, day, S, E, I, R, V` (your scenario, or all four), and the scenario summary table with one row per scenario. Values are not rounded. Attack rate is a fraction from 0 to 1.
- **Caching.** Results are cached by their exact inputs, so returning to earlier settings shows the same results without recomputing them.

## 10. Assumptions and limitations

- **Homogeneous mixing:** everyone is equally likely to contact everyone else. There are no households, age groups, locations, or networks.
- **Closed population:** no births, deaths from any cause, or migration. The disease is never fatal in this model.
- **Permanent immunity** after recovery or vaccination: no waning and no reinfection.
- **Exponential waiting times** in E and I (§2).
- **Deterministic and continuous:** no chance events, and fractional people. Small outbreaks are not realistic: a real outbreak starting from 2 people can die out by chance, but the model's never does when Rₑ > 1.
- **Fixed parameters:** β, γ, and σ do not change over time, except β under contact reduction. There is no seasonality and no behavior change in response to the epidemic.
- **Vaccination only at day 0,** with immediate, permanent protection.
- **Numerical approximation:** results are Euler approximations of the equations, with the errors given in §6.
- **Not fitted to data:** default values are illustrative and do not describe any particular disease. The disease presets (§2) use rounded published values but are not fitted to any outbreak.

## References

- Anderson, R. M., & May, R. M. (1991). *Infectious Diseases of Humans: Dynamics and Control*. Oxford University Press.
- Biggerstaff, M., Cauchemez, S., Reed, C., Gambhir, M., & Finelli, L. (2014). Estimates of the reproduction number for seasonal, pandemic, and zoonotic influenza: a systematic review of the literature. *BMC Infectious Diseases*, 14, 480.
- Kermack, W. O., & McKendrick, A. G. (1927). A contribution to the mathematical theory of epidemics. *Proceedings of the Royal Society of London, Series A*, 115(772), 700–721.
- Keeling, M. J., & Rohani, P. (2008). *Modeling Infectious Diseases in Humans and Animals*. Princeton University Press.
- Liu, Y., Gayle, A. A., Wilder-Smith, A., & Rocklöv, J. (2020). The reproductive number of COVID-19 is higher compared to SARS coronavirus. *Journal of Travel Medicine*, 27(2), taaa021.
- Liu, Y., & Rocklöv, J. (2021). The reproductive number of the Delta variant of SARS-CoV-2 is far higher compared to the ancestral SARS-CoV-2 virus. *Journal of Travel Medicine*, 28(7), taab124.
