import json

from jsonschema import Draft7Validator, validators

from errors.custom_errors import (
    FieldNotAllowed,
    InvalidFormat,
    InvalidSchema,
    MissingField,
    ValueOutOfRange,
)

STRICT_INTEGER_CHECKER = Draft7Validator.TYPE_CHECKER.redefine(
    "integer", lambda checker, instance: isinstance(instance, int) and not isinstance(instance, bool)
)
StrictDraft7Validator = validators.extend(Draft7Validator, type_checker=STRICT_INTEGER_CHECKER)

TYPE_NAMES = {
    "integer": "um número inteiro",
    "number": "um número",
    "string": "um texto",
    "object": "um objeto",
    "array": "uma lista",
    "boolean": "verdadeiro ou falso",
    "null": "nulo",
}
FORMAT_KEYWORDS = {"type", "enum", "const", "pattern"}
RANGE_KEYWORDS = {
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "minLength", "maxLength", "minItems", "maxItems", "minProperties", "maxProperties",
}


def validate_json(payload: dict, schema_path: str, root: str = "body") -> dict:
    with open(schema_path, encoding="utf-8") as schema_file:
        schema = json.load(schema_file)

    error = next(iter(StrictDraft7Validator(schema).iter_errors(payload)), None)
    if error is not None:
        raise schema_error(error, root)

    return payload


def schema_error(error, root: str) -> Exception:
    path = [str(part) for part in error.absolute_path]
    location = ".".join(path) or root
    reason = f"{location}: {error.message}"
    keyword = error.validator

    if keyword == "required":
        return MissingField(_join(path, _first_missing(error)), reason)
    if keyword == "additionalProperties":
        return FieldNotAllowed(_join(path, _first_extra(error)), reason)
    if keyword == "not":
        return FieldNotAllowed(_join(path, _first_present(error, _required_names(error.validator_value))), reason)
    if keyword == "oneOf":
        return _one_of_error(error, path, reason)
    if keyword in FORMAT_KEYWORDS and (path or keyword != "type"):
        return InvalidFormat(location, reason, _expected(error))
    if keyword in RANGE_KEYWORDS:
        return ValueOutOfRange(location, reason, _limit(keyword, error.validator_value))
    return InvalidSchema(reason)


def _join(path: list, name: str) -> str:
    return ".".join(path + [name])


def _first_missing(error) -> str:
    return next(name for name in error.validator_value if name not in error.instance)


def _first_extra(error) -> str:
    allowed = error.schema.get("properties", {})
    return next(name for name in error.instance if name not in allowed)


def _first_present(error, names: list) -> str:
    return next(name for name in names if name in error.instance)


def _required_names(subschema: dict) -> list:
    names = list(subschema.get("required", []))
    for option in subschema.get("anyOf", []) + subschema.get("oneOf", []):
        names.extend(_required_names(option))
    return names


def _one_of_error(error, path: list, reason: str) -> Exception:
    alternatives = _required_names({"oneOf": error.validator_value})
    present = [name for name in alternatives if name in error.instance]
    if not present:
        return MissingField(_join(path, "/".join(alternatives)), reason)
    if len(present) > 1:
        return FieldNotAllowed(_join(path, present[1]), reason, conflicting_field=present[0])
    return InvalidSchema(reason)


def _expected(error) -> str:
    keyword, value = error.validator, error.validator_value
    if keyword == "type":
        types = value if isinstance(value, list) else [value]
        return "esperado " + " ou ".join(TYPE_NAMES.get(name, name) for name in types)
    if keyword == "enum":
        return "esperado um destes valores: " + ", ".join(str(option) for option in value)
    if keyword == "const":
        return f"esperado o valor {value}"
    return f"o valor '{error.instance}' não está no formato esperado"


def _limit(keyword: str, value) -> str:
    if keyword in ("minLength", "minProperties") and value == 1:
        return "não pode ser vazio"
    return {
        "minimum": f"deve ser no mínimo {value}",
        "maximum": f"deve ser no máximo {value}",
        "exclusiveMinimum": f"deve ser maior que {value}",
        "exclusiveMaximum": f"deve ser menor que {value}",
        "minLength": f"deve ter pelo menos {value} caracteres",
        "maxLength": f"deve ter no máximo {value} caracteres",
        "minItems": f"deve ter pelo menos {value} itens",
        "maxItems": f"deve ter no máximo {value} itens",
        "minProperties": f"deve ter pelo menos {value} campos",
        "maxProperties": f"deve ter no máximo {value} campos",
    }[keyword]
