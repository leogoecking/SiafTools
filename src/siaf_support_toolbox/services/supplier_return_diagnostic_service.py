from __future__ import annotations

from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from enum import StrEnum

from siaf_support_toolbox.fiscal.nfe_xml_reader import NFeDocument, NFeField, NFeItem


class ComparisonStatus(StrEnum):
    MATCH = "igual"
    DIFFERENT = "divergente"
    MISSING = "ausente_no_espelho"
    ITEM_MISSING = "item_ausente_no_espelho"
    MIRROR_ONLY = "informado_apenas_no_espelho"


@dataclass(frozen=True, slots=True)
class MirrorField:
    path: str
    label: str
    value: str


RETURN_MIRROR_SCHEMA_VERSION = "1.0"
_ADDITIONAL_RETURN_ITEM_FIELDS = (
    MirrorField(
        "produto.indDevol",
        "Indicador de devolução",
        "",
    ),
    MirrorField(
        "impostoDevol.pDevol",
        "Percentual de mercadoria devolvida",
        "",
    ),
    MirrorField(
        "impostoDevol.IPI.IPIDevol.vIPIDevol",
        "Valor do IPI devolvido",
        "",
    ),
)


@dataclass(frozen=True, slots=True)
class SupplierReturnMirrorItem:
    number: int
    product_code: str
    description: str
    fields: tuple[MirrorField, ...]


@dataclass(frozen=True, slots=True)
class SupplierReturnMirror:
    source_access_key: str
    total_fields: tuple[MirrorField, ...]
    items: tuple[SupplierReturnMirrorItem, ...]


@dataclass(frozen=True, slots=True)
class FieldComparison:
    item_number: int | None
    path: str
    label: str
    original_value: str
    mirror_value: str | None
    status: ComparisonStatus


@dataclass(frozen=True, slots=True)
class SupplierReturnComparison:
    source_access_key: str
    fields: tuple[FieldComparison, ...]

    @property
    def different_count(self) -> int:
        return sum(field.status is not ComparisonStatus.MATCH for field in self.fields)

    @property
    def matches(self) -> bool:
        return self.different_count == 0


def build_supplier_return_mirror(document: NFeDocument) -> SupplierReturnMirror:
    return SupplierReturnMirror(
        source_access_key=document.access_key,
        total_fields=tuple(_mirror_field(field) for field in document.total_fields),
        items=tuple(
            SupplierReturnMirrorItem(
                number=item.number,
                product_code=item.product_code,
                description=item.description,
                fields=_mirror_item_fields(item),
            )
            for item in document.items
        ),
    )


def update_mirror_field(
    mirror: SupplierReturnMirror,
    *,
    path: str,
    value: str,
    item_number: int | None = None,
) -> SupplierReturnMirror:
    if item_number is None:
        fields, found = _updated_fields(mirror.total_fields, path, value)
        if not found:
            raise KeyError(path)
        return replace(mirror, total_fields=fields)

    updated_items: list[SupplierReturnMirrorItem] = []
    found_item = False
    found_field = False
    for item in mirror.items:
        if item.number != item_number:
            updated_items.append(item)
            continue
        found_item = True
        fields, found_field = _updated_fields(item.fields, path, value)
        updated_items.append(replace(item, fields=fields))
    if not found_item:
        raise KeyError(f"item:{item_number}")
    if not found_field:
        raise KeyError(path)
    return replace(mirror, items=tuple(updated_items))


def compare_supplier_return_mirror(
    document: NFeDocument,
    mirror: SupplierReturnMirror,
) -> SupplierReturnComparison:
    if document.access_key != mirror.source_access_key:
        raise ValueError("O espelho não pertence ao XML de origem informado.")

    comparisons = list(
        _compare_fields(
            tuple(_mirror_field(field) for field in document.total_fields),
            mirror.total_fields,
            item_number=None,
        )
    )
    mirror_items = {item.number: item for item in mirror.items}
    if len(mirror_items) != len(mirror.items):
        raise ValueError("O espelho possui número de item duplicado.")
    for source_item in document.items:
        mirror_item = mirror_items.get(source_item.number)
        source_fields = _source_item_fields(source_item)
        if mirror_item is None:
            comparisons.extend(
                FieldComparison(
                    item_number=source_item.number,
                    path=field.path,
                    label=field.label,
                    original_value=field.value,
                    mirror_value=None,
                    status=ComparisonStatus.ITEM_MISSING,
                )
                for field in source_fields
            )
            continue
        comparisons.extend(
            _compare_fields(source_fields, mirror_item.fields, item_number=source_item.number)
        )
    return SupplierReturnComparison(document.access_key, tuple(comparisons))


def _source_item_fields(item: NFeItem) -> tuple[MirrorField, ...]:
    fields = [
        MirrorField("produto.cProd", "Código do produto", item.product_code),
        MirrorField("produto.xProd", "Descrição", item.description),
        MirrorField("produto.NCM", "NCM", item.ncm),
        MirrorField("produto.CFOP", "CFOP", item.cfop),
        MirrorField("produto.uCom", "Unidade", item.unit),
        MirrorField("produto.qCom", "Quantidade", str(item.quantity)),
        MirrorField("produto.vUnCom", "Valor unitário", str(item.unit_value)),
        MirrorField("produto.vProd", "Valor dos produtos", str(item.product_value)),
    ]
    optional_text = (
        ("produto.cEAN", "Código de barras", item.barcode),
        ("produto.CEST", "CEST", item.cest),
        ("produto.indDevol", "Indicador de devolução", item.return_indicator),
    )
    fields.extend(
        MirrorField(path, label, value)
        for path, label, value in optional_text
        if value is not None
    )
    optional_decimal = (
        ("produto.vDesc", "Desconto", item.discount),
        ("produto.vFrete", "Frete", item.freight),
        ("produto.vSeg", "Seguro", item.insurance),
        ("produto.vOutro", "Outras despesas", item.other_expenses),
    )
    fields.extend(
        MirrorField(path, label, _optional_decimal_text(value))
        for path, label, value in optional_decimal
        if value is not None
    )
    return tuple(fields) + tuple(_mirror_field(field) for field in item.tax_fields)


def _mirror_item_fields(item: NFeItem) -> tuple[MirrorField, ...]:
    source_fields = _source_item_fields(item)
    source_paths = {field.path for field in source_fields}
    additional_fields = tuple(
        field for field in _ADDITIONAL_RETURN_ITEM_FIELDS if field.path not in source_paths
    )
    return source_fields + additional_fields


def _mirror_field(field: NFeField) -> MirrorField:
    return MirrorField(field.path, field.label, field.value)


def _optional_decimal_text(value: Decimal | None) -> str:
    return "" if value is None else str(value)


def _updated_fields(
    fields: tuple[MirrorField, ...],
    path: str,
    value: str,
) -> tuple[tuple[MirrorField, ...], bool]:
    found = False
    updated: list[MirrorField] = []
    for field in fields:
        if field.path == path:
            updated.append(replace(field, value=normalize_mirror_value(path, value)))
            found = True
        else:
            updated.append(field)
    return tuple(updated), found


def _compare_fields(
    source_fields: tuple[MirrorField, ...],
    mirror_fields: tuple[MirrorField, ...],
    *,
    item_number: int | None,
) -> tuple[FieldComparison, ...]:
    mirror_by_path = {field.path: field for field in mirror_fields}
    if len(mirror_by_path) != len(mirror_fields):
        raise ValueError("O espelho possui caminho de campo duplicado.")
    source_paths = {field.path for field in source_fields}
    comparisons: list[FieldComparison] = []
    for source in source_fields:
        mirror = mirror_by_path.get(source.path)
        if mirror is None or not mirror.value.strip():
            status = ComparisonStatus.MISSING
            mirror_value = None if mirror is None else mirror.value
        elif _equivalent(source.path, source.value, mirror.value):
            status = ComparisonStatus.MATCH
            mirror_value = mirror.value
        else:
            status = ComparisonStatus.DIFFERENT
            mirror_value = mirror.value
        comparisons.append(
            FieldComparison(
                item_number=item_number,
                path=source.path,
                label=source.label,
                original_value=source.value,
                mirror_value=mirror_value,
                status=status,
            )
        )
    for mirror in mirror_fields:
        if mirror.path in source_paths:
            continue
        informed_value = mirror.value.strip()
        comparisons.append(
            FieldComparison(
                item_number=item_number,
                path=mirror.path,
                label=mirror.label,
                original_value="",
                mirror_value=mirror.value,
                status=(
                    ComparisonStatus.MIRROR_ONLY
                    if informed_value
                    else ComparisonStatus.MATCH
                ),
            )
        )
    return tuple(comparisons)


def _equivalent(path: str, left: str, right: str) -> bool:
    normalized_left = left.strip()
    normalized_right = right.strip()
    if is_decimal_field(path):
        try:
            return Decimal(normalized_left) == Decimal(normalized_right)
        except InvalidOperation:
            return normalized_left == normalized_right
    return normalized_left == normalized_right


def is_decimal_field(path: str) -> bool:
    name = path.rsplit(".", 1)[-1]
    return len(name) > 1 and name[0] in {"p", "q", "v"} and name[1].isupper()


def normalize_mirror_value(path: str, value: str) -> str:
    normalized = value.strip()
    if not normalized or not is_decimal_field(path):
        return normalized
    normalized = normalized.replace(",", ".")
    try:
        Decimal(normalized)
    except InvalidOperation as error:
        raise ValueError(f"O campo {path} exige um número decimal válido.") from error
    return normalized
