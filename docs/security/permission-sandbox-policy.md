# Permission and Sandbox Policy

Astrid's current security boundary is a permission policy boundary, not a
Codex-level operating-system sandbox.

The practical rule is simple: Astrid can ask before sensitive actions, remember
allow or deny decisions, and block actions that match those decisions. It does
not currently run commands inside an OS sandbox, container, restricted user,
filesystem jail, or syscall/network isolation layer.

## Current Layers

### Permission Prompt

`PermissionManager` prompts when an action needs user approval and a prompt
handler is available. Without a prompt handler, the action fails closed.

The prompt layer currently covers:

- path access outside the current workspace
- commands classified as dangerous or explicitly forced to prompt
- file edits before they are applied

Approvals can be one-time, session-scoped, turn-scoped for edits, or persisted
depending on the user's choice.

### Command Allow/Deny Patterns

Astrid stores command allow and deny entries as command signatures. A command
signature is the command plus its arguments joined into a single string.

The command layer currently includes:

- persistent allowed command signatures
- persistent denied command signatures
- session allowed command signatures
- session denied command signatures
- built-in classification for dangerous command families such as destructive
  git operations, recursive forced deletion, disk modification commands,
  arbitrary local-code interpreters, and registry-publishing commands

This is command policy enforcement. It is not process isolation.

### Edit Allow/Deny Paths

Astrid stores edit allow and deny entries as normalized file paths.

The edit layer currently includes:

- persistent allowed edit targets
- persistent denied edit targets
- session allowed edit targets
- session denied edit targets
- turn-scoped single-file edit approvals
- turn-scoped approval for all edits in the current turn

This controls whether Astrid may apply an edit through its permission manager.
It does not stop another process outside Astrid from editing the same file.

## Sandbox Status

Current sandbox support is `policy_only`.

Astrid does not currently enforce:

- OS-level filesystem isolation
- process sandboxing
- container isolation
- restricted user execution
- syscall filtering
- network isolation

Any UI, API, or documentation should avoid claiming those protections until the
runtime actually enforces them.

## Future Sandbox Modes

Future work can add real sandbox modes, but those modes must be backed by
runtime enforcement before they are described as active protections.

Pragmatic future mode names:

- `read_only`: commands may inspect the workspace but may not write through
  Astrid-managed operations
- `workspace_write`: writes are limited to the active workspace
- `full_access`: user-approved access outside the workspace is allowed by policy

Until those modes exist in runtime code, they are design labels only.

## Programmatic Snapshot

`astrid.runtime.permissions.get_permission_policy_snapshot()` exposes the current
policy boundary as structured data. Tests assert that the snapshot marks prompt,
command, and edit policy layers as enforced, while marking OS sandbox support as
not enforced.
