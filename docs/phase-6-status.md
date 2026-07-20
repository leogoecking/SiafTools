# Fase 6 concluída — 2026-07-19

O motor de consultas somente leitura está integrado à página **Consultas**. Ele depende de uma
conexão validada e de um snapshot estrutural completo da Fase 5; se qualquer uma dessas provas
estiver ausente ou desatualizada, a consulta é bloqueada antes de abrir o Firebird.

## Entregas disponíveis

- Templates persistidos no SQLite, incluindo um diagnóstico simples e uma pesquisa
  parametrizada de relações do catálogo Firebird.
- Validador que diferencia código, comentários, literais e identificadores, aceita somente uma
  instrução `SELECT` ou `WITH` e bloqueia DML, DDL, controle transacional, múltiplas instruções,
  `SELECT INTO`, `FOR UPDATE` e `WITH LOCK`.
- Parâmetros nomeados declarados pelo template, convertidos e enviados ao driver como valores
  posicionais; valores nunca são interpolados no texto SQL.
- Revalidação do SQL tanto no serviço quanto no executor Firebird.
- Uma conexão Firebird própria do worker, com DLL x86, Firebird 2.5.7, ODS 11.2, transação
  somente leitura e rollback obrigatório.
- Leitura em lotes de 200 registros com `fetchmany`, sem `fetchall` nas bases do cliente.
- Cancelamento cooperativo verificado entre lotes.
- Cache SQLite temporário por resultado, páginas de 100 linhas na interface e limite interno de
  1.000 linhas por página.
- Remoção do cache ao substituir o resultado, fechar a aplicação ou iniciar uma nova sessão;
  sobras de encerramento anormal são removidas na próxima abertura.
- Registro de sucesso, falha, bloqueio, cancelamento, duração e quantidade processada no
  histórico, sem credenciais.

## Validação automatizada inicial

- Ruff aprovado.
- 148 testes aprovados no build corrigido da fase e 88% de cobertura combinada com o smoke da
  UI.
- Casos destrutivos, comentários/literais, parâmetros repetidos, cache paginado, limpeza de
  arquivos, falha fechada do esquema, `fetchmany(200)`, transação read-only e cancelamento entre
  lotes cobertos por regressão.
- Smoke da interface percorreu as onze páginas, incluindo **Consultas**, e fechou normalmente.
- Build PyInstaller x86 aprovado: o executável iniciou, criou a migration 4, persistiu os dois
  templates de sistema e fechou com código 0; `app.log` e `errors.log` permaneceram vazios.
- SHA-256 do executável:
  `BBF1D7C8561CB4B8BCBDD2573F0B7D495BE9E73CF7ED8CF96C247191AE68E77A`.

## Homologação de campo concluída

Os dois templates de sistema foram executados no computador do cliente contra o ambiente real
já validado e inspecionado. Tanto a consulta de data/hora do servidor quanto a pesquisa
parametrizada de relações retornaram dados na interface. Essa prova confirma o caminho completo
UI → serviço → validação de esquema → executor Firebird read-only → cache paginado.

O bloqueio de comandos destrutivos, o processamento de consultas grandes sem ocupar a thread do
Tk e o cancelamento entre lotes permanecem cobertos pela suíte automatizada. Como limitação
conhecida, o cancelamento não interrompe uma instrução enquanto o servidor ainda prepara o
primeiro lote; ele passa a valer assim que o controle retorna ao worker.

## Correções após a conclusão

- O analisador agora extrai relações de `FROM`, `JOIN`, CTEs e junções por vírgula, ignora aliases
  de CTE e exige correspondência exata com `required_tables` antes da validação do snapshot.
- Chamadas diretas a procedures selecionáveis são bloqueadas antes da conexão Firebird.
- `RDB$DATABASE` e `RDB$RELATIONS`, usados pelos templates internos, são as únicas relações de
  catálogo liberadas explicitamente pela barreira estrutural.
- O SQL dos templates deixou de passar pelo redator de logs, evitando corrupção de campos e
  parâmetros legítimos como `PASSWORD = :password`.
- Resultados anteriores são apagados da tabela visual ao trocar base/template e antes de uma
  nova execução; consultas bloqueadas ou com falha não deixam dados antigos na tela.
- Um `finally` externo ao fluxo completo apaga a senha mesmo quando repositório, cache de esquema
  ou criação do resultado temporário falham antes do executor.
- A suíte passou para 148 testes, além do smoke que confirma a limpeza de resultados obsoletos.
