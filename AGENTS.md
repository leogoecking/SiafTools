# Regras do projeto

1. O projeto é uma aplicação desktop Windows; não criar aplicação web.
2. O executável será utilizado diretamente no computador do cliente.
3. O fluxo principal deve descobrir automaticamente SIAF, Firebird, servidor e bases.
4. Host, porta e caminho não são campos obrigatórios no uso normal.
5. Configuração manual existe somente como fallback avançado.
6. O ambiente alvo utiliza Firebird 2.5.7 de 32 bits.
7. O MVP deve ser desenvolvido e empacotado com Python x86/32 bits.
8. Detectar e validar `fbclient.dll` ou `gds32.dll` x86.
9. Não depender de um único nome de serviço Firebird.
10. Detectar tanto servidor local quanto terminal conectado a servidor remoto.
11. Não realizar varredura recursiva completa do disco ao iniciar.
12. Classificar a base pelo esquema, não apenas pelo nome do arquivo.
13. Não tentar extrair, quebrar ou descriptografar senha do SIAF.
14. O modo padrão da aplicação é somente leitura.
15. A interface nunca executa SQL diretamente.
16. Não inventar tabelas, campos, menus ou regras do SIAF.
17. Validar tabelas e campos no catálogo antes de cada template.
18. Consultas grandes usam `fetchmany`; não usar `fetchall` sem limite comprovado.
19. Operações demoradas não podem congelar a interface.
20. Cada thread abre sua própria conexão Firebird.
21. Não armazenar nem registrar senhas em texto puro.
22. Bloquear comandos destrutivos no módulo de consultas.
23. Toda alteração exige SELECT de prévia, backup, confirmação, transação, validação, commit/rollback e auditoria.
24. Nunca executar UPDATE ou DELETE sem WHERE específico.
25. Alterações fiscais, financeiras, estoque e notas exigem alerta de risco.
26. Exportações grandes devem ser progressivas.
27. Escrever testes para descoberta, serviços, validações e operações.
28. Trabalhar em uma fase por vez e não avançar sem critérios de aceite.
29. Ao concluir, informar arquivos criados/alterados, testes, riscos e limitações.
30. Atualizar `ROADMAP.md` e `CHANGELOG.md` a cada fase.
