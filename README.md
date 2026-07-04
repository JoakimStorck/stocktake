# stocktake

Code-audited stock-and-flow diagrams in the notation of Forrester,
*Industrial Dynamics* (1961, MIT Press), ch. 8, built from numerical
Python simulation code.

## Design premise

**The figure is hand-declared and code-audited, not code-generated.**
Auto-layout of raw dependency graphs produces noise; hand-drawn diagrams
silently drift from the code. The audit removes the drift failure mode
while keeping human judgement over what the diagram says.

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
