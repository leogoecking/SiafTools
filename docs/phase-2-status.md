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
- Testes: 70 aprovados após a estabilização pós-fase.
- Ruff e formatação: aprovados.
- Cobertura combinada da suíte e smoke da interface: 85%.
- Cobertura da janela principal: 84%.
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

## Estabilização pós-fase

A revisão posterior encontrou e corrigiu quatro casos não cobertos inicialmente:

- último item do menu cortado no tamanho mínimo e em DPI alto;
- cabeçalho mantendo dados antigos depois de uma reanálise com erro;
- posição de janela em monitor secundário sendo movida para o monitor principal;
- colisão no arquivo temporário ao fechar mais de uma instância.

A barra lateral agora possui rolagem e traz a seleção para a área visível. O cabeçalho marca os
dados como não confirmados após falha. A geometria usa o desktop virtual do Windows, inclusive
com coordenadas negativas. A persistência usa temporários exclusivos, bloqueio entre threads e
retentativas curtas entre processos.

O smoke test comprovou acesso a `Configurações` em escala de 200% e remoção dos dados antigos.
Testes unitários preservaram coordenadas em monitores à direita e à esquerda. Uma prova com 12
processos simultâneos salvou JSON válido sem erro ou temporário residual.
