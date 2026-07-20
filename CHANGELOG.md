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
- Fase 4 encerrada tecnicamente; o cenário de terminal remoto passa a ser homologado em campo,
  diretamente no computador do cliente, sem depender de acesso remoto prévio às bases.
- Fase 5 iniciada com inspetor do catálogo Firebird 2.5.7 para relações, campos, índices,
  chaves primárias, triggers, procedures e generators.
- Toda inspeção abre conexão própria, inicia transação somente leitura, lê o catálogo com
  `fetchmany(200)` e executa rollback antes de fechar a conexão.
- Migration 3 adiciona cache dos objetos estruturais; campos e objetos são substituídos na
  mesma transação SQLite e podem ser carregados para comparação entre bases.
- Serviço de requisitos bloqueia templates quando relações ou campos obrigatórios não estão
  presentes no cache validado.
- A página de ambiente ganhou **Inspecionar estrutura**, processa todas as bases validadas em
  um worker e apaga a senha ao final do lote.
- Build x86 da Fase 5 aprovado em abertura, criação do SQLite e fechamento normal, com 114
  testes, 85% de cobertura combinada e `errors.log` vazio.
- Fase 5 concluída após inspeção real de `SIAFLOJA.FDB` e `SIAFW.FDB`: dois snapshots completos,
  6.144 campos, 1.355 objetos, Firebird 2.5.7.27050 e ODS 11.2.
- Fase 6 iniciada com templates persistidos e parametrizados, validador SQL de instrução única,
  bloqueio de comandos destrutivos e conferência obrigatória do cache estrutural.
- Executor de consultas usa conexão própria, transação Firebird read-only, `fetchmany(200)`,
  rollback, cancelamento cooperativo e credenciais somente em memória.
- Resultados são gravados em SQLite temporário, paginados em blocos de 100 linhas e removidos ao
  substituir o resultado, fechar a aplicação ou iniciar uma nova sessão.
- A página **Consultas** agora seleciona bases validadas, monta parâmetros declarados pelo
  template, executa fora da thread do Tk e permite navegar pelos resultados sem carregar tudo
  em memória.
- Build x86 inicial da Fase 6 aprovado com 143 testes, 88% de cobertura combinada, dois
  templates persistidos, abertura/fechamento normal e logs de erro vazios.
- Fase 6 concluída após os dois templates de sistema retornarem dados no ambiente real do
  cliente, confirmando o fluxo completo de consulta read-only e parametrizada pela interface.
- Estabilização da Fase 6 compara dependências extraídas do SQL com os requisitos declarados e
  bloqueia procedures selecionáveis antes de abrir uma conexão.
- Templates SQL deixam de usar a sanitização destinada a logs, preservando campos e parâmetros
  legítimos que contenham nomes como `PASSWORD`.
- Trocas de base/template e novas execuções limpam o resultado visual anterior, evitando que uma
  falha apresente linhas pertencentes a outra consulta.
- Credenciais agora são apagadas por um `finally` que cobre inclusive falhas anteriores ao
  executor Firebird; cinco regressões elevam a suíte para 148 testes.
- Build x86 corrigido aprovado em smoke com código 0, migration 4, requisitos explícitos nos
  dois templates e logs vazios.
- Fase 7 iniciada com três templates de cadastros derivados do snapshot real da `SIAFLOJA.FDB`:
  produtos em `DSIAF006`, clientes em `DSIAF010` e fornecedores em `DSIAF009`.
- Filtro de produto por fornecedor usa a relação validada `DSIAF030(PRO_COD, FOR_COD)`, sem
  depender de campo presumido na tabela de produtos.
- Buscas aceitam código e nome; clientes e fornecedores também normalizam pontuação do CPF/CNPJ
  para a pesquisa por documento.
- A página **Consultas** ganhou painel de detalhes do registro selecionado e exportação CSV/XLSX
  habilitada somente quando existe resultado temporário válido.
- Exportações leem o cache em lotes de 500, rodam em worker cancelável, usam arquivo temporário
  e troca atômica, e removem a saída parcial em falha ou cancelamento.
- CSV usa UTF-8 com BOM; XLSX usa escrita progressiva, filtro simples e cabeçalho congelado.
  Ambos neutralizam células iniciadas por caracteres de fórmula.
- Dependência `openpyxl` fixada em 3.1.5, compatível com o runtime Python 3.11 x86 do projeto.
- Suíte ampliada para 155 testes; lint, smoke da interface e reabertura estrutural do XLSX
  aprovados.
- Build PyInstaller x86 da Fase 7 gerado em diretório isolado porque o executável anterior
  estava aberto. O smoke persistiu cinco templates, migration 4 e manteve `errors.log` vazio.
- Fase 7 concluída após homologação real das buscas, detalhes e exportações no computador do
  cliente.
- O executável aberto foi encerrado com autorização, o build x86 foi regenerado no diretório
  padrão e as pastas temporárias duplicadas foram removidas.
- Build final da Fase 7: 155 testes, cinco templates, migration 4, `errors.log` vazio e SHA-256
  `8D47AAB7180E5902386F66F899A2850CFAC18D0608F51578646969058A3252BB`.

### Corrigido após a Fase 7

- Cache temporário passa a serializar e restaurar `Decimal`, `date`, `datetime` e `time` com
  marcadores próprios, preservando tipos nativos no XLSX sem perder a paginação SQLite.
- Neutralização de fórmulas abrange tabulação, quebras de linha, caractere nulo e variantes
  Unicode de largura completa; controles inválidos para XML são substituídos no XLSX.
- Uma nova consulta ou exportação limpa o caminho anterior do rodapé; falhas e cancelamentos
  também exibem explicitamente que nenhum arquivo novo foi gerado.
- Cancelamentos anteriores à obtenção das colunas deixam de criar um resultado exportável, e
  serviço, interface e exportador rejeitam defensivamente resultados sem colunas.
- Quatro regressões e o smoke ampliado elevam a suíte para 159 testes.
- Build x86 corrigido aprovado com cinco templates, migration 4, `errors.log` vazio e SHA-256
  `D383D82B3C6796286F525387A52217FA7CF61CBC65789E4E6FD2F96C1CDE0D80`.
- Fase 8 iniciada com sete templates derivados do snapshot real: NF-e de saída
  (`DSIAF036/037`), entradas (`DSIAF011/012`) e PDV (`DSIAF400/401/402`).
- Vínculos entre cabeçalhos e detalhes seguem os índices reais por `SAI_SER + SAI_PED`,
  `ENT_NOTA + FOR_COD` e `ID + PDV_COD`.
- Consultas operacionais exigem ao menos um filtro antes de solicitar credenciais e retornam no
  máximo 500 registros; a barreira também é revalidada no serviço.
- Parâmetros de período aceitam datas ISO `AAAA-MM-DD` e são vinculados como `date`, sem
  interpolação no SQL.
- Filtros operacionais são organizados em duas colunas para manter a página utilizável em telas
  menores; indicadores de contingência, cancelamento, status e TEF são exibidos sem tradução
  presumida.
- Seis regressões elevam a suíte para 165 testes; o smoke confirma 12 templates e a disposição
  compacta dos sete filtros.
- Build PyInstaller x86 da Fase 8 aprovado com migration 4, 12 templates, sete módulos de
  consulta operacional e `errors.log` vazio. SHA-256:
  `4F5D3B51A7A424305F8F47DBA69ABDC058CDF5A502C0692DAC35790DE3E859EA`.

### Corrigido após a Fase 8

- Fase 8 concluída após a homologação das consultas reais de NF-e, entradas e PDV no computador
  do cliente.
- Templates operacionais leem uma linha de controle além do limite, armazenam somente 500 e
  sinalizam claramente quando a tela e a exportação contêm um resultado parcial.
- Períodos usam `DD/MM/AAAA`, rejeitam data inicial posterior à final e preservam datas nativas
  no XLSX com apresentação brasileira; o CSV e a interface também exibem o formato brasileiro.
- O período do template de pagamentos passou a filtrar `DSIAF402.PDV_PREST_DATA`, coerente com
  a coluna de data de pagamento apresentada ao usuário.
- Consultas de PDV ordenam pelas chaves primárias existentes e filtros por período exigem as duas
  datas, sem criar índices no banco do cliente.
- Removido o limite defensivo de 31 dias após a homologação: consultas de PDV aceitam qualquer
  intervalo fechado e continuam sinalizando quando o retorno ultrapassa 500 registros.
- Fase 9 iniciada com dez templates derivados dos snapshots reais de `SIAFLOJA.FDB` e
  `SIAFW.FDB`, cobrindo as onze relações financeiras e de permissões previstas no roadmap.
- Contas a receber/pagar, cabeçalhos e lançamentos do caixa, transferências e tipos de
  venda/pagamento usam somente campos e vínculos confirmados no cache estrutural.
- Diagnósticos de acesso relacionam usuário, grupo e programa e exibem `PROG_ACE`, `PROG_INC`,
  `PROG_ALT`, `PROG_EXC` e `PROG_IMP` sem atribuir significado aos valores armazenados.
- O campo `DSIAF050.USU_SENHA` foi excluído dos SQLs, requisitos, resultados e exportações da
  Fase 9; nenhum template tenta revelar ou manipular credenciais do SIAF.
- Seis regressões elevam a suíte para 178 testes; Ruff, smoke das onze páginas e build
  PyInstaller Python 3.11.9 x86 foram aprovados.
- O executável da Fase 9 aplicou migration 5, persistiu 22 templates — dez da nova fase —,
  confirmou zero referências a `USU_SENHA`, manteve `errors.log` vazio e fechou sem instâncias
  duplicadas. SHA-256:
  `E8AA92120C3D3314CC881330D5EF841A5B96B68C11643F0E377C1040825830AF`.
- Migration 5 persiste o limite de resultado por template para que o serviço detecte truncamento
  sem depender do texto exibido na interface.

### Corrigido durante a homologação da Fase 9

- O diagnóstico de permissões só associa `DSIAF050` quando há filtro por código ou nome de
  usuário, evitando repetir cada permissão por todos os usuários do mesmo grupo nas pesquisas
  por grupo, programa, módulo ou índice.
- `DSIAF016.PRA_COD` passa a ser exibido com o próprio nome, sem o rótulo não comprovado
  `TIPO_VENDA`.
- Migration 6 adiciona `execution_history.truncated`; o histórico agora distingue consultas
  completas de resultados limitados aos primeiros 500 registros.
- Interface e serviço removem espaços nas extremidades dos filtros, e valores formados apenas
  por espaços são recusados como filtros vazios antes de abrir a conexão.
- Quatro novas regressões elevam a suíte para 182 testes; Ruff e o smoke das onze páginas foram
  aprovados.
- O build x86 corrigido abriu em perfil isolado, aplicou as seis migrations, persistiu 22
  templates — dez da Fase 9 —, confirmou a coluna de truncamento, zero referências a
  `USU_SENHA`, `errors.log` vazio e nenhuma instância restante. SHA-256:
  `7A17C83F3B3A24D0CA029347A21ACB794BB2F00BC0BB4584FC01BBB610483B6D`.
- Após a homologação da pesquisa por grupo, o diagnóstico de permissões deixou de usar o teto
  fixo de 500 linhas. A consulta continua exigindo filtro e processa o conjunto completo por
  lotes, com paginação no cache temporário e exportação progressiva.
- O novo build x86 confirmou `result_limit` nulo e ausência de `FIRST 501` somente nesse
  diagnóstico, manteve limite nos outros nove templates da Fase 9, migration 6 e `errors.log`
  vazio. SHA-256: `8048CA86BDC4D1D0AD836D6147D8B852AD93DE1AA11A01ADDB893A25F1A197B9`.
- Revisão final aprovada com 172 testes, Ruff, smoke das onze páginas e build PyInstaller
  Python 3.11.9 x86; o executável aplicou migration 5, carregou 12 templates, manteve
  `errors.log` vazio e foi fechado sem instâncias duplicadas. SHA-256:
  `597B441F0A2F9926D49C0D91DDD79D2A9392F43179A1FCCF4C2A744DC9C10965`.

### Limitações conhecidas

- Terminal remoto e matriz ampliada Windows 10/11 permanecem como homologação de campo no
  computador do cliente.
- O cancelamento é cooperativo entre lotes e não interrompe o tempo de preparação do primeiro
  lote dentro do servidor Firebird.

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

### Corrigido durante a homologação da Fase 5

- Migration 4 adiciona estado explícito do snapshot estrutural e metadados de precisão,
  comprimento em caracteres, charset e collation sem descartar o cache existente durante o
  upgrade.
- Uma nova validação Firebird invalida o snapshot anterior; requisitos e comparações agora
  falham fechados quando o cache está ausente, vazio, incompleto ou pertence a outra validação.
- `NUMERIC` e `DECIMAL` passam a ser reconhecidos sobre os códigos de armazenamento 7, 8 e 16,
  incluindo precisão e escala na comparação.
- Índices `COMPUTED BY` são preservados por `LEFT JOIN` e comparados pela assinatura da
  expressão, sem armazenar o código-fonte em texto puro.
- Views, triggers, procedures e parâmetros passam a ter assinaturas estruturais; alterações no
  PSQL ou nos tipos de parâmetros deixam de produzir equivalência falsa.
- Iniciar uma nova validação limpa o resumo bem-sucedido anterior, impedindo que uma falha
  inesperada reabilite a inspeção para outro endpoint.
- O upgrade foi exercitado sobre uma cópia do SQLite gerado pela inspeção real: 6.144 campos e
  1.352 objetos foram preservados, a integridade permaneceu válida e nenhum snapshot antigo
  foi marcado como completo.
- Oito regressões ampliam a suíte para 122 testes automatizados.
