# Fase 4 em homologação — 2026-07-18

A descoberta automática e a conexão Firebird estão implementadas no runtime Python 3.11 x86
e disponíveis no executável PyInstaller. A fase ainda não está concluída: a autenticação pela
nova interface precisa ser exercitada com credenciais autorizadas e o modo terminal remoto
precisa ser homologado em um ambiente real.

## Entregas disponíveis

- Orquestrador reúne processos, serviços, Registro, atalhos, instalações, conexões TCP,
  configurações próximas ao SIAF, DLLs e bases em uma única análise tolerante a falhas.
- Busca progressiva e limitada aos locais fundamentados pelas evidências, sem varredura
  recursiva completa do disco.
- Detecção da versão instalada do Firebird e validação da arquitetura x86 de `fbclient.dll` ou
  `gds32.dll` antes da conexão.
- Leitura limitada de arquivos de configuração para encontrar referências locais, aliases e
  endpoints remotos, ignorando linhas que possam conter senha ou outro segredo.
- Plano ranqueado de conexão local ou remota, sem solicitar host, porta ou caminho no fluxo
  normal.
- Fallback avançado para conexão manual, que só permite salvar metadados técnicos após uma
  validação bem-sucedida e nunca armazena a senha.
- Credenciais mantidas apenas em memória e apagadas ao final da tentativa, inclusive quando o
  driver retorna erro.
- Pré-teste curto de conectividade TCP para evitar espera prolongada em endpoints
  indisponíveis.
- Conexão Firebird própria no worker, transação somente leitura e classificação pelo catálogo;
  nome do arquivo isoladamente não torna uma base compatível.
- Tradução das falhas comuns de cliente, rede, autenticação, versão e esquema para mensagens
  utilizáveis pelo atendente.
- Persistência do endpoint, versão, seleção, compatibilidade e assinatura do esquema no
  SQLite, sem credencial.
- Status de análise e conexão na página de ambiente, preservando os resultados da descoberta
  quando uma tentativa de autenticação falha.
- Uma nova descoberta que falhe invalida o plano e desabilita as ações anteriores, evitando
  conexão acidental com um endpoint desatualizado.
- Exportação atômica do diagnóstico técnico em JSON, com nomes sem colisão e mascaramento de
  caminhos.

## Validação realizada

- Runtime de build: CPython 3.11.9 x86/32 bits.
- Descoberta real identificou Firebird `2.5.7.27050`, `fbclient.dll` x86 e duas bases locais:
  `SIAFW.FDB` e `SIAFLOJA.FDB`.
- O plano automático preparou as duas conexões por `localhost` sem solicitar host, porta ou
  caminho.
- Ruff e verificações do pipeline de build: aprovados.
- Testes: 107 aprovados.
- Cobertura combinada da suíte e do smoke da interface: 85%.
- Smoke da interface visitou as onze páginas, abriu os diálogos de credenciais e fallback,
  apagou as credenciais de teste e fechou normalmente.
- Executável PyInstaller `onedir` x86 iniciou, executou a descoberta, criou o SQLite e recebeu
  fechamento normal; `errors.log` permaneceu vazio.
- SHA-256 do executável:
  `DFEC1FAE4FAEF028AEFE1570BA9847DA89E87A6D60F65CF30367067EBE6EABB1`.

## Segurança comprovada

- A senha não faz parte dos modelos persistentes e possui representação textual protegida.
- Testes inspecionam o SQLite bruto e o diagnóstico exportado para impedir vazamento da senha.
- Configurações suspeitas de conter credenciais são ignoradas pelo detector.
- A interface não executa SQL; toda validação passa pelo serviço e pelo probe somente leitura.
- Nenhuma funcionalidade de escrita na base SIAF foi habilitada.

## Critérios já atendidos

- Descoberta local de Firebird e bases sem digitar host, porta ou caminho.
- Listagem de múltiplas bases para seleção.
- Classificação obrigatória pelo esquema.
- Falhas parciais não encerram a aplicação.
- Senha não persistida.
- Ausência de varredura completa do disco.
- Exportação de diagnóstico técnico.

## Pendências para concluir a fase

1. Abrir o executável no ambiente Firebird homologado, acessar **Ambiente detectado**, clicar em
   **Validar conexão** e confirmar a conexão às bases com credenciais autorizadas.
2. Executar a ferramenta em um terminal SIAF conectado a outro computador e confirmar que o
   servidor remoto é identificado ou apresentado como candidato fundamentado.
3. Repetir o smoke final em Windows 10 e Windows 11 conforme a matriz de compatibilidade do
   release.

Até essas provas serem registradas, a Fase 4 deve permanecer marcada como **em homologação** e
a Fase 5 não deve ser iniciada.

## Estabilização durante a homologação

A revisão posterior corrigiu quatro casos não cobertos inicialmente:

- Firebird 4/ODS 13 e demais combinações fora de Firebird 2.5.7/ODS 11.2 podiam ser marcadas
  como compatíveis quando o esquema SIAF era reconhecido;
- uma conexão ativa do SIAF na porta `3055` não alimentava a lista de portas Firebird e a
  máquina permanecia em modo assistido;
- aliases de instalações nas portas `3050` e `3055` eram enviados pela mesma porta do ambiente;
- depois do primeiro `fdb.load_api`, selecionar outra DLL não tinha efeito e o aplicativo não
  informava que a biblioteca anterior continuava carregada.

O probe e o serviço agora aplicam a matriz de compatibilidade em duas camadas. A descoberta
incorpora portas observadas na faixa usual de instâncias Firebird, e o plano mantém a associação
entre configuração, alias, base e porta. A DLL efetivamente carregada é comparada com a
solicitada; uma divergência interrompe a validação com orientação para reiniciar o aplicativo.

Uma segunda revisão em 2026-07-19 corrigiu os pontos restantes:

- arquivos de configuração antigos em CP1252 e arquivos UTF-16 agora preservam caminhos e
  aliases acentuados, com falhas isoladas por arquivo;
- o mascaramento percorre também caminhos embutidos em DSNs, mensagens, comandos, valores do
  Registro, variáveis de ambiente e caminhos UNC;
- erros `-902` de rede, `CreateFile` e causas desconhecidas recebem orientações diferentes;
- portas arbitrárias são correlacionadas automaticamente quando uma referência de conexão e o
  TCP do processo SIAF fornecem uma associação inequívoca. Sem essa correlação, a porta é
  exibida como candidata assistida e não aumenta a confiança do modo terminal.

O build x86 após essa revisão manteve a descoberta local em modo servidor, identificou
Firebird `2.5.7.27050`, porta `3050`, duas bases e nenhum aviso. O executável criou o SQLite,
fechou normalmente e deixou `errors.log` vazio.
