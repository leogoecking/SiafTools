# Fase 3 concluída — 2026-07-18

Todos os critérios de aceite do SQLite interno foram atendidos no runtime Python 3.11 x86 e no
executável PyInstaller de homologação.

## Entregas

- Banco `%LOCALAPPDATA%\SIAF Support Toolbox\data\siaf-support-toolbox.sqlite3` criado no
  bootstrap, antes da abertura da janela.
- Migration interna versionada por `schema_migrations`, executada em transação exclusiva curta.
- Tabelas de ambientes detectados, bases descobertas, perfis manuais de contingência,
  templates, histórico de execução, auditoria de operações, cache de estrutura e base de
  conhecimento.
- Índices para os acessos principais e chaves estrangeiras habilitadas em toda conexão.
- Repositório local com conexão própria por operação, adequado ao worker da descoberta.
- Serviço que sempre executa uma análise nova e, em seguida, atualiza o histórico SQLite.
- API para marcar uma base como validada e recuperar a descoberta validada mais recente.
- Preservação da assinatura, compatibilidade e seleção de uma base já validada durante novas
  análises do mesmo ambiente.
- Modelos explícitos para perfil manual, template, histórico, campo de esquema e conhecimento.

## Segurança

- Nenhuma tabela ou modelo possui campo de senha, token, segredo, CSC ou credencial.
- O perfil manual armazena somente usuário e dados técnicos de conexão; a senha permanece
  exclusivamente na sessão nas fases que vierem a abrir uma conexão Firebird.
- Mensagens de erro destinadas ao histórico passam pela mesma sanitização dos logs.
- Nenhuma consulta funcional ao esquema do SIAF e nenhuma operação de escrita Firebird foi
  adicionada nesta fase.

## Validação

- Runtime de build: CPython 3.11.9 x86/32 bits.
- Ruff: aprovado em `src`, `tests` e `scripts` pelo pipeline de build.
- Testes: 79 aprovados.
- Cobertura combinada dos testes e smoke da interface: 87%.
- Migration reaplicada sem duplicação e testada com 12 inicializações concorrentes.
- Smoke da interface visitou as onze páginas, alternou o tema, validou o diálogo e fechou a
  janela normalmente.
- Build PyInstaller `onedir` x86 concluído com o hook oficial de `sqlite3`.
- Executável criou o SQLite, persistiu a descoberta e encerrou normalmente com código 0.
- SHA-256 do executável: `12D066F87CFEC2FD62431E7AB207F106B430C72F34C5A7D95EF8C785FC60B864`.

## Critérios de aceite

- Banco interno criado automaticamente: **aprovado** no teste de bootstrap e no executável.
- Migrations idempotentes: **aprovado**, inclusive entre inicializações concorrentes.
- Nenhuma senha persistida: **aprovado** por desenho do esquema e teste de regressão.
- Descoberta validada reutilizável sem impedir nova análise: **aprovado**; o serviço analisa
  novamente e o repositório mantém a validação anterior no candidato atualizado.

## Limitações desta fase

- Templates e base de conhecimento começam vazios; conteúdo específico do SIAF só poderá ser
  incluído quando tabelas e campos reais forem validados.
- O cache de estrutura está preparado, mas será preenchido pelo inspetor previsto na Fase 5.
- A seleção visual de uma descoberta reutilizada pertence às próximas fases de conexão e
  ambiente; nesta fase a capacidade está disponível na camada de serviço/repositório.
- A tabela de auditoria está criada, mas operações controladas continuam bloqueadas até as
  fases próprias de backup, prévia, confirmação e transação.
