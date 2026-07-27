from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

MAX_XML_BYTES = 20 * 1024 * 1024
_FORBIDDEN_XML_DECLARATION = re.compile(br"<!\s*(?:DOCTYPE|ENTITY)\b", re.IGNORECASE)
_NFE_NAMESPACE = "http://www.portalfiscal.inf.br/nfe"
_SUPPORTED_NFE_VERSION = "4.00"
_AUTHORIZED_PROTOCOL_STATUSES = frozenset({"100", "150"})

_FIELD_LABELS = {
    "cProd": "Código do produto",
    "cEAN": "Código de barras",
    "xProd": "Descrição",
    "NCM": "NCM",
    "CEST": "CEST",
    "CFOP": "CFOP",
    "uCom": "Unidade",
    "qCom": "Quantidade",
    "vUnCom": "Valor unitário",
    "vProd": "Valor dos produtos",
    "vDesc": "Desconto",
    "vFrete": "Frete",
    "vSeg": "Seguro",
    "vOutro": "Outras despesas",
    "orig": "Origem da mercadoria",
    "CST": "CST",
    "CSOSN": "CSOSN",
    "vBC": "Base de cálculo",
    "pICMS": "Alíquota de ICMS",
    "vICMS": "Valor de ICMS",
    "vBCST": "Base de cálculo de ICMS ST",
    "pICMSST": "Alíquota de ICMS ST",
    "vICMSST": "Valor de ICMS ST",
    "pIPI": "Alíquota de IPI",
    "vIPI": "Valor de IPI",
    "pPIS": "Alíquota de PIS",
    "vPIS": "Valor de PIS",
    "pCOFINS": "Alíquota de COFINS",
    "vCOFINS": "Valor de COFINS",
    "pFCP": "Alíquota de FCP",
    "vFCP": "Valor de FCP",
    "vNF": "Total da NF-e",
}


class NFeXmlError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class NFeParty:
    document: str
    name: str
    state_registration: str | None
    state: str | None


@dataclass(frozen=True, slots=True)
class NFeField:
    path: str
    label: str
    value: str


@dataclass(frozen=True, slots=True)
class NFeItem:
    number: int
    product_code: str
    barcode: str | None
    description: str
    ncm: str
    cest: str | None
    cfop: str
    unit: str
    quantity: Decimal
    unit_value: Decimal
    product_value: Decimal
    discount: Decimal | None
    freight: Decimal | None
    insurance: Decimal | None
    other_expenses: Decimal | None
    tax_fields: tuple[NFeField, ...]
    return_indicator: str | None = None


@dataclass(frozen=True, slots=True)
class NFeDocument:
    access_key: str
    protocol_number: str
    protocol_status: str
    authorization_datetime: str
    model: str
    series: str
    number: str
    issue_datetime: str | None
    issuer: NFeParty
    recipient: NFeParty
    items: tuple[NFeItem, ...]
    total_fields: tuple[NFeField, ...]


def read_nfe_xml(path: str | Path, *, max_bytes: int = MAX_XML_BYTES) -> NFeDocument:
    source = Path(path)
    try:
        size = source.stat().st_size
    except OSError as error:
        raise NFeXmlError("read_error", "Não foi possível abrir o XML selecionado.") from error
    if size > max_bytes:
        raise NFeXmlError(
            "file_too_large",
            f"O XML excede o limite de {max_bytes // (1024 * 1024)} MB.",
        )
    try:
        payload = source.read_bytes()
    except OSError as error:
        raise NFeXmlError("read_error", "Não foi possível ler o XML selecionado.") from error
    return parse_nfe_xml(payload, max_bytes=max_bytes)


def parse_nfe_xml(payload: bytes, *, max_bytes: int = MAX_XML_BYTES) -> NFeDocument:
    if not payload:
        raise NFeXmlError("empty_xml", "O arquivo XML está vazio.")
    if len(payload) > max_bytes:
        raise NFeXmlError(
            "file_too_large",
            f"O XML excede o limite de {max_bytes // (1024 * 1024)} MB.",
        )
    if _FORBIDDEN_XML_DECLARATION.search(payload.replace(b"\x00", b"")):
        raise NFeXmlError(
            "unsafe_xml",
            "O XML contém declaração DTD ou entidade e foi bloqueado por segurança.",
        )
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as error:
        raise NFeXmlError("invalid_xml", "O arquivo não contém um XML válido.") from error

    inf_nfe, inf_protocol = _find_processed_nfe(root)
    _validate_nfe_namespace(inf_nfe)
    _validate_version(root, inf_nfe)
    ide = _required_child(inf_nfe, "ide")
    model = _required_text(ide, "mod")
    if model != "55":
        raise NFeXmlError(
            "unsupported_model",
            f"O documento é modelo {model}; este diagnóstico aceita somente NF-e modelo 55.",
        )

    access_key = _access_key(inf_nfe)
    protocol_number, protocol_status, authorization_datetime = (
        _validate_authorization_protocol(inf_protocol, access_key)
    )
    items = tuple(_parse_item(element) for element in _children(inf_nfe, "det"))
    if not items:
        raise NFeXmlError("missing_items", "A NF-e não possui itens para comparar.")
    item_numbers = tuple(item.number for item in items)
    if len(item_numbers) != len(set(item_numbers)):
        raise NFeXmlError("duplicate_item", "A NF-e possui número de item duplicado.")

    total = _required_child(inf_nfe, "total")
    return NFeDocument(
        access_key=access_key,
        protocol_number=protocol_number,
        protocol_status=protocol_status,
        authorization_datetime=authorization_datetime,
        model=model,
        series=_required_text(ide, "serie"),
        number=_required_text(ide, "nNF"),
        issue_datetime=_optional_text(ide, "dhEmi") or _optional_text(ide, "dEmi"),
        issuer=_parse_party(_required_child(inf_nfe, "emit"), "enderEmit"),
        recipient=_parse_party(_required_child(inf_nfe, "dest"), "enderDest"),
        items=items,
        total_fields=_leaf_fields(total, "total"),
    )


def _find_processed_nfe(root: ET.Element) -> tuple[ET.Element, ET.Element]:
    root_name = _local_name(root.tag)
    if root_name == "NFe":
        _require_nfe_namespace(root)
        raise NFeXmlError(
            "missing_protocol",
            "O XML contém somente a NF-e e não possui o protocolo de autorização da SEFAZ.",
        )
    if root_name == "nfeProc":
        _require_nfe_namespace(root)
        nfe = _required_child(root, "NFe")
        protocol = _child(root, "protNFe")
        if protocol is None:
            raise NFeXmlError(
                "missing_protocol",
                "A NF-e processada não possui protocolo de autorização da SEFAZ.",
            )
        if (protocol.attrib.get("versao") or "").strip() != _SUPPORTED_NFE_VERSION:
            raise NFeXmlError(
                "unsupported_version",
                "O protocolo da NF-e não utiliza a versão 4.00.",
            )
        return _required_child(nfe, "infNFe"), _required_child(protocol, "infProt")
    raise NFeXmlError(
        "unsupported_xml",
        "O arquivo não é uma NF-e processada nem um XML NFe reconhecido.",
    )


def _require_nfe_namespace(element: ET.Element) -> None:
    if _namespace(element.tag) != _NFE_NAMESPACE:
        raise NFeXmlError(
            "invalid_namespace",
            "O XML não utiliza o namespace oficial da NF-e.",
        )


def _validate_nfe_namespace(inf_nfe: ET.Element) -> None:
    if any(_namespace(element.tag) != _NFE_NAMESPACE for element in inf_nfe.iter()):
        raise NFeXmlError(
            "invalid_namespace",
            "A NF-e contém elementos fora do namespace oficial.",
        )


def _validate_version(root: ET.Element, inf_nfe: ET.Element) -> None:
    process_version = (root.attrib.get("versao") or "").strip()
    document_version = (inf_nfe.attrib.get("versao") or "").strip()
    if (
        process_version != _SUPPORTED_NFE_VERSION
        or document_version != _SUPPORTED_NFE_VERSION
    ):
        raise NFeXmlError(
            "unsupported_version",
            "O diagnóstico aceita somente XML processado da NF-e versão 4.00.",
        )


def _validate_authorization_protocol(
    inf_protocol: ET.Element,
    access_key: str,
) -> tuple[str, str, str]:
    protocol_key = _required_text(inf_protocol, "chNFe")
    if protocol_key != access_key:
        raise NFeXmlError(
            "protocol_key_mismatch",
            "A chave do protocolo não corresponde à chave da NF-e.",
        )
    status = _required_text(inf_protocol, "cStat")
    if status not in _AUTHORIZED_PROTOCOL_STATUSES:
        raise NFeXmlError(
            "not_authorized",
            f"O protocolo da NF-e não está autorizado para uso (cStat {status}).",
        )
    protocol_number = _required_text(inf_protocol, "nProt")
    if not re.fullmatch(r"\d{15}", protocol_number):
        raise NFeXmlError(
            "invalid_protocol",
            "O número do protocolo de autorização da NF-e é inválido.",
        )
    authorization_datetime = _required_text(inf_protocol, "dhRecbto")
    try:
        parsed_datetime = datetime.fromisoformat(authorization_datetime)
    except ValueError as error:
        raise NFeXmlError(
            "invalid_protocol",
            "A data de recebimento do protocolo de autorização é inválida.",
        ) from error
    if parsed_datetime.tzinfo is None:
        raise NFeXmlError(
            "invalid_protocol",
            "A data do protocolo de autorização não possui fuso horário.",
        )
    return protocol_number, status, authorization_datetime


def _access_key(inf_nfe: ET.Element) -> str:
    identifier = (inf_nfe.attrib.get("Id") or "").strip()
    access_key = identifier[3:] if identifier.startswith("NFe") else identifier
    if not re.fullmatch(r"\d{44}", access_key):
        raise NFeXmlError(
            "invalid_access_key",
            "A chave de acesso da NF-e está ausente ou não possui 44 dígitos.",
        )
    return access_key


def _parse_party(element: ET.Element, address_name: str) -> NFeParty:
    document = _optional_text(element, "CNPJ") or _optional_text(element, "CPF")
    if not document:
        raise NFeXmlError(
            "missing_party_document",
            "Emitente ou destinatário não possui CNPJ/CPF no XML.",
        )
    address = _child(element, address_name)
    return NFeParty(
        document=document,
        name=_required_text(element, "xNome"),
        state_registration=_optional_text(element, "IE"),
        state=_optional_text(address, "UF") if address is not None else None,
    )


def _parse_item(element: ET.Element) -> NFeItem:
    raw_number = (element.attrib.get("nItem") or "").strip()
    try:
        number = int(raw_number)
    except ValueError as error:
        raise NFeXmlError("invalid_item", "Um item da NF-e não possui número válido.") from error

    product = _required_child(element, "prod")
    tax = _required_child(element, "imposto")
    returned_tax = _child(element, "impostoDevol")
    tax_fields = _leaf_fields(tax, "imposto")
    if returned_tax is not None:
        tax_fields += _leaf_fields(returned_tax, "impostoDevol")
    return NFeItem(
        number=number,
        product_code=_required_text(product, "cProd"),
        barcode=_optional_text(product, "cEAN"),
        description=_required_text(product, "xProd"),
        ncm=_required_text(product, "NCM"),
        cest=_optional_text(product, "CEST"),
        cfop=_required_text(product, "CFOP"),
        unit=_required_text(product, "uCom"),
        quantity=_required_decimal(product, "qCom"),
        unit_value=_required_decimal(product, "vUnCom"),
        product_value=_required_decimal(product, "vProd"),
        discount=_optional_decimal(product, "vDesc"),
        freight=_optional_decimal(product, "vFrete"),
        insurance=_optional_decimal(product, "vSeg"),
        other_expenses=_optional_decimal(product, "vOutro"),
        tax_fields=tax_fields,
        return_indicator=_optional_text(product, "indDevol"),
    )


def _leaf_fields(element: ET.Element, prefix: str) -> tuple[NFeField, ...]:
    fields: list[NFeField] = []

    def visit(node: ET.Element, path: str) -> None:
        children = list(node)
        if not children:
            value = (node.text or "").strip()
            if value:
                name = _local_name(node.tag)
                fields.append(
                    NFeField(
                        path=path,
                        label=_FIELD_LABELS.get(name, name),
                        value=value,
                    )
                )
            return
        for child in children:
            name = _local_name(child.tag)
            visit(child, f"{path}.{name}")

    for child in element:
        name = _local_name(child.tag)
        visit(child, f"{prefix}.{name}")
    return tuple(fields)


def _required_decimal(element: ET.Element, name: str) -> Decimal:
    value = _required_text(element, name)
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise NFeXmlError(
            "invalid_decimal",
            f"O campo {name} não contém um número decimal válido.",
        ) from error


def _optional_decimal(element: ET.Element, name: str) -> Decimal | None:
    value = _optional_text(element, name)
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation as error:
        raise NFeXmlError(
            "invalid_decimal",
            f"O campo {name} não contém um número decimal válido.",
        ) from error


def _required_child(element: ET.Element, name: str) -> ET.Element:
    result = _child(element, name)
    if result is None:
        raise NFeXmlError("missing_field", f"O XML não possui o grupo obrigatório {name}.")
    return result


def _required_text(element: ET.Element, name: str) -> str:
    value = _optional_text(element, name)
    if value is None:
        raise NFeXmlError("missing_field", f"O XML não possui o campo obrigatório {name}.")
    return value


def _optional_text(element: ET.Element | None, name: str) -> str | None:
    if element is None:
        return None
    child = _child(element, name)
    if child is None:
        return None
    value = (child.text or "").strip()
    return value or None


def _child(element: ET.Element, name: str) -> ET.Element | None:
    for child in element:
        if child.tag == f"{{{_NFE_NAMESPACE}}}{name}":
            return child
    return None


def _children(element: ET.Element, name: str) -> tuple[ET.Element, ...]:
    qualified_name = f"{{{_NFE_NAMESPACE}}}{name}"
    return tuple(child for child in element if child.tag == qualified_name)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _namespace(tag: str) -> str:
    if not tag.startswith("{") or "}" not in tag:
        return ""
    return tag[1:].split("}", 1)[0]
