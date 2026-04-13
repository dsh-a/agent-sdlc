# Command Pattern

> **Type**: template

## When to use

Scaffold a command when the task requires encapsulating a request as an object — enabling queuing, logging, undo/redo, or decoupling the invoker from the executor. Common in CQRS architectures, task queues, and action-based systems.

## File locations

| File | Path |
|---|---|
| Command interface | `src/domain/commands/command.interface.ts` (shared, create once) |
| Command | `src/domain/<feature>/commands/<name>.command.ts` |
| Handler | `src/domain/<feature>/commands/<name>.handler.ts` |
| Test | `test/domain/<feature>/commands/<name>.handler.test.ts` |

Adapt paths to the project's existing directory structure.

## Dependencies

- Command: none (pure data object)
- Handler: repositories, services, or other dependencies needed to execute the command

## Template

```typescript
// --- Shared command interface (create once) ---

export interface ICommand {
  readonly type: string;
}

export interface ICommandHandler<TCommand extends ICommand, TResult = void> {
  execute(command: TCommand): Promise<TResult>;
}

// --- Specific command ---

export class <Name>Command implements ICommand {
  readonly type = '<name>';

  constructor(
    public readonly someParam: string,
    // command parameters — immutable data
  ) {}
}

// --- Handler ---

export class <Name>Handler implements ICommandHandler<<Name>Command, ResultType> {
  constructor(
    private readonly someRepository: ISomeRepository,
  ) {}

  async execute(command: <Name>Command): Promise<ResultType> {
    // validate, execute, return result
  }
}
```

## Wiring

Register command-handler mappings in the DI container or a command bus/dispatcher. Invokers submit commands without knowing which handler processes them.

## Conventions

- Commands are immutable data objects — no methods, no dependencies
- One handler per command (Single Responsibility)
- Handlers contain the execution logic and dependencies
- Command names are descriptive verb phrases (e.g., `CreateUserCommand`, `TransferFundsCommand`)
- If using CQRS, commands are writes; queries are separate

## Tests

- Test the handler, not the command (commands are pure data)
- Test validation within the handler
- Test side effects (repository calls, events emitted)
- Test error cases (invalid command data, dependency failures)
