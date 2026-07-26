"""Guard test: operator-facing deprecated aliases must have a warning hook.

House standard (``docs/root/developer_guide/deprecation.md``): any
operator-facing Pydantic model that uses ``AliasChoices`` to accept a
DEPRECATED legacy field name must ALSO register a
``model_validator(mode="before")`` that emits a ``logger.warning``.
``AliasChoices`` alone accepts the old key *silently* — the before-validator is
what makes the deprecation visible in the operator-facing server logs.

This is a canary, deliberately scoped to the ``Template`` aggregate (the
canonical example of the pattern) rather than sweeping every Pydantic model in
the codebase. A blanket sweep would false-positive on camelCase/snake_case
synonym aliases (e.g. ``machineCount``) that are naming conveniences, not
deprecations. Every multi-choice alias on ``Template`` is a genuine legacy
rename (``instance_type`` -> ``machine_type`` and friends).

Intent: if someone adds a new deprecated alias to ``Template`` without wiring up
the before-validator warning hook, the fields-vs-validator assertion below must
fail.
"""

from pydantic import AliasChoices

from orb.domain.template.template_aggregate import Template


def _deprecated_alias_fields(model: type) -> list[str]:
    """Return field names whose validation_alias accepts more than one name.

    A ``AliasChoices`` with more than one choice means the field accepts a
    legacy alias in addition to its canonical name — i.e. a deprecated field
    name that still deserialises.
    """
    fields: list[str] = []
    for name, info in model.model_fields.items():
        alias = info.validation_alias
        if isinstance(alias, AliasChoices) and len(alias.choices) > 1:
            fields.append(name)
    return fields


def _has_before_model_validator(model: type) -> bool:
    """True if the model registers at least one ``model_validator(mode="before")``."""
    validators = model.__pydantic_decorators__.model_validators
    return any(decorator.info.mode == "before" for decorator in validators.values())


def test_template_exposes_deprecated_aliases() -> None:
    """Sanity anchor: Template really does carry deprecated legacy aliases.

    If this ever returns empty the canary below would pass vacuously, so guard
    against the fields being removed/renamed out from under the test.
    """
    assert _deprecated_alias_fields(Template), (
        "Expected Template to expose deprecated legacy aliases via AliasChoices; "
        "none found. Update this guard if the deprecation pattern changed."
    )


def test_template_deprecated_aliases_have_before_validator() -> None:
    """Deprecated aliases on Template must be paired with a warning hook.

    The presence of any deprecated alias obliges the model to register a
    ``model_validator(mode="before")`` (Template's ``_warn_deprecated_field_names``)
    so the deprecated key is not accepted silently.
    """
    deprecated = _deprecated_alias_fields(Template)
    assert deprecated  # anchored by test above; keeps the implication non-vacuous

    validators = Template.__pydantic_decorators__.model_validators
    assert validators, (
        "Template exposes deprecated aliases "
        f"({', '.join(sorted(deprecated))}) but registers no model_validator. "
        "AliasChoices accepts the legacy key silently — add a "
        'model_validator(mode="before") emitting logger.warning per '
        "docs/root/developer_guide/deprecation.md."
    )
    assert _has_before_model_validator(Template), (
        "Template exposes deprecated aliases "
        f"({', '.join(sorted(deprecated))}) but has no "
        'model_validator(mode="before"). The before-validator is the '
        "load-bearing hook that emits the operator-facing logger.warning on "
        "every deserialization path; AliasChoices alone is silent."
    )
