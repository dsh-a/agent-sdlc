Split from #249 (**D-3**). Time-boxed spike, not a feature. Depends on the substrate
sibling — this evaluates a replacement for part of it, so the baseline must exist first.

## What Patrol buys that `integration_test` structurally cannot

| Surface | Where it lives |
|---|---|
| OS permission dialogs | `permission_handler ^12.0.1`, `image_picker ^1.2.2`, `image_cropper ^12.2.1` |
| Deep-link return | reset-password scheme, `lib/data/services/auth_service.dart:206` |
| Email round-trip sign-in | `signInWithOtp`, `lib/ui/auth/view_models/login_view_model.dart:92` |

`integration_test` cannot dismiss a native dialog or return through a URL scheme. Patrol
can. That is the entire question.

## Why it is a spike and not the substrate

The e2e layer is **not blocked** on this: a fixture injects a Supabase session directly
rather than driving the real OTP email round trip, so only the auth flow itself needs native
control. Adopting Patrol across the whole layer upfront would cost native build
configuration per platform plus `patrol_cli` in CI, and **Patrol has no web support** —
which collides with any later web fan-out (#249 D-4).

So: prove the value on the flows that need it, then decide.

## Questions the spike answers

- [ ] Can Patrol drive the OTP sign-in end to end, including the email round trip, against
  the local Supabase stack?
- [ ] Can it dismiss the `permission_handler` dialogs for the image-picker path?
- [ ] What does it cost — native build config, `patrol_cli` in CI, and can Patrol and plain
  `integration_test` flows coexist in `integration_test/`, or is it all-or-nothing?
- [ ] Does the answer change the platform choice (#249 Q-17)?

## Deliverable

A recommendation with evidence, plus a throwaway proof-of-concept flow. **Not** a migration
of existing flows.

## Note

The deep link it would drive is `io.supabase.flutterquickstart://reset-password/` —
unreplaced Supabase quickstart boilerplate, filed separately as a bug. The spike should use
whatever scheme that bug settles on, or note the dependency.

---

> **Path correction — 2026-09-30.** Flows live at **`integration_test/flows/<flow>_test.dart`**, not `e2e/flows/`. **Proven by experiment:** `flutter test` decides whether a file is an integration test **solely** by whether its path starts with `<project>/integration_test` (`flutter_tools/lib/src/commands/test.dart:888-902`, constant at `:34`), and only then does it request a device (`:621`). The identical test file under `e2e/` ran as a plain **widget** test — exit 0, *"All tests passed!"*, no device requested, asserting nothing about a real app; under `integration_test/` it correctly exited 1 with *"No devices are connected"*. #249's D-2 chose `e2e/` and called the name *"load-bearing, not cosmetic"* — right instinct, wrong conclusion. **D-2's goal survives:** a bare `flutter test` was verified to load only `test/`, ignoring `integration_test/`, so it stays outside the swept tree exactly as `e2e/` would have. Only the name changes. #249 and #415 are closed and stay archival; **#549** owns the substrate.
>
> ⚠️ **This sharpens the spike's coexistence question.** Patrol ships its own runner (`patrol_cli`), which may not respect `flutter test`'s `integration_test/` directory gate at all — so "can Patrol and plain `integration_test` flows coexist in one directory?" is now partly a question about **two different routing mechanisms**, not only about native build configuration. Worth answering explicitly rather than assuming the directory behaves the same for both.

