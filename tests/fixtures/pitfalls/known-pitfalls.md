# Known pitfalls

Project-owned. One entry per bug that has already cost a cycle.

## Async Future.delayed race
Globs: lib/**/data/**, test/**/*_repository_test.dart
Severity: hard
Body:
Do not settle a constructor-launched load with `await Future<void>.value()` or a
microtask pump. The load is scheduled on the event queue, not the microtask
queue, so the pump returns before it runs and the test asserts on the pre-load
state. Use `await tester.pumpAndSettle()` or an explicit completer.

## Theme accent selector rebuild
Globs: lib/ui/**
Severity: warn
Body:
Selecting the whole theme object rebuilds every listener on any theme change.
Select the accent colour itself.

## Entry with no globs
Severity: hard
Body:
This one can never match anything, which is the point of the fixture.

## Entry with a typo'd severity
Globs: lib/**
Severity: hardd
Body:
Read as hard, because the fail-safe direction is the one that costs a sentence.

## Entry with no body
Globs: lib/**
Severity: warn
