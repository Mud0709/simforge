# IB Foundations track (Track A): catalogue and syllabus mapping

> **ADDITIVE TRACK. This document adds to SimForge; it replaces nothing.** The existing
> roadmap (Track B, the Advanced Simulation Studio: Phases 0-7 in `ROADMAP.md`) is unchanged
> in scope, content and order. No Track B item may be removed, downgraded, merged away or
> postponed indefinitely because of this track. See "Preservation rule" below.

**Status:** proposed, awaiting review (revised 2026-10-16 against the official guides supplied by
the author). Nothing in this catalogue is implemented.

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
3. **No dependency between the tracks.** Track B is the primary sequence and progresses on
   its own. Track A modules are additional milestones that may be interleaved when practical.
   No Track A module is ever a prerequisite for, or a gate on, any Track B step, and Track B
   never waits for Track A.
4. Shared code is extracted only when real modules from both tracks need it (the existing
   two-examples rule).

## Syllabus sources and their limits
| Course | Guide that applies | Confidence |
|---|---|---|
| Physics SL/HL | **Official IB *Physics guide, first assessment 2025*** (published February 2023, updated May 2023), read directly from a copy supplied by the author. Five themes, 24 subtopics (A.1-E.5); the syllabus roadmap (guide p. 25) marks each subtopic as all students, all students plus additional HL, or HL only. Skills: Tools 1-3 and Inquiry 1-3 (guide pp. 27-32). | **Verified against the guide** for the themes, subtopic titles, SL/HL markers, A.1-A.5 and the Tools and Inquiry skills. Subtopic *content* for B-E was checked only at the level of the roadmap; detailed lines there are marked "verify". |
| Economics SL/HL | **Official IB *Economics guide, first assessment 2024*** (published February 2020; updated May 2020, August 2020, October 2020 and October 2022), read directly from a copy supplied by the author. Units: 1 Introduction to economics; 2 Microeconomics; 3 Macroeconomics; 4 The global economy, with subtopics 1.1-4.10 (guide pp. 20-21). | Unit and subtopic mapping **verified against this guide** (Units 1-4, including the HL-only markers and the "Diagrams and calculations" columns). **Cohort applicability: unverified** (see below). |

**Which Economics guide applies to an IBDP1 student in October 2026 (exams May 2028)?**
- The supplied guide says "First assessment 2024". It does not state a last assessment session.
- A web search (2026-10-16) found **no Economics subject guide labelled "first assessment
  2027"**. The only IB document with that label it surfaced was the Extended Essay guide.
  ibo.org and the Programme Resource Centre, where a newer edition would appear, could not be
  checked from the development environment.
- **Therefore the Economics mapping below is provisional for the May 2028 session.** It is
  verified against the first-assessment-2024 guide; if the school uses a later edition, every
  Economics subtopic number, HL marker and calculation listed here must be re-checked. The
  author's teacher or the Programme Resource Centre can settle this.
- The earlier draft cited a "first assessment 2022" guide from search excerpts. That label is
  superseded: the subtopic numbering matches, but the supplied 2024 guide is the reference.

**What was and was not checked (2026-10-16).** ibo.org cannot be reached from the development
environment (its network policy blocks it). The two official guides above were read directly
from copies supplied by the author: the syllabus outline, roadmap and skills sections, Physics
A.1-A.5, and Economics Units 1-4 (subtopics 2.1-2.8, 3.1-3.7, 4.1-4.6 line by line). Anything
not read line by line is marked "verify". **Before building a module, its mapping is re-checked
against the guide that applies to the author's exam session.**

**"Syllabus" vs "extension".** Each module separates what the guide requires (with its HL
markers) from modelling choices SimForge adds, such as explicit linear equations. An extension
is labelled in the app and never presented as examinable content.

Subtopic codes: Physics A.1-E.5; Economics 1.1-4.10 (2.5 is "Elasticities of demand", 2.6
"Elasticity of supply", 2.7 "Role of government in microeconomics", 2.8 "Market
failure—externalities and common pool or common access resources"; 2.4 and 2.10-2.12 are HL
only).

## Model identities vs claims about the real world
Several validation checks below are **model identities**: they hold exactly *inside* the stated
model, so they test that the code implements the model correctly. They are not evidence that
real markets or policies behave this way. In particular:
- **Welfare accounting** (`CS + PS + (government revenue − government spending) + DWL =
  initial total surplus`, where DWL is the deadweight loss) is an identity of partial-equilibrium, surplus-based welfare analysis with linear
  curves. It assumes surplus measures welfare, gains and losses are weighted equally across
  people, other markets are unaffected, and there are no administration, enforcement or
  compliance costs. For a **price ceiling**, the identity also needs an assumption about who
  gets the scarce units (the model assumes they go to the buyers who value them most); real
  rationing by queues or black markets loses more. For a **price floor** with government
  purchase, the cost of buying, storing or destroying the surplus enters as a cost.
- **The Pigouvian result** (a tax equal to the marginal external cost restores the social
  optimum) holds when the market is otherwise competitive, the external cost is known and
  measured in money, the tax equals the marginal external cost **at the social optimum** (with
  a constant marginal external cost, at every quantity), there are no other distortions, and
  enforcement is costless. Real policies face measurement problems, which the guide itself
  lists (2.8: "challenges involved in measurement of externalities").
- Each module's app text states which results are model identities, which are approximations
  and which come from data.

---

## Catalogue

Each entry lists: syllabus mapping, learning objective, controls, visualisation, equations,
assumptions, validation, what a student should be able to explain afterwards, an inquiry
question, a deeper extension, and links to Track B. Cost is a rough size (S, M or L PR).

### Economics

#### E1. Market equilibrium lab: demand, supply, shifts, shortages and surpluses (cost S-M)
- **Syllabus:** Econ 2.1 Demand, 2.2 Supply, 2.3 Competitive market equilibrium (diagrams of
  shifts, shortages and surpluses; consumer, producer and social surplus). HL: calculating
  consumer and producer surplus from a diagram (2.3). **Extension:** explicit linear
  equations for demand and supply are a SimForge modelling choice, *not* required by the
  guide; the app labels them as such.
- **Objective:** see how shifts in demand or supply change the equilibrium, and what happens
  when the price is not at equilibrium.
- **Controls:** intercepts and slopes of demand and supply; named shift buttons (income,
  price of a substitute, cost of production, number of firms); a "set price" slider.
- **Visualisation:** the standard diagram, with the baseline and shifted curves; shortage or
  surplus shaded at the chosen price; a table of P*, Q* before and after.
- **Equations:** `Qd = a − bP`, `Qs = c + dP` (b, d > 0). `P* = (a − c)/(b + d)`,
  `Q* = (ad + bc)/(b + d)`. Excess demand at price P: `Qd(P) − Qs(P)`.
- **Assumptions:** perfect competition, linear curves, ceteris paribus, a single good.
- **Validation (model identities):** closed-form equilibrium; `Qd(P*) = Qs(P*)` exactly in rational arithmetic;
  comparative-statics signs (demand up raises P* and Q*) on a grid; invalid inputs (no
  positive equilibrium) rejected.
- **Explain afterwards:** why a rise in demand raises both price and quantity, but a rise in
  supply raises quantity and lowers price; why a price above P* creates a surplus.
- **Inquiry:** demand and supply both rise. Can you predict the change in price? Find
  settings where it rises, falls and stays the same.
- **Extension:** derive P* and Q* yourself; consumer and producer surplus as triangle areas.
- **Track B link:** none directly; becomes the engine for E3, E4, E7 and E8.

#### E2. Elasticity and total revenue (cost S, built on E1)
- **Syllabus:** Econ 2.5 Elasticities of demand (PED and its relationship with total revenue;
  YED with the Engel-curve diagram; calculations of PED and YED from data; HL: changing PED
  along a straight-line demand curve) and 2.6 Elasticity of supply (PES; calculations from
  data).
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
- **Assumptions:** as E1; partial equilibrium with surplus as the welfare measure; no
  administration, enforcement or compliance costs; ceilings ration the scarce units to the
  buyers who value them most; for floors, the government buys the surplus at the floor price
  (the guide asks for the effects of floors on markets and stakeholders; the purchase
  arrangement is a modelling choice, stated in the app).
- **Validation (model identities, see "Model identities vs claims about the real world"):**
  the welfare accounting identity checked exactly; the incidence formula; deadweight loss
  `= ½·t²·bd/(b + d)` (exactly quadratic in t for linear curves); taxing the seller or the
  buyer gives identical outcomes. These test the implementation of the model, not real-world
  welfare.
- **Explain afterwards:** why the side with the more inelastic curve bears more of the tax;
  why a price ceiling can make some consumers worse off.
- **Inquiry:** a government wants to raise revenue with the least deadweight loss. Which
  goods should it tax? Test your answer.
- **Extension:** derive the incidence share in elasticity form.
- **Track B link:** Phase 3 fiscal policy works at the macro level; this is the micro view.

#### E4. Externalities and policy (cost M, built on E3)
- **Syllabus:** Econ 2.8 (negative and positive externalities of production and consumption;
  MSB = MSC as the social optimum; responses including Pigouvian and carbon taxes, tradable
  permits, subsidies, legislation and regulation). HL: calculating welfare loss from a
  diagram.
- **Objective:** see the gap between private and social optimum, and how policy closes it.
- **Controls:** type of externality; marginal external cost or benefit; policy (tax, subsidy,
  permit cap, regulation) and its size.
- **Visualisation:** MPC, MSC, MPB, MSB curves; market and socially optimal quantities; the
  welfare-loss triangle that shrinks as the policy approaches the right size.
- **Equations:** `MSC = MPC + MEC` (constant MEC as the baseline); social optimum where
  `MSB = MSC`; welfare loss `½·MEC·(Q_market − Q_social)` (exact for linear curves and
  constant MEC); a Pigouvian tax equal to MEC restores `Q_social`.
- **Assumptions:** otherwise competitive market; linear curves; marginal external cost or
  benefit known to the government and measured in money; the tax equals the marginal external
  cost at the social optimum; no other distortions; costless enforcement; surplus-based
  welfare with equal weights.
- **Validation (model identities):** within those assumptions, a tax equal to MEC gives
  exactly `Q_social`; welfare loss is zero there and positive on both sides (over- and
  under-correction); with a fixed permit cap, the market permit price equals the tax that
  gives the same quantity. The app states that real policies face the measurement and
  information problems the guide lists, which these checks do not test.
- **Explain afterwards:** why the free market over-produces goods with external costs; why the
  "right" tax depends on information governments rarely have.
- **Inquiry:** what happens to welfare if the government sets the tax at twice the external
  cost?
- **Extension:** common-pool resources with a simple stock-and-harvest dynamic (a difference
  equation, like Solow), showing overuse.
- **Track B link:** policy experiments in Phase 3; the extension reuses Solow-style dynamics.

#### E5. AD-AS diagram explorer (cost M)
- **Syllabus:** Econ 3.2 (AD and its components; SRAS; monetarist/new classical LRAS and
  the Keynesian AS curve; inflationary and deflationary/recessionary gaps); 3.3 objectives
  (HL: AD/AS link to the short-run and long-run Phillips curve). The guide uses diagrams, not
  equations, here; the linear functional forms are a labelled modelling choice.
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
- **Extension:** the Keynesian multiplier (3.6, HL only: `1/(1 − MPC)` or
  `1/(MPS + MPT + MPM)`, and the effect on GDP of a change in an injection).
- **Track B link:** a **precursor** to Phase 3 (AD-AS with dynamics, the three-equation NK
  model, schools of thought). Phase 3 remains unchanged.

#### E6. Exchange rates (cost S, reuses E1)
- **Syllabus:** Econ 4.5 Exchange rates (floating-rate determination; factors shifting demand
  and supply of a currency; calculations: the price of a good in different currencies and
  changes in a currency's value from data; HL only: fixed versus floating systems).
- **Objective:** see how demand for exports, interest rates and speculation move a floating
  exchange rate, and the effect on import and export prices.
- **Visualisation, equations, validation:** the E1 engine with currency labels; conversion
  of prices at old and new rates checked exactly.
- **Track B link:** none yet.

#### E7. Trade and protection (cost M, reuses E1 and E3)
- **Syllabus:** Econ 4.1 Benefits of international trade (HL: quantities of exports and imports,
  import expenditure and export revenue from a diagram) and 4.2 Types of trade protection (HL:
  effects on stakeholders of tariffs, quotas and subsidies from a diagram).
- **Objective:** see who gains and loses from free trade and from a tariff.
- **Equations:** world price `Pw` with perfectly elastic world supply; imports
  `Qd(Pw) − Qs(Pw)`; tariff revenue; two deadweight-loss triangles.
- **Assumptions:** a small economy that takes the world price as given (perfectly elastic
  world supply); otherwise as E3.
- **Validation (model identities):** the welfare accounting identity as in E3; a tariff of
  zero reproduces free trade exactly.

#### E8. Inequality: Lorenz curve and Gini coefficient (cost S)
- **Syllabus:** Econ 3.4 Economics of inequality and poverty (Lorenz curve and Gini coefficient
  as measures; HL: constructing a Lorenz curve from income quintile data; HL: average and
  marginal tax rates). **Extension:** *calculating* the Gini coefficient is not listed as a
  required calculation in the guide.
- **Objective:** see how a tax-and-transfer scheme reshapes the Lorenz curve and the Gini
  coefficient.
- **Equations:** from grouped (quintile) shares, the trapezium rule
  `G = 1 − Σ (X_k − X_{k−1})(Y_k + Y_{k−1})`.
- **What "exact" means here:** this formula is **exact for the piecewise-linear Lorenz curve
  drawn through the grouped data points**. It is not the Gini coefficient of the underlying
  population, because it assumes everyone within a group has the same income. A Lorenz curve
  is convex, so the straight segments lie on or above it: the grouped Gini is a **lower bound**
  on the population Gini. The app says so.
- **Validation:** perfect equality gives 0; all income in the top quintile gives 0.8, the
  largest value five equal groups can show; a hand-worked textbook example; equal lump-sum
  transfers lower the grouped G. A test also checks the lower-bound property: splitting a
  synthetic population into finer groups never lowers G.

#### E9. Measuring economic activity (cost S, lower priority)
- **Syllabus:** Econ 3.1 (calculations of nominal GDP, GNI, real GDP and GNI using a price
  deflator, per capita values); 3.3 (inflation rate from CPI data; HL: a weighted price
  index).
- Real versus nominal GDP, price indices, GDP per capita. Mainly calculations; lower
  simulation value, so listed last.

### Physics

#### P1. Kinematics and motion graphs (cost S, high reuse)
- **Syllabus:** Physics A.1 Kinematics (SL and HL; no additional HL content): the equations of
  motion; projectiles without fluid resistance treated quantitatively; the effect of fluid
  resistance **qualitatively** only. The trajectory equation is not required.
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
  angle-sweep and integrator pages. Those pages' quantitative drag goes beyond A.1 and is
  labelled as an extension there.

#### P2. Forces and Newton's laws: free-body diagrams on a slope (cost S-M)
- **Syllabus:** Physics A.2 Forces and momentum (SL and HL): Newton's three laws; free-body
  diagrams in one and two dimensions; friction `Ff ≤ μs·FN` (static) and `Ff = μd·FN`
  (dynamic); tension; Hooke's law; viscous drag `Fd = 6πηrv` (the linear drag already in
  SimForge's projectile model); buoyancy.
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
- **Syllabus:** Physics A.2 Forces and momentum (SL and HL): conservation of linear momentum,
  impulse `J = FΔt`, `F = Δp/Δt`, elastic and inelastic collisions of two bodies, explosions,
  and energy considerations in each. Guidance: quantitative collisions and explosions are
  **one-dimensional for SL and two-dimensional for HL**; "the use of simultaneous equations
  involving conservation of momentum and energy in collisions is not required". Energy
  comparisons use A.3.
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
  The guide does not use e and does not require the simultaneous-equation solution, so these
  formulas are an **extension**, labelled as such. The core view uses only momentum
  conservation plus the chosen collision type.
- **HL view:** two-dimensional collisions (momentum conserved in each component), since the
  guide expects them quantitatively at HL.
- **Assumptions:** one dimension, no external horizontal force during the collision, rigid
  bodies with constant mass.
- **Validation (model identities):** total momentum conserved to rounding for all e;
  kinetic-energy loss matches the formula; for e = 1 the relative velocity exactly reverses;
  the centre-of-mass velocity is unchanged; the kinetic-energy loss is the same in every
  inertial frame (a Galilean boost test, linking to HL A.5); explosions conserve zero total
  momentum.
- **Explain afterwards:** where the "lost" kinetic energy goes; why a car crumple zone
  reduces the force on passengers without changing the impulse.
- **Inquiry:** a light cart hits a heavy one at rest, elastically. Predict the direction of
  the light cart afterwards, then test it. What happens when the masses are equal?
- **Extension:** derive the e-formulas from momentum conservation and the definition of e.
- **Track B link:** a **precursor** to Phase 4 collisions (2-D discs, event-driven
  simulation) and Phase 4b kinetic theory. Phase 4 remains unchanged and does not depend on
  this module. If both exist, the 1-D formulas can serve as an extra reference test in
  Phase 4, but Phase 4 can derive them itself.

#### P4. Work, energy, power and efficiency (cost M)
- **Syllabus:** Physics A.3 Work, energy and power (SL and HL): `W = Fs cos θ`, Sankey diagrams,
  conservation of mechanical energy without resistive forces, the change in mechanical energy
  as the work of non-conservative forces, `P = Fv`, efficiency, energy density of fuels.
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
- **Syllabus:** Physics C.1 Simple harmonic motion (all students, plus additional HL content
  such as phase angle; detailed lines: verify).
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
- **Syllabus:** Physics B.5 Current and circuits (all students; detailed lines: verify).
- **Validation:** Kirchhoff's laws checked on every circuit; power delivered equals power
  dissipated.

#### P9. Gravitational fields and circular orbits (cost S-M)
- **Syllabus:** Physics D.1 Gravitational fields (all students plus additional HL content;
  detailed lines: verify).
- **Validation:** `T² ∝ r³` exactly; energy and speed formulas.
- **Track B link:** a **precursor** to Phase 4 orbits (Kepler's equation, long-run
  integrator studies). Phase 4 remains unchanged.

#### P10. Radioactive decay as a random process (cost S-M)
- **Syllabus:** Physics E.3 Radioactive decay (all students plus additional HL content;
  detailed lines: verify).
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
- **Syllabus:** "Skills in the study of physics" (guide pp. 27-32). Tool 3: Mathematics,
  "Processing uncertainties" (absolute, fractional and percentage uncertainties; propagation
  through addition, subtraction, multiplication, division and powers) and "Graphing"
  (uncertainty bars, lines of best fit, maximum and minimum gradient lines "by eye",
  uncertainty in gradients and intercepts, linearising graphs). Tool 2: Technology includes
  "generate data from models and simulations" and "use computer modelling".
- **Objective:** see how uncertainties propagate and how a best-fit line with maximum and
  minimum gradients works.
- **Equations:** the IB rules (absolute uncertainties add for sums; fractional ones add for
  products; powers multiply the fractional uncertainty). These rules give **worst-case
  linear approximations**. The app compares them with a Monte Carlo propagation and labels
  the difference.
- **Validation:** Monte Carlo agrees with the linear rules for small uncertainties and
  diverges, as expected, for large ones (a statistical check, labelled as such); least squares
  checked against a closed form. The app notes that the guide's max/min-gradient method is
  done "by eye", while least squares is an extension.
- **Track B link:** a **precursor** to Phase 5 regression and uncertainty in the Quant Lab.
  Phase 5 remains unchanged.
- **Academic integrity:** this tool explains methods. Although the guide allows
  investigations involving simulations and modelling, it must not process data for an assessed
  internal assessment unless the teacher approves, and the IA remains the student's own work.

---

## Prioritised shortlist
Scored on educational value now (DP1 teaching order typically starts with mechanics and
microeconomics; verify against your school's scheme of work), implementation cost, prerequisites
and reuse of existing code.

| Rank | Module | Why now | Cost | Reuse |
|---|---|---|---|---|
| 1 | **E1 + E2** Market equilibrium and elasticity | Core early microeconomics; the engine for E3, E4, E6 and E7 | S-M | Workspace, `record_run`, schema-driven fields |
| 2 | **P3** Momentum and collisions | Core A.2 (1-D SL, 2-D HL); momentum vs kinetic energy is a classic confusion; exact validation; precursor to Phase 4 | M | Workspace, Plotly |
| 3 | **E3** Taxes, subsidies, price controls | Builds directly on rank 1; welfare accounting is an exact test | M | E1 engine |
| 4 | **P1 + P2** Kinematics graphs and slope forces | A.1-A.2; P1 reuses the projectile engine | S-M | projectile engine |
| 5 | **P11** Uncertainty and graphing | Useful across the whole course and the IA; precursor to Quant | M | none yet |

Next wave: E4, P4, P5, P10, E5, P6. Later: E6, E7, E8, P7, P8, P9, E9.

## How the two tracks coexist
- **Track B is the primary sequence.** It proceeds in its own order (1.2 → 1.3 → 1.4 → 1.5 →
  1.6 → Phases 2-7) whether or not any Track A module has been built. Every original
  milestone stays, in its original order.
- **Track A is additional and optional in timing.** Its modules may be interleaved between
  Track B steps *when practical*. A reasonable rhythm is at most one Track A module between
  consecutive Track B steps, but this is a suggestion, not a schedule.
- **No cross-track prerequisites, in either direction.** No Track B step requires a Track A
  module, and no Track A module is allowed to block the next Track B step. If a Track A module
  is unfinished, Track B continues.
- **Inside Track A**, some modules build on others (E2, E3, E6 and E7 reuse the E1 engine).
  Those dependencies stay within Track A.
- **What Track A uses from Track B:** only what already exists (the workspace, `record_run`,
  schema-driven fields). If later Track B steps add replay or a generic log, Track A runs
  benefit automatically, but Track A never waits for them.
- **Order of Track A modules** can follow the school's teaching order.

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

## Sources
**Primary (read directly; copies supplied by the author, not committed to the repository):**
- International Baccalaureate Organization, *Diploma Programme Physics guide, first
  assessment 2025* (published February 2023, updated May 2023).
- International Baccalaureate Organization, *Diploma Programme Economics guide, first
  assessment 2024* (published February 2020, updated October 2022).

**Secondary (web search only, used for the cohort question and superseded where they
conflict with the primary sources):**
- Extended essay guide, first assessment 2027 (the only "first assessment 2027" IB document
  found): https://ibo.org/globalassets/new-structure/university-admission/pdfs/subject-guides/extended-essay-first-assessment-2027-guide-sbs.pdf
- IB subject briefs: https://ibo.org/globalassets/new-structure/programmes/dp/pdfs/sl-economics-en.pdf
  and https://ibo.org/globalassets/new-structure/programmes/dp/pdfs/hl-economics-en.pdf
- Economics review timing (third party): https://owltutors.co.uk/advice/ib/economics/syllabus/
