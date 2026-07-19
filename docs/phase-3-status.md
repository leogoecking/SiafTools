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
- Testes: 85 aprovados após a estabilização pós-fase.
- Cobertura combinada dos testes e smoke da interface: 87%.
- Migrations reaplicadas sem duplicação e testadas com 12 inicializações concorrentes.
- Smoke da interface visitou as onze páginas, alternou o tema, validou o diálogo e fechou a
  janela normalmente.
- Build PyInstaller `onedir` x86 concluído com o hook oficial de `sqlite3`.
- Executável criou o SQLite, persistiu a descoberta e encerrou normalmente com código 0.
- SHA-256 do executável: `39884000F6567BE10CDA2C1F3C3D399F3A52889A7F28078F31921F73ED93809F`.

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

## Estabilização pós-fase

A revisão posterior encontrou e corrigiu quatro casos não cobertos inicialmente:

- terminais que mudavam de servidor remoto reutilizavam o mesmo ambiente e podiam combinar o
  endpoint atual com uma base histórica de outro servidor;
- campos livres da base de conhecimento e de outros registros podiam receber uma credencial em
  texto puro;
- uma base incompatível podia ser marcada como selecionada e retornada como reutilizável;
- um SQLite corrompido interrompia o bootstrap antes da janela e não chegava ao log da aplicação.

A identidade do ambiente agora inclui endpoint remoto ou instalação local. Toda persistência
textual passa por sanitização central. A migration 2 normaliza seleções anteriores e instala
triggers de integridade. O bootstrap preserva o arquivo problemático, registra a exceção e
mostra uma orientação de recuperação ao usuário.
