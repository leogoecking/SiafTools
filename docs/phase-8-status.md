# Fase 8 concluída — 2026-07-19

As consultas de NF-e, entradas de fornecedor e PDV/NFC-e estão implementadas na página
**Consultas**. A fase permanece estritamente somente leitura e depende de conexão validada e
snapshot estrutural completo da `SIAFLOJA.FDB`.

## Contratos confirmados no esquema real

- `DSIAF036` possui chave primária `SAI_SER + SAI_PED`; `DSIAF037` possui índice com
  `SAI_SER + SAI_PED + PRO_COD`.
- `DSIAF011` possui índice único `ENT_NOTA + FOR_COD`; `DSIAF012` possui índice com
  `ENT_NOTA + FOR_COD + PRO_COD`.
- `DSIAF400` possui chave primária `ID`; `DSIAF401` indexa `PDV_COD` e `DSIAF402` contém o
  mesmo campo de vínculo financeiro.

Todos os campos selecionados e filtrados pelos templates foram conferidos no snapshot real
inspecionado em 2026-07-19. A validação de requisitos continua bloqueando a consulta antes da
conexão quando uma tabela ou campo não existe na base selecionada.

## Templates implementados

1. **NF-e — saídas e indicadores:** série, número, chave, cliente ou período.
2. **NF-e — itens da saída:** série, número, produto, barra ou período.
3. **Entradas — notas de fornecedor:** nota, fornecedor, série, chave ou período.
4. **Entradas — itens da nota:** nota, fornecedor, produto, barra ou período.
5. **PDV — vendas e NFC-e:** ID, chave, cliente, terminal, status ou período.
6. **PDV — itens da venda:** ID do PDV, produto, barra, terminal ou período.
7. **PDV — pagamentos da venda:** ID do PDV, tipo, TEF, terminal ou período.

Cada template exige pelo menos um filtro e possui limite persistido de 500 linhas. O SQL busca
uma linha adicional somente para detectar a existência de mais dados; a linha de controle não é
exibida nem exportada. Quando o limite é atingido, a interface informa que o resultado é parcial,
solicita filtros mais específicos e identifica a exportação como `RESULTADO-PARCIAL`.

Datas são informadas como `DD/MM/AAAA`, vinculadas ao driver como valores `date` e exibidas no
mesmo formato na interface e no CSV. O XLSX mantém o tipo nativo com formatação brasileira.
Períodos invertidos são bloqueados antes da consulta. Nos templates de PDV, o uso do período
exige as duas datas, mas não possui limite de duração; a ordenação usa as chaves primárias
`DSIAF400.ID` ou
`DSIAF402.ID`, evitando a ordenação pela coluna de data sem índice. Nenhum índice ou outro objeto
é criado no banco do cliente.

O template **PDV — pagamentos da venda** filtra o período por `PDV_PREST_DATA`, a mesma data de
pagamento apresentada no resultado, e não pela data do cabeçalho da venda.

Indicadores como `SAI_DPECPEND`, `SAI_CANCEL`, `SAI_DENEGADO`, `PDV_STATUS`,
`TEF_CONFIRMADO` e campos semelhantes são apresentados com o valor original. A ferramenta não
atribui significado a códigos que ainda não foram homologados por regra de negócio.

## Homologação e validação

- Ruff aprovado.
- 172 testes automatizados aprovados.
- As consultas reais dos sete templates retornaram os dados esperados no computador do cliente.
- Os sete SQLs foram aceitos pelo validador somente leitura e suas dependências declaradas
  correspondem exatamente às relações extraídas.
- Todos os campos obrigatórios foram comparados com o snapshot real, sem ausências.
- Regressões cobrem datas brasileiras, períodos invertidos ou excessivos, filtro obrigatório,
  detecção de truncamento, período correto dos pagamentos e relações de cabeçalho/item.
- O smoke da interface percorre as onze páginas, confirma 12 templates persistidos, valida a
  apresentação brasileira das datas e organiza sete filtros em quatro linhas para telas menores.
- Build PyInstaller com Python 3.11.9 x86 aprovado. O executável abriu no smoke, criou o SQLite
  com migration 5, persistiu os 12 templates esperados e os sete limites da Fase 8, fechou sem
  instâncias duplicadas e manteve `errors.log` vazio.
- Artefato: `dist/SIAFSupportToolbox/SIAFSupportToolbox.exe`.
- SHA-256: `597B441F0A2F9926D49C0D91DDD79D2A9392F43179A1FCCF4C2A744DC9C10965`.

Nenhuma rotina de correção, alteração fiscal, financeira ou de status foi liberada. A fase
permanece estritamente somente leitura.
