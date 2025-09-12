import dataclasses

import polars as pl


@dataclasses.dataclass
class TypeMismatch:
    expected: type[pl.DataType]
    got: type[pl.DataType]


@dataclasses.dataclass
class SchemaErrors:
    missing_columns: list[str] = dataclasses.field(default_factory=list)
    mismatched_types: dict[str, TypeMismatch] = dataclasses.field(default_factory=dict)

    def __bool__(self):
        return not self.missing_columns and not self.mismatched_types


class ValidationError(Exception):
    def __init__(self, errors: SchemaErrors) -> None:
        self._errors = errors
        super().__init__(f"Errors have been found\n\n{errors}")


def lazy_validate(df: pl.DataFrame, schema: dict[str, type[pl.DataType]]):
    errors = SchemaErrors()

    for k, v in schema.items():
        if k not in df.columns:
            errors.missing_columns.append(k)
            continue

        dtype = df.schema[k]

        if dtype != v:
            errors.mismatched_types[k] = TypeMismatch(expected=v, got=dtype.__class__)

    return errors


def validate(df: pl.DataFrame, schema: dict[str, type[pl.DataType]]):
    errors = lazy_validate(df, schema=schema)

    if errors:
        raise ValidationError(errors=errors)
