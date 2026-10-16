# IB Foundations track (Track A): catalogue and syllabus mapping

> **ADDITIVE TRACK. This document adds to SimForge; it replaces nothing.** The existing
> roadmap (Track B, the Advanced Simulation Studio: Phases 0-7 in `ROADMAP.md`) is unchanged
> in scope, content and order. No Track B item may be removed, downgraded, merged away or
> postponed indefinitely because of this track. See "Preservation rule" below.

**Status:** proposed, awaiting review (2026-10-16). Nothing in this catalogue is implemented.

## Purpose
Track A adds simpler, interactive simulations aligned with the IB Diploma Programme courses the
author is studying: **Physics HL** (including SL core) and **Economics SL** (with HL-only items
marked as optional extensions). Each simulation should let a student experiment, see cause and
effect, and then explain the result in their own words. The standards are the same as Track B:
stated assumptions and units, validated inputs, independent reference tests, and approximations
labelled as such.

## Preservation rule (non-negotiable)
1. Track B (Phases 0-7 and every item in the capability map) stays exactly as written in
   `ROADMAP.md`. Track A is listed in its own section and never edits Track B's phases.
2. Where a Track A module covers a topic that Track B also covers (collisions, oscillators,
   AD-AS, the multiplier, orbits, kinetic theory, regression), the Track A module is an
   **introductory precursor**. The Track B item remains planned in full.
3. Track A modules are slotted *between* Track B steps. They never block or reorder Track B.
4. Shared code is extracted only when real modules from both tracks need it (the existing
   two-examples rule).

## Syllabus sources and their limits
| Course | Guide that applies | Confidence |
|---|---|---|
| Physics SL/HL | *Physics guide, first assessment 2025* (first teaching 2023). Five themes: A Space, time and motion; B The particulate nature of matter; C Wave behaviour; D Fields; E Nuclear and quantum physics. 24 subtopics, no options. | Theme and subtopic titles: high (several independent sources agree). Subtopic *content* below: medium (see note). |
| Economics SL/HL | *Economics guide, first assessment 2022* (first teaching 2020). Units: 1 Introduction to economics; 2 Microeconomics; 3 Macroeconomics; 4 The global economy. A third-party copy of the HL subject brief reports last assessment in 2029, which would cover a May 2028 exam session (verify on ibo.org). No newer Economics guide was found in searches; the next DP review waves found (first assessment 2028 and 2029) did not list Economics. | Unit and subtopic titles: high. Whether a revision affects 2028 candidates: medium. |

**What was and was not checked (2026-10-16).** The official pages
(`ibo.org/programmes/diploma-programme/curriculum/sciences/physics/` and
`.../individuals-and-societies/economics/`) could not be opened from the development
environment, because its network policy blocks ibo.org. The mapping below therefore relies on
web-search excerpts of the official guides (copies hosted by schools), IB subject briefs, and
publisher and revision sites. The guides themselves were not read in full. **Before building
each module, the subtopic content it claims to cover must be checked against the official
guide or with a teacher.** Where a mapping depends on detail I could not confirm, it is marked
"verify".

Subtopic codes used: Physics A.1-E.5 (2025 guide); Economics 2.1-4.10 (2022 guide). Economics
2.5 is Elasticity of demand, 2.6 Elasticity of supply, 2.7 Role of government in
microeconomics, 2.8 Market failure: externalities and common pool or common access resources.
2.10-2.12 are HL only.

---

## Catalogue

Each entry lists: syllabus mapping, learning objective, controls, visualisation, equations,
assumptions, validation, what a student should be able to explain afterwards, an inquiry
question, a deeper extension, and links to Track B. Cost is a rough size (S, M or L PR).

### Economics

#### E1. Market equilibrium lab: demand, supply, shifts, shortages and surpluses (cost S-M)
- **Syllabus:** Econ 2.1 Demand, 2.2 Supply, 2.3 Competitive market equilibrium. Linear demand
  and supply functions are HL calculations (verify exact HL scope).
- **Objective:** see how shifts in demand or supply change the equilibrium, and what happens
  when the price is not at equilibrium.
- **Controls:** intercepts and slopes of demand and supply; named shift buttons (income,
  price of a substitute, cost of production, number of firms); a "set price" slider.
- **Visualisation:** the standard diagram, with the baseline and shifted curves; shortage or
  surplus shaded at the chosen price; a table of P*, Q* before and after.
- **Equations:** `Qd = a − bP`, `Qs = c + dP` (b, d > 0). `P* = (a − c)/(b + d)`,
  `Q* = (ad + bc)/(b + d)`. Excess demand at price P: `Qd(P) − Qs(P)`.
- **Assumptions:** perfect competition, linear curves, ceteris paribus, a single good.
- **Validation:** closed-form equilibrium; `Qd(P*) = Qs(P*)` exactly in rational arithmetic;
  comparative-statics signs (demand up raises P* and Q*) on a grid; invalid inputs (no
  positive equilibrium) rejected.
- **Explain afterwards:** why a rise in demand raises both price and quantity, but a rise in
  supply raises quantity and lowers price; why a price above P* creates a surplus.
- **Inquiry:** demand and supply both rise. Can you predict the change in price? Find
  settings where it rises, falls and stays the same.
- **Extension:** derive P* and Q* yourself; consumer and producer surplus as triangle areas.
- **Track B link:** none directly; becomes the engine for E3, E4, E7 and E8.

#### E2. Elasticity and total revenue (cost S, built on E1)
- **Syllabus:** Econ 2.5 Elasticity of demand (PED, YED; HL: PED varying along a linear demand
  curve), 2.6 Elasticity of supply (PES).
- **Objective:** discover why the same price rise raises revenue for some goods and lowers it
  for others.
- **Controls:** a price slider moving along the demand curve; a price-change size; income
  for YED; preset goods (necessity, luxury, inferior good).
- **Visualisation:** demand curve coloured by elastic/unit/inelastic; a total-revenue curve
  directly below it, sharing the quantity axis; TR rectangle on the demand diagram.
- **Equations:** IB form `PED = %ΔQd / %ΔP`. Point PED on a line: `−bP/Q`.
  `|PED| = 1` at `P = a/(2b)`, where `TR = a²/(4b)` is greatest. `YED = %ΔQ/%ΔY`,
  `PES = %ΔQs/%ΔP`.
- **Assumptions:** as E1; YED uses a demand intercept that varies linearly with income.
- **Validation:** TR maximum found numerically equals the closed form `a/(2b)`; the IB
  percentage formula depends on the direction of the change, and a test documents this
  (the app shows the midpoint version as an extension, labelled as a different convention);
  sign tests for normal and inferior goods.
- **Explain afterwards:** why a firm facing elastic demand loses revenue by raising its price;
  why PED changes along a straight-line demand curve even though its slope is constant.
- **Inquiry:** is it ever possible for a price cut to leave revenue unchanged? Where?
- **Extension:** prove TR is maximal where `|PED| = 1` using calculus.
- **Track B link:** elasticities reappear in Phase 3 sensitivity analysis.

#### E3. Taxes, subsidies and price controls (cost M, built on E1)
- **Syllabus:** Econ 2.7 Role of government in microeconomics (indirect taxes, subsidies,
  price ceilings and floors; HL: calculating their effects on markets and stakeholders).
- **Objective:** see who really pays a tax, and why interventions create welfare losses.
- **Controls:** specific tax or subsidy per unit; ad valorem rate (extension); ceiling or floor
  price; who the tax is levied on (to show it does not matter).
- **Visualisation:** shifted supply curve; consumer price, producer price; shaded consumer
  surplus, producer surplus, government revenue or spending, and deadweight loss; a bar chart
  of the same areas before and after.
- **Equations (specific tax t):** `Pc = P* + t·d/(b + d)`, `Pp = Pc − t`,
  `Qt = Q* − t·bd/(b + d)`; consumer share of the tax `d/(b + d)`; revenue `t·Qt`;
  deadweight loss `½·t·(Q* − Qt)`.
- **Assumptions:** as E1; no administration costs; for floors, the government buys the
  surplus at the floor price (the IB convention for agricultural floors; verify wording).
- **Validation:** welfare accounting identity `CS + PS + G + DWL = initial total surplus`
  checked exactly; incidence formula; DWL proportional to `t²` (second order) checked by
  fitting; the levied-on side gives identical outcomes.
- **Explain afterwards:** why the side with the more inelastic curve bears more of the tax;
  why a price ceiling can make some consumers worse off.
- **Inquiry:** a government wants to raise revenue with the least deadweight loss. Which
  goods should it tax? Test your answer.
- **Extension:** derive the incidence share in elasticity form.
- **Track B link:** Phase 3 fiscal policy works at the macro level; this is the micro view.

#### E4. Externalities and policy (cost M, built on E3)
- **Syllabus:** Econ 2.8 Market failure: externalities and common pool or common access
  resources (negative/positive, production/consumption; Pigouvian taxes, subsidies, tradable
  permits; HL calculation, verify scope).
- **Objective:** see the gap between private and social optimum, and how policy closes it.
- **Controls:** type of externality; marginal external cost or benefit; policy (tax, subsidy,
  permit cap, regulation) and its size.
- **Visualisation:** MPC, MSC, MPB, MSB curves; market and socially optimal quantities; the
  welfare-loss triangle that shrinks as the policy approaches the right size.
- **Equations:** `MSC = MPC + MEC` (constant MEC as the baseline); social optimum where
  `MSB = MSC`; welfare loss `½·MEC·(Q_market − Q_social)`; a Pigouvian tax equal to MEC
  restores `Q_social`.
- **Assumptions:** constant external cost or benefit, known to the government; linear curves.
- **Validation:** a tax equal to MEC gives exactly `Q_social`; welfare loss is zero there and
  positive on both sides (over- and under-correction); permit price equals the equivalent tax.
- **Explain afterwards:** why the free market over-produces goods with external costs; why the
  "right" tax depends on information governments rarely have.
- **Inquiry:** what happens to welfare if the government sets the tax at twice the external
  cost?
- **Extension:** common-pool resources with a simple stock-and-harvest dynamic (a difference
  equation, like Solow), showing overuse.
- **Track B link:** policy experiments in Phase 3; the extension reuses Solow-style dynamics.

#### E5. AD-AS diagram explorer (cost M)
- **Syllabus:** Econ 3.2 Variations in economic activity: aggregate demand and aggregate
  supply; 3.3 Macroeconomic objectives (output gaps, unemployment, inflation).
- **Objective:** shift AD, SRAS and LRAS and read off output, the price level and the output
  gap, in both the neo-classical and Keynesian AS models.
- **Controls:** components of AD (C, I, G, X − M); cost shocks; a switch between
  neo-classical (vertical LRAS) and Keynesian (horizontal, then rising, then vertical) AS.
- **Visualisation:** the IB-style diagram with baseline and new curves; output gap labelled.
- **Equations:** linear AD and SRAS for the comparative statics; a piecewise Keynesian AS.
  These are **illustrative shapes**, not an estimated model, and the app says so.
- **Assumptions:** comparative statics only (no time path); illustrative functional forms.
- **Validation:** equilibrium solves both curves exactly; sign tests for each shock; the
  Keynesian flat section gives zero price-level change.
- **Explain afterwards:** why the same AD increase can cause inflation in one model and no
  inflation in the other.
- **Inquiry:** under what conditions does fiscal expansion raise output without inflation?
- **Extension:** the multiplier (3.6, HL calculation: `1/(MPS + MPT + MPM)`).
- **Track B link:** a **precursor** to Phase 3 (AD-AS with dynamics, the three-equation NK
  model, schools of thought). Phase 3 remains unchanged.

#### E6. Exchange rates (cost S, reuses E1)
- **Syllabus:** Econ 4.5 Exchange rates (verify subtopic number and HL calculations).
- **Objective:** see how demand for exports, interest rates and speculation move a floating
  exchange rate, and the effect on import and export prices.
- **Visualisation, equations, validation:** the E1 engine with currency labels; conversion
  of prices at old and new rates checked exactly.
- **Track B link:** none yet.

#### E7. Trade and protection (cost M, reuses E1 and E3)
- **Syllabus:** Econ 4.1 Benefits of international trade, 4.2 Types of trade protection (HL:
  calculating the effects of tariffs, quotas and subsidies; verify).
- **Objective:** see who gains and loses from free trade and from a tariff.
- **Equations:** world price `Pw` with perfectly elastic world supply; imports
  `Qd(Pw) − Qs(Pw)`; tariff revenue; two deadweight-loss triangles.
- **Validation:** welfare accounting identity as in E3; tariff of zero reproduces free trade.

#### E8. Inequality: Lorenz curve and Gini coefficient (cost S)
- **Syllabus:** Econ 3.4 Economics of inequality and poverty.
- **Objective:** see how a tax-and-transfer scheme reshapes the Lorenz curve and the Gini
  coefficient.
- **Equations:** Gini from quintile shares by the trapezium rule:
  `G = 1 − Σ (X_k − X_{k−1})(Y_k + Y_{k−1})`, exact for a piecewise-linear Lorenz curve.
- **Validation:** perfect equality gives 0; all income in the top quintile gives 0.8, the
  largest value five groups can show (a measurement limit worth seeing); a known textbook
  example; equal lump-sum transfers always lower G.

#### E9. Measuring economic activity (cost S, lower priority)
- **Syllabus:** Econ 3.1 Measuring economic activity; 3.3 (inflation from a basket of goods).
- Real versus nominal GDP, price indices, GDP per capita. Mainly calculations; lower
  simulation value, so listed last.

### Physics

#### P1. Kinematics and motion graphs (cost S, high reuse)
- **Syllabus:** Physics A.1 Kinematics (motion graphs, equations of motion for uniform
  acceleration, projectile motion; fluid resistance treated qualitatively, verify).
- **Objective:** link s-t, v-t and a-t graphs to the motion; see why a projectile's horizontal
  and vertical motions are independent.
- **Controls:** initial velocity, acceleration, launch speed and angle; a "drag on/off"
  comparison.
- **Visualisation:** the motion animated; three linked graphs with a shared time cursor;
  gradient and area read-outs.
- **Equations:** `v = u + at`, `s = ut + ½at²`, `v² = u² + 2as`; projectile components.
- **Validation:** reuses the existing exact projectile solution with `b = 0`; gradients and
  areas checked against the equations of motion.
- **Explain afterwards:** what the area under a v-t graph means; why the horizontal velocity
  of a projectile in a vacuum stays constant.
- **Inquiry:** two balls are released at the same time, one dropped and one thrown sideways.
  Which lands first? Then switch drag on.
- **Track B link:** reuses Phase 0 projectile code; leads into the existing projectile,
  angle-sweep and integrator pages.

#### P2. Forces and Newton's laws: free-body diagrams on a slope (cost S-M)
- **Syllabus:** Physics A.2 Forces and momentum (Newton's laws, free-body diagrams, friction
  with static and dynamic coefficients; verify).
- **Objective:** build the free-body diagram and predict whether and how fast a block moves.
- **Controls:** mass, slope angle, μs, μd, an applied force and its direction.
- **Visualisation:** the block with force arrows to scale; resolved components; resultant
  force and acceleration; a "does it move?" indicator.
- **Equations:** static if the required friction ≤ `μs·N`; otherwise
  `a = (F_parallel − μd·N)/m` with `N = mg cos θ ± (applied component)`.
- **Assumptions:** rigid block, point contact, constant coefficients, no air resistance.
- **Validation:** limiting angle `tan θ = μs` with no applied force; Newton's third-law pairs
  shown and checked to be equal and opposite; mass cancels when only gravity and friction act.
- **Explain afterwards:** why a heavier block slides at the same angle as a light one.
- **Inquiry:** find the smallest push that starts the block moving up the slope.

#### P3. Momentum, impulse and one-dimensional collisions (cost M)
- **Syllabus:** Physics A.2 Forces and momentum (momentum, impulse, conservation of momentum,
  elastic and inelastic collisions and explosions; verify exact wording); energy comparisons
  use A.3.
- **Objective:** see that momentum is conserved in **every** collision while kinetic energy
  is conserved **only** in elastic ones.
- **Controls:** masses and initial velocities of two carts; collision type (elastic,
  inelastic, perfectly inelastic, explosion from rest); contact time for the force-time graph.
  Each mass is a property of its body and stays with it; nothing is exchanged except momentum
  and energy.
- **Visualisation:** the collision animated; momentum bars that keep the same total; kinetic
  energy bars whose total drops for inelastic collisions; a force-time graph whose area is
  the impulse.
- **Equations:** with coefficient of restitution e (0 = perfectly inelastic, 1 = elastic):
  `v1 = [(m1 − e·m2)u1 + (1 + e)m2·u2]/(m1 + m2)`,
  `v2 = [(m2 − e·m1)u2 + (1 + e)m1·u1]/(m1 + m2)`.
  Kinetic energy lost: `½·μ·(1 − e²)(u1 − u2)²` with `μ = m1m2/(m1 + m2)`.
  Impulse `J = m1(v1 − u1) = −m2(v2 − u2)`; average force `J/Δt`.
  The IB course names collision types; e itself is an **extension** (verify whether your
  course uses it) and the app labels it that way.
- **Assumptions:** one dimension, no external horizontal force during the collision, rigid
  bodies with constant mass.
- **Validation:** total momentum conserved to rounding for all e; kinetic-energy loss matches
  the formula; for e = 1 the relative velocity exactly reverses; the centre-of-mass velocity
  is unchanged; the kinetic-energy loss is the same in every inertial frame (a Galilean
  boost test); explosions conserve zero total momentum.
- **Explain afterwards:** where the "lost" kinetic energy goes; why a car crumple zone
  reduces the force on passengers without changing the impulse.
- **Inquiry:** a light cart hits a heavy one at rest, elastically. Predict the direction of
  the light cart afterwards, then test it. What happens when the masses are equal?
- **Extension:** derive the e-formulas from momentum conservation and the definition of e.
- **Track B link:** a **precursor** to Phase 4 collisions (2-D discs, event-driven
  simulation) and Phase 4b kinetic theory. Phase 4 remains unchanged; the 1-D formulas above
  will serve as an exact reference in its tests.

#### P4. Work, energy, power and efficiency (cost M)
- **Syllabus:** Physics A.3 Work, energy and power.
- **Objective:** follow energy transfers on a track with friction, and see efficiency and
  power.
- **Controls:** track shape (preset ramps), mass, friction, launch speed, motor power.
- **Visualisation:** energy bar chart (kinetic, gravitational potential, elastic, dissipated)
  updating as the object moves; Sankey-style efficiency diagram.
- **Equations:** `W = Fs cos θ`, `ΔEp = mgΔh`, `Ek = ½mv²`, `P = Fv`,
  `efficiency = useful output / input`.
- **Validation:** the energy total (including dissipated energy) is constant along the track;
  frictionless case returns to the starting height exactly.
- **Explain afterwards:** why the speed at the bottom doesn't depend on the slope's shape
  when there is no friction.

#### P5. Simple harmonic motion (cost M)
- **Syllabus:** Physics C.1 Simple harmonic motion (HL extends with phase and energy
  equations; verify split).
- **Objective:** see x, v and a out of phase, and the constant exchange of kinetic and
  potential energy.
- **Equations:** `x = A cos(ωt + φ)`, `ω = √(k/m)`, `T = 2π√(L/g)` for a small-angle pendulum.
- **Validation:** exact solution; period independent of amplitude for the spring; for the
  pendulum, the small-angle period is shown against the exact period (elliptic integral) so
  the approximation is visible and labelled.
- **Track B link:** a **precursor** to Phase 2 oscillators (damped and driven, resonance) and
  the nonlinear-pendulum extension. Phase 2 remains unchanged.

#### P6. Waves, superposition, standing waves and the Doppler effect (cost M-L)
- **Syllabus:** Physics C.2 Wave model, C.3 Wave phenomena, C.4 Standing waves and resonance,
  C.5 Doppler effect.
- **Objective:** see `v = fλ`, superposition, standing-wave harmonics in strings and pipes,
  and the frequency shift from a moving source.
- **Equations:** `y = A sin(kx − ωt)`; strings and open pipes `λn = 2L/n`; pipes closed at
  one end `λ = 4L/(2n − 1)`; Doppler `f' = f·v/(v ∓ us)` and `f' = f(v ± uo)/v`.
- **Validation:** nodes exactly at the predicted positions; superposition of two travelling
  waves equals the standing-wave formula; Doppler against the formula and its symmetry
  checks.

#### P7. Thermal physics: heating curves and gas laws (cost M)
- **Syllabus:** Physics B.1 Thermal energy transfers (specific heat capacity, specific
  latent heat), B.3 Gas laws.
- **Equations:** `Q = mcΔT`, `Q = mL`, `pV = nRT`.
- **Validation:** heating curve plateaus at the right energies; gas-law invariants.
- **Track B link:** a **precursor** to Phase 4b kinetic theory, where pressure and
  temperature emerge from particles. Phase 4b remains unchanged.

#### P8. Electric circuits (cost M)
- **Syllabus:** Physics B.5 Current and circuits (series and parallel, emf and internal
  resistance, potential dividers; verify).
- **Validation:** Kirchhoff's laws checked on every circuit; power delivered equals power
  dissipated.

#### P9. Gravitational fields and circular orbits (cost S-M)
- **Syllabus:** Physics D.1 Gravitational fields (orbital speed, Kepler's third law, escape
  speed; verify).
- **Validation:** `T² ∝ r³` exactly; energy and speed formulas.
- **Track B link:** a **precursor** to Phase 4 orbits (Kepler's equation, long-run
  integrator studies). Phase 4 remains unchanged.

#### P10. Radioactive decay as a random process (cost S-M)
- **Syllabus:** Physics E.3 Radioactive decay (half-life, decay constant at HL; verify).
- **Objective:** see a smooth exponential emerge from random individual decays, and the
  fluctuations around it.
- **Equations:** `N = N0·e^(−λt)`, `T½ = ln 2 / λ`; each nucleus decays in a step with
  probability `1 − e^(−λΔt)`.
- **Validation:** recorded random seed (bit-identical replay); the mean of many runs matches
  the exponential within a statistically derived tolerance; the spread matches the binomial
  variance. These are statistical tests and are labelled as such.
- **Track B link:** the first seeded Monte Carlo model; feeds the Quant Lab's statistics
  thinking.

#### P11. Measurement uncertainty and graphing (cost M; high IA value)
- **Syllabus:** the guide's tools and inquiry skills for the experimental programme
  (uncertainties, propagation, gradients and intercepts with uncertainty). **Verify the exact
  tool names and content in the official guide.**
- **Objective:** see how uncertainties propagate and how a best-fit line with maximum and
  minimum gradients works.
- **Equations:** the IB rules (absolute uncertainties add for sums; fractional ones add for
  products; powers multiply the fractional uncertainty). These rules give **worst-case
  linear approximations**. The app compares them with a Monte Carlo propagation and labels
  the difference.
- **Validation:** Monte Carlo agrees with the linear rules for small uncertainties and
  diverges, as expected, for large ones; least squares checked against a closed form.
- **Track B link:** a **precursor** to Phase 5 regression and uncertainty in the Quant Lab.
  Phase 5 remains unchanged.
- **Academic integrity:** this tool explains methods. It must not process data for an
  assessed internal assessment unless the teacher approves, and the IA remains the student's
  own work.

---

## Prioritised shortlist
Scored on educational value now (DP1 teaching order typically starts with mechanics and
microeconomics; verify against your school's scheme of work), implementation cost, prerequisites
and reuse of existing code.

| Rank | Module | Why now | Cost | Reuse |
|---|---|---|---|---|
| 1 | **E1 + E2** Market equilibrium and elasticity | Core early microeconomics; the engine for E3, E4, E6 and E7 | S-M | Workspace, `record_run`, schema-driven fields |
| 2 | **P3** Momentum and collisions | Core A.2; momentum vs kinetic energy is a classic confusion; exact validation; precursor to Phase 4 | M | Workspace, Plotly |
| 3 | **E3** Taxes, subsidies, price controls | Builds directly on rank 1; welfare accounting is an exact test | M | E1 engine |
| 4 | **P1 + P2** Kinematics graphs and slope forces | A.1-A.2; P1 reuses the projectile engine | S-M | projectile engine |
| 5 | **P11** Uncertainty and graphing | Useful across the whole course and the IA; precursor to Quant | M | none yet |

Next wave: E4, P4, P5, P10, E5, P6. Later: E6, E7, E8, P7, P8, P9, E9.

## How the two tracks coexist
- **Cadence:** about one Track A module per Track B step, slotted between steps. Track B
  steps keep their order: 1.2 → 1.3 → 1.4 → 1.5 → 1.6 → Phases 2-7.
- **Suggested order:** Track B 1.2 (physics moves into the workspace) → **A1** (E1 + E2,
  plus the Foundations index page) → B 1.3 (Quant datasets) → **A2** (P3 collisions) →
  B 1.4 (replay) → **A3** (E3) → B 1.5 → **A4** (P1 + P2) → B 1.6 → **A5** (P11) → then
  alternate with Phases 2-7.
- **Dependencies:** Track A modules depend only on what already exists (workspace,
  `record_run`, schema-driven fields), so none waits for Track B. After B 1.4 and 1.5, Track A
  runs gain replay and the generic log automatically.
- **Flexibility:** the order of Track A modules can follow the school's teaching order.
  Track B's order does not change.

## Product structure (proposed)
- Track A lives **inside** the Physics and Economy labs as a "Foundations" level, with a
  `/foundations` index listing every module by subject and syllabus topic. It is not a
  fourth lab.
- Pages reuse the existing `Workspace`. If the first module needs an "Explain" or "Check
  yourself" panel, it is added then, and generalised only when a second module needs it.
- Engines stay in the Python core, like Track B, so every module gets the same validation,
  run records and replay. Slider updates call the API; revisit only if measured latency is a
  problem.
- Learning material goes into the existing lab guides (a "Foundations" part in
  `docs/LEARNING_GUIDE.md` and `docs/ECONOMY_LEARNING_GUIDE.md`).

## Sources consulted (search excerpts; see "limits" above)
- Physics guide, first assessment 2025, school-hosted copy:
  https://peda.net/kuopio/lukiot/lyseonlukio/ib/syllabukset/group-4-sciences/physics-2025.pdf:file/download/c56a8c8592e847bbb555540b087b0990d1ade5b0/Physics,%202025.pdf
- Economics guide, first assessment 2022, school-hosted copies:
  https://dp.uwcea.org/docs/Economics%20Subject%20Guide.pdf and
  https://www.ibdeconomics.com/uploads/1/1/7/5/11758934/new_economics_guide_first_assessment_2022.pdf
- IB subject briefs (official): https://ibo.org/globalassets/new-structure/programmes/dp/pdfs/sl-economics-en.pdf
  and https://ibo.org/globalassets/new-structure/programmes/dp/pdfs/hl-economics-en.pdf
- Physics syllabus summaries: https://www.savemyexams.com/learning-hub/exam-guides/ib-physics-syllabus-update/
- Economics review timing: https://owltutors.co.uk/advice/ib/economics/syllabus/
