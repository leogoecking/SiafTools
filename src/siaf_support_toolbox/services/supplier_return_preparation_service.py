from __future__ import annotations

import re
from dataclasses import dataclass, replace
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import StrEnum

from siaf_support_toolbox.fiscal.nfe_xml_reader import NFeDocument, NFeItem

CENT = Decimal("0.01")
COMPARISON_TOLERANCE = Decimal("0.0001")
_PLAIN_DECIMAL = re.compile(r"^\d+(?:[.,]\d+)?$")


class GuidanceLevel(StrEnum):
    CONFIRMED = "comprovado"
    POSSIBLE_CAUSE = "possivel_causa"
    PENDING_CONFIRMATION = "pendente_confirmacao"


@dataclass(frozen=True, slots=True)
class ReturnItemPreparation:
    item_number: int
    product_code: str
    description: str
    original_quantity: Decimal
    original_unit_value: Decimal
    original_product_value: Decimal
    selected: bool
    return_quantity: Decimal
    unit_value: Decimal
    mirror_product_total: Decimal | None = None
    siaf_product_total: Decimal | None = None
    original_icms_rate: Decimal | None = None
    original_reduction_rate: Decimal | None = None
    original_ipi_rate: Decimal | None = None
    mirror_icms_rate: Decimal | None = None
    mirror_reduction_rate: Decimal | None = None
    mirror_ipi_rate: Decimal | None = None
    siaf_icms_rate: Decimal | None = None
    siaf_reduction_rate: Decimal | None = None
    siaf_ipi_rate: Decimal | None = None

    @property
    def product_total(self) -> Decimal:
        if self.mirror_product_total is not None:
            return money(self.mirror_product_total)
        if (
            self.return_quantity == self.original_quantity
            and self.unit_value == self.original_unit_value
        ):
            return money(self.original_product_value)
        return money(self.return_quantity * self.unit_value)


@dataclass(frozen=True, slots=True)
class ReturnTotals:
    merchandise: Decimal | None = None
    discount: Decimal | None = None
    freight: Decimal | None = None
    insurance: Decimal | None = None
    packaging: Decimal | None = None
    additional_expenses: Decimal | None = None
    increase: Decimal | None = None
    bonus: Decimal | None = None
    complement: Decimal | None = None
    icms_base: Decimal | None = None
    icms_rate: Decimal | None = None
    icms_reduction_rate: Decimal | None = None
    icms_value: Decimal | None = None
    ipi_rate: Decimal | None = None
    ipi_value: Decimal | None = None
    st_base: Decimal | None = None
    st_value: Decimal | None = None
    invoice_total: Decimal | None = None


@dataclass(frozen=True, slots=True)
class SupplierReturnPreparation:
    source_access_key: str
    items: tuple[ReturnItemPreparation, ...]
    mirror_totals: ReturnTotals
    siaf_totals: ReturnTotals

    @property
    def selected_items(self) -> tuple[ReturnItemPreparation, ...]:
        return tuple(item for item in self.items if item.selected)

    @property
    def calculated_merchandise(self) -> Decimal:
        return money(sum((item.product_total for item in self.selected_items), Decimal("0")))


@dataclass(frozen=True, slots=True)
class ReturnGuidance:
    level: GuidanceLevel
    title: str
    detail: str
    siaf_location: str | None = None
    item_number: int | None = None


@dataclass(frozen=True, slots=True)
class SupplierReturnAnalysis:
    selected_item_count: int
    calculated_merchandise: Decimal
    inferred_icms_base: Decimal | None
    guidance: tuple[ReturnGuidance, ...]

    def count(self, level: GuidanceLevel) -> int:
        return sum(item.level is level for item in self.guidance)


TOTAL_FIELD_LABELS = {
    "merchandise": "Mercadoria",
    "discount": "Desconto",
    "freight": "Frete",
    "insurance": "Seguro",
    "packaging": "Embalagem",
    "additional_expenses": "Despesas acessórias",
    "increase": "Acréscimo",
    "bonus": "Bonificação",
    "complement": "Complemento",
    "icms_base": "Base de ICMS",
    "icms_rate": "Alíquota de ICMS",
    "icms_reduction_rate": "Redução de ICMS",
    "icms_value": "Valor de ICMS",
    "ipi_rate": "Alíquota de IPI",
    "ipi_value": "Valor de IPI",
    "st_base": "Base de ICMS ST/retido",
    "st_value": "Valor de ICMS ST/retido",
    "invoice_total": "Total da nota",
}

TOTAL_FIELD_LOCATIONS = {
    "merchandise": "Nota Fiscal de Saída → rodapé → Vr. Merc.",
    "discount": "Nota Fiscal de Saída → rodapé → Desconto",
    "freight": "Nota Fiscal de Saída → rodapé → Frete",
    "additional_expenses": "Nota Fiscal de Saída → rodapé → Desp.Acess.",
    "increase": "Nota Fiscal de Saída → rodapé → Acréscimo",
    "icms_base": "Nota Fiscal de Saída → rodapé → Base ICMS",
    "icms_value": "Nota Fiscal de Saída → rodapé → Vr. ICMS",
    "ipi_value": "Nota Fiscal de Saída → rodapé → Vr. IPI",
    "st_base": "Nota Fiscal de Saída → rodapé → Base Subst.",
    "st_value": "Nota Fiscal de Saída → rodapé → Vr. Subst.",
    "invoice_total": "Nota Fiscal de Saída → rodapé → Total Nota",
}


def build_supplier_return_preparation(
    document: NFeDocument,
) -> SupplierReturnPreparation:
    return SupplierReturnPreparation(
        source_access_key=document.access_key,
        items=tuple(_build_item(item) for item in document.items),
        mirror_totals=ReturnTotals(),
        siaf_totals=ReturnTotals(),
    )


def update_preparation_item(
    preparation: SupplierReturnPreparation,
    item_number: int,
    *,
    selected: bool | None = None,
    values: dict[str, str] | None = None,
) -> SupplierReturnPreparation:
    updated_items: list[ReturnItemPreparation] = []
    found = False
    for item in preparation.items:
        if item.item_number != item_number:
            updated_items.append(item)
            continue
        found = True
        changes: dict[str, object] = {}
        if selected is not None:
            changes["selected"] = selected
        for field_name, raw_value in (values or {}).items():
            if field_name not in _ITEM_EDITABLE_FIELDS:
                raise KeyError(field_name)
            parsed = parse_optional_decimal(
                raw_value,
                label=_ITEM_EDITABLE_FIELDS[field_name],
            )
            if field_name in {"return_quantity", "unit_value"} and parsed is None:
                raise ValueError(f"{_ITEM_EDITABLE_FIELDS[field_name]} é obrigatório.")
            if field_name.endswith("_rate") and parsed is not None and parsed > 100:
                raise ValueError(
                    f"{_ITEM_EDITABLE_FIELDS[field_name]} não pode superar 100%."
                )
            changes[field_name] = parsed
        updated = replace(item, **changes)
        _validate_item(updated)
        updated_items.append(updated)
    if not found:
        raise KeyError(f"item:{item_number}")
    return replace(preparation, items=tuple(updated_items))


def update_preparation_totals(
    preparation: SupplierReturnPreparation,
    *,
    source: str,
    values: dict[str, str],
) -> SupplierReturnPreparation:
    if source not in {"mirror", "siaf"}:
        raise ValueError("A origem dos totais deve ser mirror ou siaf.")
    current = (
        preparation.mirror_totals if source == "mirror" else preparation.siaf_totals
    )
    changes: dict[str, Decimal | None] = {}
    for field_name, raw_value in values.items():
        label = TOTAL_FIELD_LABELS.get(field_name)
        if label is None:
            raise KeyError(field_name)
        parsed = parse_optional_decimal(raw_value, label=label)
        if (
            field_name in {"icms_rate", "icms_reduction_rate", "ipi_rate"}
            and parsed is not None
            and parsed > 100
        ):
            raise ValueError(f"{label} não pode superar 100%.")
        changes[field_name] = parsed
    updated = replace(current, **changes)
    if source == "mirror":
        return replace(preparation, mirror_totals=updated)
    return replace(preparation, siaf_totals=updated)


def analyze_supplier_return_preparation(
    preparation: SupplierReturnPreparation,
) -> SupplierReturnAnalysis:
    guidance: list[ReturnGuidance] = []
    selected = preparation.selected_items
    calculated_merchandise = preparation.calculated_merchandise
    mirror = preparation.mirror_totals
    siaf = preparation.siaf_totals

    if not selected:
        guidance.append(
            ReturnGuidance(
                GuidanceLevel.PENDING_CONFIRMATION,
                "Nenhum item selecionado",
                "Selecione ao menos um item e informe a quantidade que será devolvida.",
            )
        )
    elif mirror.merchandise is None:
        guidance.append(
            ReturnGuidance(
                GuidanceLevel.PENDING_CONFIRMATION,
                "Mercadoria do espelho não informada",
                (
                    f"Os itens selecionados somam {_brl(calculated_merchandise)}. "
                    "Informe o total de mercadoria exibido no espelho."
                ),
            )
        )
    elif not _same_money(mirror.merchandise, calculated_merchandise):
        guidance.append(
            ReturnGuidance(
                GuidanceLevel.CONFIRMED,
                "Total dos itens não coincide com a mercadoria do espelho",
                (
                    f"Itens selecionados: {_brl(calculated_merchandise)}; "
                    f"espelho: {_brl(mirror.merchandise)}; "
                    f"diferença: {_signed_brl(mirror.merchandise - calculated_merchandise)}."
                ),
                "Itens da Nota Fiscal de Saída → QUANT. e PR.VENDA",
            )
        )

    for item in selected:
        _compare_item_rates(item, guidance)

    _compare_direct_totals(mirror, siaf, guidance)
    inferred_base = _infer_icms_base(mirror)
    _analyze_icms_composition(
        mirror,
        selected,
        calculated_merchandise,
        inferred_base,
        guidance,
    )
    _analyze_packaging(mirror, siaf, guidance)
    _analyze_st(mirror, siaf, guidance)
    _analyze_invoice_composition(mirror, guidance)

    return SupplierReturnAnalysis(
        selected_item_count=len(selected),
        calculated_merchandise=calculated_merchandise,
        inferred_icms_base=inferred_base,
        guidance=tuple(guidance),
    )


def format_supplier_return_analysis(analysis: SupplierReturnAnalysis) -> str:
    lines = [
        f"Itens selecionados: {analysis.selected_item_count}",
        f"Mercadoria calculada: {_brl(analysis.calculated_merchandise)}",
    ]
    if analysis.inferred_icms_base is not None:
        lines.append(
            "Base de ICMS aproximada por valor ÷ alíquota: "
            f"{_brl(analysis.inferred_icms_base)} "
            "(o arredondamento do imposto pode admitir outra base próxima)"
        )
    lines.extend(
        (
            "Resultados: "
            f"{analysis.count(GuidanceLevel.CONFIRMED)} comprovado(s), "
            f"{analysis.count(GuidanceLevel.POSSIBLE_CAUSE)} possível(is) causa(s), "
            f"{analysis.count(GuidanceLevel.PENDING_CONFIRMATION)} pendente(s).",
            "",
        )
    )
    if not analysis.guidance:
        lines.append("Nenhuma divergência foi identificada com os valores informados.")
        return "\n".join(lines)
    level_labels = {
        GuidanceLevel.CONFIRMED: "COMPROVADO",
        GuidanceLevel.POSSIBLE_CAUSE: "POSSÍVEL CAUSA",
        GuidanceLevel.PENDING_CONFIRMATION: "PENDENTE DE CONFIRMAÇÃO",
    }
    for index, item in enumerate(analysis.guidance, start=1):
        item_suffix = f" — item {item.item_number}" if item.item_number is not None else ""
        lines.append(f"{index}. [{level_labels[item.level]}]{item_suffix} {item.title}")
        lines.append(f"   {item.detail}")
        if item.siaf_location:
            lines.append(f"   Local no SIAF: {item.siaf_location}")
        lines.append("")
    lines.append(
        "O resultado reproduz e compara valores informados; não confirma a correção fiscal."
    )
    return "\n".join(lines)


def parse_optional_decimal(value: str, *, label: str) -> Decimal | None:
    normalized = value.strip()
    if not normalized:
        return None
    if not _PLAIN_DECIMAL.fullmatch(normalized):
        raise ValueError(f"{label} exige um número decimal sem notação científica.")
    try:
        parsed = Decimal(normalized.replace(",", "."))
    except InvalidOperation as error:
        raise ValueError(f"{label} exige um número decimal válido.") from error
    if not parsed.is_finite() or parsed < 0:
        raise ValueError(f"{label} não pode ser negativo, infinito ou NaN.")
    return parsed


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


_ITEM_EDITABLE_FIELDS = {
    "return_quantity": "Quantidade devolvida",
    "unit_value": "Preço unitário",
    "mirror_product_total": "Total do item no espelho",
    "siaf_product_total": "Total do item no SIAF",
    "mirror_icms_rate": "ICMS do espelho",
    "mirror_reduction_rate": "Redução do espelho",
    "mirror_ipi_rate": "IPI do espelho",
    "siaf_icms_rate": "ICMS calculado no SIAF",
    "siaf_reduction_rate": "Redução calculada no SIAF",
    "siaf_ipi_rate": "IPI calculado no SIAF",
}


def _build_item(item: NFeItem) -> ReturnItemPreparation:
    return ReturnItemPreparation(
        item_number=item.number,
        product_code=item.product_code,
        description=item.description,
        original_quantity=item.quantity,
        original_unit_value=item.unit_value,
        original_product_value=item.product_value,
        selected=False,
        return_quantity=item.quantity,
        unit_value=item.unit_value,
        original_icms_rate=_tax_decimal(item, "pICMS"),
        original_reduction_rate=_tax_decimal(item, "pRedBC"),
        original_ipi_rate=_tax_decimal(item, "pIPI"),
    )


def _tax_decimal(item: NFeItem, field_name: str) -> Decimal | None:
    for field in item.tax_fields:
        if field.path.rsplit(".", 1)[-1] != field_name:
            continue
        try:
            parsed = Decimal(field.value)
        except InvalidOperation:
            return None
        return parsed if parsed.is_finite() else None
    return None


def _validate_item(item: ReturnItemPreparation) -> None:
    if item.return_quantity <= 0:
        raise ValueError("A quantidade devolvida deve ser maior que zero.")
    if item.return_quantity > item.original_quantity:
        raise ValueError(
            "A quantidade devolvida não pode superar a quantidade da nota de entrada."
        )
    if item.unit_value < 0:
        raise ValueError("O preço unitário não pode ser negativo.")


def _compare_item_rates(
    item: ReturnItemPreparation,
    guidance: list[ReturnGuidance],
) -> None:
    if (
        item.mirror_product_total is not None
        and item.siaf_product_total is not None
        and not _same_money(item.mirror_product_total, item.siaf_product_total)
    ):
        guidance.append(
            ReturnGuidance(
                GuidanceLevel.CONFIRMED,
                "Total do item divergente",
                (
                    f"Espelho: {_brl(item.mirror_product_total)}; "
                    f"SIAF: {_brl(item.siaf_product_total)}; diferença: "
                    f"{_signed_brl(item.mirror_product_total - item.siaf_product_total)}."
                ),
                "Itens da Nota Fiscal de Saída → coluna TOTAL",
                item.item_number,
            )
        )
    fields = (
        (
            "ICMS",
            item.mirror_icms_rate,
            item.siaf_icms_rate,
            "Itens da Nota Fiscal de Saída → coluna %ICMS",
        ),
        (
            "redução de ICMS",
            item.mirror_reduction_rate,
            item.siaf_reduction_rate,
            "Itens da Nota Fiscal de Saída → coluna %RED.",
        ),
        (
            "IPI",
            item.mirror_ipi_rate,
            item.siaf_ipi_rate,
            "Itens da Nota Fiscal de Saída → coluna %IPI",
        ),
    )
    for label, mirror_value, siaf_value, location in fields:
        if mirror_value is None:
            continue
        if siaf_value is None:
            guidance.append(
                ReturnGuidance(
                    GuidanceLevel.PENDING_CONFIRMATION,
                    f"{label} do SIAF não informado",
                    (
                        f"O espelho informa {mirror_value}% para {label}. "
                        "Informe o valor mostrado na linha do item no SIAF para comparar."
                    ),
                    location,
                    item.item_number,
                )
            )
        elif not _close(mirror_value, siaf_value):
            guidance.append(
                ReturnGuidance(
                    GuidanceLevel.CONFIRMED,
                    f"Alíquota/percentual de {label} divergente",
                    (
                        f"Espelho: {mirror_value}%; SIAF: {siaf_value}%; "
                        f"diferença: {mirror_value - siaf_value:+} ponto(s) percentual(is)."
                    ),
                    location,
                    item.item_number,
                )
            )


def _compare_direct_totals(
    mirror: ReturnTotals,
    siaf: ReturnTotals,
    guidance: list[ReturnGuidance],
) -> None:
    fields = (
        "merchandise",
        "discount",
        "freight",
        "insurance",
        "additional_expenses",
        "increase",
        "bonus",
        "complement",
        "icms_base",
        "icms_value",
        "ipi_value",
        "st_base",
        "st_value",
        "invoice_total",
    )
    for field_name in fields:
        mirror_value = getattr(mirror, field_name)
        siaf_value = getattr(siaf, field_name)
        if (
            mirror_value is None
            or siaf_value is None
            or _same_money(mirror_value, siaf_value)
        ):
            continue
        guidance.append(
            ReturnGuidance(
                GuidanceLevel.CONFIRMED,
                f"{TOTAL_FIELD_LABELS[field_name]} divergente",
                (
                    f"Espelho: {_brl(mirror_value)}; SIAF: {_brl(siaf_value)}; "
                    f"diferença: {_signed_brl(mirror_value - siaf_value)}."
                ),
                TOTAL_FIELD_LOCATIONS.get(field_name),
            )
        )


def _infer_icms_base(totals: ReturnTotals) -> Decimal | None:
    if totals.icms_base is not None:
        return money(totals.icms_base)
    if (
        totals.icms_rate is None
        or totals.icms_value is None
        or totals.icms_rate == 0
    ):
        return None
    return money(totals.icms_value * Decimal("100") / totals.icms_rate)


def _analyze_icms_composition(
    mirror: ReturnTotals,
    selected_items: tuple[ReturnItemPreparation, ...],
    merchandise: Decimal,
    inferred_base: Decimal | None,
    guidance: list[ReturnGuidance],
) -> None:
    components = merchandise
    components += _value(mirror.freight)
    components += _value(mirror.insurance)
    components += _value(mirror.packaging)
    components += _value(mirror.additional_expenses)
    components += _value(mirror.increase)
    components += _value(mirror.complement)
    components -= _value(mirror.discount)
    components -= _value(mirror.bonus)
    components = money(components)

    item_rates = tuple(item.mirror_icms_rate for item in selected_items)
    has_item_rate = any(rate is not None for rate in item_rates)
    all_items_have_rate = bool(selected_items) and all(
        rate is not None for rate in item_rates
    )
    if has_item_rate and not all_items_have_rate:
        guidance.append(
            ReturnGuidance(
                GuidanceLevel.PENDING_CONFIRMATION,
                "Alíquotas de ICMS incompletas nos itens",
                (
                    "Alguns itens selecionados possuem ICMS do espelho e outros não. "
                    "Informe a alíquota de todos os itens para evitar um cálculo "
                    "agregado incorreto."
                ),
                "Itens da Nota Fiscal de Saída → coluna %ICMS",
            )
        )
        return

    if all_items_have_rate:
        item_result = _calculate_item_icms(selected_items)
        extra_components = money(components - merchandise)
        configurations = {
            (
                item.mirror_icms_rate,
                item.mirror_reduction_rate or Decimal("0"),
            )
            for item in selected_items
        }
        if extra_components != 0 and len(configurations) > 1:
            guidance.append(
                ReturnGuidance(
                    GuidanceLevel.PENDING_CONFIRMATION,
                    "Despesas exigem rateio entre alíquotas diferentes",
                    (
                        f"Existem {_brl(extra_components)} fora do valor dos itens e mais de "
                        "uma combinação de ICMS/redução. Não é seguro atribuir esse valor a uma "
                        "alíquota sem conhecer o rateio usado pelo espelho."
                    ),
                    "Nota Fiscal de Saída → itens e rodapé",
                )
            )
            return
        calculated_base, calculated_icms = item_result
        if extra_components != 0:
            rate, reduction = next(iter(configurations))
            extra_base = _reduced_base(extra_components, reduction)
            calculated_base = money(calculated_base + extra_base)
        if len(configurations) == 1:
            rate, _reduction = next(iter(configurations))
            calculated_icms = _calculate_icms(calculated_base, rate)
        _append_icms_result(
            mirror,
            components,
            calculated_base,
            calculated_icms,
            "cálculo item a item",
            "reduções informadas por item",
            guidance,
        )
        return

    rate = mirror.icms_rate
    reduction = mirror.icms_reduction_rate or Decimal("0")
    if rate is None and mirror.icms_base is None:
        return
    calculated_base = _reduced_base(components, reduction)
    calculated_icms = (
        None if rate is None else _calculate_icms(calculated_base, rate)
    )
    _append_icms_result(
        mirror,
        components,
        calculated_base,
        calculated_icms,
        "cálculo agregado",
        f"redução total de {reduction}%",
        guidance,
        inferred_base=inferred_base,
    )


def _calculate_item_icms(
    selected_items: tuple[ReturnItemPreparation, ...],
) -> tuple[Decimal, Decimal]:
    total_base = Decimal("0")
    total_icms = Decimal("0")
    for item in selected_items:
        rate = item.mirror_icms_rate
        if rate is None:
            continue
        reduction = item.mirror_reduction_rate or Decimal("0")
        base = _reduced_base(item.product_total, reduction)
        total_base += base
        total_icms += _calculate_icms(base, rate)
    return money(total_base), money(total_icms)


def _reduced_base(value: Decimal, reduction: Decimal) -> Decimal:
    return money(value * (Decimal("100") - reduction) / Decimal("100"))


def _calculate_icms(base: Decimal, rate: Decimal) -> Decimal:
    return money(base * rate / Decimal("100"))


def _append_icms_result(
    mirror: ReturnTotals,
    components: Decimal,
    calculated_base: Decimal,
    calculated_icms: Decimal | None,
    method: str,
    reduction_description: str,
    guidance: list[ReturnGuidance],
    *,
    inferred_base: Decimal | None = None,
) -> None:
    base_matches = (
        mirror.icms_base is not None
        and _same_money(calculated_base, mirror.icms_base)
    )
    value_matches = (
        calculated_icms is not None
        and mirror.icms_value is not None
        and _same_money(calculated_icms, mirror.icms_value)
    )
    if base_matches or value_matches:
        included = _described_nonzero_components(mirror)
        detail = (
            f"O {method} usa composição de {_brl(components)}, {reduction_description} "
            f"e resulta em base {_brl(calculated_base)}"
        )
        if calculated_icms is not None:
            detail += f" e ICMS {_brl(calculated_icms)}"
        detail += (
            f", coincidente com o espelho ({included}). Confirme no SIAF a incidência "
            "e o rateio dos componentes."
        )
        guidance.append(
            ReturnGuidance(
                GuidanceLevel.POSSIBLE_CAUSE,
                "Composição provável da base de ICMS identificada",
                detail,
                "Nota Fiscal de Saída → rodapé e colunas %RED./%ICMS dos itens",
            )
        )
        return

    if mirror.icms_base is None and mirror.icms_value is None:
        return
    reference_base = mirror.icms_base or inferred_base
    base_detail = (
        ""
        if reference_base is None
        else (
            f" Base esperada/aproximada: {_brl(reference_base)}; "
            f"base calculada: {_brl(calculated_base)}."
        )
    )
    value_detail = (
        ""
        if mirror.icms_value is None or calculated_icms is None
        else (
            f" ICMS do espelho: {_brl(mirror.icms_value)}; "
            f"ICMS calculado: {_brl(calculated_icms)}."
        )
    )
    guidance.append(
        ReturnGuidance(
            GuidanceLevel.PENDING_CONFIRMATION,
            "Composição de ICMS não coincide com o espelho",
            f"O {method} não reproduziu os valores informados.{base_detail}{value_detail}",
            "Nota Fiscal de Saída → rodapé e colunas %RED./%ICMS dos itens",
        )
    )


def _analyze_packaging(
    mirror: ReturnTotals,
    siaf: ReturnTotals,
    guidance: list[ReturnGuidance],
) -> None:
    if mirror.packaging is None or mirror.packaging == 0:
        return
    represented = any(
        value is not None and _same_money(value, mirror.packaging)
        for value in (siaf.additional_expenses, siaf.increase)
    )
    if represented:
        return
    guidance.append(
        ReturnGuidance(
            GuidanceLevel.POSSIBLE_CAUSE,
            "Embalagem pode não estar representada no SIAF",
            (
                f"O espelho informa {_brl(mirror.packaging)} de embalagem. Nas telas "
                "homologadas não existe um campo com esse nome; confira se o valor deve ser "
                "representado como despesa acessória ou acréscimo e se compõe a base tributária."
            ),
            "Nota Fiscal de Saída → rodapé → Desp.Acess. ou Acréscimo (confirmar)",
        )
    )


def _analyze_st(
    mirror: ReturnTotals,
    siaf: ReturnTotals,
    guidance: list[ReturnGuidance],
) -> None:
    mismatch = any(
        mirror_value is not None
        and siaf_value is not None
        and not _same_money(mirror_value, siaf_value)
        for mirror_value, siaf_value in (
            (mirror.st_base, siaf.st_base),
            (mirror.st_value, siaf.st_value),
        )
    )
    if not mismatch:
        return
    guidance.append(
        ReturnGuidance(
            GuidanceLevel.POSSIBLE_CAUSE,
            "Configuração estadual pode influenciar o ICMS ST",
            (
                "A base ou o valor de substituição diverge. A tela fornecida mostra que o "
                "produto possui configuração por UF com MVA, ICMS débito e ICMS substituição; "
                "confira esses valores sem alterá-los automaticamente."
            ),
            (
                "Cadastro do produto → Custos → Venda para Fora do Estado → "
                "%MVA, %ICMS DÉB. e %ICMS SUBS."
            ),
        )
    )


def _analyze_invoice_composition(
    mirror: ReturnTotals,
    guidance: list[ReturnGuidance],
) -> None:
    if mirror.invoice_total is None or mirror.merchandise is None:
        return
    composition = mirror.merchandise
    composition -= _value(mirror.discount)
    composition += _value(mirror.freight)
    composition += _value(mirror.insurance)
    composition += _value(mirror.packaging)
    composition += _value(mirror.additional_expenses)
    composition += _value(mirror.increase)
    composition += _value(mirror.complement)
    composition -= _value(mirror.bonus)
    composition += _value(mirror.ipi_value)
    composition += _value(mirror.st_value)
    composition = money(composition)
    if _same_money(composition, mirror.invoice_total):
        guidance.append(
            ReturnGuidance(
                GuidanceLevel.POSSIBLE_CAUSE,
                "Totais informados reconciliam aritmeticamente",
                (
                    f"A composição dos valores digitados resulta em {_brl(composition)}, "
                    "igual ao total do espelho. Isso confirma a soma, mas não a regra fiscal."
                ),
                "Nota Fiscal de Saída → rodapé → Total Nota",
            )
        )
    else:
        guidance.append(
            ReturnGuidance(
                GuidanceLevel.PENDING_CONFIRMATION,
                "Total do espelho não foi totalmente explicado",
                (
                    f"Componentes digitados: {_brl(composition)}; total do espelho: "
                    f"{_brl(mirror.invoice_total)}; diferença restante: "
                    f"{_signed_brl(mirror.invoice_total - composition)}."
                ),
                "Nota Fiscal de Saída → rodapé",
            )
        )


def _described_nonzero_components(totals: ReturnTotals) -> str:
    parts: list[str] = ["mercadoria"]
    for name in (
        "discount",
        "freight",
        "insurance",
        "packaging",
        "additional_expenses",
        "increase",
        "bonus",
        "complement",
    ):
        value = getattr(totals, name)
        if value is not None and value != 0:
            parts.append(TOTAL_FIELD_LABELS[name].lower())
    return ", ".join(parts)


def _value(value: Decimal | None) -> Decimal:
    return Decimal("0") if value is None else value


def _close(left: Decimal, right: Decimal) -> bool:
    return abs(left - right) <= COMPARISON_TOLERANCE


def _same_money(left: Decimal, right: Decimal) -> bool:
    return money(left) == money(right)


def _brl(value: Decimal) -> str:
    return f"R$ {money(value):.2f}".replace(".", ",")


def _signed_brl(value: Decimal) -> str:
    formatted = f"{money(value):+.2f}".replace(".", ",")
    return f"R$ {formatted}"
