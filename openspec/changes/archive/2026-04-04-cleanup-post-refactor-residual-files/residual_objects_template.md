# Residual Objects Checklist Template

Use this template to track cleanup candidates after a refactor batch is complete and verified.

## Batch Info
- `change`: ``
- `refactor_batch`: ``
- `validated_at`: ``
- `validated_by`: ``
- `source_docs`: ``

## Admission Criteria
- [ ] Replacement path is landed and passes regression.
- [ ] Documentation has switched to the new formal boundary.
- [ ] The object is no longer part of the formal source of truth.
- [ ] A rollback path exists for the exact deletion batch.

## Cleanup Candidate
- `object_type`: `file | directory | doc | compat_entry | helper | script`
- `path`: ``
- `current_role`: ``
- `replacement_path`: ``
- `evidence_of_replacement`: ``
- `delete_or_deprecate_action`: ``
- `owner_module`: ``
- `priority`: `low | medium | high`

## Validation Notes
- `validation_command`: ``
- `validation_result`: ``
- `compat_check`: ``
- `doc_check`: ``

## Rollback Notes
- `rollback_action`: ``
- `rollback_path`: ``
- `rollback_owner`: ``
- `rollback_trigger`: ``

## Disposal Decision
- [ ] Keep as compat
- [ ] Mark deprecated only
- [ ] Delete in next cleanup batch
- [ ] Delete now

## Decision Rationale
```
Explain why the object can or cannot be removed now.
```

