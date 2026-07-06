# stocktake: code-audited stock-and-flow diagrams

A whitepaper on the principles behind the tool and how they are
implemented.

Version 0.3.0 · Origin: `github.com/JoakimStorck/technology-fields`
(`experiment/cld/`)

---

## 1. What the tool is, and the premise it defends

`stocktake` generates stock-and-flow diagrams in the notation of Jay
Forrester, *Industrial Dynamics* (1961, MIT Press, ch. 8), from
numerical Python simulation code. Its design keeps three things
separate that are easy to conflate:

> **What the diagram *shows* is hand-declared. Whether it is *true of the
> code* is audited. Where it is *drawn* is generated automatically.**

A human decides the diagram's content — which nodes exist, what
Forrester role each plays, which edges connect them, in what channel.
The code decides whether that content is true. The machine decides only
the layout, which asserts nothing about the model: moving a node changes
nothing the diagram claims.

What the tool rejects is a fourth thing — generating the diagram's
*content* from the code — and it rejects it in both of its usual forms,
each with a characteristic failure mode:

- **Auto-generation from the raw dependency graph.** A real model has
  hundreds of variable dependencies; laying them all out automatically
  is unreadable noise, and no algorithm recovers the theoretical
  structure a modeller means to show.
- **Hand-drawing** the figure in a separate tool produces *drift*. The
  moment the code changes, the hand-drawn figure is silently wrong, and
  nothing detects it.

The distinction that dissolves the apparent tension — a hand-declared
figure that is nonetheless laid out automatically — is between the two
kinds of automation. Auto-laying-out the *raw dependency graph* (every
edge the code contains) is the rejected noise. Auto-laying-out the
*declared figure* (the handful of edges the modeller chose and the audit
verified) is not: the human has already done the only irreducible work,
which is deciding what the diagram says. The layout is a mechanical
consequence of that decision and carries no claim of its own.

stocktake therefore keeps human judgement over *what the diagram says*,
verifies it against the code, and removes both failure modes — the noise
of raw auto-generation and the drift of hand-drawing — at once.

A green build **certifies a precise, narrow correspondence**: every
declared figure edge is either supported by the extracted concept-level
dependency graph, or explicitly justified as an `identity` or
`parameter` relation with a stated mechanism. That is all it proves. It
does **not** prove that the signs of the relationships are right, that
the causal or economic interpretation is sound, that the relation is
numerically or dimensionally consistent, or that the branch of code
supporting an edge is active in any particular run. Those remain the
modeller's declared claims; the tool records the stated mechanism for
each edge in an audit trail but does not adjudicate it. The narrowness
is deliberate: a guarantee that promised more would be one the tool
could not keep.

---

## 2. Architecture at a glance

The pipeline has three audit layers, an emitter, and a layout engine:

```
run_dynamic.py ──▶ extract ──▶ concepts ──▶ audit ──▶ emit ──▶ Forrester .dot
   (the model)      code         concept      figure    layout      + audit .csv
                    edges        edges        audit     (swim-lane)
                                                │
concept_map.toml ───────────────────────────────┘
   (the declaration: [extract] [variables] [concepts] [[figures]])
```

Each module has one job: `extract` reads the AST, `concepts` maps code
names to theoretical concepts, `schema` loads and validates the TOML,
`audit` checks every declared edge against the code, `emit` writes
Forrester dot, `layout` places the figure, `metrics` measures the
result, `build` orchestrates, `cli` is the command line, and `errors`
is the failure hierarchy. There are no runtime dependencies; the only
external requirement is the Graphviz binary, and only for rendering.

---

## 3. The audit

### 3.1 Code edges (layer 1)

`extract` walks the abstract syntax tree of the simulation source. Every
assignment — `Assign`, `AnnAssign`, `AugAssign` — yields directed
`target ← dependency` edges: for `inflow = GAMMA * pressure`, the edges
`GAMMA → inflow` and `pressure → inflow`. Attribute and subscript
targets are handled (`state.stock += …` credits `stock`), and an
`aliases` table renames or drops identifiers (module prefixes like `np`
and `math` map to the empty string and disappear).

Extraction is deliberately **conservative**, and the asymmetry is the
point:

> A false negative — a real dependency the extractor misses — surfaces
> downstream as a loud audit failure, and the modeller fixes it by
> adding a mapping. A false positive — a phantom dependency the
> extractor invents — would silently certify an edge that the code does
> not support. The first is acceptable; the second is not.

So the extractor errs toward missing rather than inventing — with one
exception that runs the other way and is treated separately below. The
`return`-expression blind spot is a clean false negative: dependencies
inside a bare `return` are not captured (the compensating convention is
to map the function name itself as a variable), so a missed witness
fails loudly and is safe by the asymmetry above.

Feature-flag branches are a different case, and the honest statement is
that the extractor is **configuration-insensitive**: it extracts the
syntactic dependencies present in the parsed source, whether or not a
given branch runs in the configuration being modelled. This is a
*false-positive* risk — the dangerous direction — because it can support
an edge with a dependency that is inactive in the current run. The
present mitigation is a convention, not a guarantee: variant-only
variables are left unmapped, so they produce no witnesses. A
configuration-aware extractor is the proper fix; until it exists, the
modeller must not map variables that live only in an inactive branch.

### 3.2 Concept edges (layer 2)

`concepts` maps code variable names to named theoretical concepts through
the `[variables]` dictionary, then lifts the code edges into concept
space: `pressure → inflow` becomes `Pressure → Inflow` if both are
mapped, and is dropped if either endpoint is unmapped or the mapping
makes it a self-loop.

Variables that no mapping names fall out and are **reported**, not
silently discarded. The unmapped-variable report, sorted by frequency,
is code that the theoretical vocabulary does not yet name — a standing
to-do list for the modeller. A per-model `ignore` list and
`ignore_prefixes` suppress the genuine noise (loop counters, module
prefixes) so the report stays legible.

### 3.3 The figure audit (layer 3)

The diagram is hand-declared in a `[[figures]]` TOML array: nodes with
Forrester kinds (`level`, `rate`, `aux`, `param`, `source`, `sink`) and
edges with channel types (`material`, `personnel`, `orders`, `money`,
`capital`, `information`). Every declared edge must clear one of three
bars:

1. **Witnessed.** The edge lists concept-level *witnesses* — pairs like
   `pressure->inflow` — and each witness must exist as an
   AST-supported concept edge. If a witness has no AST support, the
   figure no longer matches the code: **hard failure**
   (`UnsupportedWitnessError`).
2. **Identity.** The edge carries `identity = true`: it is definitional
   (a source outside the accounting, a mechanism stated in prose rather
   than dataflow). It must state its mechanism, or **hard failure**
   (`MissingMechanismError`).
3. **Parameter.** The edge carries `parameter = true`: a constant is a
   *declaration*, not a dataflow claim. It, too, must state its
   mechanism.

An edge that lists no witnesses and carries neither mark is
**unwitnessed** — the default failure (`UnwitnessedEdgeError`). There is
no silent pass: an edge is justified or the build stops.

### 3.4 The audit runs both ways

The audit is symmetric, and the reverse direction is as important as the
forward one:

- **Forward** (figure → code): every edge the diagram *shows* must be in
  the code. This is the anti-drift guarantee.
- **Reverse** (code → figure): every AST-supported concept edge that *no*
  figure cites is reported (`unwitnessed_concept_edges.csv`). These are
  mechanisms the code has that the diagram omits. Omission is legitimate
  — a diagram is a chosen view, not a dump — but the report makes each
  omission a *decision* the modeller can see and defend, rather than an
  oversight.

Together with the unmapped-variable report, this closes the loop: the
diagram cannot show what the code lacks, the code cannot contain a named
mechanism the diagram silently drops, and the vocabulary's gaps are
visible.

### 3.5 Failure is a feature

Every failure mode above raises a subclass of `StocktakeError`
(`SchemaError` for structural defects, the `AuditError` family for audit
failures). The CLI translates these to exit code 1; library consumers
catch them as exceptions. An adverse audit is the tool *working*, not
the tool breaking — a drifted figure that fails the pipeline loudly is
exactly the outcome the tool exists to produce. Honest failure
reporting is therefore not a courtesy but the core deliverable.

---

## 4. The layout

A figure that passes the audit still has to be drawn. The layout is
**derived from the declared structure** — what is a level, a rate, an
auxiliary, a constant, a boundary — so that the modeller needs manual
placement hints only as exceptions. This is the automation the premise
permits: it lays out the *declared* figure (the handful of audited
edges), not the raw dependency graph, and it decides only placement,
never content.

### 4.1 The grounding distinction

Everything in the layout rests on one distinction, taken from Forrester:
a diagram contains two fundamentally different kinds of relation.

- **Conserved flows** — material, personnel, orders, money, capital —
  transport an accumulated quantity through levels and rates. They are
  the diagram's skeleton.
- **Information relations** — a variable read, computed, or used to set
  a rate — transport nothing. They hang off the skeleton.

These are drawn differently (solid or decorated lines for flows, dashed
lines with a take-off circle for information) *and* they behave
differently under layout, which is the subtler point.

### 4.2 The skeleton is rigid

Conserved-flow chains — `source → rate → level → rate → … → sink` — form
vertical **columns**, held straight (their nodes share one x by
construction), with the flow direction fixing the rank order (sources at
the top, sinks at the bottom). Levels are placed by their position in
the chain, rates sit between their upstream and downstream. The spine
never bends to shorten an information line. A column may *translate
vertically* as a rigid unit to align with the variables it serves, but
its shape is fixed.

The current implementation identifies a column with a **weakly connected
component** of the conserved-flow subgraph. This is an approximation that
holds for chain-like channels — the case in the origin model — but is not
the final theory. A weakly connected component says only "these flow
nodes belong together"; it does not distinguish a simple spine from a
branch, a confluence, or two distinct channels that happen to meet at a
shared rate. The principled replacement is **channel decomposition** —
laying out by conserved-quantity channel (material, personnel, orders,
money, capital) rather than by mere connectivity — and it will be needed
when a figure with branching or merging flows arrives. Until then, the
weakly-connected-component rule stands as a documented first
approximation.

### 4.3 Information does not shape the skeleton

Information edges must not distort the flow ranks. The consequence, made
concrete, is the **swim-lane model**, which is the heart of the layout:

> Between and outside the flow columns are **swim lanes** — vertical
> bands in which the variables (auxiliaries and constants) live,
> confined so they can never collapse onto a flow.

The confinement is what makes the layout stable: a variable cannot drift
onto a spine node, because the lane it lives in is a separate horizontal
region.

### 4.4 The unit of lane assignment is the connected component

Which lane does a variable go in? The answer is **not** per-variable —
that was a real bug in an early version — but per **connected
component** of the variable subgraph:

- A component that **bridges two columns** (has neighbours in both) goes
  in the lane **between** them.
- A **connected cluster** attached to a single column stays **together**
  and goes to the **central** side (toward the other columns).
- A **lone** node goes to the **periphery**, on the outer side.

The reason this must be a component, not a node: a hub variable may feed
two other variables which in turn feed a rate, so it is connected to the
flow only *transitively*. Assigning lanes per node splits such a hub
from the cluster it belongs to and forces their mutual edges to cross
the flow. The component captures the transitive link and keeps the
cluster whole. (In the origin model this is the `A_K → {∂ΔΓ, 1−a} →
seeding` cluster: A_K touches no flow node directly, yet belongs firmly
in the middle of the cluster.)

Stated for an arbitrary number of columns, the rule is: let a component
touch the set `C` of flow columns. If `|C| = 0`, it goes in the nearest
default lane; if `|C| = 1`, in a lane adjacent to that column (inward
unless congested); if `|C| ≥ 2`, in the lane interval spanning `min(C)`
to `max(C)`. One case is deliberately left open as a known
generalisation point: a component that connects columns 1 and 3 but not
2 must either straddle column 2's band or be split, and choosing between
those wants a rule the single origin figure does not yet motivate. The
two-column case is fully settled; the `≥ 3`-column ordering and this
straddling case are provisional.

### 4.5 Placement is a force balance, not a length minimisation

Inside the lanes, nodes are placed by a **spring-electrical
equilibrium**:

- **Attraction** along every edge (Fruchterman–Reingold: a force
  proportional to `d²/K`, pulling connected nodes together).
- **Soft repulsion** between every pair of nodes (proportional to
  `K²/d`, pushing them apart).
- A **hard minimum-gap** pass afterward as a floor, guaranteeing no two
  node boxes overlap.

The distinction between the soft repulsion and the hard gap is the
lesson that took the longest to learn and matters most:

> **The goal is the force balance, not minimum edge length.**

Minimising total line length alone is a trap: two coincident nodes have
zero line between them and no crossing, so a pure length-minimiser
*rewards* collapsing a connected mesh into a single tangled knot. The
soft repulsion is what spreads such a mesh into a **convex, untangled
shape**; without it, attraction wins and the cluster implodes. A hard
minimum-gap constraint is not a substitute — it prevents boxes from
overlapping but does nothing to untangle the edges between them. Both
are needed: the soft repulsion for the shape, the hard gap for the
floor.

### 4.6 Parameters

The force model's parameters are documented defaults, tuned against
Figure 2 of the origin manuscript to reach a clean result. They are
data, not magic:

| parameter | value | role |
|---|---|---|
| `IDEAL_EDGE_LEN` | 70 pt | spring rest length; raise to spread nodes |
| `REPULSION` | `K²` | strength of the spreading force |
| `INIT_TEMPERATURE` | 60 pt | initial max displacement per step |
| `COOLING` | 0.985 | geometric temperature decay |
| `ITERATIONS` | 300 | iteration count |
| `NODE_GAP` | 12 pt | hard minimum clearance between boxes |
| `LANE_CLEARANCE` | 52 pt | keep variables off the flow columns |
| `COLUMN_PULL` | 0.02 | strength of vertical column translation |

The simulation is fully **deterministic**: fixed initial positions (from
a first Graphviz pass), fixed iteration count, fixed cooling schedule, no
randomness.

### 4.7 The priority model and layout modes

Derived layout never overrides the modeller:

```
explicit user layout  >  derived layout  >  Graphviz default
```

This holds in principled mode, not only in manual. In principled mode
the derived layout improves everything the modeller has *not* fixed,
while honouring what they have:

- A node with an explicit `pos = "x,y"` is **pinned**: excluded from the
  force displacement entirely, an immovable anchor the rest of the
  layout arranges around (and avoids, via repulsion). This is the
  round-trip the interactive-editing goal called for — render, read a
  node's coordinates, pin them in the TOML, rebuild.
- Nodes sharing a user `ranks` group are **rank-locked**: frozen to a
  common y, free to move only laterally within their lane.

Lane-pinning (fix a node's lateral band but let it float vertically) and
per-edge `hints` are not yet honoured inside the force pass; a figure
that needs those still uses manual mode. A figure may set `layout =
"manual"` to bypass the engine entirely and use only the declared
`group`/`ranks`/`hints` — the escape hatch, and the mode that reproduces
a hand-tuned layout exactly. `layout = "principled"` (the default) runs
the swim-lane engine. If Graphviz is absent, the engine falls back to a
structural emission that any Graphviz layout can render, rather than
failing.

---

## 5. Measurement

Layout quality is **measured, not asserted by eye**. Five structural
metrics live in `metrics`, each added because it caught a defect the
others missed:

1. **Crossings** — information lines that cross. The headline
   readability number.
2. **Information-line length** — total drawn length of dashed lines.
   Long swooping lines read badly even when nothing crosses.
3. **Node overlaps** — pairs of node boxes that overlap. This must be
   measured separately precisely because length and crossings both
   *reward* the collapse that produces overlaps.
4. **Lines through node bodies** — a routing defect that the overlap
   count misses entirely (a line can pass cleanly through a node that
   overlaps nothing).
5. **Spine lateral drift** — the maximum sideways spread within any
   conserved-flow column. The four metrics above measure general
   graphical readability; this one guards the Forrester *skeleton*
   specifically. A wandering material spine was one of the original
   defects, and because the skeleton is the layout's core, its
   straightness is worth measuring on its own rather than folding into a
   general score. (With flow columns snapped to a single x, it is now 0
   by construction, but the metric remains the guard that would catch a
   regression.)

`DiagramMetrics.is_clean()` reports the hard legibility floor: zero
overlaps and zero lines through nodes. Crossings, length and spine drift
are minimised, not required to be zero. The metrics are computed from the
geometry Graphviz actually produced (parsed from its JSON output); the
absolute values are proxies (spline control points, not the sampled
curve) but consistent across layouts, which is what a regression
guardrail needs.

A caveat the tool takes seriously: **metrics are a guardrail, not the
goal.** Layout of a system-dynamics diagram cannot be reduced to a
scalar. The final judge remains a human looking at the rendered figure;
the metrics exist to catch regressions and degeneracies automatically,
so the human's attention is spent on the questions only a human can
answer.

---

## 6. Implementation

### 6.1 Module map

| module | responsibility |
|---|---|
| `extract` | AST → code edges; aliasing; conservative extraction |
| `concepts` | code → concept mapping; unmapped-variable report |
| `schema` | load and validate the TOML; structural invariants |
| `audit` | witness checking; the three bars; dual-direction report |
| `emit` | Forrester dot; label typesetting; layout orchestration |
| `layout` | swim-lane force model; pure and deterministic |
| `metrics` | the five structural-quality measures |
| `build` | the pipeline; the build report |
| `cli` | `stocktake build model.py map.toml -o dir [--render]` |
| `errors` | `StocktakeError` hierarchy |

### 6.2 The two-pass layout

`layout` is kept pure — no subprocess calls — so it is testable without
Graphviz. The Graphviz calls live in `emit.compute_layout`, which runs
the layout in two passes:

1. **Structural frame.** Emit the figure as structural dot (spines held
   straight by derived groups, information edges set `constraint=false`)
   and run `dot -Tjson` on it to read the initial node positions and
   sizes.
2. **Force balance.** Feed that frame to `layout.derive_positions`, the
   pure spring-electrical simulation, which returns final positions.

The positioned figure is then emitted with every node pinned via `pos`
and rendered with `neato -n2`, which draws at the given coordinates and
routes the splines. Manual mode skips both passes and lets `dot` lay the
structural emission out directly.

### 6.3 The schema

The concept map is a single TOML file with four sections:

- `[extract]` — model-specific `aliases`, `ignore`, and
  `ignore_prefixes` (kept out of the tool so the tool stays generic).
- `[variables]` — code name → concept id.
- `[concepts]` — concept id → display name.
- `[[figures]]` — one or more hand-declared figures, each with `nodes`
  and `edges`, optional `layout` mode, and optional user layout
  (`group`, `ranks`, `hints`).

Validation is strict and fails early: a duplicate node id, an edge or
rank referencing an undeclared node (which Graphviz would otherwise
turn into a silent phantom node), an unknown node kind or channel, a
`[variables]` value naming a concept absent from `[concepts]`, or a
witness naming an unknown concept (so a typo reads "unknown concept",
not the misleading "no AST support") — each is a `SchemaError` before
the audit runs.

### 6.4 Forrester notation as implemented

The notational conventions were settled over six render iterations in
the origin repo and are not relitigated without cause:

- **Levels** are rectangles; **rates** are the valve glyph ⋈ (U+22C8) in
  the flow channel, with the name beneath; **auxiliaries** are circles;
  **sources and sinks** are dashed ellipses (approximating Forrester's
  clouds); **parameters** carry the Forrester constant symbol ─⊖─ above
  a ported cell.
- **Channels**: material is a solid line; personnel a double line;
  information a dashed line with a take-off circle (`arrowtail=odot`) at
  the source. A constant's information line departs from the port
  undecorated — the bar-through-circle glyph *is* the take-off.
- **No `+`/`−` signs on edges.** *Industrial Dynamics* carries the
  mechanism in the rate equations; stocktake carries it in the audit's
  mechanism column, not as sign annotations that would themselves drift.
- Labels are plain math-ish text (`theta_abs`, `A_K(t)`, `∂_tΔΓ^D`); the
  emitter converts `_token`/`^token` to subscript/superscript and
  newlines to line breaks, with explicit DejaVu Sans faces inside the
  HTML labels.
- **Deliberately no equation numbers inside the symbols** — hardcoded
  manuscript numbering in a generated artifact is silent-drift bait;
  equation linkage belongs in the figure caption.

---

## 7. Known limitations

In keeping with the tool's own ethos, the current state is reported as
it is:

- **The return-expression blind spot.** Dependencies inside a bare
  `return` are not extracted; the compensating convention is to map the
  function name as a variable. A clean false negative, safe by the
  conservative asymmetry, documented as an `xfail` test, awaiting a real
  fix.
- **Configuration-insensitive extraction — a false-positive risk.** The
  extractor reads syntactic dependencies from the parsed source
  regardless of which feature-flag branch runs. This is the *dangerous*
  direction: it can support an edge whose dependency is inactive in the
  modelled configuration. The present mitigation (leave variant-only
  variables unmapped) is a convention, not a guarantee. A
  configuration-aware extractor is the proper fix.
- **Parameters tuned against one figure.** The force-model defaults were
  tuned against a single figure. They are robust to cosmetic changes in
  that figure, but a genuinely different figure may need retuning; the
  five metrics are the guardrail that will catch it.
- **Weakly connected components as flow columns.** A column is currently
  a weakly connected component of the flow subgraph — an approximation
  valid for chain-like channels but blind to branches, confluences, and
  distinct channels meeting at a shared rate. Channel decomposition is
  the intended replacement, needed when a branching or merging flow
  arrives.
- **Provisional lane rules.** The ordering of three-or-more parallel
  spines, the side distribution of several lone variables on one node,
  and the straddling of a component that skips a middle column are all
  settled only for the two-column case exercised so far.
- **The priority model is partially implemented.** In principled mode,
  explicit `pos` pins a node (excluded from displacement) and a user
  `ranks` group locks its members' shared y — these now survive the
  force balance, verified by regression tests. What does *not* yet
  survive it: lane-only pinning (fix lateral band, float vertically) and
  per-edge `hints`. A figure needing those uses manual mode. Closing the
  remaining gap completes the model.

None of these compromises the audit, which is the tool's core guarantee.
They are extraction and layout refinements, and each will become visible
— and be addressed — when a second figure or a third channel arrives.

---

## 8. Provenance

stocktake was extracted from the research repository
`github.com/JoakimStorck/technology-fields`, where it began as
`experiment/cld/` and produced Figure 2 of a manuscript on dynamic
labour-market modelling. The research repository now consumes stocktake
as a dependency rather than containing it; a thin consumer
(`experiment/cld/build_figure.py`) audits the model against the figure
declaration and emits the figure into the results directory, failing the
pipeline loudly on an adverse audit. The Forrester notational
conventions and the layout principles above were both settled in that
setting, against a real model under active revision.

MIT licensed. Zero runtime dependencies. Python ≥ 3.11.
