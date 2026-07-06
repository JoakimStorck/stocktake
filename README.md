# stocktake

Code-audited stock-and-flow diagrams in the notation of Forrester,
*Industrial Dynamics* (1961, MIT Press), ch. 8, built from numerical
Python simulation code.

## Design premise

**What the diagram shows is hand-declared; whether it is true of the code
is audited; where it is drawn is generated automatically.** What the tool
rejects is generating the diagram's *content* from the code —
auto-laying-out the raw dependency graph produces noise, and hand-drawing
the figure in a separate tool drifts silently from the code. Auto-laying
out the *declared* figure is neither: the human decides what the diagram
says, the code verifies it, and the layout follows mechanically and
asserts nothing.

The pipeline has three layers plus an emitter:

1. **Code edges** — variable dependencies extracted from the AST of the
   simulation source (every assignment yields target ← dependency edges).
2. **Concept edges** — code variables mapped to named theoretical
   concepts through a TOML dictionary; unmapped variables fall out and
   are reported.
3. **Figure audit** — the diagram is hand-declared in a `[[figures]]`
   TOML section (nodes with Forrester kinds, edges with channel types),
   and every edge must list concept-level witnesses that exist with AST
   support, or carry `identity = true` (definitional, mechanism stated)
   or `parameter = true` (a constant is a declaration, not a dataflow
   claim). An unwitnessed edge is a hard build failure.
4. **Emitter** — graphviz dot in Forrester notation, plus an audit CSV
   carrying the mechanism text.

The audit runs in both directions: AST-supported concept edges that no
figure cites are reported (mechanisms the code has that the diagrams
omit — deliberate omissions become decisions), and unmapped variables
are code the vocabulary does not yet name.

A green build certifies figure–code correspondence. It does not certify
that signs or economic interpretations are right; those remain declared.

## Layout

Figures are laid out from their declared structure — no manual
`group`/`ranks`/`hints` needed except as exceptions. Flows are rigid
vertical columns (the spine, held straight) that may translate
vertically; between them are swim lanes where the variables live,
confined so they cannot collapse onto a flow. The unit of lane
assignment is a variable's connected component: a component bridging two
columns goes between them, a connected cluster stays together and goes
central, a lone node goes to the periphery. Placement inside the lanes
is a spring-electrical equilibrium — attraction along edges plus soft
repulsion between nodes — so connected meshes spread into convex,
untangled shapes rather than collapsing into a knot. The goal is the
force balance, not minimum edge length.

Layout quality is measured, not asserted by eye: `stocktake.metrics`
reports crossings, information-line length, node overlaps, and lines
passing through node bodies, used as regression guardrails. Explicit
user layout always wins over the derived layout; `layout = "manual"` on
a figure bypasses the engine entirely.

## Usage

```
stocktake build model.py concept_map.toml -o results/ --render
```

Requires Python ≥ 3.11 (no runtime dependencies) and graphviz for
`--render`. See `tests/fixtures/` for a complete minimal example of a
model and concept map; the schema is documented in
`src/stocktake/schema.py`.

Adverse audit outcomes are reported as-is and exit non-zero: honest
failure reporting is a feature of the tool.

## Provenance

Extracted from
[technology-fields](https://github.com/JoakimStorck/technology-fields)
(`experiment/cld/`, commit `69ec1fd`), where it audits a dynamic
labour-market model and produces a manuscript figure. The Forrester
notational conventions were settled there over six render iterations.

## License

MIT.
