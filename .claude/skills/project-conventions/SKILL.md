---
name: project-conventions
description: Canonical project conventions for this codebase — the single source of truth loaded by ui-story, scaffold, test, and review. Member order, naming, layer boundaries, logging, file locations, entity construction. Do not duplicate these rules in agent prompts. Project-specific overrides live in `.omp/agent-config.md` § Pattern Compliance and § Layer Boundaries.
disable-model-invocation: true
---

# Project Conventions

> **This is the ACTIVE conventions skill.** Agents load it deterministically via their
> `skills:` frontmatter — it is the one place language/framework rules live. The body
> below is populated from the **`flutter` pack** (`.claude/packs/flutter/conventions.md`).
> To switch stacks, run `/setup` or copy another pack's `conventions.md` body here. See
> `.claude/packs/README.md`.
>
> **Active pack:** see `.omp/agent-config.md` → **Active Pack** (`flutter`).

This codebase targets **Flutter/Dart** with **MVVM (`ChangeNotifier` + Provider)**. The rules below are authoritative when this pack is active. Project-specific overrides live in `.omp/agent-config.md` § Pattern Compliance and § Layer Boundaries — read those first; what follows applies unless overridden.

---

## Layer boundaries

- **Views** call methods on the ViewModel only — never repositories, services, or use cases directly.
- **ViewModels** depend on use cases / facades — never repositories or adapters directly.
- **Use cases** depend on repositories / services. Never Flutter imports (pure Dart).
- **Facades** aggregate repository interfaces. Public constructor fields (not private). Never Flutter imports.
- **Repositories** depend on data sources + adapters. Drift / Supabase live here.

---

## ViewModels

- Extend `ChangeNotifier`.
- Dependencies via constructor (use cases, facades — never repos directly).
- Use `Logger`, never `print`.
- **Class member order**: external deps → internal deps → state variables → constructor → public methods → private methods.
- State exposure pattern: private field + public getter.

```dart
class FeatureViewModel extends ChangeNotifier {
  final Logger _log = Logger('Feature ViewModel');

  bool _isLoading = false;
  bool get isLoading => _isLoading;

  String? _errorMessage;
  String? get errorMessage => _errorMessage;

  // Constructor with required deps
  // Public methods (called by View)
  // Private methods
}
```

File location: `lib/ui/<feature>/view_models/<feature>_view_model.dart`. DI wiring: `lib/dependencies/di_view_models.dart` as a `ChangeNotifierProvider`.

---

## Views

- Use `context.watch<ViewModel>()` or `context.read<ViewModel>()` from Provider.
- Use theme tokens: `Theme.of(context).textTheme`, `Theme.of(context).colorScheme`. **Never hardcoded styles.**
- Use `const` constructors wherever possible.
- Break `build()` into small private widget classes when it exceeds ~40 lines.
- Never perform network calls or heavy computation inside `build()`.
- Use `ListView.builder` / `SliverList` for any list longer than a handful of static items.
- Use `Key` values on widgets that need to be found in tests.
- Handle loading and error states explicitly.

File location: `lib/ui/<feature>/views/<feature>_view.dart`. Route wiring (if needed): `lib/router.dart`.

---

## Member order (all classes)

1. Static fields and constants
2. External dependencies (constructor-injected)
3. Internal dependencies / collaborators
4. State variables (private with public getter)
5. Constructor
6. Public methods
7. Private methods

---

## Naming defaults

- Files: `snake_case.dart`.
- Classes: `PascalCase`.
- Members: `camelCase`; private members `_camelCase`.
- Booleans: `isLoading`, `hasError`, `canSubmit` — prefer affirmative names.
- ViewModels: `<Feature>ViewModel`; Views: `<Feature>View`; UseCases: `<Verb>UseCase`; Repositories interface `I<Entity>Repository`.

---

## Logging

- Always `Logger('<Owner> <Role>')` from package `logging`. Never `print`.
- Owners that emit logs: ViewModels, use cases, facades, services, repositories. Views generally do not log.

---

## Imports

- Domain layer (`lib/domain/`, `lib/data/repositories/.../*_repository.dart` interfaces): pure Dart only. No `package:flutter/...` imports.
- UI layer (`lib/ui/`): Flutter imports allowed.
- Data layer (`lib/data/`): Flutter imports allowed for services that wrap platform APIs.

---

## Entity / model construction

Models are immutable — change them only via `copyWith`.

- Constructing inline (full constructor, not copyWith): assign every field of the class explicitly. Do not lean on positional defaults or silently omit nullable fields.
- Calling `copyWith`: name only the fields that change.
- Before you commit, cross-check the constructor call against the class's full field list. A missing or defaulted field is the most common silent data-loss bug in this codebase.

---

## Testing conventions (cross-reference)

Test patterns live in the `test` skill / agent. Two cross-cutting rules anchored here:

- Test path mirrors source path: `lib/ui/auth/login_view_model.dart` → `test/ui/auth/login_view_model_test.dart`.
- Widget tests use a `buildTestApp` helper that wraps `MultiProvider` + the test ViewModel + `MaterialApp(home: MyView())`. Reuse helpers from `test/test_helpers.dart`.

---

## What this skill does NOT cover

- Per-pattern scaffolding detail (use the `scaffold` skill and `.claude/agents/scaffold/*.md`).
- Widget-test patterns (use the `test` skill / agent).
- Architecture-review rubric (use `review` agent's checklist).
- Project-specific overrides (live in `.omp/agent-config.md` § Pattern Compliance).
