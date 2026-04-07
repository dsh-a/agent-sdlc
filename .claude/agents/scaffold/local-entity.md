# Local-Only Entity

Same as syncable entity with these differences. Stored only in Drift — no Supabase sync.

## New files to create
1. `lib/domain/models/<entity>_model.dart` — model (no Syncable mixin)
2. `lib/data/database/tables/<entity>_table.dart` — extends `Table` directly
3. `lib/data/adapter/<entity>_adapter.dart` — implements `ModelAdapter`
4. `lib/data/repositories/<entity>/i_<entity>_repository.dart` — interface
5. `lib/data/repositories/<entity>/<entity>_repository.dart` — implementation

## Modified files
6. `lib/data/database/app_database.dart` — add table import and include
7. `lib/dependencies/di_repositories.dart` — add to `AppRepositories`, `_createRepo`, provider list

## Model
- Do **not** use `Syncable` mixin
- Include `id` (String, default `Utils.newUUID()`) and entity-specific fields
- Still implement `copyWith()` and `toString()`
- No `needsSync`, `lastSync`, `isDeleted` fields
- No framework imports — domain layer is pure TypeScript

## Drift table
- Extend `Table` directly (not `SyncableTable`)
- Define `id` column manually: `TextColumn get id => text()()`
- Override `primaryKey => {id}`

## Adapter
- Still implements `ModelAdapter`; `toJson`/`fromJson` can be minimal or throw `UnimplementedError` if no remote use
- `fromDrift` and `toCompanion` are still required

## Repository
- Check if a `LocalRepository` pattern exists in the codebase first
- Otherwise: extend `Repository` with a no-op `RemoteDataSource`

## Wire into DI
- `lib/dependencies/di_repositories.dart`: add imports, field, constructor param, `_createRepo` call, provider
- `lib/data/database/app_database.dart`: import table, add to `@DriftDatabase(tables: [...])`

## Run codegen
```
npm run codegen
```
