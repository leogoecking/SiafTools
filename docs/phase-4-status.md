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
- Firebird fora da faixa 2.5.7 a 2.5.9, ODS diferente de 11.2 e DLL de arquitetura
  incompatível são bloqueados.
- Fallback avançado sem armazenamento de senha.
- Falhas parciais não encerram a aplicação e o diagnóstico técnico é exportado com caminhos e
  credenciais mascarados.
- Build x86 executado com sucesso em máquina sem Python instalado.

## Estabilização multi-SIAF — 2026-07-27

- Instalações são agrupadas pela pasta do executável, com associação das bases e arquivos de
  configuração encontrados dentro de cada raiz.
- A instalação em execução recebe prioridade; a interface permite selecionar outra instalação
  ou validar todas sem preencher host, porta, caminho ou DLL.
- O parser deixa de interpretar horários como `00:00` e `08:35` como referências
  `host:alias`.
- Cada DLL x86 passa por um preflight em processo isolado, com verificação dos exports mínimos
  da API Firebird e leitura da versão do arquivo.
- `fbclient.dll` utilizável e na faixa 2.5.7 a 2.5.9 recebe prioridade; bibliotecas rejeitadas
  não chegam ao plano automático.
- Se uma biblioteca falhar especificamente durante o carregamento, a validação tenta a próxima
  candidata confirmada sem repetir tentativas para erros de rede, credencial, caminho ou
  esquema.
- Cópias binariamente idênticas são verificadas uma única vez por descoberta.

No ambiente local, o fluxo selecionou automaticamente
`C:\Program Files\Firebird\Firebird_2_5\WOW64\fbclient.dll` x86 versão 2.5.9.27139 e rejeitou
as cópias de `gds32.dll` versão 9.0.3.437 por ausência de `fb_interpret`. A descoberta agrupou
`C:\Siafw` com seis bases e não produziu mais os falsos hosts `00` e `08`.

Validação final: Ruff aprovado, 257 testes aprovados, smoke Tkinter aprovado e executável
`onedir` x86 responsivo. O próprio executável confirmou os dois resultados de preflight. O
artefato contém 949 arquivos e 25.221.693 bytes; o executável possui 3.474.912 bytes e SHA-256
`00325BAF2F5B5D2DE5398D88403AF8DFE84F931B63AFEE712CDF62DD8E2D68C5`.

## Homologação de campo

Não há acesso remoto prévio aos bancos dos clientes. Por decisão operacional, o executável
será levado ao computador do cliente para identificar o ambiente e realizar as manutenções.
Assim, o cenário de terminal SIAF conectado a outro servidor permanece na matriz como
homologação de campo e não bloqueia o desenvolvimento das fases seguintes.

Na primeira execução em cada cliente, deve-se registrar se o programa identificou o servidor
remoto ou apresentou candidatos fundamentados, se as bases foram classificadas corretamente e
se a conexão read-only foi aceita com a credencial autorizada. Qualquer divergência deve ser
tratada como correção da Fase 4 antes de usar consultas ou operações.
