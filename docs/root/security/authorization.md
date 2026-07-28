# Authorization Claims

ORB derives a caller's roles and permissions from the authenticated principal.
Every authentication strategy populates the same two fields on its
authentication result — `user_roles` and `permissions` — so that downstream
authorization behaves identically regardless of how the caller authenticated.

## Canonical claim names

For token-based strategies (bearer JWT, enhanced bearer JWT), authorization
claims are read from two canonical, optional claims in the token payload:

| Claim | Type | Meaning |
|-------|------|---------|
| `roles` | array of strings | The principal's role names (e.g. `["operator"]`). |
| `permissions` | array of strings | Explicitly-granted, two-segment permission strings (e.g. `["templates.read"]`). |

Both claims are optional. A missing claim is treated as an empty list.

A JWT that carries `roles=["operator"]` yields `user_roles = ["operator"]`; a
JWT that additionally carries `permissions=["templates.read"]` surfaces that
list verbatim in `permissions`. Callers that cannot yet emit a `roles` claim
may grant access by supplying an explicit `permissions` array instead.

### Claim normalisation

Token payloads are untrusted input, so both claims are normalised before use:

- a scalar string (`"roles": "operator"`) is coerced to a single-element list;
- non-string and empty entries are dropped;
- surrounding whitespace is stripped and duplicates removed;
- any other type (object, number) yields an empty list (fail-closed).

This prevents a scalar claim from being stored as a bare string, which would
otherwise make role/permission membership checks perform substring matching
(for example `"adm" in "admin"`) — a fail-open authorization bypass.

## Provider strategy claim sources

Provider-native strategies map their own identity model onto the same
`user_roles` / `permissions` fields:

- **AWS Cognito** maps `cognito:groups` to ORB roles, then derives permissions
  from those roles.
- **AWS IAM** derives roles from the server principal's ARN. Admin access is
  granted only via an explicit, exact-match ARN allowlist
  (`provider_auth.iam.admin_arns`); no substring or name-pattern match is used
  when an allowlist is configured.
- **Kubernetes** maps the authenticated ServiceAccount principal to ORB roles
  via the operator-supplied service-account role mapping.
