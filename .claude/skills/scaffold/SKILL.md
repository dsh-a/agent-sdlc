# Scaffold

You are scaffolding a new component. This skill supports multiple scaffold types — not just syncable entities.

The component to scaffold: **$ARGUMENTS**

---

## Step 1 — Determine scaffold type

Inspect $ARGUMENTS to determine what to scaffold. If ambiguous, ask the user.

| Type | Trigger | Example |
|---|---|---|
| **Syncable entity** | "entity", "model", or a noun that implies a data object | `/scaffold Equipment` |
| **Local-only entity** | "local entity", "local model", or explicitly no sync | `/scaffold local Notification` |
| **Use case** | "use case" or a verb phrase | `/scaffold use case CreateWorkout` |
| **Facade** | "facade" | `/scaffold facade RoutineBuilder` |
| **Service** | "service" | `/scaffold service Analytics` |
| **ViewModel + View** | "view", "screen", "page" | `/scaffold view WorkoutDetail` |

Then jump to the corresponding section below.

---

## Step 2 — Check for conflicts (all types)

Before creating anything:
- Search `lib/` for existing files with the same name
- If conflicts exist, stop and ask the user whether to extend or rename

---

## Syncable Entity (full stack)

For entities that sync between local Drift DB and remote Supabase.

### Gather requirements
1. What is the entity name?
2. What fields does it have? (name, type, nullable, default)
3. Does it belong to a user? (needs `createdBy`, `visibility` fields)
4. Does it have foreign keys to other entities?

### Propose the plan

**New files:**
1. `lib/domain/models/<entity>_model.dart` — model with `Syncable` mixin
2. Drift table in `lib/data/database/tables/` — extends `SyncableTable`
3. `lib/data/adapter/<entity>_adapter.dart` — implements `ModelAdapter`
4. `lib/data/repositories/<entity>/i_<entity>_repository.dart` — interface
5. `lib/data/repositories/<entity>/<entity>_repository.dart` — implementation

**Modified files:**
6. `lib/data/database/app_database.dart` — add table import and include
7. `lib/dependencies/di_repositories.dart` — add to `AppRepositories`, `_createRepo`, provider list

Wait for user approval before writing code.

### Create the model
- Place in `lib/domain/models/<entity>_model.dart`
- Use `with Syncable<EntityName>`
- Include: `id` (String, default `Utils.newUUID()`), `createdDate`, `lastUpdated`
- If user-owned: `createdBy`, `visibility`
- Syncable fields: `needsSync`, `lastSync`, `isDeleted`
- Implement `copyWith()` (required by Syncable)
- Implement `toString()`
- No Flutter imports — domain layer is pure Dart

### Create the Drift table
- Extend `SyncableTable` (provides `id`, `lastUpdated`, `needsSync`, `lastSync`, `isDeleted`)
- Add entity-specific columns
- If user-owned: `createdBy` with `.references(UserLocal, #id)` and `visibility` with `.map(visibilityConverter)`
- Use Drift converters from `drift_converters.dart` for enums
- Override `primaryKey => {id}`

### Create the adapter
- Implement `ModelAdapter<Entity, EntityData, EntityCompanion>`
- Constructor takes `AppDatabase`
- Implement: `fromJson`, `toJson`, `fromDrift`, `toCompanion`, `tableName` getter, `table` getter
- Use `snake_case` keys in JSON (Supabase column names)
- Use `Value()` wrapper for all Companion fields

### Create the repository
**Interface**: `abstract interface class I<Entity>Repository implements IRepository<Entity> {}`

**Implementation**:
- Extend `Repository<Entity, EntityData, EntityCompanion>`
- Implement `I<Entity>Repository`
- Constructor takes `DriftDataSource`, `RemoteDataSource`, `ConnectivityService`, and adapter
- Add a `Logger` instance
- Override `insert`, `update`, `delete` with validation if needed
- Add `_validate()` method stub

### Wire into DI
- `lib/dependencies/di_repositories.dart`: add imports, field, constructor param, `_createRepo` call, provider
- `lib/data/database/app_database.dart`: import table, add to `@DriftDatabase(tables: [...])`

### Run codegen
`flutter pub run build_runner build --delete-conflicting-outputs`

### Supabase remote table (user-confirmed)

For syncable entities, a matching table must exist in Supabase. **Never auto-execute schema changes.** Follow this process:

1. **Read the current Supabase schema** using the Supabase MCP (`list_tables`) to understand what exists
2. **Generate the CREATE TABLE SQL** matching the Drift table definition:
   - Table name matches the adapter's `tableName`
   - Column names use `snake_case` matching the adapter's `toJson` keys
   - Column types map from Dart types (String → text, DateTime → timestamptz, bool → boolean, int → integer)
   - Include `id text PRIMARY KEY`
3. **Generate RLS policies** (opus-level judgment):
   - Default: enable RLS, add policy for authenticated users to CRUD their own rows (`auth.uid() = created_by`)
   - If the entity has `visibility = public`, add a SELECT policy for all authenticated users
4. **Present the full SQL to the user** and ask for explicit approval before executing
5. **Allowed operations**: CREATE TABLE, ALTER TABLE (ADD COLUMN only), UPDATE (non-destructive data backfills), CREATE POLICY, ALTER POLICY
   **Forbidden operations**: DROP (table, column, policy), DELETE, TRUNCATE, ALTER TABLE (DROP COLUMN, ALTER TYPE that loses data, RENAME that breaks references)
   If a forbidden operation is needed, present it to the user and let them handle it.
6. **If execution fails or is rejected**, note it as a remaining step — do not block the rest of the scaffold

**Safety rule**: Prefer incomplete tasks over any risk of corrupting or destroying existing Supabase data. If there is any doubt about whether a SQL statement could affect existing data, do not execute it — present it to the user instead.

### Verify
- `flutter analyze`
- List remaining steps (UI, tests, any Supabase steps that were deferred)

---

## Local-Only Entity

For entities stored only in Drift with no Supabase sync. Same as syncable entity with these differences:

### Model
- Do **not** use `Syncable` mixin
- Include `id` (String, default `Utils.newUUID()`) and entity-specific fields
- Still implement `copyWith()` and `toString()`
- No `needsSync`, `lastSync`, `isDeleted` fields

### Drift table
- Extend `Table` directly (not `SyncableTable`)
- Define `id` column manually: `TextColumn get id => text()()`
- Override `primaryKey => {id}`
- No sync columns

### Adapter
- Still implements `ModelAdapter` but `toJson`/`fromJson` can be minimal or throw `UnimplementedError` if there's truly no remote use
- `fromDrift` and `toCompanion` are still required

### Repository
- Extend `Repository` but the `RemoteDataSource` can be a no-op implementation
- OR create a simpler local-only repository that wraps just the `DriftDataSource` without the sync `Repository` base class — check if a `LocalRepository` pattern exists in the codebase first

### DI wiring
Same as syncable entity.

---

## Use Case

Use cases encapsulate a single business operation. They live in `lib/domain/`.

### Gather requirements
1. What does this use case do? (single verb phrase)
2. What repositories, services, or other use cases does it depend on?
3. What does it return?

### File location
`lib/domain/<feature>/use_cases/<use_case_name>_use_case.dart`

### Pattern (from existing use cases)
```dart
import 'package:logging/logging.dart';
// import dependencies

class <Name>UseCase {
  final Logger _log = Logger('<Name> Use Case');

  // Dependencies (repos, services, other use cases)
  final ISomeRepository _someRepository;

  <Name>UseCase({
    required ISomeRepository someRepository,
  }) : _someRepository = someRepository;

  /// [description of what execute does]
  Future<ReturnType> execute(ParamType param) async {
    // implementation
  }
}
```

### Convention
- One public method: `execute()` (or a descriptively named method if `execute` is ambiguous)
- Dependencies injected via constructor, stored as private final fields
- Uses `Logger`, never `print`
- No Flutter imports — pure Dart
- Calls repositories/services, never adapters or database directly

### Wire into DI
Add to `lib/dependencies/di_use_cases.dart` as a `Provider`.

---

## Facade

Facades aggregate multiple repositories for complex feature logic. They live in `lib/domain/`.

### Gather requirements
1. What feature area does this facade serve?
2. Which repositories does it aggregate?
3. What operations does it expose?

### File location
`lib/domain/<feature>/facades/<feature>_facade.dart`

### Pattern (from `FeedSocialFacade`)
```dart
import 'package:logging/logging.dart';
// import repository interfaces

class <Feature>Facade {
  final Logger _log = Logger('<Feature> Facade');

  final ISomeRepository someRepository;
  final IOtherRepository otherRepository;

  <Feature>Facade({
    required this.someRepository,
    required this.otherRepository,
  });

  // Public methods that orchestrate across repositories
}
```

### Convention
- Dependencies are repository **interfaces** (not implementations)
- Public constructor fields (not private) — unlike use cases, facades expose their repos for flexibility
- No Flutter imports — pure Dart
- Contains cross-repo orchestration logic, not business rules (those go in use cases)

### Wire into DI
Add to `lib/dependencies/di_facades.dart` as a `Provider`.

---

## Service

Services wrap infrastructure concerns (auth, connectivity, settings). They live in `lib/data/services/`.

### Gather requirements
1. What infrastructure concern does this service wrap?
2. What external dependencies does it need (Supabase, platform APIs, etc.)?

### File location
`lib/data/services/<service_name>_service.dart`

### Pattern (from existing services)
- Class with `Logger` instance
- Constructor takes external dependencies
- Public methods expose the operations
- May use Flutter imports (unlike domain layer)

### Wire into DI
Add to `lib/dependencies/di_services.dart` as a `Provider`.

---

## ViewModel + View

ViewModels are `ChangeNotifier`s that expose state and actions to Views.

### Gather requirements
1. What screen or component is this for?
2. What use cases or facades does the ViewModel depend on?
3. What state does it expose? (loading, error, data fields)
4. What actions does it expose? (methods the View calls)

### File locations
- ViewModel: `lib/ui/<feature>/view_models/<feature>_view_model.dart`
- View: `lib/ui/<feature>/views/<feature>_view.dart`

### ViewModel pattern (from `LoginViewModel`)
```dart
import 'package:flutter/foundation.dart';
import 'package:logging/logging.dart';

class <Feature>ViewModel extends ChangeNotifier {
  // Dependencies (use cases, facades, services)
  final Logger _log = Logger('<Feature> ViewModel');

  // State
  bool _isLoading = false;
  bool get isLoading => _isLoading;

  String? _errorMessage;
  String? get errorMessage => _errorMessage;

  // Constructor with required deps

  // Public methods (called by View)

  // Private methods
}
```

### View convention
- Calls methods on ViewModel only — never repos, services, or use cases
- Uses `Theme.of(context).textTheme` and `Theme.of(context).colorScheme`
- Uses `const` constructors where possible
- Breaks large `build()` into small private `Widget` classes

### Wire into DI
- ViewModel: add to `lib/dependencies/di_view_models.dart` as a `ChangeNotifierProvider`
- Route (if needed): add to `lib/router.dart`

---

## Final step (all types)

- Run `flutter analyze`
- Confirm everything compiles cleanly
- List remaining steps the user needs (tests, additional wiring)
