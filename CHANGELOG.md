# Changelog

Todas as alterações relevantes deste projeto serão registradas neste arquivo.

## [0.1.0-dev] - 2026-07-18

### Adicionado

- Fundação do repositório para a Fase 0.
- Modelos de descoberta com evidências, confiança e falhas não fatais.
- Detectores iniciais de processos, serviços, Registro, rede, DLLs e bases SIAF.
- Orquestrador e classificador inicial de servidor local, terminal ou modo assistido.
- Janela mínima com descoberta em worker.
- Verificação obrigatória de runtime x86 para o build.
- Testes unitários iniciais e matriz de compatibilidade.
- Dependência `psutil` fixada em 5.9.8, versão com wheel Win32 compatível com Python 3.11.
- Ambiente Python 3.11.9 x86 criado e dependências Win32 homologadas.
- Primeiro build PyInstaller `onedir` x86 gerado e aprovado em smoke test local.
- Bases `SIAFW.FDB` e `SIAFLOJA.FDB` locais encontradas pela descoberta progressiva.
- Script interativo seguro para validar as bases descobertas em modo somente leitura.
- Atalho `Validar_Bases.cmd` mantém o resultado visível e salva relatório sem credenciais.
- Fase 0 concluída após conexão bem-sucedida às duas bases e execução do build no Windows
  Sandbox sem Python instalado.
- Fase 1 concluída com estrutura do repositório, dependências, documentação e diretórios de
  dados por usuário homologados.
- Testes de paths para override, `%LOCALAPPDATA%`, fallback do perfil e criação de diretórios.
- Teste de rotação real dos logs com criação do arquivo de backup.
- Sanitização ampliada para credenciais simples, entre aspas e em estruturas semelhantes a
  dicionários.
- Configuração de logging idempotente, sem duplicar os handlers de aplicação e erros.
- Build x86 regenerado e aprovado em smoke test após as mudanças da fundação.
- Fase 2 concluída com interface desktop estruturada em menu lateral, topo, conteúdo e rodapé
  persistentes.
- Onze páginas previstas no roadmap, mantendo recursos futuros apenas como placeholders.
- Temas claro e escuro com preferência persistida no perfil do usuário.
- Tamanho, posição, estado maximizado e última página salvos em `window-state.json`.
- Diálogo modal reutilizável e smoke test isolado da interface.
- Descoberta migrada para worker daemon, permitindo fechamento imediato durante a análise.
- Fase 3 concluída com banco SQLite interno criado automaticamente no perfil do usuário.
- Migration versionada e idempotente com ambientes, bases, perfis manuais, histórico,
  templates, auditoria, cache de estrutura e base de conhecimento.
- Repositório local preserva a validação dos candidatos quando uma nova descoberta atualiza o
  mesmo ambiente.
- Serviço de descoberta persiste o resultado fora da interface e mantém falhas do histórico
  local como avisos não fatais.
- Perfis manuais não possuem campo de senha e mensagens de erro do histórico são sanitizadas.
- Inicializações concorrentes do SQLite são serializadas para permitir múltiplas instâncias.
- Executável x86 reconstruído com suporte ao SQLite e aprovado em criação do banco, descoberta
  e fechamento normal.
- Fase 4 iniciada com plano automático de conexão para servidor local, terminal remoto e
  descoberta assistida, sempre baseado nas evidências encontradas no ambiente.
- Leitura limitada de configurações próximas à instalação do SIAF para identificar aliases,
  servidor, porta e caminhos, sem varredura recursiva completa do disco.
- Validação Firebird somente leitura executada em worker próprio, com pré-teste de porta,
  classificação obrigatória pelo catálogo e coleta da versão do servidor e ODS.
- Credenciais solicitadas em diálogo próprio e apagadas da sessão após cada tentativa, sem
  persistência em SQLite, logs, diagnóstico ou perfil manual.
- Fallback avançado para informar conexão manual e salvar somente o perfil técnico quando a
  validação for bem-sucedida.
- Status de conexão e assinatura do esquema persistidos no histórico local, preservando a
  separação entre endpoints.
- Exportação atômica e sem colisões do diagnóstico técnico, com caminhos mascarados e nenhuma
  credencial.
- Build x86 da Fase 4 aprovado em inicialização, descoberta e fechamento normal, com 94 testes
  e 85% de cobertura combinada.
- Uma reanálise com falha invalida também o plano e os botões de conexão anteriores, impedindo
  tentativa acidental contra um endpoint desatualizado.

### Limitações conhecidas

- Cenários de terminal remoto e matriz ampliada Windows 10/11 ainda não homologados.
- A Fase 4 permanece em homologação até uma conexão real ser validada pela nova tela com
  credenciais autorizadas e o fluxo de terminal remoto ser exercitado.

### Corrigido após a Fase 0

- Bases com assinatura fraca ou ambígua não são mais aceitas como SIAF.
- Classificação de terminal exige conexão remota na porta Firebird detectada.
- Classificação de servidor local exige Firebird e base local como evidências combinadas.
- Todos os detectores centrais convertem falhas inesperadas em avisos não fatais.
- Configurações de múltiplas instalações Firebird preservam portas e aliases por instância.
- Atalhos do SIAF passam a fornecer destino e diretório de trabalho para a descoberta.
- Serviços removidos durante a enumeração não geram aviso falso.
- Build pode ser iniciado de qualquer diretório e inclui lint antes dos testes.
- Cobertura ampliada de 38% para 73%, com 42 testes automatizados.
- Fundação da Fase 1 encerrada com 50 testes automatizados e cobertura total mantida em 73%.

### Corrigido após a Fase 1

- Sanitização passa a abranger o texto final formatado, incluindo traceback e stack trace.
- Valores sensíveis com aspas escapadas são removidos integralmente.
- Reconfigurar o diretório de logs fecha os handlers anteriores e passa a escrever somente no
  novo destino.
- `%LOCALAPPDATA%` vazio ou relativo usa o diretório pessoal como fallback absoluto.
- Suíte ampliada para 55 testes e cobertura total elevada para 74%.
- Executável x86 reconstruído e aprovado em smoke test com duas bases e log de erros vazio.

### Corrigido após a Fase 2

- Menu lateral passa a ter rolagem e mantém a página selecionada visível no tamanho mínimo e
  em DPI alto.
- Cabeçalho invalida resultados anteriores ao reanalisar ou quando a nova análise falha.
- Persistência utiliza os limites do desktop virtual do Windows e aceita monitores à direita,
  à esquerda ou acima do principal.
- Formatação de geometria suporta coordenadas negativas na janela e nos diálogos.
- Preferências usam temporários exclusivos, serialização local e retentativas para fechamentos
  concorrentes entre instâncias.
- Suíte ampliada para 70 testes e cobertura combinada elevada para 85%.
- Executável x86 reconstruído e aprovado em abertura, descoberta e fechamento normal.

### Corrigido após a Fase 3

- Ambientes da mesma máquina e modo passam a ser separados pelo servidor remoto ou pela
  instalação Firebird local, impedindo mistura de bases entre endpoints.
- Sanitização de credenciais centralizada para textos e estruturas JSON antes de qualquer
  gravação pelos repositórios locais.
- Migration 2 corrige seleções inválidas existentes e cria barreiras SQLite para estados de
  compatibilidade desconhecidos ou seleção de bases incompatíveis.
- Recuperação de descoberta considera reutilizáveis somente bases compatíveis com assinatura
  validada.
- Falhas ao abrir o SQLite no bootstrap são registradas e exibem orientação ao usuário sem
  apagar ou substituir o arquivo existente.
- Suíte ampliada para 85 testes, mantendo cobertura combinada em 87%.

### Corrigido durante a homologação da Fase 4

- Validações com versão diferente de Firebird 2.5.7 ou ODS diferente de 11.2 são bloqueadas e
  persistidas como incompatíveis, mesmo se um probe injetado informar sucesso indevido.
- Conexões estabelecidas pelo processo SIAF nas portas `3050–3099` passam a alimentar a
  descoberta, permitindo reconhecer instâncias Firebird próximas à porta padrão.
- Cada alias e base associada a uma configuração Firebird preserva a porta da própria
  instância no plano de conexão e no SQLite.
- A ferramenta compara a DLL solicitada com a biblioteca realmente mantida pelo driver e pede
  reinicialização quando uma troca na mesma sessão seria ignorada pelo `fdb`.
- Seis regressões automatizadas cobrem os quatro cenários; a suíte foi ampliada para 100 testes
  com 85% de cobertura combinada.
- Executável x86 reconstruído e aprovado em inicialização, descoberta e fechamento normal,
  mantendo `errors.log` vazio.
- Configurações do SIAF e Firebird passam a reconhecer UTF-8 com ou sem BOM, UTF-16 e CP1252,
  preservando aliases e caminhos com acentos.
- O diagnóstico mascara caminhos mesmo quando aparecem dentro de DSNs, mensagens, comandos,
  valores do Registro, variáveis de ambiente ou compartilhamentos UNC.
- `SQLCODE -902` deixa de ser tratado genericamente como caminho inválido: indicadores de rede
  têm prioridade, `CreateFile` continua associado ao caminho e casos ambíguos usam orientação
  neutra.
- Portas TCP arbitrárias observadas no processo SIAF são correlacionadas com referências de
  conexão quando possível; as demais aparecem na interface como candidatas assistidas sem
  serem promovidas indevidamente a Firebird confirmado.
- Sete regressões adicionais ampliam a suíte para 107 testes, mantendo 85% de cobertura
  combinada.
