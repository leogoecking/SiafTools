# Fase 5 concluída — 2026-07-19

O inspetor de estrutura Firebird está implementado e disponível no executável x86. Depois da
validação de conexão, a página **Ambiente detectado** habilita **Inspecionar estrutura** e lê
todas as bases compatíveis da sessão.

## Entregas disponíveis

- Relações e views, campos e tipos, índices e segmentos, chaves primárias, triggers,
  procedures e generators lidos diretamente do catálogo Firebird 2.5.
- Uma conexão Firebird própria para cada base, transação read-only e rollback obrigatório.
- Leitura de todas as consultas de catálogo em lotes de 200 registros, sem `fetchall`.
- Validação de `fbclient.dll`/`gds32.dll` x86, Firebird 2.5.7 e ODS 11.2 antes da inspeção.
- Migration 4 para snapshots estruturais completos, mantendo e atualizando os caches das
  migrations anteriores.
- Substituição transacional do snapshot no SQLite, preservando o cache anterior se a gravação
  falhar.
- Comparação de relações, campos, tipos e demais objetos entre duas bases armazenadas.
- Verificação case-insensitive de tabelas e campos obrigatórios; uma consulta futura só recebe
  autorização quando todos os requisitos existem.
- Invalidação obrigatória do snapshot após qualquer nova validação Firebird; cache ausente,
  vazio, incompleto ou desatualizado bloqueia requisitos e comparações.
- Precisão numérica, comprimento em caracteres, charset e collation incluídos nos campos.
- Índices por expressão e definições de views, triggers, procedures e seus parâmetros
  comparados por hashes SHA-256, sem persistir o PSQL em texto puro.
- Senha mantida apenas em memória e apagada ao final do lote de inspeções.
- Histórico técnico da inspeção sem credenciais.

## Validação realizada

- Runtime: CPython 3.11.9 x86/32 bits.
- Ruff: aprovado.
- Testes: 122 aprovados.
- Cobertura combinada dos testes e smoke da interface: 85%.
- Inspetor: 91% de cobertura; serviço de inspeção: 93%.
- Smoke da interface: onze páginas, diálogos e invalidação de ações aprovados.
- Executável PyInstaller `onedir` x86 iniciou, criou o SQLite com a migration 4 e fechou com
  código 0; `app.log` e `errors.log` permaneceram vazios.
- SHA-256 do executável:
  `1597A07AFF3E70DA84707D1EB67AAF157A5A0A6869F90E934CC4B159A3FC0468`.

## Homologação real concluída

A inspeção foi executada no computador do cliente contra `SIAFLOJA.FDB` e `SIAFW.FDB`, usando
Firebird 2.5.7.27050 e ODS 11.2. Foram persistidos dois snapshots completos: 5.637 campos e
1.314 objetos na base de loja, mais 507 campos e 41 objetos na base geral. O total de 6.144
campos confirma a leitura integral do catálogo. A validação complementar encontrou três
índices por expressão, 213 assinaturas de triggers, 16 assinaturas de procedures e nenhum
inteiro escalado classificado incorretamente. Esses resultados encerram a Fase 5.
