# Syncable Entity — Full Stack

For entities that sync between local Drift DB and remote Supabase.

## New files to create
1. `lib/domain/models/<entity>_model.dart` — model with `Syncable` mixin
2. `lib/data/database/tables/<entity>_table.dart` — extends `SyncableTable`
3. `lib/data/adapter/<entity>_adapter.dart` — implements `ModelAdapter`
4. `lib/data/repositories/<entity>/i_<entity>_repository.dart` — interface
5. `lib/data/repositories/<entity>/<entity>_repository.dart` — implementation

## Modified files
6. `lib/data/database/app_database.dart` — add table import and include
7. `lib/dependencies/di_repositories.dart` — add to `AppRepositories`, `_createRepo`, provider list

## Create the model
- Place in `lib/domain/models/<entity>_model.dart`
- Use `with Syncable<EntityName>`
- Include: `id` (String, default `Utils.newUUID()`), `createdDate`, `lastUpdated`
- If user-owned: `createdBy`, `visibility`
- Syncable fields: `needsSync`, `lastSync`, `isDeleted`
- Implement `copyWith()` (required by Syncable)
- Implement `toString()`
- No Flutter imports — domain layer is pure Dart

## Create the Drift table
- Extend `SyncableTable` (provides `id`, `lastUpdated`, `needsSync`, `lastSync`, `isDeleted`)
- Add entity-specific columns
- If user-owned: `createdBy` with `.references(UserLocal, #id)` and `visibility` with `.map(visibilityConverter)`
- Use Drift converters from `drift_converters.dart` for enums
- Override `primaryKey => {id}`

## Create the adapter
- Implement `ModelAdapter<Entity, EntityData, EntityCompanion>`
- Constructor takes `AppDatabase`
- Implement: `fromJson`, `toJson`, `fromDrift`, `toCompanion`, `tableName` getter, `table` getter
- Use `snake_case` keys in JSON (Supabase column names)
- Use `Value()` wrapper for all Companion fields

## Create the repository

**Interface**: `abstract interface class I<Entity>Repository implements IRepository<Entity> {}`

**Implementation**:
- Extend `Repository<Entity, EntityData, EntityCompanion>`
- Implement `I<Entity>Repository`
- Constructor takes `DriftDataSource`, `RemoteDataSource`, `ConnectivityService`, and adapter
- Add a `Logger` instance
- Override `insert`, `update`, `delete` with validation if needed
- Add `_validate()` method stub

## Wire into DI
- `lib/dependencies/di_repositories.dart`: add imports, field, constructor param, `_createRepo` call, provider
- `lib/data/database/app_database.dart`: import table, add to `@DriftDatabase(tables: [...])`

## Run codegen
```
flutter pub run build_runner build --delete-conflicting-outputs
```

## Supabase remote table

Present the following SQL to the user — **do not execute it**:

Generate the CREATE TABLE SQL matching the Drift table:
- Table name matches the adapter's `tableName`
- Column names use `snake_case` matching the adapter's `toJson` keys
- Types: String → text, DateTime → timestamptz, bool → boolean, int → integer
- Include `id text PRIMARY KEY`

Also generate RLS policies:
- Enable RLS
- Authenticated users can CRUD their own rows: `auth.uid() = created_by`
- If entity has `visibility = public`, add SELECT policy for all authenticated users

**Safety rule**: Never execute Supabase schema changes autonomously. Present the full SQL to the user and await their approval.
