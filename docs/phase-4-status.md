# Fase 4 concluída tecnicamente — 2026-07-19

A descoberta automática e a conexão Firebird estão implementadas no runtime Python 3.11 x86
e disponíveis no executável PyInstaller. O fluxo local foi validado com Firebird 2.5.7,
`fbclient.dll` x86, `SIAFW.FDB` e `SIAFLOJA.FDB`, sempre em transação somente leitura e sem
persistência de credenciais.

## Critérios atendidos

- Descoberta progressiva de SIAF, Firebird, DLLs e bases sem varredura completa do disco.
- Plano automático local e remoto baseado em processos, serviços, configurações e conexões TCP.
- Classificação obrigatória pelo catálogo; o nome do arquivo isolado não aceita uma base.
- Múltiplas bases listadas e validadas fora da thread da interface.
- Firebird diferente de 2.5.7, ODS diferente de 11.2 e DLL de arquitetura incompatível são
  bloqueados.
- Fallback avançado sem armazenamento de senha.
- Falhas parciais não encerram a aplicação e o diagnóstico técnico é exportado com caminhos e
  credenciais mascarados.
- Build x86 executado com sucesso em máquina sem Python instalado.

## Homologação de campo

Não há acesso remoto prévio aos bancos dos clientes. Por decisão operacional, o executável
será levado ao computador do cliente para identificar o ambiente e realizar as manutenções.
Assim, o cenário de terminal SIAF conectado a outro servidor permanece na matriz como
homologação de campo e não bloqueia o desenvolvimento das fases seguintes.

Na primeira execução em cada cliente, deve-se registrar se o programa identificou o servidor
remoto ou apresentou candidatos fundamentados, se as bases foram classificadas corretamente e
se a conexão read-only foi aceita com a credencial autorizada. Qualquer divergência deve ser
tratada como correção da Fase 4 antes de usar consultas ou operações.
