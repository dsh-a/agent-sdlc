# Interpreter Pattern

> **Type**: template
> **Category**: behavioral
> **Triggers**: interpreter, grammar, expression tree, DSL, rule engine, evaluate expression, query language
> **Related**: composite, iterator, visitor, flyweight

## Intent

Given a language, define a representation for its grammar along with an interpreter that uses the representation to interpret sentences in the language.

## When to use

Scaffold an interpreter when there is a **recurring problem expressible as sentences in a simple language**, and representing those sentences as an expression tree lets you evaluate them uniformly.

- There is a language to interpret, and statements can be represented as abstract syntax trees.
- The grammar is **simple**. For complex grammars the class hierarchy becomes unmanageable — use a parser generator instead, which builds the tree without a class per rule.
- Efficiency is not a critical concern. The most efficient interpreters usually translate to another form first rather than walking trees directly.
- Typical fits: search filters, permission rules, pricing conditions, feature-flag predicates, validation rule sets that users or config can author.

**Not when:**
- The grammar is large or evolving fast. One class per rule stops scaling; reach for a parser generator or an existing expression library.
- The "language" is a fixed set of a few conditions. Write them as code; `minimalism` forbids a grammar for three cases.
- Evaluation is on a hot path where tree-walking overhead matters.
- The input is untrusted and you have not bounded depth and cost — an interpreter over hostile input is a denial-of-service surface.

## Participants

| Role | Responsibility | Path |
|---|---|---|
| AbstractExpression | Declares the `interpret` operation common to every node | `<domain layer>/<feature>/Expressions/I<Name>Expression.<ext>` |
| TerminalExpression | A leaf; implements `interpret` for a terminal symbol (literal, field reference) | `<domain layer>/<feature>/Expressions/<Name>LiteralExpression.<ext>` |
| NonterminalExpression | A composite rule; holds child expressions and interprets by recursing | `<domain layer>/<feature>/Expressions/<Rule>Expression.<ext>` |
| Context | Carries global state the interpreter needs during evaluation | `<domain layer>/<feature>/Expressions/<Name>Context.<ext>` |
| Parser / builder | Turns source text or config into the expression tree (not part of GoF; usually needed) | `<domain layer>/<feature>/Expressions/<Name>Parser.<ext>` |
| Client | Builds (or is handed) the tree and invokes `interpret` | `<domain layer>/<feature>/<Feature>Service.<ext>` |
| Test — expression | Verifies each rule node in isolation | `<test tree>/<feature>/Expressions/<Rule>ExpressionTests.<ext>` |
| Test — parser | Verifies text/config maps to the expected tree, and that bad input fails | `<test tree>/<feature>/Expressions/<Name>ParserTests.<ext>` |

Adapt paths to the project's structure (per `.omp/agent-config.md` § Layer Boundaries).

### Structure

```
  Client ──▶ «interface» AbstractExpression ◀──── Context
                 + interpret(context)
                        △
        ┌───────────────┴───────────────┐
  TerminalExpression          NonterminalExpression ──children──┐
   + interpret()               + interpret()  ◀─────────────────┘
                               (recurses into children)
```

**Collaborations:** the client builds the sentence as a tree of Nonterminal and Terminal expressions, initialises the context, and invokes `interpret`. Each NonterminalExpression defines `interpret` in terms of its children; TerminalExpression nodes form the base cases of the recursion.

## Dependencies

- AbstractExpression and all expression nodes: domain types and the Context only — no framework imports, no injected services.
- Context: the domain values evaluation reads (the subject under test, variable bindings, a clock).
- Parser: the expression node types; it is the only component that touches raw input.

## Template

Use the active pack's `scaffold-snippets.md` for the concrete idiom. Shape:

```
// AbstractExpression: I<Name>Expression with interpret(<Name>Context) -> <Result>.
// TerminalExpression: one class per terminal symbol; interpret() reads from the
//   context and returns a value. No children.
// NonterminalExpression: one class PER GRAMMAR RULE (And, Or, Not, Comparison…);
//   holds child expressions; interpret() recurses and combines.
// Context: immutable where possible; carries variable bindings and evaluation input.
// Parser: source/config -> tree. Validates and fails with a domain error; the
//   expression nodes themselves then assume a well-formed tree.
```

## Wiring

Register the parser and, if the grammar is fixed, a cached compiled tree in the DI container (per `.omp/agent-config.md` § Pattern Compliance). Expression nodes are **built, not injected** — the parser or a builder constructs them. Parse once and reuse the tree where the same rule is evaluated repeatedly; re-parsing per evaluation is the usual performance mistake with this pattern. Where many trees share identical terminal nodes, `flyweight.md` applies to the terminals.

## Conventions

- One class per grammar rule, named for the rule. If a class handles two rules, the grammar and the hierarchy have drifted apart.
- Expression nodes are immutable and free of side effects — `interpret` reads the context and returns a value; it does not mutate it.
- All evaluation state lives in the Context, never in the nodes, so one tree can be evaluated concurrently against different contexts.
- The parser owns validation. By the time a tree exists it is well-formed, so nodes need no defensive checks.
- Bound recursion depth explicitly when input is untrusted, and prefer an explicit stack for deep trees.
- Keep the grammar documented next to the expression classes; the hierarchy *is* the grammar, and an undocumented one cannot be reviewed.
- Adding a new **operation** over the tree (pretty-print, optimise, type-check) is a job for `visitor.md`, not another method on every node.

## Tests

- Test each expression class in isolation with a hand-built tree and a constructed context.
- Test each terminal against present, absent, and wrong-typed context values.
- Test each nonterminal's combination logic, including short-circuit behaviour where it applies.
- Test nesting to at least three levels, so recursion is genuinely exercised.
- Test the parser separately: valid input builds the expected tree; malformed input fails with a domain error rather than a partial tree.
- Test round-tripping if the grammar has a printer, and depth limits if input is untrusted.

## Consequences

1. **It is easy to change and extend the grammar.** Because the pattern uses classes to represent grammar rules, inheritance changes or extends the grammar; existing expressions can be modified incrementally, and new ones defined as variations on old ones.
2. **Implementing the grammar is easy, too.** Classes defining nodes have similar implementations — they are easy to write and often generatable.
3. **Adding new ways to interpret expressions is easy.** A new operation over the tree (pretty-printing, type-checking, optimisation) is added with `visitor.md` rather than by editing every expression class.
4. **Cost: complex grammars are hard to maintain.** The pattern needs at least one class per rule, so a grammar with many rules becomes a large, hard-to-manage hierarchy. At that point a parser generator or compiler is the right tool — it can interpret the same expressions without building the class hierarchy at all.
