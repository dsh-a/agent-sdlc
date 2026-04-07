# Service

Services wrap infrastructure concerns (auth, connectivity, settings). They live in `lib/data/services/`.

## File location
`lib/data/services/<service_name>_service.dart`

## Convention
- Class with `Logger` instance
- Constructor takes external dependencies
- Public methods expose the operations
- May use framework imports (unlike domain layer)

## Wire into DI
Add to `lib/dependencies/di_services.dart` as a `Provider`.
