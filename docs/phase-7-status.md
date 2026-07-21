# Fase 7 concluída — 2026-07-19

A primeira entrega de consultas operacionais está implementada na página **Consultas**. Ela
permanece integralmente em modo somente leitura e depende da validação da conexão e do snapshot
estrutural completo das fases anteriores.

## Consultas implementadas

- **Produtos:** `DSIAF006`, com filtros opcionais por código, nome, código de barras, referência
  e fornecedor. O vínculo com fornecedor usa exclusivamente a relação real
  `DSIAF030(PRO_COD, FOR_COD)`.
- **Clientes:** `DSIAF010`, com filtros opcionais por código, nome e CPF/CNPJ.
- **Fornecedores:** `DSIAF009`, com filtros opcionais por código, nome/razão e CPF/CNPJ.

As tabelas e cada campo selecionado foram conferidos no snapshot real da `SIAFLOJA.FDB`
inspecionado em 2026-07-19. Antes de executar um template, o serviço compara suas dependências
com o SQL e com esse cache; ausência ou divergência bloqueia a consulta antes de abrir o
Firebird. Cada busca usa parâmetros vinculados e retorna todo o conjunto correspondente; a
leitura continua em lotes e a interface permanece paginada.

## Interface e exportação

- A seleção de uma linha mostra todos os campos retornados no painel de detalhes.
- O resultado continua paginado em cache SQLite temporário e pode ser exportado para CSV ou
  XLSX sem nova consulta à base do cliente.
- A exportação lê esse cache em lotes de 500 e roda em worker próprio, mantendo a interface
  responsiva.
- CSV usa UTF-8 com BOM e separador ponto e vírgula.
- XLSX usa o modo de escrita progressiva do `openpyxl`, cabeçalho em negrito, primeira linha
  congelada e um único filtro de planilha.
- Quando um resultado ultrapassa 1.048.575 linhas de dados, o XLSX abre abas `Dados 2`,
  `Dados 3` e seguintes, repetindo cabeçalho e filtro sem exceder o limite do Excel.
- Nomes de arquivo são exclusivos e a publicação é atômica. Falha ou cancelamento remove o
  arquivo parcial.
- Textos iniciados por `=`, `+`, `-`, `@`, caracteres de controle ou variantes Unicode recebem
  proteção contra injeção de fórmula.

## Validação automatizada inicial

- Ruff aprovado.
- 159 testes automatizados aprovados após a revisão pós-homologação.
- Os testes cobrem dependências exatas dos templates, filtros opcionais, relacionamento de
  produtos e fornecedores, leitura em lotes, cancelamento sem arquivo parcial, proteção de
  fórmulas e integração entre cache e exportador.
- O XLSX gerado é reaberto por `openpyxl` no teste para conferir valores, filtro e congelamento,
  evitando entregar uma planilha estruturalmente inválida.
- O smoke da interface percorre as onze páginas, confirma os cinco templates persistidos,
  detalhes da linha, habilitação/invalidação das exportações e fechamento normal.
- Build PyInstaller final com Python 3.11.9 x86 aprovado no diretório padrão. O executável
  permaneceu ativo no smoke, criou o SQLite com migration 4, persistiu cinco templates — três
  deles da Fase 7 — e manteve `errors.log` vazio.
- Artefato final: `dist/SIAFSupportToolbox/SIAFSupportToolbox.exe`.
- SHA-256 do build corrigido:
  `D383D82B3C6796286F525387A52217FA7CF61CBC65789E4E6FD2F96C1CDE0D80`.

## Correções pós-homologação

- Datas, horários e decimais mantêm o tipo durante o caminho Firebird → cache → XLSX.
- A neutralização de fórmulas cobre caracteres de controle e variantes Unicode, além dos quatro
  prefixos tradicionais.
- O rodapé remove o caminho antigo ao iniciar outra operação e após falha ou cancelamento.
- Um cancelamento anterior à criação das colunas não habilita nem produz exportação vazia.
- Um cancelamento após o recebimento de linhas preserva a paginação, mas identifica o conjunto
  como resultado parcial na interface, na auditoria e no nome da exportação.
- O build corrigido permaneceu ativo no smoke, criou a migration 4, persistiu os cinco templates
  esperados e manteve `errors.log` vazio.

## Homologação de campo concluída

No computador do cliente, foram testados com sucesso:

1. Busca de produto por código e por nome.
2. Busca de cliente ou fornecedor por CPF/CNPJ.
3. Seleção de uma linha e conferência do painel de detalhes.
4. Exportação do resultado para CSV e XLSX.
5. Conferência dos valores retornados no ambiente real do SIAF.

Com essa prova, a Fase 7 está concluída. Nenhuma consulta de NF-e, entrada, PDV, financeiro ou
operação de escrita foi antecipada nesta fase.

## Revisão global de resultados — 2026-07-20

O corte de 500 registros foi removido também das três consultas desta fase. A regressão com 750
linhas, a suíte com 183 testes e o smoke do executável x86 confirmaram leitura completa por
lotes, paginação local e exportação progressiva. O build comum às Fases 7–9 possui SHA-256
`FCD8FAAFBA27467299DAD27C24E54DA83EEF1B40EF48CC0B507742C8A0E8AE94`.
