# Fase 9 em homologação — 2026-07-19

As consultas financeiras e de permissões estão implementadas na página **Consultas**. A fase
permanece estritamente somente leitura, exige conexão validada e utiliza o snapshot estrutural
completo antes de abrir cada consulta.

## Contratos confirmados no esquema real

- A `SIAFLOJA.FDB` contém `DSIAF015/016/017/018/025/026/136` para títulos, caixa diário,
  transferências e cadastros de tipos.
- A `SIAFW.FDB` contém `DSIAF050/051/052/053` para usuários, permissões, programas e grupos.
- `DSIAF015.REC_DUP` é chave primária; `DSIAF016.PAG_NUM` possui índice único.
- Caixa diário possui índices por `CAI_DATA`, `CAI_COD` e `CAI_TURNO` nas combinações reais.
- `DSIAF051` indexa `GRU_USU`; `DSIAF050`, `DSIAF052` e `DSIAF053` possuem os índices de busca
  confirmados no snapshot.

Todos os campos declarados pelos templates foram comparados com o cache real sem ausências.
Nenhum SQL seleciona `DSIAF050.USU_SENHA`.

## Templates implementados

1. **Contas a receber — títulos e baixas:** duplicata, cliente, saída ou vencimento.
2. **Contas a pagar — títulos e baixas:** número, duplicata, fornecedor, entrada ou vencimento.
3. **Caixa diário — cabeçalhos:** caixa, turno ou período.
4. **Caixa diário — lançamentos:** caixa, turno, duplicata, pagamento, transferência ou período.
5. **Caixa diário — transferências:** código, caixas, usuário ou período.
6. **Tipos de venda:** código, descrição ou tipo de pagamento vinculado.
7. **Tipos de pagamento:** código ou descrição.
8. **Usuários e grupos:** usuário, nome, grupo ou descrição do grupo.
9. **Permissões — diagnóstico por usuário, grupo e programa:** usuário, grupo, descrição,
   módulo ou índice do programa, sem corte fixo de registros.
10. **Permissões — catálogo de programas:** descrição ou módulo.

Cada template exige ao menos um filtro. Os templates financeiros e os demais templates de
permissões buscam uma linha de controle além do limite e apresentam no máximo 500 registros;
se houver mais dados, a interface e a exportação identificam o resultado como parcial. O
diagnóstico por usuário, grupo e programa não possui corte fixo: ele continua usando leitura em
lotes, cache paginado e exportação progressiva. Datas usam `DD/MM/AAAA` e aceitam períodos
longos sem limite artificial.

Permissões e indicadores financeiros são apresentados exatamente como armazenados. A ferramenta
não converte valores em “permitido”, “negado”, “aberto”, “pago” ou outra regra de negócio que
ainda não tenha sido conferida no SIAF.

## Correções da revisão pós-implementação

- A relação com usuários no diagnóstico de permissões só é ativada quando existe filtro por
  código ou nome de usuário. Pesquisas por grupo ou programa retornam uma linha por permissão,
  sem multiplicá-la por todos os usuários pertencentes ao grupo.
- `DSIAF016.PRA_COD` é apresentado como `PRA_COD`; o significado funcional desse campo não é
  inferido pela ferramenta.
- A migration 6 registra no histórico se a consulta foi truncada pelo limite de 500 linhas.
- Espaços nas extremidades dos filtros são removidos na interface e novamente no serviço.
  Valores contendo apenas espaços não satisfazem a exigência de filtro.
- Após a homologação por grupo, o limite fixo de 500 registros foi removido somente do
  diagnóstico de permissões; filtros continuam obrigatórios.

## Validação automatizada inicial

- Ruff e 182 testes automatizados aprovados.
- Dez templates e onze relações previstas cobertas.
- SQLs aceitos pelo validador somente leitura, com dependências extraídas iguais às declaradas.
- Regressões cobrem filtro obrigatório, normalização de espaços, datas brasileiras sem limite
  de duração, limite de resultado, histórico de truncamento, cardinalidade das permissões,
  rótulo neutro de `PRA_COD` e ausência do campo de senha.
- O smoke da interface percorreu as onze páginas, carregou 22 templates no total, confirmou o
  diagnóstico de permissões sem limite e preservou o teto de 500 nos outros nove templates da
  Fase 9.
- Build PyInstaller com Python 3.11.9 x86 aprovado. O executável abriu, aplicou migration 6,
  persistiu os 22 templates, manteve zero referências a `USU_SENHA`, deixou `errors.log` vazio e
  foi fechado sem instâncias duplicadas.
- Artefato: `dist/SIAFSupportToolbox/SIAFSupportToolbox.exe`.
- SHA-256: `8048CA86BDC4D1D0AD836D6147D8B852AD93DE1AA11A01ADDB893A25F1A197B9`.

## Homologação de campo pendente

1. Conferir um título a receber pela duplicata e pelo cliente.
2. Conferir um título a pagar pelo número/fornecedor.
3. Comparar um dia de caixa e seus lançamentos.
4. Conferir uma transferência entre caixas.
5. Conferir um tipo de venda e um tipo de pagamento.
6. Na `SIAFW.FDB`, localizar um usuário e confirmar seu grupo.
7. Pesquisar uma rotina conhecida e comparar os cinco campos de permissão na tela do SIAF.
8. Exportar uma amostra financeira e uma de permissões.

Até essa prova, a Fase 9 permanece em homologação. Nenhuma alteração financeira, permissão ou
senha foi implementada.
