# Fase 2 concluída — 2026-07-18

Todos os critérios de aceite da interface base foram atendidos no runtime Python 3.11 x86 e no
executável PyInstaller de homologação.

## Entregas

- Janela principal desktop em `tkinter`/`ttk`.
- Menu lateral com as onze áreas definidas no roadmap.
- Barra superior persistente com máquina, modo, Firebird, bases, conexão, modo somente leitura,
  arquitetura e versão.
- Barra inferior persistente com operação atual, registros, tempo, progresso, arquivo, avisos e
  botão de cancelamento preparado para fases futuras.
- Página funcional de ambiente detectado e placeholders explícitos para os demais módulos.
- Temas claro e escuro sem dependência externa adicional.
- Persistência de tamanho, posição, maximização, tema e última página em
  `%LOCALAPPDATA%\SIAF Support Toolbox\data\window-state.json`.
- Diálogo modal reutilizável.
- Descoberta em thread daemon, comunicando resultados à interface por fila e `after()`.

## Validação

- Runtime: Python 3.11.9 x86.
- Testes: 65 aprovados.
- Ruff e formatação: aprovados.
- Cobertura combinada da suíte e smoke da interface: 83%.
- Cobertura da janela principal: 78%.
- Cobertura de navegação e tema: 100%.
- Smoke test visitou as onze páginas, alternou o tema, abriu e fechou o diálogo e persistiu o
  estado da janela.
- Executável x86 abriu, detectou duas bases com zero avisos, recebeu fechamento normal do
  Windows, encerrou e salvou as preferências.
- `errors.log` permaneceu vazio.

## Critérios de aceite

- Navegação funciona sem travar: **aprovado**.
- Aplicação fecha corretamente: **aprovado**, inclusive com worker daemon preparado para não
  bloquear o encerramento.

Nenhuma consulta funcional, SQLite interno ou operação de escrita foi implementada. Esses
recursos permanecem nas fases seguintes.
