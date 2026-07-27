from __future__ import annotations

from decimal import Decimal

import pytest

from siaf_support_toolbox.fiscal.nfe_xml_reader import (
    NFeXmlError,
    parse_nfe_xml,
    read_nfe_xml,
)

ACCESS_KEY = "35260712345678000123550010000001231000001234"


def _nfe_xml(
    *,
    model: str = "55",
    root: str = "nfeProc",
    protocol_status: str = "100",
    protocol_key: str = ACCESS_KEY,
) -> bytes:
    nfe = f"""
      <NFe xmlns="http://www.portalfiscal.inf.br/nfe">
        <infNFe Id="NFe{ACCESS_KEY}" versao="4.00">
          <ide>
            <cUF>35</cUF>
            <mod>{model}</mod>
            <serie>1</serie>
            <nNF>123</nNF>
            <dhEmi>2026-07-26T10:00:00-03:00</dhEmi>
          </ide>
          <emit>
            <CNPJ>12345678000123</CNPJ>
            <xNome>FORNECEDOR TESTE</xNome>
            <enderEmit><UF>SP</UF></enderEmit>
            <IE>123456789</IE>
          </emit>
          <dest>
            <CNPJ>98765432000198</CNPJ>
            <xNome>EMPRESA CLIENTE</xNome>
            <enderDest><UF>MG</UF></enderDest>
            <IE>987654321</IE>
          </dest>
          <det nItem="1">
            <prod>
              <cProd>ABC-1</cProd>
              <cEAN>7891234567890</cEAN>
              <xProd>PRODUTO DE TESTE</xProd>
              <NCM>12345678</NCM>
              <CEST>1234567</CEST>
              <CFOP>6102</CFOP>
              <uCom>UN</uCom>
              <qCom>2.0000</qCom>
              <vUnCom>50.0000000000</vUnCom>
              <vProd>100.00</vProd>
              <vDesc>5.00</vDesc>
            </prod>
            <imposto>
              <ICMS>
                <ICMS00>
                  <orig>0</orig>
                  <CST>00</CST>
                  <vBC>100.00</vBC>
                  <pICMS>12.0000</pICMS>
                  <vICMS>12.00</vICMS>
                </ICMS00>
              </ICMS>
              <IPI>
                <IPITrib>
                  <CST>50</CST>
                  <pIPI>5.0000</pIPI>
                  <vIPI>5.00</vIPI>
                </IPITrib>
              </IPI>
            </imposto>
          </det>
          <total>
            <ICMSTot>
              <vProd>100.00</vProd>
              <vICMS>12.00</vICMS>
              <vIPI>5.00</vIPI>
              <vNF>100.00</vNF>
            </ICMSTot>
          </total>
        </infNFe>
      </NFe>
    """.strip()
    if root == "NFe":
        return f'<?xml version="1.0" encoding="UTF-8"?>{nfe}'.encode()
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">'
        f"{nfe}"
        '<protNFe versao="4.00"><infProt>'
        f"<chNFe>{protocol_key}</chNFe>"
        "<nProt>135260000000123</nProt>"
        "<dhRecbto>2026-07-26T10:01:00-03:00</dhRecbto>"
        f"<cStat>{protocol_status}</cStat>"
        "<xMotivo>Autorizado o uso da NF-e</xMotivo>"
        "</infProt></protNFe>"
        "</nfeProc>"
    ).encode()


def test_parse_processed_nfe_extracts_parties_items_taxes_and_totals():
    document = parse_nfe_xml(_nfe_xml())

    assert document.access_key == ACCESS_KEY
    assert document.protocol_number == "135260000000123"
    assert document.protocol_status == "100"
    assert document.model == "55"
    assert document.series == "1"
    assert document.number == "123"
    assert document.issuer.document == "12345678000123"
    assert document.issuer.state == "SP"
    assert document.recipient.document == "98765432000198"
    assert document.recipient.state == "MG"
    assert len(document.items) == 1

    item = document.items[0]
    assert item.product_code == "ABC-1"
    assert item.quantity == Decimal("2.0000")
    assert item.product_value == Decimal("100.00")
    assert item.discount == Decimal("5.00")
    assert ("imposto.ICMS.ICMS00.pICMS", "12.0000") in {
        (field.path, field.value) for field in item.tax_fields
    }
    assert ("total.ICMSTot.vNF", "100.00") in {
        (field.path, field.value) for field in document.total_fields
    }


def test_parse_rejects_bare_nfe_without_authorization_protocol():
    with pytest.raises(NFeXmlError) as captured:
        parse_nfe_xml(_nfe_xml(root="NFe"))

    assert captured.value.code == "missing_protocol"


@pytest.mark.parametrize("status", ["100", "150"])
def test_parse_accepts_authorized_protocol_statuses(status):
    document = parse_nfe_xml(_nfe_xml(protocol_status=status))

    assert document.protocol_status == status


def test_parse_rejects_protocol_key_different_from_document_key():
    with pytest.raises(NFeXmlError) as captured:
        parse_nfe_xml(_nfe_xml(protocol_key="0" * 44))

    assert captured.value.code == "protocol_key_mismatch"


@pytest.mark.parametrize("status", ["110", "204", "539"])
def test_parse_rejects_protocol_without_authorization(status):
    with pytest.raises(NFeXmlError) as captured:
        parse_nfe_xml(_nfe_xml(protocol_status=status))

    assert captured.value.code == "not_authorized"


def test_parse_rejects_fake_nfe_namespace():
    payload = _nfe_xml().replace(
        b"http://www.portalfiscal.inf.br/nfe",
        b"https://example.invalid/nfe",
    )

    with pytest.raises(NFeXmlError) as captured:
        parse_nfe_xml(payload)

    assert captured.value.code == "invalid_namespace"


def test_parse_rejects_processed_nfe_without_protocol():
    payload = _nfe_xml()
    protocol_start = payload.index(b'<protNFe versao="4.00">')
    protocol_end = payload.index(b"</protNFe>", protocol_start) + len(b"</protNFe>")
    payload = payload[:protocol_start] + payload[protocol_end:]

    with pytest.raises(NFeXmlError) as captured:
        parse_nfe_xml(payload)

    assert captured.value.code == "missing_protocol"


def test_parse_rejects_invalid_protocol_number_or_datetime():
    invalid_number = _nfe_xml().replace(
        b"<nProt>135260000000123</nProt>",
        b"<nProt>123</nProt>",
    )
    invalid_datetime = _nfe_xml().replace(
        b"<dhRecbto>2026-07-26T10:01:00-03:00</dhRecbto>",
        b"<dhRecbto>2026-07-26T10:01:00</dhRecbto>",
    )

    with pytest.raises(NFeXmlError) as number_error:
        parse_nfe_xml(invalid_number)
    with pytest.raises(NFeXmlError) as datetime_error:
        parse_nfe_xml(invalid_datetime)

    assert number_error.value.code == "invalid_protocol"
    assert datetime_error.value.code == "invalid_protocol"


def test_parse_preserves_return_specific_fields_from_xml():
    returned_tax = (
        b"<impostoDevol><pDevol>100.00</pDevol><IPI><IPIDevol>"
        b"<vIPIDevol>5.00</vIPIDevol></IPIDevol></IPI></impostoDevol>"
    )
    payload = _nfe_xml().replace(b"</imposto>", b"</imposto>" + returned_tax, 1)

    document = parse_nfe_xml(payload)

    assert ("impostoDevol.pDevol", "100.00") in {
        (field.path, field.value) for field in document.items[0].tax_fields
    }
    assert ("impostoDevol.IPI.IPIDevol.vIPIDevol", "5.00") in {
        (field.path, field.value) for field in document.items[0].tax_fields
    }


def test_parse_rejects_non_model_55():
    with pytest.raises(NFeXmlError) as captured:
        parse_nfe_xml(_nfe_xml(model="65"))

    assert captured.value.code == "unsupported_model"


@pytest.mark.parametrize(
    "payload",
    [
        b'<!DOCTYPE foo [<!ENTITY xxe "segredo">]><foo>&xxe;</foo>',
        b'<\x00!\x00D\x00O\x00C\x00T\x00Y\x00P\x00E\x00 \x00f\x00o\x00o\x00>',
    ],
)
def test_parse_blocks_dtd_and_entity_declarations(payload):
    with pytest.raises(NFeXmlError) as captured:
        parse_nfe_xml(payload)

    assert captured.value.code == "unsafe_xml"


def test_parse_rejects_invalid_or_empty_xml():
    with pytest.raises(NFeXmlError) as empty:
        parse_nfe_xml(b"")
    with pytest.raises(NFeXmlError) as invalid:
        parse_nfe_xml(b"<nfeProc>")

    assert empty.value.code == "empty_xml"
    assert invalid.value.code == "invalid_xml"


def test_parse_rejects_duplicate_item_number():
    payload = _nfe_xml()
    start = payload.index(b'<det nItem="1">')
    end = payload.index(b"</det>", start) + len(b"</det>")
    payload = payload[:end] + payload[start:end] + payload[end:]

    with pytest.raises(NFeXmlError) as captured:
        parse_nfe_xml(payload)

    assert captured.value.code == "duplicate_item"


def test_read_rejects_file_above_configured_limit(tmp_path):
    path = tmp_path / "entrada.xml"
    path.write_bytes(b"<xml>conteudo</xml>")

    with pytest.raises(NFeXmlError) as captured:
        read_nfe_xml(path, max_bytes=5)

    assert captured.value.code == "file_too_large"
