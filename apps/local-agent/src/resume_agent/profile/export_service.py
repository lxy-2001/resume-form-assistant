"""Local-only, selected-scope export for the F001 profile library.

The exporter receives an already validated snapshot and writes a deliberately
small, structured JSON document to a user-selected local path.  It has no HTTP
or model dependency and never returns the exported values to the caller.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from resume_agent.profile.errors import ExportFailedError, InvalidProfileSelectionError
from resume_agent.profile.models import (
    FieldValue,
    ProfileSnapshot,
    RepeatableRecord,
    Scope,
    is_contract_id,
)

_URI_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*://")
_NETWORK_PREFIXES = (r"\\\\", "//")
_FIELD_SELECTOR_KEYS = {"id", "scope", "scope_context"}


def _selection_error(reason: str) -> InvalidProfileSelectionError:
    return InvalidProfileSelectionError("export selection is invalid", details={"reason": reason})


def _selected_kind(selection: Mapping[str, Any]) -> tuple[str, Any]:
    if not isinstance(selection, Mapping):
        raise _selection_error("selection")
    allowed = {"field_ids", "field_values", "record_ids", "scopes", "all_profile_data"}
    if set(selection) - allowed:
        raise _selection_error("selection_keys")
    present = [key for key in allowed if key in selection]
    if len(present) != 1:
        raise _selection_error("selection_ambiguous")
    kind = present[0]
    value = selection[kind]
    if kind == "all_profile_data":
        if value is not True:
            raise _selection_error("all_profile_data")
        return kind, value
    if kind == "field_values":
        if not isinstance(value, list) or not value:
            raise _selection_error("selection_empty")
        selectors: list[tuple[str, Scope, str | None]] = []
        seen: set[tuple[str, Scope, str | None]] = set()
        for raw in value:
            if not isinstance(raw, Mapping):
                raise _selection_error("field_value_selector")
            if set(raw) - _FIELD_SELECTOR_KEYS or "id" not in raw or "scope" not in raw:
                raise _selection_error("field_value_selector")
            field_id = raw.get("id")
            if not isinstance(field_id, str) or not is_contract_id(field_id):
                raise _selection_error("field_value_selector_id")
            try:
                raw_scope = raw.get("scope")
                if not isinstance(raw_scope, (str, Scope)):
                    raise TypeError("scope")
                scope = raw_scope if isinstance(raw_scope, Scope) else Scope(raw_scope)
            except (TypeError, ValueError) as exc:
                raise _selection_error("field_value_selector_scope") from exc
            context = raw.get("scope_context")
            if scope is Scope.GLOBAL:
                if "scope_context" in raw:
                    raise _selection_error("global_field_value_selector_context")
                context = None
            elif not is_contract_id(context):
                raise _selection_error("field_value_selector_context")
            selector = (field_id, scope, context)
            if selector in seen:
                raise _selection_error("duplicate_field_value_selector")
            seen.add(selector)
            selectors.append(selector)
        return kind, selectors
    if not isinstance(value, list) or not value:
        raise _selection_error("selection_empty")
    try:
        unique = len(value) == len(set(value))
    except TypeError:
        unique = False
    if not unique or not all(
        isinstance(item, str) and item.strip() and len(item) <= 128 for item in value
    ):
        raise _selection_error("selection_values")
    if kind == "scopes" and not all(item in {scope.value for scope in Scope} for item in value):
        raise _selection_error("scope")
    return kind, value


def _local_destination(
    destination: str | Path,
    *,
    overwrite_existing: bool,
    overwrite_confirmed: bool,
) -> Path:
    if not isinstance(destination, (str, Path)):
        raise ExportFailedError("export destination is invalid")
    raw = str(destination)
    if not raw.strip() or _URI_RE.match(raw) or raw.startswith(_NETWORK_PREFIXES):
        raise ExportFailedError("export destination must be a local file")
    path = Path(destination)
    if not path.is_absolute() or path.name in {"", ".", ".."}:
        raise ExportFailedError("export destination must be an absolute file path")
    if overwrite_existing and overwrite_confirmed is not True:
        raise ExportFailedError("overwriting an existing export requires confirmation")
    if path.exists() and not overwrite_existing:
        raise ExportFailedError("export destination already exists")
    return path


def _write_atomic(path: Path, payload: bytes, *, overwrite_existing: bool) -> None:
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite_existing:
            os.replace(temporary, path)
            temporary = None
        else:
            # A hard-link create is an atomic no-clobber install: if another
            # process creates the destination after the preflight existence
            # check, the link fails instead of replacing that file.
            os.link(temporary, path)
            temporary.unlink(missing_ok=True)
            temporary = None
        try:
            directory_fd = os.open(path.parent, os.O_RDONLY)
        except OSError:
            directory_fd = None
        if directory_fd is not None:
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except (OSError, TypeError, ValueError) as exc:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
        raise ExportFailedError("profile export failed") from exc


def _field_dict(field: FieldValue) -> dict[str, Any]:
    return field.to_dict()


def _record_dict(record: RepeatableRecord, fields: list[FieldValue]) -> dict[str, Any]:
    result = record.to_dict()
    result["fields"] = [_field_dict(field) for field in fields]
    return result


class ProfileExportService:
    """Create a local JSON copy of a selected profile snapshot."""

    def export(
        self,
        snapshot: ProfileSnapshot,
        *,
        selection: Mapping[str, Any],
        destination: str | Path,
        overwrite_existing: bool = False,
        overwrite_confirmed: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(snapshot, ProfileSnapshot):
            raise ExportFailedError("profile snapshot is invalid")
        kind, selected = _selected_kind(selection)
        path = _local_destination(
            destination,
            overwrite_existing=overwrite_existing,
            overwrite_confirmed=overwrite_confirmed,
        )

        all_fields: list[FieldValue] = list(snapshot.fields)
        all_records: list[RepeatableRecord] = list(snapshot.records)
        if kind == "all_profile_data":
            selected_fields = all_fields
            selected_records = all_records
        elif kind == "field_ids":
            ids = set(selected)
            available_ids = {field.id for field in all_fields} | {
                field.id for record in all_records for field in record.fields
            }
            if not ids.issubset(available_ids):
                raise _selection_error("unknown_field_id")
            selected_fields = [field for field in all_fields if field.id in ids]
            selected_records = [
                record for record in all_records if any(field.id in ids for field in record.fields)
            ]
        elif kind == "field_values":
            selected_keys = set(selected)
            available_keys = {
                (field.id, field.scope, field.scope_context) for field in all_fields
            } | {
                (field.id, field.scope, field.scope_context)
                for record in all_records
                for field in record.fields
            }
            if not selected_keys.issubset(available_keys):
                raise _selection_error("unknown_field_value_selector")
            selected_fields = [
                field
                for field in all_fields
                if (field.id, field.scope, field.scope_context) in selected_keys
            ]
            selected_records = [
                record
                for record in all_records
                if any(
                    (field.id, field.scope, field.scope_context) in selected_keys
                    for field in record.fields
                )
            ]
        elif kind == "record_ids":
            ids = set(selected)
            available_ids = {record.record_id for record in all_records}
            if not ids.issubset(available_ids):
                raise _selection_error("unknown_record_id")
            selected_fields = []
            selected_records = [record for record in all_records if record.record_id in ids]
        else:
            scopes = set(selected)
            selected_fields = [field for field in all_fields if field.scope.value in scopes]
            selected_records = [
                record
                for record in all_records
                if any(field.scope.value in scopes for field in record.fields)
            ]

        selected_field_ids = {field.id for field in selected_fields}
        selected_key_set = set(selected) if kind == "field_values" else set()
        selected_records_out: list[dict[str, Any]] = []
        record_ids: list[str] = []
        for record in selected_records:
            if kind == "all_profile_data" or kind == "record_ids":
                record_fields = list(record.fields)
            elif kind == "field_ids":
                record_fields = [field for field in record.fields if field.id in set(selected)]
            elif kind == "field_values":
                record_fields = [
                    field
                    for field in record.fields
                    if (field.id, field.scope, field.scope_context) in selected_key_set
                ]
            else:
                record_fields = [
                    field for field in record.fields if field.scope.value in set(selected)
                ]
            if not record_fields:
                continue
            record_payload = _record_dict(record, record_fields)
            selected_records_out.append(record_payload)
            record_ids.append(record.record_id)
            selected_field_ids.update(field.id for field in record_fields)

        definitions = [
            definition.to_dict()
            for definition in snapshot.field_definitions
            if kind == "all_profile_data" or definition.id in selected_field_ids
        ]
        output = {
            "schema_version": "0.1",
            "export_version": "1",
            "profile_id": snapshot.profile_id,
            "profile_version": snapshot.profile_version,
            "fields": [_field_dict(field) for field in selected_fields],
            "records": selected_records_out,
            "field_definitions": definitions,
        }
        payload = json.dumps(
            output, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        _write_atomic(path, payload, overwrite_existing=overwrite_existing)
        exported_scopes: list[str] = []
        for field in selected_fields:
            if field.scope.value not in exported_scopes:
                exported_scopes.append(field.scope.value)
        for record_payload in selected_records_out:
            for field in record_payload["fields"]:
                scope = field["scope"]
                if scope not in exported_scopes:
                    exported_scopes.append(scope)
        return {
            "profile_id": snapshot.profile_id,
            "profile_version": snapshot.profile_version,
            "export_id": f"export-{uuid.uuid4().hex}",
            "format": "json",
            "status": "written",
            "destination_display_name": path.name,
            "exported_field_ids": sorted(selected_field_ids),
            "exported_record_ids": record_ids,
            "exported_scopes": exported_scopes,
            "bytes_written": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
            "warnings": [],
        }


def export_profile_snapshot(
    snapshot: ProfileSnapshot,
    *,
    selection: Mapping[str, Any],
    destination: str | Path,
    overwrite_existing: bool = False,
    overwrite_confirmed: bool = False,
) -> dict[str, Any]:
    return ProfileExportService().export(
        snapshot,
        selection=selection,
        destination=destination,
        overwrite_existing=overwrite_existing,
        overwrite_confirmed=overwrite_confirmed,
    )


__all__ = ["ProfileExportService", "export_profile_snapshot"]
