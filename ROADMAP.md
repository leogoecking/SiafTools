# ROADMAP — SIAF Support Toolbox

> Documento mestre para desenvolvimento com Codex de uma aplicação desktop Windows (`.exe`) destinada ao suporte técnico do ERP SIAF, com descoberta automática do ambiente Firebird e acesso controlado às bases.
>
> **Revisão 1.1:** o aplicativo será executado no próprio computador do cliente. O fluxo principal não solicita host, porta ou caminho; esses dados são detectados automaticamente.

## Metadados do projeto

| Item | Definição |
|---|---|
| Nome provisório | **SIAF Support Toolbox** |
| Plataforma | Windows 10 e Windows 11 |
| Formato final | Aplicação desktop portátil com interface gráfica e executável `.exe`; sem navegador e sem servidor web |
| Local de execução | **No próprio computador do cliente**, durante o atendimento |
| Modelo operacional | Descoberta automática do ambiente SIAF, Firebird, executáveis, serviços e bases |
| Banco do SIAF | **Firebird 2.5.7 — 32 bits** |
| Bases principais | `SIAFLOJA.FDB` e `SIAFW.FDB` |
| Porta Firebird | Detectada automaticamente; padrão provável TCP `3050`, sem exigir digitação no fluxo normal |
| Linguagem | Python 3.11, com build x86/32 bits no MVP |
| Driver Python | `fdb` |
| Interface recomendada | `tkinter` + `ttk`, com tema opcional `ttkbootstrap` |
| Banco interno | SQLite |
| Empacotamento | PyInstaller |
| Base de conhecimento usada | SIAF consolidada v1.0 |
| Versão deste documento | **1.1 — Execução local e autodetecção** |
| Data deste documento | 2026-07-18 |

> **Premissa revisada:** o atendente não deverá cadastrar host, porta e caminho da base para o uso comum. Ao abrir o `.exe`, a ferramenta deverá inspecionar o computador, identificar como o SIAF está instalado/conectado e apresentar automaticamente as bases disponíveis. A configuração manual será apenas um recurso de contingência.

---

---

## 1. Objetivo

Criar uma ferramenta gráfica portátil para apoiar atendimentos do SIAF diretamente no computador do cliente. Ao ser aberta, a ferramenta deverá descobrir automaticamente o ambiente local, identificar o Firebird utilizado pelo SIAF, localizar as bases disponíveis e estabelecer uma conexão segura em modo somente leitura.

A ferramenta deve reduzir o uso de SQL manual, padronizar procedimentos, evitar comandos perigosos, registrar auditoria e apresentar informações técnicas de forma simples para o atendente.

### Fluxo esperado pelo atendente

```text
Abrir SIAFSupportToolbox.exe
        ↓
Ferramenta analisa o computador
        ↓
Detecta SIAF e Firebird
        ↓
Localiza SIAFW.FDB e uma ou mais SIAFLOJA.FDB
        ↓
Valida estrutura e conexão
        ↓
Exibe as lojas/bases encontradas
        ↓
Atendente seleciona a loja, quando houver mais de uma
        ↓
Consultas, diagnósticos e relatórios ficam disponíveis
```

### Objetivos prioritários

- Executar no próprio computador do cliente sem exigir instalação de Python.
- Detectar automaticamente se a máquina é o servidor do Firebird ou apenas um terminal do SIAF.
- Detectar serviços, processos, instalação e versão do Firebird.
- Identificar `fbclient.dll` ou `gds32.dll` compatível com Firebird 2.5.7 x86.
- Descobrir automaticamente `SIAFW.FDB` e todas as bases `SIAFLOJA.FDB`.
- Identificar o servidor remoto utilizado pelo SIAF quando a ferramenta for executada em um terminal.
- Conectar com segurança às bases encontradas.
- Consultar produtos, clientes, fornecedores, notas, entradas, PDV, financeiro, usuários e permissões.
- Gerar diagnósticos automáticos e relatórios exportáveis.
- Comparar duas lojas sem alterar dados.
- Processar bases grandes em lotes, evitando erros de memória.
- Disponibilizar operações controladas somente após validação, backup, prévia e confirmação.
- Manter uma arquitetura preparada para ampliar a biblioteca de consultas e soluções do SIAF.

### Fora do escopo inicial

- Aplicação web, API HTTP, painel aberto no navegador ou servidor local.
- Exigir que o atendente conheça ou digite host, porta e caminho da base no fluxo normal.
- Escanear todo o disco de forma indiscriminada e demorada ao abrir o programa.
- Tentar descobrir, quebrar ou extrair senhas armazenadas pelo SIAF.
- Incorporar credenciais administrativas em texto puro dentro do executável.
- Editor SQL destrutivo livre.
- Alterações fiscais automáticas sem validação humana.
- Integração direta com Bitrix24 na primeira versão.
- Substituição do próprio SIAF.
- Restauração automática sobre base produtiva.
- Atualização automática de estoque sem considerar regras de movimentação.

---

## 2. Arquitetura operacional e Firebird 2.5.7 x86

O ambiente informado utiliza **Firebird 2.5.7 de 32 bits**, e o executável será utilizado diretamente no computador do cliente. A arquitetura deve ser projetada para reconhecer o ambiente existente, e não para exigir que o cliente forneça parâmetros técnicos.

### Estratégia de compatibilidade do MVP

- Construir e homologar o executável com **Python 3.11 x86/32 bits**.
- Carregar uma biblioteca cliente Firebird x86 compatível, preferencialmente descoberta no ambiente do cliente.
- Manter uma `fbclient.dll` x86 homologada junto ao aplicativo como fallback, desde que a distribuição interna esteja autorizada.
- Também reconhecer `gds32.dll`, comum em aplicações antigas compatíveis com InterBase/Firebird.
- Validar em tempo de execução a arquitetura do processo e da DLL antes de conectar.
- Nunca tentar carregar uma DLL 64 bits em processo 32 bits.
- Detectar a versão pelo executável do servidor, propriedades do arquivo, serviço ou consulta ao servidor após a conexão.
- Usar o serviço Firebird existente para abrir as bases; não manipular o arquivo `.FDB` como arquivo comum.
- Trabalhar inicialmente com Firebird 2.5.7/ODS compatível, bloqueando operações se a versão for incompatível.

### Modos operacionais detectados

#### Modo A — Servidor local

A ferramenta está sendo executada no computador que possui o serviço Firebird e os arquivos `.FDB`.

Fluxo:

```text
Detectar serviço/processo Firebird
→ descobrir diretório da instalação
→ localizar bases SIAF
→ montar conexão local
→ validar tabelas
```

Nesse cenário, o host deverá ser definido internamente como `localhost` ou por conexão local equivalente. O atendente não digita host nem porta.

#### Modo B — Terminal do SIAF

A ferramenta está sendo executada em um computador que utiliza o SIAF, mas o Firebird está em outro computador.

A ferramenta deverá tentar identificar o servidor por:

- arquivos de configuração encontrados na instalação do SIAF;
- atalhos e diretórios de trabalho do SIAF;
- conexões TCP ativas do processo `SIAFW.EXE`;
- conexões estabelecidas para a porta do Firebird;
- nomes de servidor, aliases ou caminhos encontrados em configurações legíveis;
- informações já detectadas em execuções anteriores naquele computador.

Nesse cenário, o host poderá ser remoto, mas continuará sendo descoberto automaticamente.

#### Modo C — Descoberta assistida

Usado somente quando:

- o SIAF não estiver instalado no caminho esperado;
- existirem múltiplas instalações;
- o processo não estiver aberto;
- houver mais de um servidor possível;
- os arquivos de configuração não forem legíveis;
- várias bases tiverem o mesmo nome.

A interface deverá mostrar os candidatos encontrados e pedir apenas que o atendente selecione a opção correta. A digitação manual será o último recurso.

### Princípio de autenticação

Descoberta automática de ambiente não significa extrair senha do SIAF.

No MVP:

- a ferramenta descobre servidor e bases automaticamente;
- a credencial Firebird é fornecida pelo suporte no momento da conexão, quando necessária;
- a senha permanece apenas em memória durante a sessão;
- nenhuma senha é escrita em SQLite, log, relatório ou arquivo temporário;
- uma fase futura poderá usar Windows Credential Manager/DPAPI para credenciais autorizadas.

### Provas obrigatórias na Fase 0

- Confirmar processo x86.
- Detectar serviços Firebird/InterBase sem depender de um nome único.
- Detectar `fbserver.exe`, `fbguard.exe` ou equivalentes quando presentes.
- Ler chaves de registro de 32 e 64 bits relevantes à instalação.
- Localizar `fbclient.dll`/`gds32.dll` e validar arquitetura.
- Detectar uma instalação local do SIAF pelo processo, atalho ou diretório.
- Encontrar candidatos a `SIAFW.FDB` e `SIAFLOJA.FDB` sem varredura completa do disco.
- Identificar servidor remoto a partir de uma conexão ativa do SIAF, quando aplicável.
- Conectar a uma cópia de teste e executar `SELECT` em `RDB$DATABASE`.
- Classificar corretamente a base pelo esquema, não apenas pelo nome do arquivo.
- Gerar um build PyInstaller x86 e testar em máquina sem Python.

---

## 3. Visão funcional do SIAF incorporada ao projeto

SIAF é o sistema/ERP comercial, fiscal e operacional usado no suporte da Adsoft, com foco em rotinas de varejo e empresas como supermercados, autopeças, restaurantes e operações similares.

### Módulos principais conhecidos

- Financeiro
- Estoque
- Vendas / PDV
- Fiscal / NF-e / NFC-e / SPED
- Relatórios / Dashboards
- Cadastros
- Configurações / Permissões / Impressão

### Bases principais

| Base | Responsabilidade |
|---|---|
| `SIAFW.FDB` | Base relacionada a configurações gerais, usuários, permissões, lojas, terminais, TEF, parâmetros e estruturas de controle. |
| `SIAFLOJA.FDB` | Base operacional da loja: clientes, produtos, vendas, notas fiscais, PDV, entradas, financeiro, estoque e fiscal. |

### Princípios de suporte que a ferramenta deve aplicar

- Entender fluxo da tela antes de mexer no banco
- Validar regras de negócio com fiscal/contabilidade quando envolver CFOP, CST/CSOSN, NCM, impostos ou documentos fiscais
- Usar consultas Firebird para diagnóstico e correções apenas com backup e SELECT prévio
- Registrar problema, causa, solução e cuidados em formato reutilizável para a base JSON

---

## 4. Stack oficial do MVP

| Camada | Tecnologia | Uso |
|---|---|---|
| Runtime | Python 3.11 x86 | Compatibilidade com o ambiente Firebird 2.5.7 x86 |
| Interface | tkinter + ttk | Aplicação desktop nativa |
| Tema opcional | ttkbootstrap | Aparência moderna mantendo Tk |
| Firebird | fdb | Conexão e transações Firebird 2.5 |
| Cliente nativo | fbclient.dll/gds32.dll x86 | Descoberta e fallback para comunicação Firebird |
| Configuração local | sqlite3 | Ambientes detectados, histórico, templates e auditoria |
| Excel | openpyxl | Exportação XLSX progressiva |
| CSV/JSON | Biblioteca padrão | Exportações leves e logs técnicos |
| Senhas | Solicitação por sessão no MVP | Evitar texto puro |
| Testes | pytest | Unidade, integração e regressão |
| Empacotamento | PyInstaller | Build `.exe` sem console |
| Qualidade | ruff + mypy opcional | Padronização e tipagem |

### Dependências iniciais sugeridas

```text
fdb
psutil
openpyxl
ttkbootstrap
pytest
pytest-cov
ruff
pyinstaller
```

`tkinter`, `sqlite3`, `csv`, `json`, `logging`, `threading`, `queue`, `hashlib`, `pathlib`, `subprocess` e `winreg` serão utilizados da biblioteca padrão.

---

## 5. Arquitetura do projeto

A interface não poderá executar SQL diretamente. O fluxo obrigatório será:

```text
Tela / Widget
    ↓
Controller / ViewModel
    ↓
Service
    ↓
Repository
    ↓
Firebird Query Executor
    ↓
SIAFLOJA.FDB / SIAFW.FDB
```

### Estrutura sugerida

```text
siaf-support-toolbox/
├── src/
│   ├── main.py
│   ├── app.py
│   ├── core/
│   │   ├── config.py
│   │   ├── constants.py
│   │   ├── exceptions.py
│   │   ├── logging_config.py
│   │   ├── paths.py
│   │   ├── security.py
│   │   └── version.py
│   ├── discovery/
│   │   ├── discovery_orchestrator.py
│   │   ├── windows_service_detector.py
│   │   ├── registry_detector.py
│   │   ├── process_detector.py
│   │   ├── network_detector.py
│   │   ├── siaf_install_detector.py
│   │   ├── firebird_client_detector.py
│   │   ├── database_locator.py
│   │   ├── candidate_ranker.py
│   │   └── environment_validator.py
│   ├── database/
│   │   ├── firebird_client.py
│   │   ├── firebird_connection.py
│   │   ├── firebird_metadata.py
│   │   ├── firebird_query_executor.py
│   │   ├── transaction_manager.py
│   │   ├── sqlite_connection.py
│   │   └── migrations.py
│   ├── repositories/
│   │   ├── products_repository.py
│   │   ├── customers_repository.py
│   │   ├── suppliers_repository.py
│   │   ├── entries_repository.py
│   │   ├── invoices_repository.py
│   │   ├── pdv_repository.py
│   │   ├── finance_repository.py
│   │   ├── permissions_repository.py
│   │   ├── services_repository.py
│   │   └── diagnostics_repository.py
│   ├── services/
│   │   ├── environment_discovery_service.py
│   │   ├── connection_service.py
│   │   ├── schema_service.py
│   │   ├── consultation_service.py
│   │   ├── diagnostics_service.py
│   │   ├── report_service.py
│   │   ├── export_service.py
│   │   ├── compare_service.py
│   │   ├── backup_service.py
│   │   ├── operation_service.py
│   │   └── audit_service.py
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── controllers/
│   │   ├── pages/
│   │   ├── dialogs/
│   │   ├── widgets/
│   │   └── themes/
│   ├── workers/
│   │   ├── base_worker.py
│   │   ├── query_worker.py
│   │   ├── export_worker.py
│   │   ├── compare_worker.py
│   │   └── operation_worker.py
│   └── resources/
│       ├── icons/
│       ├── sql/
│       ├── templates/
│       └── firebird/x86/fbclient.dll
├── data/
├── exports/
├── logs/
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── scripts/
├── docs/
├── requirements.txt
├── requirements-dev.txt
├── pyproject.toml
├── AGENTS.md
├── CHANGELOG.md
├── README.md
├── ROADMAP.md
└── build.spec
```

---

## 6. Interface final

### Menu lateral

```text
Painel
Ambiente detectado
Consultas
Diagnósticos
Relatórios
Comparar lojas
Operações controladas
Backup
Histórico e auditoria
Base de conhecimento
Configurações
```

### Tela inicial de descoberta

Ao abrir, a aplicação deverá mostrar uma etapa curta de análise:

```text
Analisando ambiente...
✓ Aplicação x86
✓ Firebird 2.5.7 detectado
✓ SIAF localizado
✓ 1 base SIAFW encontrada
✓ 3 lojas encontradas
```

Quando houver mais de uma loja, exibir cartões ou tabela:

| Loja/base | Caminho/servidor | Tamanho | Situação |
|---|---|---:|---|
| Loja 1 | Detectado automaticamente | 1,8 GB | Compatível |
| Loja 2 | Detectado automaticamente | 940 MB | Compatível |
| Loja 3 | Detectado automaticamente | 2,3 GB | Compatível |

### Barra superior persistente

- Nome do computador.
- Modo detectado: Servidor local, Terminal ou Assistido.
- Firebird detectado e versão.
- Serviço/processo encontrado.
- Loja/base selecionada.
- Tipo da base: SIAFLOJA ou SIAFW.
- Status da conexão.
- Modo atual: Somente leitura ou Operação controlada.
- Arquitetura da aplicação e DLL Firebird.
- Versão do programa.

Host, porta e caminho técnico podem aparecer em uma área de detalhes, mas não devem ser campos obrigatórios para o atendente.

### Barra inferior persistente

- Mensagem da operação atual.
- Quantidade de registros processados.
- Tempo decorrido.
- Barra de progresso.
- Botão cancelar.
- Caminho do arquivo exportado.
- Indicador de erro ou aviso.

### Ações da tela “Ambiente detectado”

- Reanalisar computador.
- Abrir detalhes técnicos.
- Selecionar outra loja.
- Validar novamente a base.
- Selecionar candidato manualmente, apenas em contingência.
- Exportar diagnóstico do ambiente sem credenciais.
- Copiar detalhes técnicos para o ticket.

### Regra de responsividade

Nenhuma descoberta, consulta, comparação, exportação ou operação poderá executar na thread principal da interface. Utilizar `threading`/`ThreadPoolExecutor`, `queue.Queue` e atualização segura do Tk por `after()`.

Cada worker deverá abrir sua própria conexão Firebird. Conexões não devem ser compartilhadas entre threads.

---

## 7. Banco SQLite interno

### Tabelas mínimas

#### `detected_environments`

```text
id, machine_name, detection_mode, siaf_executable_path,
firebird_service_name, firebird_server_path, firebird_version,
firebird_architecture, client_library_path, client_library_name,
detected_host, detected_port, confidence_level, last_scan,
last_success, active
```

#### `discovered_databases`

```text
id, environment_id, database_type, database_path, database_host,
database_port, file_size, modified_at, schema_signature,
compatibility_status, confidence_score, selected, first_seen,
last_seen
```

#### `connection_profiles`

Mantida apenas como contingência para ambientes que não puderem ser descobertos automaticamente.

```text
id, name, environment_id, host, port, database_path, database_type,
username, charset, fbclient_path, favorite, last_connection,
last_success, active, created_at, updated_at
```

#### `query_templates`

```text
id, name, module, description, sql_template, required_tables,
required_fields, parameters_schema, read_only, risk_level,
enabled, version, source_reference
```

#### `execution_history`

```text
id, environment_id, database_id, action_name, action_type,
started_at, finished_at, success, records_processed, duration_ms,
error_code, error_message, output_file, app_version, windows_user
```

#### `operation_audit`

```text
id, environment_id, database_id, operation_name, database_path_hash,
preview_hash, execution_sql_hash, affected_records, confirmation_text,
backup_confirmed, backup_path, started_at, finished_at, success,
rollback_executed, validation_result, windows_user
```

#### `schema_cache`

```text
id, database_id, relation_name, field_name, field_type, field_length,
field_scale, nullable, primary_key, index_names, checked_at
```

#### `knowledge_entries`

```text
id, category, module, problem, symptoms_json, causes_json,
solution_json, system_path, validations_json, observations,
keywords_json, confidence_level, source, version, active
```

### Segurança de credenciais

- No MVP, não salvar senha: solicitar a cada sessão somente quando a autenticação exigir.
- A descoberta não poderá tentar extrair ou descriptografar senha do SIAF.
- Nunca gravar senha, certificado, CSC, token ou chave em logs.
- Futuramente, utilizar Windows Credential Manager/DPAPI após uma fase específica de segurança.
- O caminho completo das bases poderá ser mascarado em relatórios enviados ao cliente.
- Não usar fingerprint invasivo; guardar apenas o necessário para reconhecer o ambiente técnico.

---

## 8. Descoberta automática e conexão Firebird

Esta é uma das partes centrais do projeto. O fluxo normal deve funcionar sem cadastro manual de host, porta e caminho.

### 8.1 Orquestrador de descoberta

Criar um `DiscoveryOrchestrator` que execute as etapas abaixo e produza uma lista ranqueada de ambientes e bases candidatas.

```text
1. Verificar arquitetura e privilégios
2. Detectar processos do SIAF
3. Detectar instalação do SIAF
4. Detectar serviços/processos Firebird ou InterBase
5. Detectar cliente Firebird x86
6. Descobrir se a máquina é servidor ou terminal
7. Localizar configurações e bases candidatas
8. Detectar host/porta automaticamente
9. Validar conexão e esquema
10. Classificar SIAFW e SIAFLOJA
11. Apresentar lojas encontradas
```

Cada detector deve funcionar isoladamente e retornar evidências, confiança e erros não fatais. Uma falha em um detector não deve encerrar toda a análise.

### 8.2 Detecção do SIAF

Buscar, nesta ordem:

1. Processo `SIAFW.EXE` em execução.
2. Caminho do executável do processo.
3. Atalhos no Menu Iniciar, área de trabalho pública e área de trabalho do usuário.
4. Diretório de trabalho do atalho.
5. Registros de desinstalação ou configuração, quando existirem.
6. Pastas configuráveis conhecidas pelo suporte.
7. Busca progressiva e limitada por `SIAFW.EXE`.

A busca não deve iniciar com uma varredura recursiva completa de todas as unidades.

### 8.3 Detecção do Firebird local

Inspecionar:

- Serviços do Windows cujo executável ou descrição indiquem Firebird/InterBase.
- `ImagePath` dos serviços.
- Processos como `fbserver.exe`, `fbguard.exe`, `fb_inet_server.exe` ou equivalentes.
- Registro do Windows em áreas nativas e `WOW6432Node`.
- Diretórios próximos ao executável do SIAF.
- `fbclient.dll` e `gds32.dll` disponíveis.
- Propriedades de versão dos binários encontrados.

Não depender de um único nome de serviço, pois ele pode variar por instalação.

### 8.4 Determinação do modo da máquina

#### Servidor local

Considerar provável servidor local quando houver combinação de evidências:

- serviço Firebird ativo;
- executável servidor local;
- arquivos `.FDB` em disco local;
- conexão local bem-sucedida;
- esquema SIAF validado.

#### Terminal

Considerar provável terminal quando:

- `SIAFW.EXE` existe ou está em execução;
- não há servidor Firebird local correspondente;
- o processo mantém conexão com outro IP;
- configuração do SIAF aponta para servidor remoto;
- bases não estão fisicamente no computador.

### 8.5 Descoberta do servidor remoto no terminal

Tentar, nesta ordem:

1. Ler configurações textuais do SIAF dentro dos diretórios detectados.
2. Procurar referências a `SIAFW.FDB`, `SIAFLOJA.FDB`, aliases, nomes de servidor e DSNs.
3. Inspecionar conexões TCP estabelecidas pertencentes ao processo do SIAF.
4. Correlacionar IP remoto e porta com processos/conexões do aplicativo.
5. Usar histórico técnico já validado naquela máquina.
6. Solicitar abertura do SIAF e repetir análise, quando nenhuma conexão estiver disponível.
7. Exibir candidatos para seleção assistida.

Não capturar tráfego, não instalar driver de rede e não executar técnicas invasivas.

### 8.6 Localização das bases

Fontes permitidas:

- caminhos explícitos em configuração;
- diretório do SIAF e subdiretórios próximos;
- caminhos do serviço Firebird;
- aliases do Firebird, quando encontrados;
- caminhos conhecidos cadastrados internamente pelo suporte;
- busca limitada por nomes exatos `SIAFW.FDB` e `SIAFLOJA.FDB`;
- histórico local da própria ferramenta.

A busca deve ser progressiva:

```text
Nível 1: diretórios já conhecidos
Nível 2: pasta do SIAF e Firebird
Nível 3: raízes configuradas pelo suporte
Nível 4: seleção manual de pasta
```

Evitar varredura completa de `C:\` como comportamento padrão.

### 8.7 Ranqueamento dos candidatos

Cada candidato recebe pontuação por evidências:

- nome de arquivo esperado;
- proximidade da instalação do SIAF;
- referência em configuração;
- referência em conexão ativa;
- presença de tabelas esperadas;
- assinatura de esquema;
- compatibilidade ODS;
- conexão bem-sucedida;
- data e tamanho plausíveis;
- ocorrência em execução anterior validada.

O nome do arquivo sozinho nunca é suficiente.

### 8.8 Classificação pelo esquema

#### Indícios de `SIAFLOJA.FDB`

Validar presença de tabelas como:

- `DSIAF006`
- `DSIAF010`
- `DSIAF011`
- `DSIAF036`
- `DSIAF037`
- `DSIAF400`
- `DSIAF401`

#### Indícios de `SIAFW.FDB`

Validar presença de tabelas como:

- `DSIAF001`
- `DSIAF050`
- `DSIAF051`
- `DSIAF052`
- `DSIAF053`
- `DSIAF095`

A classificação deve aceitar diferenças de versão e usar níveis de confiança.

### 8.9 Montagem automática da conexão

#### Banco local

```text
localhost:C:\CAMINHO_REAL\SIAFLOJA.FDB
```

#### Banco remoto

```text
SERVIDOR_DETECTADO:C:\CAMINHO_NO_SERVIDOR\SIAFLOJA.FDB
```

O caminho remoto precisa ser o caminho visto pelo serviço Firebird no servidor. Um caminho UNC ou uma unidade mapeada do terminal não deve ser usado como substituto automático.

Quando o caminho físico remoto não puder ser determinado, a ferramenta poderá usar alias detectado ou solicitar somente a escolha entre candidatos conhecidos.

### 8.10 Validação da conexão

Para cada candidato:

- validar biblioteca cliente x86;
- abrir conexão com timeout;
- executar `SELECT CURRENT_TIMESTAMP FROM RDB$DATABASE`;
- consultar versão e ODS quando possível;
- ler uma amostra de metadados;
- classificar tipo de base;
- encerrar cursor, transação e conexão;
- registrar resultado sem credenciais.

### 8.11 Tela de detalhes técnicos

Mostrar:

- modo detectado;
- versão do Firebird;
- serviço/processo;
- biblioteca cliente usada;
- host/porta detectados;
- bases encontradas;
- nível de confiança;
- evidências usadas;
- avisos e falhas parciais.

### 8.12 Tradução mínima de erros

| Situação | Mensagem para o atendente |
|---|---|
| SIAF não localizado | Não foi possível localizar automaticamente a instalação do SIAF |
| Firebird não detectado | O serviço ou cliente Firebird não foi encontrado neste computador |
| Terminal sem conexão ativa | Abra o SIAF e execute novamente a análise do ambiente |
| Várias bases candidatas | Foram encontradas várias lojas; selecione a base correta |
| Caminho inexistente | O Firebird não encontrou a base no caminho detectado |
| SQLCODE -902 / I/O CreateFile | O caminho detectado não é válido para o serviço Firebird |
| Porta indisponível | Não foi possível alcançar automaticamente o serviço Firebird |
| Login inválido | Informe a credencial autorizada do suporte |
| DLL não encontrada | O cliente Firebird x86 não foi localizado |
| WinError 193 | A DLL encontrada é incompatível com a arquitetura do aplicativo |
| Unsupported ODS | O cliente/servidor não é compatível com a estrutura da base |
| Base não é SIAF | O arquivo abriu, mas não contém as tabelas esperadas do SIAF |

### 8.13 Fallback manual

A tela manual deve permanecer escondida em “Opções avançadas” e permitir:

- selecionar pasta do SIAF;
- selecionar cliente Firebird;
- selecionar um `.FDB`;
- informar host/porta somente em último caso;
- salvar o ambiente validado para a próxima execução.

O fallback nunca deve substituir a descoberta automática como fluxo principal.

---

## 9. Motor seguro de consultas

### Regras obrigatórias

- O modo padrão aceita somente consultas de leitura registradas.
- Bloquear `UPDATE`, `DELETE`, `INSERT`, `MERGE`, `ALTER`, `DROP`, `CREATE`, `EXECUTE BLOCK` e múltiplos comandos no editor de consulta.
- Usar parâmetros, nunca concatenar valores de usuário.
- Validar tabelas e campos no catálogo Firebird antes de executar.
- Usar `fetchmany()` com lote configurável; nunca usar `fetchall()` em consultas potencialmente grandes.
- Limitar a visualização e permitir exportação completa por streaming.
- Permitir cancelamento cooperativo.
- Fechar cursor, transação e conexão em `finally`.
- Registrar duração, quantidade, filtros e resultado, sem credenciais.
- Mostrar o SQL ao atendente somente quando apropriado e mascarar parâmetros sensíveis.

### Paginação

Como Firebird 2.5 trabalha com `FIRST` e `SKIP`, a paginação deve ser implementada com ordenação determinística. Para relatórios completos, preferir cursor sequencial e exportação em lotes.

---

## 10. Módulos funcionais

### 10.1 Produtos e estoque

- Busca por código, nome, referência, barra, GTIN, grupo e fornecedor.
- Estoque atual, custo, custo médio, preço de venda, margem e situação.
- Produtos com estoque negativo, zero ou nulo.
- Produtos com preço abaixo do custo.
- Produtos sem NCM, CEST, CST/CSOSN ou classificação IBS/CBS.
- Códigos de barra, GTIN e referências duplicadas.
- Vínculo de fornecedor/referência na DSIAF030.
- Grade DSIAF140.
- Comparação entre lojas.
- Reprocessamento apenas como orientação/diagnóstico no MVP.

### 10.2 Clientes e fornecedores

- Busca por código, nome, CPF/CNPJ, cidade, UF e situação.
- Validação de campos fiscais e cadastro.
- Limite, classe e bloqueios do cliente.
- Relação com notas, contas a receber e PDV.
- Fornecedor e referências de produtos.

### 10.3 NF-e de saída e Monitor Fiscal

- Busca por número, série, data, cliente e chave.
- Cabeçalho DSIAF036 e itens DSIAF037.
- Status, chave, protocolo, autorização e contingência.
- Validação do campo SAI_DPECPEND.
- Referências de documentos e chave via fluxo equivalente ao Ctrl+Shift+F8.
- Análise de pagamento/SAI_RECEBE.
- Análise de VOutros, desconto/troco e itens fiscais.
- Retorno de rejeições conhecidas.
- Geração de texto padronizado para ticket.

### 10.4 Nota Fiscal de Entrada

- Cabeçalho DSIAF011 e itens DSIAF012.
- Busca por nota, fornecedor, chave, data e produto.
- Validação de atualização de custo e estoque.
- Detecção de série INV.
- Entrada de uso e consumo/ativo/brinde sem produto normal, conforme procedimento validado.
- Referência de fornecedor/produto e possíveis vínculos incorretos.
- Prestação da entrada DSIAF002.

### 10.5 PDV e NFC-e

- Cabeçalho DSIAF400, itens DSIAF401 e financeiro DSIAF402.
- Localizar venda, NFC-e, itens e pagamentos.
- Status/cancelamento.
- Terminal do PDV.
- Troco e divergências financeiras.
- Produto não cadastrado/grade.
- Existe Cupom para importação em NF-e sem duplicar estoque/financeiro.

### 10.6 Financeiro

- Contas a Receber DSIAF015.
- Contas a Pagar DSIAF016.
- Caixa Diário DSIAF017/DSIAF018.
- Transferência de caixa DSIAF136.
- Tipos de venda DSIAF025.
- Tipos de pagamento DSIAF026.
- Baixa, baixa retroativa, juros, desconto, duplicatas e permissões.
- Consulta de outros caixas.
- Boletos, comissões e fluxo de caixa em fases de relatório.

### 10.7 Usuários e permissões

- Usuários DSIAF050.
- Permissões DSIAF051.
- Programas DSIAF052.
- Grupos DSIAF053.
- Diagnóstico por PROG_MOD, PROG_IND e PROG_DESC.
- Campos PROG_ACE, PROG_INC, PROG_ALT, PROG_EXC e PROG_IMP.
- Comparação de grupos e identificação da permissão que bloqueia uma rotina.

### 10.8 Serviços, OS e indústria

- Cadastro de serviço DSIAF070.
- Nota Fiscal de Serviço DSIAF075/076/077.
- Ordem de Serviço DSIAF085/086/087.
- Aplicação dos produtos no módulo O.S. DSIAF141.
- Módulo Indústria e Ordem de Produção DSIAF032/038.
- Esses módulos devem começar somente com consulta e mapa de fluxo.

### 10.9 Impressoras e formulários

- Impressoras DSIAF080.
- Parametrização de formulários DSIAF081.
- Diagnóstico de impressora padrão.
- Spooler e fila de impressão.
- Etiquetas e layouts Argox/Elgin já conhecidos.
- Comandos de gaveta apenas como referência controlada.

### 10.10 Base de conhecimento

- Pesquisa local por problema, sintoma, tabela, campo, menu, atalho e palavra-chave.
- Exibir nível de confiança: confirmado pelo usuário, documento, print, inferido ou pendente.
- Gerar resposta pronta para cliente.
- Gerar Motivo/Resolução para ticket.
- Permitir importar versões futuras da base JSON.
- Nunca executar automaticamente um procedimento apenas por ter sido localizado na base.

---

## 11. Diagnóstico automático

### Banco e ambiente

- Conectividade TCP 3050.
- Arquitetura da aplicação e cliente Firebird.
- Abertura das bases.
- Versão do servidor.
- Tabelas críticas existentes.
- Campos críticos existentes.
- Triggers, procedures, índices e generators.
- Transações/conexões monitoráveis.
- Tamanho do arquivo e espaço livre, quando a base for local e houver permissão.
- Diferença de estrutura entre clientes/lojas.

### Diagnósticos operacionais iniciais

- Produtos negativos, zerados, sem custo, sem preço ou com preço abaixo do custo.
- Produtos sem dados fiscais essenciais.
- GTIN e referências duplicadas.
- NF-e em contingência.
- NF-e sem chave, protocolo ou autorização.
- NF-e com total de pagamento divergente.
- Clientes sem dados necessários para operações fiscais.
- Usuários sem grupo ou permissões inconsistentes.
- Entradas série INV.
- Referências de fornecedor potencialmente incorretas.
- Vendas/PDV com status ou terminal que merecem análise.

### Classificação dos resultados

| Nível | Significado |
|---|---|
| Crítico | Pode impedir operação ou envolver risco fiscal/financeiro |
| Alto | Deve ser analisado antes de novas movimentações |
| Médio | Divergência que pode causar retrabalho |
| Informativo | Dado útil sem erro confirmado |

---

## 12. Relatórios e exportações

### Relatórios prioritários

- Estoque atual.
- Movimento de produtos.
- Produtos sem movimentação.
- Produtos com estoque negativo/zero.
- Tabela de preços e custos.
- Vendas por período, produto, cliente, vendedor, grupo e fornecedor.
- Notas por CFOP.
- Entradas por fornecedor e produto.
- Contas a receber e a pagar.
- Caixa diário.
- Comparativo mensal.
- Curva ABC.
- Margem e preço abaixo do custo.
- Permissões por grupo/programa.
- Diagnóstico técnico da base.

### Regras de exportação

- CSV em UTF-8 com BOM e opção de separador `;`.
- XLSX com `openpyxl` em modo de escrita progressiva para grandes volumes.
- Nunca converter códigos de barras/GTIN em notação científica.
- Datas formatadas sem perder o valor original.
- Valores monetários e quantidades com precisão adequada.
- Aba `Parâmetros` com filtros usados.
- Aba `Consulta` com identificação do template, não credenciais.
- Aba `Alertas` quando houver inconsistências.

---

## 13. Comparação entre lojas

O módulo deve operar em leitura e processar cada base em lotes.

### Comparações previstas

- Produtos existentes somente na origem.
- Produtos existentes somente no destino.
- Mesmo PRO_COD com nome diferente.
- Referência e código de barras divergentes.
- Estoque divergente.
- Custo, custo médio e preço divergentes.
- Grupo/subgrupo divergentes.
- NCM, CEST, CST/CSOSN, PIS/COFINS e IBS/CBS divergentes.
- Produtos desativados em apenas uma loja.
- Cadastros auxiliares ausentes.
- Diferenças de estrutura da tabela.

### Saída

- Grade filtrável.
- Resumo por tipo de divergência.
- Exportação XLSX/CSV.
- Seleção manual para uma operação futura.
- Nenhuma alteração direta na fase de comparação.

---

## 14. Operações controladas

Esta etapa só começa depois de consultas, diagnósticos e comparação estarem estáveis.

### Fluxo obrigatório

```text
Selecionar perfil/base
→ validar estrutura
→ executar SELECT de prévia
→ mostrar registros
→ confirmar backup
→ digitar frase de confirmação
→ iniciar transação
→ executar em lote pequeno
→ validar resultado
→ COMMIT somente se válido
→ ROLLBACK em erro
→ registrar auditoria
```

### Frase padrão

```text
CONFIRMO ALTERAÇÃO NA BASE PRODUTIVA
```

### Operações candidatas

- Copiar produtos inexistentes entre lojas em lotes.
- Atualizar campos explicitamente selecionados após comparação.
- Desativar produtos selecionados após validação.
- Retirar contingência de uma nota específica, conforme procedimento validado.
- Corrigir uma referência de produto específica.
- Atualizar uma permissão específica mediante seleção do grupo/programa.
- Aplicar uma correção registrada na biblioteca interna e compatível com a estrutura detectada.

### Operações proibidas no MVP

- UPDATE ou DELETE genérico.
- Comando sem WHERE.
- Alteração em todos os clientes/produtos sem filtros e aprovação técnica.
- Alteração fiscal em massa automática.
- Exclusão de notas, vendas, entradas ou financeiro.
- Renumeração de NF-e.
- Restauração sobre base produtiva.
- Zerar estoque sem procedimento contábil/operacional validado.

---

## 15. Cópia de produtos em lotes

O módulo deve substituir o comando de cópia que pode gerar `Out of memory` em grandes cadastros.

### Opções da tela

- Perfil/base de origem.
- Perfil/base de destino.
- Tamanho do lote, padrão 200.
- Somente produtos inexistentes.
- Comparar antes.
- Copiar estoque atual.
- Copiar preços.
- Copiar custos.
- Copiar dados fiscais.
- Copiar somente grupo selecionado.
- Preservar produtos existentes.
- Gerar relatório de conflitos.

### Regras

- Comparar estruturas das duas DSIAF006.
- Copiar somente campos comuns e autorizados.
- Validar PRO_COD e PRO_EST.
- Processar por `fetchmany()` e `executemany()`.
- Commit por lote apenas em operação explicitamente configurada; manter relatório detalhado.
- Interromper em erro e preservar o último lote confirmado.
- Não copiar notas, vendas, entradas, PDV, financeiro ou histórico de movimentação.
- Alertar que copiar apenas PRO_EST pode causar divergência com o histórico; exigir decisão explícita.

---

## 16. Backup e manutenção Firebird

### Primeira versão

- Localizar `gbak.exe` compatível com Firebird 2.5 x86.
- Selecionar origem e arquivo de destino.
- Executar backup fora da interface principal.
- Capturar saída e código de retorno.
- Validar existência e tamanho do arquivo.
- Registrar hash, data e perfil.
- Nunca sobrescrever sem confirmação.

### Versões futuras

- Validação de backup.
- Restore obrigatório para caminho diferente.
- Estatísticas com `gstat`.
- Consulta de conexões/transações.
- Orientação para sweep/manutenção, sem execução automática em produção.

---

## 17. Roadmap de implementação

### Fase 0 — Prova de compatibilidade x86

> **Concluída em 2026-07-18.** O ambiente confirmou Python 3.11 x86, Firebird 2.5.7
> Win32, carregamento de `fbclient.dll` x86, conexão somente leitura às bases SIAFW e
> SIAFLOJA, build PyInstaller `onedir` x86 e execução bem-sucedida no Windows Sandbox sem
> Python instalado. A revisão pós-fase corrigiu falsos positivos de classificação, isolamento
> de detectores, múltiplas configurações, atalhos e build externo, com 42 testes e 73% de
> cobertura. Consulte `docs/phase-0-status.md`.

**Entregas:**

- Criar ambiente Python 3.11 32 bits.
- Instalar `fdb`.
- Carregar `fbclient.dll` x86 explicitamente.
- Testar Firebird 2.5.7.
- Gerar primeiro `.exe` mínimo.
- Documentar matriz de compatibilidade.

**Critérios de aceite:**

- Aplicação comprova arquitetura 32 bits.
- Conexão abre as duas bases de teste.
- Build funciona sem Python instalado.

### Fase 1 — Fundação do repositório

> **Concluída em 2026-07-18.** A estrutura do projeto, dependências, documentação e paths por
> usuário foram homologados. Logs rotativos e sanitização de credenciais foram comprovados
> por testes no runtime Python x86. A revisão pós-fase também cobriu tracebacks, valores com
> escape, troca do destino dos logs e variáveis de perfil inválidas. A suíte encerrou a
> estabilização com 55 testes e 74% de cobertura. Consulte `docs/phase-1-status.md`.

**Entregas:**

- Criar estrutura de pastas.
- Configurar `pyproject.toml`, requirements, logs e testes.
- Criar `AGENTS.md`, README, CHANGELOG e ROADMAP.
- Criar paths de dados por usuário.

**Critérios de aceite:**

- Testes executam.
- Logs rotativos funcionam.
- Nenhuma credencial é registrada.

### Fase 2 — Interface base

> **Concluída em 2026-07-18.** A interface desktop recebeu menu lateral, barras persistentes,
> onze páginas, temas claro/escuro, persistência da janela e diálogo reutilizável. Navegação e
> fechamento foram aprovados em smoke test isolado e no executável x86. A revisão pós-fase
> adicionou navegação rolável para DPI alto, invalidação de dados antigos, suporte ao desktop
> virtual e persistência concorrente. A estabilização encerrou com 70 testes e 85% de cobertura
> combinada. Consulte `docs/phase-2-status.md`.

**Entregas:**

- Janela principal.
- Menu lateral.
- Barra superior e inferior.
- Páginas vazias.
- Tema e persistência da janela.
- Diálogos reutilizáveis.

**Critérios de aceite:**

- Navegação funciona sem travar.
- Aplicação fecha corretamente.

### Fase 3 — SQLite interno

> **Concluída em 2026-07-18.** O SQLite interno agora é criado no bootstrap, possui migration
> versionada e idempotente e persiste as descobertas sem compartilhar conexão entre threads.
> Perfis de contingência não possuem senha, mensagens históricas são sanitizadas e uma base
> validada continua reutilizável depois de novas análises. A estabilização encerrou com 85 testes,
> cobertura combinada de 87% e smoke aprovado no executável x86. Consulte
> `docs/phase-3-status.md`.

**Entregas:**

- Criar migrations.
- Ambientes detectados.
- Bases descobertas.
- Perfis manuais somente como fallback.
- Histórico.
- Templates.
- Cache de estrutura.
- Base de conhecimento.

**Critérios de aceite:**

- Banco interno é criado automaticamente.
- Migrations são idempotentes.
- Nenhuma senha é persistida.
- Uma descoberta validada pode ser reutilizada sem impedir nova análise.

### Fase 4 — Descoberta automática e conexão Firebird

> **Em homologação desde 2026-07-18.** A descoberta automática agora prepara conexões locais
> e remotas a partir de evidências do SIAF, valida cada base em modo somente leitura fora da
> thread da interface e persiste somente metadados técnicos. O fallback avançado, a tradução
> de falhas e a exportação de diagnóstico sem credenciais também estão disponíveis. A suíte
> possui 100 testes, 85% de cobertura combinada e build PyInstaller x86 aprovado em smoke.
> A estabilização passou a bloquear versões diferentes de Firebird 2.5.7/ODS 11.2, detectar
> portas remotas `3050–3099` observadas pelo SIAF, preservar a porta de cada instância e impedir
> troca silenciosa da DLL cliente durante a sessão.
> Permanecem pendentes a autenticação pela nova tela em uma base real e a homologação em um
> terminal conectado a servidor remoto. Consulte `docs/phase-4-status.md`.

**Entregas:**

- Orquestrador de descoberta.
- Detecção da arquitetura do processo.
- Detecção do processo e instalação do SIAF.
- Detecção de serviços/processos Firebird/InterBase.
- Leitura segura do Registro do Windows.
- Detecção de `fbclient.dll` e `gds32.dll` x86.
- Identificação de servidor local ou terminal.
- Detecção de conexões TCP do processo SIAF.
- Busca progressiva por `SIAFW.FDB` e `SIAFLOJA.FDB`.
- Ranqueamento de candidatos.
- Classificação pelo esquema.
- Conexão automática local/remota.
- Fallback assistido.
- Tradução de erros.
- Status persistente na interface.

**Critérios de aceite:**

- Em servidor local homologado, o programa encontra Firebird e as bases sem digitar host, porta ou caminho.
- Em terminal homologado, o programa identifica o servidor usado pelo SIAF ou apresenta candidatos fundamentados.
- Múltiplas lojas são listadas para seleção.
- Uma base não é aceita apenas pelo nome do arquivo.
- Erros parciais não fecham o programa.
- Senha não é salva.
- Não é feita varredura completa do disco ao iniciar.
- O atendente consegue exportar um diagnóstico técnico da descoberta.

### Fase 5 — Inspetor de estrutura

**Entregas:**

- Ler relações, campos, índices, PKs, triggers, procedures e generators.
- Criar cache.
- Comparar estruturas.

**Critérios de aceite:**

- Consulta só executa quando requisitos existem.

### Fase 6 — Motor de consulta somente leitura

**Entregas:**

- Templates parametrizados.
- Validador de SQL.
- Workers.
- Fetch em lotes.
- Cancelamento.
- Paginação.

**Critérios de aceite:**

- Consulta grande não congela a interface.
- Comando destrutivo é bloqueado.

### Fase 7 — Produtos, clientes e fornecedores

**Entregas:**

- Consultas rápidas.
- Filtros.
- Detalhes.
- Exportação CSV/XLSX.

**Critérios de aceite:**

- Busca por código/nome/documento funciona.

### Fase 8 — NF-e, entrada e PDV

**Entregas:**

- DSIAF036/037.
- DSIAF011/012.
- DSIAF400/401/402.
- Consulta por número/chave/período.
- Indicadores de contingência e status.

**Critérios de aceite:**

- Resultados batem com amostras conferidas no SIAF.

### Fase 9 — Financeiro e permissões

**Entregas:**

- DSIAF015/016/017/018/025/026/136.
- DSIAF050/051/052/053.
- Diagnóstico por grupo/programa.

**Critérios de aceite:**

- Consultas validadas em casos reais.

### Fase 10 — Diagnóstico automático

**Entregas:**

- Checks de banco, produtos, fiscal, financeiro e permissões.
- Classificação de alertas.
- Relatório técnico.

**Critérios de aceite:**

- Diagnóstico gera resumo e evidências.

### Fase 11 — Relatórios

**Entregas:**

- Modelos configuráveis.
- Exportação progressiva.
- Parâmetros e abas auxiliares.

**Critérios de aceite:**

- Exporta volume alto sem estouro de memória.

### Fase 12 — Comparação entre lojas

**Entregas:**

- Duas conexões.
- Mapeamento em lotes.
- Diferenças.
- Exportação.

**Critérios de aceite:**

- Nenhum dado é alterado.
- Conflitos são identificados.

### Fase 13 — Base de conhecimento local

**Entregas:**

- Importar JSON consolidado.
- Pesquisa.
- Respostas/tickets.
- Níveis de confiança.

**Critérios de aceite:**

- Busca retorna procedimento e fonte.

### Fase 14 — Backup

**Entregas:**

- Integração com gbak.
- Progresso.
- Logs.
- Validação do arquivo.

**Critérios de aceite:**

- Backup de teste restaura em caminho separado.

### Fase 15 — Operações controladas

**Entregas:**

- Framework de prévia, confirmação, transação, rollback e auditoria.
- Implementar uma operação piloto de baixo escopo.

**Critérios de aceite:**

- Sem confirmação não há alteração.
- Erro provoca rollback.

### Fase 16 — Cópia de produtos

**Entregas:**

- Migrar o script de cópia em lotes para a interface.
- Comparação prévia.
- Seleção de campos.
- Relatório de conflitos.

**Critérios de aceite:**

- Base grande é processada sem Out of memory.

### Fase 17 — Empacotamento e release

**Entregas:**

- PyInstaller onedir para homologação.
- PyInstaller onefile final.
- Ícone, versão, recursos e DLL.
- Teste em PCs limpos.
- Instalador opcional.

**Critérios de aceite:**

- Usuário executa pelo ícone sem console e sem Python instalado.

---

## 18. Estratégia de testes

### Testes unitários

- Validação e classificação de SQL.
- Conversão de tipos Firebird.
- Paginação.
- Exportação.
- Cálculos de comparação.
- Hashes de auditoria.
- Mascaramento.
- Ranqueamento de candidatos.
- Classificação de `SIAFW` e `SIAFLOJA`.
- Parser de caminhos, aliases e configurações.
- Detecção de arquitetura de DLL.
- Tratamento de erros de cada detector.

### Testes de integração

Utilizar:

- Cópias anonimizadas de SIAFLOJA e SIAFW.
- Firebird 2.5.7 x86.
- Máquina servidor com serviço local.
- Máquina terminal sem serviço local.
- Terminal com SIAF aberto e conexão remota ativa.
- Terminal com SIAF fechado, mas configuração disponível.
- Uma loja.
- Múltiplas lojas.
- Bases grandes.
- Banco indisponível.
- DLL incorreta.
- Configuração ambígua.
- Arquivo com nome correto, mas esquema incompatível.

### Matriz de homologação

| Cenário | Validação |
|---|---|
| Windows 10 64 bits | Executável x86 e descoberta local |
| Windows 11 64 bits | Executável x86 e descoberta local |
| Máquina sem Python | Executável funciona |
| Servidor Firebird local | Serviço, versão e bases detectados automaticamente |
| Terminal com SIAF aberto | Servidor remoto inferido pela configuração/conexão |
| Terminal com SIAF fechado | Ambiente encontrado por instalação/configuração |
| Várias lojas | Todas são listadas e classificadas |
| Mais de uma instalação SIAF | Candidatos são ranqueados e apresentados |
| Firebird parado | Mensagem amigável e opção de reanálise |
| Cliente DLL ausente | Fallback homologado ou orientação clara |
| Base pequena | Fluxo completo |
| Base com muitos produtos | Consulta/exportação/cópia em lotes |
| Internet indisponível | Aplicação continua funcional |
| Usuário sem administrador | Descoberta parcial funciona ou informa limitação |
| Antivirus ativo | Build assinado/homologado sem comportamento suspeito |

### Testes de segurança

- Nenhuma senha em logs.
- Nenhuma credencial embutida em texto simples.
- Bloqueio de SQL destrutivo.
- Rollback em erro.
- Operação sem backup bloqueada.
- Auditoria gerada.
- A descoberta não lê arquivos fora do escopo necessário.
- A ferramenta não tenta extrair senhas do SIAF.
- Caminhos e dados sensíveis podem ser mascarados ao exportar diagnóstico.

---

## 19. Logs, auditoria e privacidade

### Arquivos

```text
logs/app.log
logs/errors.log
logs/audit.log
```

### Nunca registrar

- Senha Firebird.
- Certificado digital.
- Senha de certificado.
- Token CSC.
- Chaves privadas.
- Dados pessoais completos sem necessidade.
- Conteúdo integral de XML fiscal em log comum.

### Registrar em operações

- Usuário do Windows.
- Perfil e base identificados por hash/código.
- Nome da operação.
- Filtros.
- Quantidade de registros.
- Backup confirmado.
- Resultado de validação.
- Commit ou rollback.
- Versão da aplicação.

---

## 20. Empacotamento `.exe`

### Objetivo de distribuição

Entregar uma ferramenta portátil que possa ser copiada para o computador do cliente e executada durante o atendimento.

Meta final:

```text
SIAFSupportToolbox.exe
```

O atendente abre o executável, aguarda a descoberta do ambiente e seleciona a loja quando necessário.

### Estratégia de build

#### Homologação inicial

Utilizar `onedir`, porque facilita:

- análise de DLLs;
- diagnóstico de plugins;
- atualização de recursos;
- investigação de antivírus;
- correção de incompatibilidades.

#### Release portátil

Após estabilizar:

- testar `onefile`;
- usar `--windowed`;
- controlar o diretório temporário do PyInstaller;
- carregar DLL x86 de forma previsível;
- assinar digitalmente o executável, quando possível;
- evitar exigir instalação administrativa.

### Requisitos

- Build realizado em Windows com Python x86.
- Não gerar build x86 confiando apenas em ambiente 64 bits.
- Testar em máquina sem Python.
- Testar com e sem cliente Firebird instalado.
- Testar a descoberta no servidor e no terminal.
- Tratar caminho temporário do `onefile`.
- Incluir versão, ícone e metadados.
- Não incluir credenciais.
- Não exigir internet.

### Saída recomendada de homologação

```text
dist/
└── SIAFSupportToolbox/
    ├── SIAFSupportToolbox.exe
    ├── recursos internos
    └── bibliotecas necessárias
```

### Saída final desejada

```text
SIAFSupportToolbox.exe
```

O `.exe` final poderá extrair internamente seus componentes, mas o usuário deverá interagir apenas com a interface gráfica.

---

## 21. Regras para o `AGENTS.md`

```markdown
# Regras do projeto

1. O projeto é uma aplicação desktop Windows; não criar aplicação web.
2. O executável será utilizado diretamente no computador do cliente.
3. O fluxo principal deve descobrir automaticamente SIAF, Firebird, servidor e bases.
4. Host, porta e caminho não são campos obrigatórios no uso normal.
5. Configuração manual existe somente como fallback avançado.
6. O ambiente alvo utiliza Firebird 2.5.7 de 32 bits.
7. O MVP deve ser desenvolvido e empacotado com Python x86/32 bits.
8. Detectar e validar fbclient.dll ou gds32.dll x86.
9. Não depender de um único nome de serviço Firebird.
10. Detectar tanto servidor local quanto terminal conectado a servidor remoto.
11. Não realizar varredura recursiva completa do disco ao iniciar.
12. Classificar a base pelo esquema, não apenas pelo nome do arquivo.
13. Não tentar extrair, quebrar ou descriptografar senha do SIAF.
14. O modo padrão da aplicação é somente leitura.
15. A interface nunca executa SQL diretamente.
16. Não inventar tabelas, campos, menus ou regras do SIAF.
17. Validar tabelas e campos no catálogo antes de cada template.
18. Consultas grandes usam fetchmany; não usar fetchall sem limite comprovado.
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
30. Atualizar ROADMAP.md e CHANGELOG.md a cada fase.
```

---

---

## 22. Prompt mestre para iniciar no Codex

```text
Você está iniciando o projeto SIAF Support Toolbox.

Objetivo:
Criar uma aplicação desktop portátil para suporte ao ERP SIAF. O executável será aberto diretamente no computador do cliente e deverá descobrir automaticamente o ambiente SIAF/Firebird, localizar as bases SIAFW.FDB e SIAFLOJA.FDB e conectar em modo somente leitura.

Fluxo esperado:
1. Abrir o .exe.
2. Analisar o computador.
3. Detectar instalação/processo do SIAF.
4. Detectar Firebird 2.5.7 x86 ou ambiente compatível.
5. Determinar se a máquina é servidor local ou terminal.
6. Descobrir servidor, porta e bases automaticamente.
7. Validar o esquema.
8. Exibir as lojas encontradas.
9. Permitir selecionar a loja.
10. Liberar consultas e diagnósticos.

Ambiente obrigatório:
- Firebird 2.5.7 de 32 bits.
- Python 3.11 x86/32 bits no MVP.
- Biblioteca fdb.
- psutil para inspeção controlada de processos/conexões.
- tkinter/ttk; ttkbootstrap pode ser usado para tema.
- SQLite para ambientes detectados, histórico, templates e auditoria.
- PyInstaller para gerar .exe sem console.
- Aplicação somente desktop; não criar servidor HTTP, API web ou navegador.

Regras críticas:
- Não exigir host, porta e caminho no fluxo normal.
- Criar fallback manual apenas em Opções avançadas.
- Detectar serviço/processo sem depender de nome único.
- Ler Registro do Windows por winreg, incluindo visão de 32 bits quando necessário.
- Detectar fbclient.dll e gds32.dll x86.
- Não fazer busca completa do disco ao iniciar.
- Buscar primeiro em processo, atalho, pasta SIAF, serviço Firebird, configuração e diretórios conhecidos.
- Detectar servidor remoto por configuração ou conexão ativa do processo SIAFW.EXE.
- Não capturar tráfego e não instalar driver de rede.
- Não extrair ou descriptografar senha do SIAF.
- Não salve senha Firebird.
- Não registre credenciais nos logs.
- Classifique SIAFW e SIAFLOJA pela estrutura de tabelas.
- O modo padrão é somente leitura.
- Não implemente UPDATE, DELETE ou INSERT nesta primeira entrega.
- Use fetchmany para dados grandes.
- Operações longas devem executar em worker e comunicar a interface por fila/after.
- Cada worker deve possuir sua própria conexão Firebird.
- A interface não executa SQL diretamente.
- Não invente tabelas ou campos do SIAF.

Primeira entrega — Fase 0 e fundação da Fase 4:
1. Ler integralmente ROADMAP.md e AGENTS.md.
2. Propor estrutura do repositório.
3. Criar ambiente Python 3.11 x86 documentado.
4. Criar teste que confirme processo 32 bits.
5. Criar modelos de resultado de descoberta com evidências e confiança.
6. Criar detector de processos do SIAF.
7. Criar detector de serviços/processos Firebird.
8. Criar detector de Registro do Windows.
9. Criar detector de fbclient.dll/gds32.dll e arquitetura.
10. Criar busca progressiva por SIAFW.EXE, SIAFW.FDB e SIAFLOJA.FDB.
11. Criar classificador inicial de servidor local versus terminal.
12. Criar prova de leitura de conexões TCP do processo SIAF.
13. Criar prova de conexão com uma base de teste descoberta automaticamente.
14. Criar estrutura de pastas, logging, configuração e testes.
15. Criar uma janela mínima que mostre:
    - arquitetura;
    - SIAF encontrado;
    - Firebird encontrado;
    - modo da máquina;
    - DLL;
    - bases candidatas;
    - nível de confiança.
16. Gerar build PyInstaller x86 de homologação.
17. Documentar execução, testes e riscos.

Antes de escrever código:
- apresente o plano;
- liste arquivos previstos;
- identifique riscos de bitness, serviço, DLL, múltiplas lojas e permissões do Windows;
- defina critérios de aceite;
- não peça host, porta ou caminho como premissa inicial.

Depois implemente somente essa entrega.
Não avance para consultas funcionais do SIAF.
Ao final, execute testes e informe resultados objetivos.
```

---

## 23. Prompt padrão para cada fase

```text
Leia integralmente ROADMAP.md, AGENTS.md e o código atual.
Implemente somente a Fase [NÚMERO E NOME].

Antes de alterar:
1. Identifique arquivos afetados.
2. Apresente um plano curto.
3. Liste riscos e critérios de aceite.
4. Não modifique módulos fora do escopo sem justificativa.

Durante:
- preserve separação entre UI, services, repositories e database;
- mantenha compatibilidade Firebird 2.5.7 x86;
- adicione tratamento de erros e logs sem dados sensíveis;
- use workers para tarefas demoradas;
- escreva testes;
- não quebre fases anteriores.

Ao final:
1. Execute os testes.
2. Informe arquivos criados e alterados.
3. Informe decisões técnicas e limitações.
4. Atualize ROADMAP.md e CHANGELOG.md.
5. Não avance para a fase seguinte.
```

---

## 24. Mapa de menus conhecido do SIAF

### Arquivos

Menu de cadastros, configurações e manutenção do sistema.

- Clientes
- Fornecedores
- Transportadoras
- Funcionários
- Grupos de Funcionários
- Profissionais
- Rotas
- Produtos
- Grupos
- Subgrupos
- Tabela de Venda
- Classificação IBS/CBS
- Departamentos
- Centros de Custos
- Classificação de Centro de Custo
- Bancos
- Cfop
- Natureza da Receita
- Código Serviço SPED
- Cartas
- Tipos de Vendas
- Tipos de Pagamentos
- Caixas
- Manifesto Elet. Doc. Fiscais (MDF-e)
- Lista de Compras
- Reprocessa Produtos
- Processamento das Classes
- Controle de Acesso
- Configurações do Sistema

### Arquivos > Controle de Acesso

Submenu de usuários, grupos, permissões e auditoria/acessos.

- Usuários
- Grupos de Usuários
- Grupos X Programas
- Arquivos acessados por Usuários

### Arquivos > Configurações do Sistema

Submenu de empresa, parâmetros, impressoras, formulários e manutenção.

- Empresa Licenciada
- Parâmetros do Sistema
- Empresas
- Impressoras
- Parametrização Formulários
- Manutenção de Arquivos

### Lançamentos

Menu operacional: vendas, notas fiscais, financeiro, caixa, pedidos, entregas e controles internos.

- Orçamentos — `Ctrl+O`
- Pedidos — `Ctrl+1`
- Nota Fiscal de Saída — `Ctrl+S`
- Monitor NF-e — `Ctrl+6`
- MDF-e — `Ctrl+9`
- Pedido Fornecedor — `Ctrl+N`
- Nota Fiscal de Entrada — `Ctrl+E`
- Contas a Receber — `Ctrl+R`
- Contas a Pagar — `Ctrl+P`
- Caixa Diário — `Ctrl+J`
- Ajuste de Caixa — `Ctrl+8`
- Controle de Cheques Recebidos — `Ctrl+H`
- Controle de Cheques Emitidos — `Ctrl+7`
- Controle de Funcionários — `Ctrl+U`
- Controle de Entregas/Retiradas — `Ctrl+T`
- Controle de Profissionais — `Ctrl+Y`
- Liberação de Pedidos — `Ctrl+2`
- Livro de Ponto — `Ctrl+L`

### Relatórios

Menu de relatórios operacionais, fiscais, financeiros, estoque, comissão e gerenciais.

- Produtos
- Custo/Faturamento
- Estatísticas
- Contas a Receber
- Contas a Pagar
- Pedido Fornecedor
- Nota Fiscal de Entrada
- Orçamento
- Pedido Cliente
- Nota Fiscal de Saída
- Controle de Entrega/Retirada
- Cupom Fiscal
- Vendas por Vendedor
- Vendas por Cliente
- Vendas com Juros
- Nota Fiscal por CFOP
- Comissões de Vendedores
- Caixa Diário
- Controle de Cheques Recebidos
- Controle de Cheques Emitidos
- Controle de Funcionários
- Controle de Profissionais
- Diversos
- Sintegra

### Relatórios > Produtos

- Tabela de Preços
- Movimento de Produtos
- Movimento Orçamento/Nota/Cupom
- Produtos X Clientes
- Vendedores X Produtos
- Produtos X Kits
- Estoque Financeiro
- Produtos com Est. Mínimo Ultrapassado
- Desvios de Preços Praticados
- Previsão de Compras
- Análise de Produtos não Vendidos/Comprados
- Análise de Produtos Vendidos
- Gráficos de Análise de Produtos
- Inventário de Estoque

**Tabela de Preços:** Tabela de Preços, Tabela de Preços com Fornecedor, Tabela de Preços agrupado por Fornecedor

**Movimento de Produtos:** Geral, Resumido

**Previsão de Compras:** Previsão de Compras Modelo I, Previsão de Compras Modelo II

### Relatórios > Custo/Faturamento

- Planilha de Custos
- Custos Fixos
- Custo da Mercadoria Vendida (CMV)
- Gráficos Faturamento/CMV
- Índice de Marcação de Preço (MKP)
- Fluxo de Caixa Realizado
- Fluxo de Caixa (Cash Flow)
- Previsão Fluxo de Caixa

### Relatórios > Diversos

Submenu de relatórios diversos identificado no menu Relatórios.

- Cartas
- Etiquetas
- Livro de Ponto

---

## 25. Catálogo oficial conhecido de tabelas SIAFLOJA

Este catálogo serve como referência. A aplicação deve sempre validar a estrutura real do cliente.

| Tabela | Descrição conhecida |
|---|---|
| `DSIAF002` | Prestação da NF de Entrada |
| `DSIAF003` | Funcionários |
| `DSIAF005` | Grupos |
| `DSIAF006` | Produtos |
| `DSIAF007` | Controle de Cheques |
| `DSIAF008` | Centro de Custos |
| `DSIAF009` | Fornecedores |
| `DSIAF010` | Clientes |
| `DSIAF011` | Nota Fiscal de Entrada |
| `DSIAF012` | Nota Fiscal de Entrada Itens |
| `DSIAF013` | Orçamento |
| `DSIAF014` | Orçamento Itens |
| `DSIAF015` | Contas a Receber |
| `DSIAF016` | Contas a Pagar |
| `DSIAF017` | Caixa Diário (Cabeçalho) |
| `DSIAF018` | Itens Caixa Diário |
| `DSIAF019` | Subgrupo |
| `DSIAF020` | Bancos |
| `DSIAF021` | Cartas |
| `DSIAF022` | Transportadora |
| `DSIAF023` | Custos Fixos |
| `DSIAF024` | Cadastro Caixa |
| `DSIAF025` | Tipos de Venda |
| `DSIAF026` | Tipos de Pagamento |
| `DSIAF027` | Kit |
| `DSIAF028` | Descrição pendente no documento |
| `DSIAF029` | Controle de Funcionários |
| `DSIAF030` | Fornecedores dos Produtos |
| `DSIAF031` | Promoção dos Produtos |
| `DSIAF032` | Ordem de Produção |
| `DSIAF033` | CFOP (Código Fiscal de Operação) |
| `DSIAF034` | Descrição pendente no documento |
| `DSIAF035` | Nota Fiscal de Saída Prestações |
| `DSIAF036` | Nota Fiscal de Saída |
| `DSIAF037` | Nota Fiscal de Saída Itens |
| `DSIAF038` | Ordem de Produção Itens |
| `DSIAF044` | Grava informações do backup/classe/reprocessamento/exportações |
| `DSIAF046` | Grava o código do produto que precisa do reprocessamento |
| `DSIAF047` | Lista de Compras |
| `DSIAF060` | Arquivos acessados por usuários |
| `DSIAF061` | Informações de Redução Z |
| `DSIAF062` | Cupom Fiscal Prestações |
| `DSIAF063` | Cupom Fiscal Cabeçalho |
| `DSIAF064` | Cupom Fiscal Itens |
| `DSIAF065` | Cupom Fiscal Tipo de Pagamento usado no Cupom |
| `DSIAF066` | Nota de Entrada |
| `DSIAF067` | Itens Nota Fiscal de Entrada |
| `DSIAF068` | Prestação Nota de Entrada |
| `DSIAF070` | Cadastro Serviço |
| `DSIAF072` | Cupom Fiscal Serviço Prestações |
| `DSIAF073` | Cupom Fiscal Serviço Cabeçalho |
| `DSIAF074` | Cupom Fiscal Serviço Itens |
| `DSIAF075` | Nota Fiscal Serviço Prestações |
| `DSIAF076` | Nota Fiscal Serviço Cabeçalho |
| `DSIAF077` | Nota Fiscal Serviço Itens |
| `DSIAF080` | Impressoras |
| `DSIAF081` | Parametrização de Formulário |
| `DSIAF085` | Ordem de Serviço Prestações |
| `DSIAF086` | Ordem de Serviço Cabeçalho |
| `DSIAF087` | Ordem de Serviço Itens |
| `DSIAF090` | Livro de Ponto |
| `DSIAF091` | Agenda |
| `DSIAF094` | Requisição |
| `DSIAF095` | Itens de Requisição |
| `DSIAF098` | Inventário de Estoque |
| `DSIAF136` | Caixa Diário Transferência |
| `DSIAF137` | Salário do Funcionário |
| `DSIAF138` | Grupo de Funcionários |
| `DSIAF140` | Grade do Produto |
| `DSIAF141` | Aplicação dos Produtos Módulo O.S. |
| `DSIAF145` | Profissionais |

---

## 26. Tabelas detalhadas conhecidas — SIAFW

### `DSIAF000` — Configurações

**Finalidade:** Tabela/base de configuração inicial identificada no SIAFW.FDB.

**Observações:** Estrutura detalhada ainda não mapeada.

### `DSIAF001` — Configurações Gerais

**Finalidade:** Configurações gerais do sistema.

**Campos conhecidos:** `Máscaras`, `Relatórios`, `Regras de cliente`, `Caixa`, `Recebimentos/pagamentos`, `Orçamento`, `Entrada/saída`, `Cupom/serviços`, `Comissão`, `Boleto`, `Metas`, `API fiscal`, `Integrações WhatsApp/API`

**Observações:** Tabela ampla. Alterações devem ser feitas apenas conhecendo o campo específico.

### `DSIAF050` — Usuários

**Finalidade:** Cadastro de usuários; campo GRU_USU vincula o usuário ao grupo de permissões.

**Chave provável:** `USU_COD`

**Campos conhecidos:** `USU_COD`, `USU_NOME`, `USU_SENHA`, `GRU_USU`, `USU_CAD`, `ATU_USUA`

### `DSIAF051` — Permissões / Grupo X Programas

**Finalidade:** Permissões por grupo de usuário x programa/rotina, controlando acesso, inclusão, alteração, exclusão e impressão.

**Campos conhecidos:** `GRU_USU`, `PROG_DESC`, `PROG_ACE`, `PROG_INC`, `PROG_ALT`, `PROG_EXC`, `PROG_IMP`, `PROG_IND`, `PROG_MOD`

**Observações:** Tabela central para diagnóstico de acesso bloqueado, botão desabilitado e impossibilidade de incluir, alterar, excluir ou imprimir. No atendimento, partir do usuário em DSIAF050, identificar GRU_USU, conferir grupo em DSIAF053 e validar permissões na DSIAF051 por PROG_DESC/PROG_MOD/PROG_IND.

### `DSIAF052` — Permissões

**Finalidade:** Cadastro/lista de programas ou módulos usados nas permissões do Grupo X Programas.

**Campos conhecidos:** `PROG_DESC`, `PROG_MOD`, `PROG_IND`

### `DSIAF053` — Permissões

**Finalidade:** Cadastro de grupos de usuários usados no controle de acesso e na tela Grupo X Programas.

**Campos conhecidos:** `GRU_USU`, `GRU_DUSU`, `ATU_USUA`, `GRU_CAD`

### `DSIAF095` — Lojas

**Finalidade:** Cadastro/configuração de lojas.

**Campos conhecidos:** `LOJ_COD`, `LOJ_NOME`, `LOJ_CAD`, `ATU_USUA`, `LOJ_DIR`, `LOJ_REPROCESSAR`

### `DSIAF096` — Configurações

**Finalidade:** Relação LIS_COD e CEN_COD.

**Campos conhecidos:** `LIS_COD`, `CEN_COD`

### `DSIAF100` — TEF

**Finalidade:** Configuração TEF.

**Campos conhecidos:** `LIS_COD`, `TEF_REDE`, `TEF_DIR`

### `DSIAF101` — Terminais / MAC

**Finalidade:** Controle/cadastro de MAC.

**Campos conhecidos:** `MAC`, `DATAHORACADASTRO`

### `DSIAF102` — Terminais / MAC

**Finalidade:** Controle/cadastro de MAC semelhante à DSIAF101.

**Campos conhecidos:** `MAC`, `DATAHORACADASTRO`

### `DSIAF103` — Terminais / Usuário / MAC

**Finalidade:** Controle de MAC, usuário, tipo e cadastro.

**Campos conhecidos:** `ID`, `USUARIO`, `MAC`, `TIPO`, `DATAHORACADASTRO`, `IDUSUARIO`

### `DSIAF104` — Fiscal / Série

**Finalidade:** Configuração de série/modelo de saída.

**Campos conhecidos:** `LIS_COD`, `SAI_SER`, `SAI_MOD`

### `DSIAF105` — Terminais / PinPad

**Finalidade:** Terminais e porta do PinPad.

**Campos conhecidos:** `LIS_COD`, `TERMINAL_NOME`, `TERMINAL_CODIGO`, `PINPAD_PORTA`

### `DSIAF110` — Documentos / Fiscal

**Finalidade:** Cadastro/configuração de documentos/cadastro fiscal.

**Campos conhecidos:** `ID`, `TIPO_DOC`, `NUM_DOC`, `MOD_NFE`, `MOD_NFCE`, `TIPO_CAD`, `COD_CAD`, `NOME_CAD`

---

## 27. Tabelas detalhadas conhecidas — SIAFLOJA

### `DSIAF002` — Financeiro / Fornecedor

**Finalidade:** Provável contas a pagar/duplicatas de fornecedor, cheques ou financeiro de entrada.

**Campos conhecidos:** `ENT_NOTA`, `FOR_COD`, `PRA_DATA`, `PRA_VAL`, `PRA_DUP`, `LIS_COD`, `BAN_COD`, `CEN_NPLA`, `CHE_CHE`, `CHE_FORN`, `CHE_HIST`, `CHE_NOMETERC`, `CHE_SER`, `CHEFOR_COD`, `FOR_CNPJ`, `FOR_CPF`, `TIP_CODS`

**Observações:** Função exata associada a contas a pagar ainda precisa de validação por tela.

### `DSIAF006` — Produtos

**Finalidade:** Cadastro principal de produtos.

**Chave provável:** `PRO_COD`

**Campos conhecidos:** `PRO_COD`, `PRO_NOME`, `PRO_REF`, `PRO_BARRA`, `PRO_SIM`, `GRU_COD`, `SUB_COD`, `PRO_ST`, `PRO_ST2`, `PRO_UNI`, `PRO_EMB`, `PRO_LOC`, `PRO_APL`, `PRO_UNIT`, `PRO_COM`, `PRO_CUSTO`, `PRO_MEDIO`, `PRO_LUCRO`, `PRO_VENDA`, `PRO_MIN`, `PRO_MAX`, `PRO_EST`, `PRO_CAD`, `ATU_USUA`, `PRO_FOTO`, `PRO_CF`, `PRO_ICMS`, `PRO_PESO`, `PRO_IPI`, `PRO_MAT`, `PRO_ICMSC`, `PRO_SUBS`, `PRO_SUBSL`, `PRO_FRETE`, `PRO_QTPROD`, `PRO_INDUS`, `PRO_VALID`, `PRO_COMP`, `PRO_PESOB`, `PRO_CUBO`, `PRO_LARG`, `PRO_ALTU`, `PRO_RED`, `PRO_SIMPLES`, `PRO_VEIC`, `PRO_CUSTOADMC`, `PRO_PIS`, `PRO_COFINS`, `PRO_PIS2`, `PRO_COFINS2`, `PRO_RENDA`, `PRO_SOCIAL`, `PRO_CUSTOADMV`, `PRO_ICMSMVA`, `PRO_SUBS2`, `PRO_IPI2`, `PRO_ANTPARC`, `PRO_DESCANT`, `PRO_NFECOMP`, `PRO_DESCMAX`, `PRO_GTIN`, `PRO_IAT`, `PRO_IPPT`, `PRO_GEN`, `PRO_EX_IPI`, `PRO_TIPO`, `PRO_DESAT`, `PRO_CONVER`, `PRO_STIPI`, `PRO_STPIS`, `PRO_STCOFINS`, `PRO_CESP`, `PRO_CLAR`, `PRO_CCOM`, `PRO_CSO`, `PRO_CREDSN`, `PRO_REDV`, `PRO_STIPI2`, `PRO_STPIS2`, `PRO_STCOFINS2`, `PRO_PISVL`, `PRO_COFINSVL`, `PRO_PISVL2`, `PRO_COFINSVL2`, `PRO_NAT_BC_CRED`, `PRO_NAT_REC`, `PRO_PAUTA`, `PRO_PAUTAALIQ`, `PRO_PAUTAMAIOR`, `MD5`, `SER_COD_LST`, `PRO_PRMAX`, `PRO_ANP`, `CFOP_CODSN`, `CFOP_CODSD`, `CFOP_CODED`, `CFOP_CODEN`, `PRO_SUBSICMSCREDE`, `PRO_SUBSICMSCREDS`, `PRO_SUBSICMSDEBE`, `PRO_SUBSMVAE`, `PRO_MODBCST`, `PRO_PAUTAE`, `PRO_PAUTAALIQE`, `PRO_PAUTAMAIORE`, `CCON_COD`, `PRO_SUBICMSDEBE`, `PRO_NMOTOR`, `PRO_CMKG`, `PRO_DIST`, `PRO_RENAVAM`, `PRO_ANOMOD`, `PRO_PONTO`, `PRO_PESOL`, `PRO_CEST`, `PRO_ICMSDIF`, `PRO_ENQIPI`, `PRO_REDST`, `PRO_REDVST`, `FAM_COD`, `SFAM_COD`, `COD_CTA_ENT`, `COD_CTA_SAI`, `PRO_PGLP`, `PRO_PGNN`, `PRO_PGNI`, `PRO_VPART`, `PRO_FCP`, `PRO_CONVENT`, `PRO_FRACIONADO`, `PRO_UTRIB`, `PRO_QTRIB`, `PRO_ACOU`, `PRO_ICMSANTCREDITO`, `PRO_ICMSANTDEBITO`, `PRO_PFCPST`, `PRO_DESONICMS`, `PRO_DATAVALID`, `PRO_CODIF`, `PRO_BASECIDE`, `PRO_VALIQCIDE`, `PRO_VCIDE`, `PRO_QTEMP`, `PRO_PBIO`, `PRO_INDIMPORT`, `PRO_CUFORIG`, `PRO_PORIG`, `PRO_QBCMONO`, `PRO_ADREMICMS`, `PRO_VICMSMONO`, `PRO_QBCMONORETEN`, `PRO_ADREMICMSRETEN`, `PRO_VICMSMONORETEN`, `PRO_PREDADREM`, `PRO_MOTREDADREM`, `PRO_VICMSMONOOP`, `PRO_PDIF`, `PRO_VICMSMONODIF`, `PRO_QBCMONORET`, `PRO_ADREMICMSRET`, `PRO_VICMSMONORET`, `PRO_KITNFE`, `PRO_ID_REVISAO_FISCAL`, `PRO_DT_REVISAO_FISCAL`, `PRO_COMPRA_ENT`, `PRO_DESPADM_ENT`, `PRO_DESC_ENT`, `USA_PRECO_NF_ENTRADA`, `PRO_FRETE_INCIDE`, `PRO_ST_IBS_CBS`, `PRO_CLAS_IBS_CBS`, `PRO_ST_IS`, `PRO_CLAS_IS`, `PRO_PRESU_IBS_CBS`, `PRO_ENT_REF_PIS`, `PRO_ENT_REF_IBSUF`, `PRO_ENT_REF_IBSMUN`, `PRO_ENT_REF_CBS`, `PRO_ENT_REF_IS`, `PRO_ENT_REF_IBSUF_RED`, `PRO_ENT_REF_IBSMUN_RED`, `PRO_ENT_REF_CBS_RED`, `PRO_SAI_REF_PIS`, `PRO_SAI_REF_IBSUF`, `PRO_SAI_REF_IBSMUN`, `PRO_SAI_REF_CBS`, `PRO_SAI_REF_IS`, `PRO_SAI_REF_IBSUF_RED`, `PRO_SAI_REF_IBSMUN_RED`, `PRO_SAI_REF_CBS_RED`, `PRO_ADREMIBSRET`, `PRO_VIBSMONORET`, `PRO_ADREMCBSRET`, `PRO_VCBSMONORET`

**Observações:** PRO_CF deve ser tratado como provável NCM/classificação fiscal até confirmação. Tabela concentra estoque, preço, custos, tributação, NCM/CEST e reforma tributária.

### `DSIAF010` — Clientes

**Finalidade:** Cadastro principal de clientes.

**Chave provável:** `CLI_COD`

**Campos conhecidos:** `CLI_COD`, `CLI_NOME`, `CLI_END`, `CLI_BAI`, `CLI_CEP`, `CLI_CID`, `CLI_EST`, `CLI_FONE`, `CLI_FAX`, `CLI_CEL`, `CLI_TIPO`, `CLI_CPF`, `CLI_CI`, `CLI_NASC`, `CLI_CGC`, `CLI_INSC`, `CLI_SEG`, `CLI_PROF`, `CLI_CRED`, `CLI_SIT`, `CLI_DES`, `CLI_CLAS`, `CLI_MAIL`, `CLI_OBS`, `CLI_CAD`, `ATU_USUA`, `CLI_FOTO`, `CLI_FANT`, `CLI_PAI`, `CLI_MAE`, `CLI_ENDCOB`, `CLI_BAICOB`, `CLI_CEPCOB`, `CLI_CIDCOB`, `CLI_ESTCOB`, `CLI_LOCTRAB`, `CLI_RENDA`, `CLI_CONJ`, `CLI_CONJLOCTRAB`, `CLI_CONJRENDA`, `CLI_CONJCPF`, `CLI_CONJCI`, `CLI_CONJNASC`, `CLI_REF1LOJ`, `CLI_REF1FON`, `CLI_REF1DES`, `CLI_REF1QT`, `CLI_REF1MEDCOM`, `CLI_REF1MEDPAG`, `CLI_REF2LOJ`, `CLI_REF2FON`, `CLI_REF2DES`, `CLI_REF2QT`, `CLI_REF2MEDCOM`, `CLI_REF2MEDPAG`, `CLI_FILIACAO`, `CLI_GRAUPAR`, `CLI_FILIACAOF`, `CLI_GRAUPARF`, `CLI_OBSFIN`, `CLI_TETO`, `CLI_LIS`, `CLI_INSCM`, `CLI_CADPRO`, `CLI_LIMITE`, `CLI_CUBO`, `CLI_VIDRO`, `CLI_INFO1`, `CLI_INFO2`, `CLI_INFO3`, `CLI_INFO4`, `CLI_NUM`, `CLI_COMPL`, `CLI_NUMCOB`, `CLI_COMPLCOB`, `CLI_CODIBGE`, `CLI_CODIBGECOB`, `CLI_PAIS`, `CLI_CPAIS`, `CLI_SUFRAMA`, `CLI_CODM`, `CID_COD`, `CID_CODCOB`, `CLI_SITE`, `CLI_CONJPROF`, `CLI_CONJFONE`, `ROT_COD`, `CLI_TIPOCR`, `CLI_TIPOCOMP`, `CLI_CNAE`, `CLI_DESCP`, `CLI_DESCS`, `CLI_TIPOCONTRIB`, `CLI_ORIGEM`, `BAN_COD`, `CLI_INTERMED`, `CLI_TP_ENTE_GOV`, `CLI_PERC_REDUTOR`

**Observações:** Deve ser tratada como cadastro principal de clientes; chave provável CLI_COD.

### `DSIAF011` — Entrada / Nota Fiscal de Entrada

**Finalidade:** Cabeçalho de entrada/nota de fornecedor.

**Chave provável:** `ENT_NOTA + FOR_COD`

**Campos conhecidos:** `ENT_NOTA`, `FOR_COD`, `ENT_SER`, `ENT_SE`, `CFOP_COD`, `ENT_EMIS`, `ENT_DATA`, `ENT_DESCON`, `ENT_DESACE`, `ENT_ACRE`, `ENT_BASE`, `ENT_VBASE`, `ENT_ISUB`, `ENT_VISUB`, `ENT_IPI`, `ENT_ISENTO`, `ENT_TOT`, `PRA_COD`, `ENT_PREST`, `ENT_ENTRA`, `ENT_DTENT`, `ENT_DUP1`, `ENT_DUP2`, `TRA_COD`, `TRA_VAL`, `TRA_VENC`, `TRA_DUP1`, `TRA_QUIT`, `ENT_CAD`, `ATU_USUA`, `ENT_HORA`, `ENT_CONTA`, `TRA_EMIS`, `TRA_MOD`, `TRA_SERIE`, `TRA_BASE`, `TRA_ICMS`, `TRA_CONHE`, `TRA_SEG`, `TRA_CFOP`, `ENT_MOD`, `TPRA_COD`, `TRA_PREST`, `ENT_CHAVE`, `TRA_VLPIS`, `TRA_VLCOFINS`, `IND_NAT_FRT`, `TRA_CST_PIS`, `TRA_CST_COFINS`, `NAT_BC_CRED`, `ENT_INF1`, `ENT_INF2`, `ENT_INF3`, `ENT_INF4`, `ENT_INF5`, `ENT_INF6`, `ENT_INF7`, `ENT_INF8`, `ENT_INF9`, `PRA_CODS`, `TIP_CODS`, `TPRA_CODS`, `TTIP_CODS`, `TRA_CHAVECTE`, `ENT_NC`, `TRA_TIPOCTE`, `TRA_DTENT`, `TRA_COD_CTA`, `VBCFCP`, `VFCP`, `VBCFCPST`, `VFCPST`, `ENT_VICMSDESON`

### `DSIAF012` — Entrada / Itens / Produtos

**Finalidade:** Itens/produtos de entrada/nota de fornecedor ou movimentação de entrada.

**Chave provável:** `ENT_NOTA + FOR_COD + PRO_COD`

**Campos conhecidos:** `ENT_NOTA`, `FOR_COD`, `PRO_COD`, `PRO_REF`, `PRO_NOME`, `PRO_EST`, `PRO_COMPRA`, `PRO_ICMS`, `PRO_IPI`, `PRO_CUSTO`, `PRO_MEDIO`, `PRO_RESUL`, `PRO_ATUAL`, `ENT_DATA`, `LIS_COD`, `ENT_HORA`, `ENT_SE`, `PRO_CUSTOANT`, `PRO_EST2`, `PRO_BARRA`, `PRO_ENT`, `PRO_SAI`, `CFOP_COD`, `PRO_GRADE`, `PRO_CODP`, `ENT_NOTAV`, `FOR_CODV`, `LIS_CODV`, `PRO_COMPRAITEM`, `PRO_DESCITEM`, `PRO_DESC`, `PRO_FRETE`, `PRO_UNI`, `PRO_TIPO`, `PRO_GEN`, `PRO_CF`, `PRO_NCM`, `PRO_CSOSN`

### `DSIAF013` — Cupom / Saída

**Finalidade:** Cabeçalho/resumo de cupom/saída.

**Campos conhecidos:** `SAI_PED`, `SAI_DATA`, `CLI_COD`, `CLI_NOME`, `VEN_COD`, `SAI_DESC`, `SAI_TOTAL`, `PRA_COD`, `TIP_COD`, `SAI_OBS`, `SAI_HORA`, `CUP_COO`, `ECF_NUM`, `CUP_SERIE`, `dados do cliente`, `MD5`

### `DSIAF014` — Cupom / Itens

**Finalidade:** Itens de venda/cupom simples.

**Campos conhecidos:** `SAI_PED`, `PRO_COD`, `PRO_BARRA`, `PRO_NOME`, `PRO_EST`, `PRO_VENDA`, `LIS_COD`, `grade/variações`, `SAI_DATA`, `SAI_CANCEL`, `PRO_UNI`, `ORC_FECHA`

### `DSIAF015` — Financeiro / Contas a Receber

**Finalidade:** Contas a receber/duplicatas do cliente.

**Campos conhecidos:** `REC_DUP`, `REC_BAN`, `CLI_COD`, `CLI_NOME`, `REC_HIST`, `VEN_COD`, `REC_LANC`, `PRA_COD`, `TIP_COD`, `REC_VENC`, `REC_BRUTO`, `REC_DESC`, `REC_VAL`, `VEN_BAI`, `CEN_COD`, `REC_DPAG`, `REC_DIAS`, `REC_JUROS`, `REC_PAG`, `SAI_GERA`, `SAI_SER`, `SAI_NOTA`, `CUP_PED`, `SER_SER`, `SER_NOTA`, `CUPS_PED`, `REC_CAD`, `ATU_USUA`, `SELECAO`, `TIPO_PAG`, `CAI_COD`, `SER_OS`, `REC_PARC`, `REC_TGERA`, `REC_FC`, `CAI_CODG`, `REC_IMPORT`, `REC_COMPENS`, `PEDIDO_GOURMET`, `PGTOPARCIAL`, `CODPGTOPARCIAL`, `REC_COMP`, `REC_TEF`, `VRTAXAGARCON`, `PERCTAXAGARCON`, `VRPGTOPARCIAL`, `REC_LANCH`, `ARQ_BOLETO`, `REC_MULTA`, `CTE_SER`, `CTE_NUM`, `REC_TEFAUT`, `REC_RECEB`, `REC_TROCO`, `CLI_ORIGEM`, `REC_BOL_BANCO`, `REC_NOSSO_NUMERO`

### `DSIAF033` — Fiscal / CFOP

**Finalidade:** Cadastro de CFOP/natureza fiscal.

**Chave provável:** `CFOP_COD`

**Campos conhecidos:** `CFOP_COD`, `CFOP_DESC`, `CFOP_REL`, `CFOP_OBS`, `ATU_USUA`, `CFOP_CAD`, `PRO_NAT_REC`, `PRO_STCOFINS`, `PRO_STCOFINS2`, `PRO_STIPI`, `PRO_STIPI2`, `PRO_STNF`, `PRO_STNF2`, `PRO_STPIS`, `PRO_STPIS2`, `CFOP_IBPT`, `CFOP_TRANS`, `CFOP_TRANSC`, `PRO_CSO`, `PRO_CSO2`

**Observações:** CFOP_IBPT aparece como 'S' em vários registros.

### `DSIAF036` — Fiscal / Nota Fiscal de Saída

**Finalidade:** Cabeçalho de saída/venda/NFe.

**Chave provável:** `SAI_SER + SAI_PED`

**Campos conhecidos:** `SAI_SER`, `SAI_PED`, `SAI_SE`, `SAI_DATA`, `CFOP_COD`, `CLI_COD`, `CLI_NOME`, `CLI_END`, `CLI_BAI`, `CLI_CEP`, `CLI_CID`, `CLI_EST`, `CLI_FONE`, `CLI_CPF`, `CLI_CGC`, `CLI_INSC`, `VEN_COD`, `SAI_CONTA`, `PRA_COD`, `TIP_COD`, `SAI_VISS`, `SAI_BASE`, `SAI_VBASE`, `SAI_IPI`, `SAI_ISENTO`, `SAI_DESACE`, `SAI_ACRE`, `SAI_MERC`, `SAI_DESC`, `SAI_TOTAL`, `TIPO_PAG`, `SAI_PREST`, `SAI_ENTRA`, `SAI_DUP1`, `SAI_DUP2`, `TRA_COD`, `TRA_CONHE`, `TRA_EMIS`, `TRA_PLACA`, `TRA_QUAN`, `TRA_ESP`, `TRA_PESO`, `TRA_SEG`, `TRA_FRETE`, `TRA_VENC`, `TRA_DUP1`, `SAI_CANCEL`, `SAI_CUPOM`, `SAI_IMP`, `SAI_CAD`, `ATU_USUA`, `SAI_HORA`, `TRA_MOD`, `TRA_SERIE`, `TRA_BASE`, `TRA_ICMS`, `TRA_CFOP`, `SAI_SUBS`, `SAI_VSUBS`, `SAI_ENTRE`, `PROF_COD`, `SAI_MOD`, `SAI_RECEB`, `SAI_TROCO`, `CAI_COD`, `CLI_NUM`, `SAI_PROTOC`, `SAI_RECIBO`, `SAI_LOTE`, `SAI_AUTORI`, `SAI_CHAVE`, `SAI_NC`, `SAI_SERREF`, `SAI_PEDREF`, `SAI_CHAVEREF`, `CID_COD`, `SAI_LOTECANC`, `SAI_PROTOCDTHRCANC`, `SAI_PROTOCCANC`, `SAI_DENEGADO`, `SAI_MOTCANC`, `SAI_CNF`, `SAI_PROCESSAMENTO`, `SAI_NCFE`, `TIPO_PGTO`, `SAI_CAD_USUARIO`, `CLI_CARTAO`, `CLI_NOME_ENT`, `CLI_CEL`, `CUP_SERIE`, `CUP_CAIXA`, `CUP_COO`, `CUP_DATA`, `CUP_PED`, `SAI_TPNFDEBITO`, `SAI_TPNFCREDITO`, `SAI_DPECPEND`, `SAI_VIBSUF`, `SAI_VIBSMUN`, `SAI_VCBS`, `SAI_VIS`

**Observações:** SAI_PED é o número da nota fiscal de saída. SAI_DPECPEND confirmado para contingência/DPEC com valores 'S' e 'N'.

### `DSIAF037` — Fiscal / Itens da Nota Fiscal de Saída

**Finalidade:** Itens detalhados da saída/NFe.

**Chave provável:** `SAI_SER + SAI_PED + item/produto`

**Campos conhecidos:** `SAI_SER`, `SAI_PED`, `PRO_COD`, `PRO_BARRA`, `PRO_NOME`, `PRO_VENDA`, `PRO_ICMS`, `PRO_IPI`, `SAI_DATA`, `LIS_COD`, `CFOP_COD`, `PRO_DESC`, `SAI_CANCEL`, `estoque`, `grade`, `veículo`, `importação`, `impostos`, `PIS/COFINS`, `ICMS`, `CEST`, `unidade tributável`, `pedido`, `kit`, `campos da reforma tributária`

**Observações:** Possui cerca de 180 campos, incluindo 144 campos PRO_.

### `DSIAF039` — Entrega / Retirada

**Finalidade:** Controle de entrega/recebimento de saída.

**Campos conhecidos:** `LIS_SAI_PED`, `LIS_COD`, `SAI_SER`, `SAI_PED`, `PRO_DTENT`, `PRO_ENTRE`, `PRO_ENTRECEBEU`, `PRO_ENTENTREGOU`, `USU_COD`, `USU_NOME`, `ATU_USUA`

### `DSIAF400` — PDV / NFC-e

**Finalidade:** Cabeçalho do PDV/venda balcão.

**Chave provável:** `ID`

**Campos conhecidos:** `ID`, `PDV_DATA`, `CFOP_COD`, `CLI_COD`, `CLI_NOME`, `CLI_END`, `CLI_NUM`, `CLI_BAI`, `CLI_CEP`, `CLI_CID`, `CLI_EST`, `CLI_FONE`, `CLI_CPF`, `CLI_CGC`, `CLI_INSC`, `VEN_COD`, `PRA_COD`, `TIP_COD`, `PDV_ACRE`, `PDV_DESC`, `PDV_MERC`, `PDV_TOTAL`, `TIPO_PAG`, `SAI_PREST`, `SAI_ENTRA`, `SAI_DTENT`, `SAI_DUP1`, `SAI_DUP2`, `SAI_CANCEL`, `SAI_IMP`, `PROF_COD`, `PDV_RECEB`, `PDV_TROCO`, `CAI_COD`, `PDV_CHAVE`, `PDV_CAD`, `PDV_HORA`, `ATU_USUA`, `PDV_STATUS`, `PDV_INFO`, `IDPEDIDO`, `IDORCAMENTO`, `SAI_SERIE`, `SAI_NOTA`, `SAI_INF1`, `SAI_INF2`, `SAI_INF3`, `SAI_INF4`, `SAI_INF5`, `SAI_INF6`, `SAI_INF7`, `SAI_INF8`, `SAI_INF9`, `SAI_RETI`, `SAI_ENTRE`, `SAI_PREVIDT`, `TERMINAL`, `PDV_IMPORTADO`, `USU_COD`, `PDV_DESC_PERCENTUAL`, `CLI_CEL`, `SAI_VIBSUF`, `SAI_VIBSMUN`, `SAI_VCBS`, `SAI_VIS`

### `DSIAF401` — PDV / Itens

**Finalidade:** Itens do PDV/venda balcão.

**Chave provável:** `ID`

**Campos conhecidos:** `ID`, `PDV_COD`, `PRO_COD`, `PDV_ITEM_ORDER`, `PDV_ITEM_DATA`, `PDV_ITEM_HORA`, `PRO_UNI`, `PRO_BARRA`, `PRO_NOME`, `PRO_VENDA`, `PRO_VENDAOLD`, `PRO_VENDAOLDT`, `PRO_VENDAITEM`, `PRO_DESC`, `PDV_ITEM_QUANT`, `CFOP_COD`, `PRO_CSOSN`, `PRO_ST2`, `PRO_STPIS2`, `PRO_STCOFINS2`, `PRO_CEST`, `PDV_ITEM_CANCELADO`, `PRO_CREDSN`, `PRO_IPI`, `PRO_REDV`, `PRO_ICMS`, `PRO_PAUTA`, `PRO_PAUTAALIQ`, `PRO_MVAST`, `PRO_CF`, `PRO_EST2`, `SAI_ORCV`, `LIS_CODORI`, `PRO_GRADE`, `PRO_GRCOR`, `TEM_KIT`, `SAI_PEDV`, `PRO_DESCITEM`, `SAI_STATUSENTREGA`, `PRO_FCP`, `PRO_NAT_REC`, `PRO_PIS`, `PRO_COFINS`, `PRO_QTRIB`, `PRO_VUNTRIB`, `PRO_UTRIB`, `PRO_VDESC`, `PRO_LOTVALID`, `PRO_TEMPROMOCAO`, `PRO_DESCOLD`, `PRO_DESCITEMOLD`, `KIT_ITEMNFE`, `KIT_ITEM_ORDER`, `campos IBS/CBS/IS`

### `DSIAF402` — PDV / Financeiro

**Finalidade:** Financeiro/prestações do PDV.

**Campos conhecidos:** `ID`, `PDV_COD`, `PDV_PREST_DATA`, `PDV_PREST_VAL`, `CLI_COD`, `TIP_COD`, `BAN_COD`, `CHE_AGE`, `CHE_CON`, `CHE_SER`, `CHE_CHE`, `CHE_CLICOD`, `CHE_CLI`, `CHE_CPF`, `CHE_CNPJ`, `CHE_HIST`, `CHE_NOMETERC`, `CHE_TERC`, `PDV_PREST_TEFAUT`, `REC_TEF`, `REC_COMP`, `TEF_CONFIRMADO`, `TEF_CONTROLE`, `PRA_IDPAGTO`, `PRA_BANDCARTAO`, `CAI_COD`, `USU_COD`, `VEN_COD`, `PDV_PREST_ALTERADO`

### `DSIAF504` — Clientes

**Finalidade:** Provável dependentes do cliente.

**Campos conhecidos:** `CLI_COD`

**Observações:** Estrutura completa pendente.

### `DSIAF506` — Clientes

**Finalidade:** Provável endereços adicionais do cliente.

**Campos conhecidos:** `CLI_COD`

**Observações:** Estrutura completa pendente.

### `DSIAF_API_RETORNO` — Fiscal / API

**Finalidade:** Retorno da API fiscal com NCM/ICMS/PIS/COFINS/CFOP/CEST.

**Observações:** Possui grande volume de campos fiscais; estrutura detalhada pendente.

### `DSIAF_API_HISTORICO` — Fiscal / API

**Finalidade:** Histórico fiscal com ICMS, NCM, PIS, COFINS, ICMSCST, CSOSN, CFOP e CEST.

**Observações:** Estrutura detalhada pendente.

### `DSIAF172` — Fiscal / NFe

**Finalidade:** Provável controle/importação de NFe.

**Campos conhecidos:** `NFE_CHAVE`, `NFE_SERIE`, `NFE_NUMERO`, `NFE_CNPJ`, `NFE_SIT`

### `DSIAF140` — Produtos / Grade / PDV

**Finalidade:** Tabela relacionada à grade de produtos; citada em atendimento do erro “Produto não cadastrado no PDV”.

**Campos conhecidos:** `PRO_COD`

**Observações:** Usuário informou que alguns produtos podem ser jogados na tabela 140. Se cliente não usa módulo Grade, remoção dos registros relacionados pode fazer os itens voltarem a constar no PDV. Confirmar estrutura real antes de qualquer comando.

### `DSIAF136` — Financeiro / Caixa Diário / Transferência

**Finalidade:** Registra transferências entre caixas na aba Caixa Diário > Transferência.

**Chave provável:** `TRANS_COD`

**Campos conhecidos:** `TRANS_COD`, `CAI_COD`, `CAI_DATA`, `CAI_HIST`, `CAI_VAL`, `CEN_COD`, `CAI_COD2`, `CAI_DATA2`, `CAI_HIST2`, `ATU_USUA`

### `DSIAF080` — Configurações / Impressoras

**Finalidade:** Cadastro/configuração de padrões de impressoras e comandos de impressão.

**Campos conhecidos:** `Código`, `Descrição`, `Liga impressão Comprimida`, `Desliga impressão Comprimida`, `Liga impressão Expandida`, `Desliga impressão Expandida`, `Espaçamento de linha 1/6`, `Espaçamento de linha 1/8`, `Porta`, `Corte de Papel`

**Observações:** Tabela vinculada à tela Impressoras; campos reais do banco ainda precisam de confirmação técnica.

### `DSIAF081` — Configurações / Parametrização Formulários

**Finalidade:** Parametrização de formulários de impressão, layouts, portas e comandos.

**Campos conhecidos:** `Código`, `Título`, `Impressora`, `Comandos`, `Máximo de linhas`, `Número de vias`, `Formulário padrão`, `Portas por usuário/computador`

**Observações:** Tabela vinculada à tela Parametrização Formulários; campos reais do banco ainda precisam de confirmação técnica.

### `DSIAF009` — Fornecedores

**Finalidade:** Cadastro principal de fornecedores no SIAFLOJA.FDB.

**Chave provável:** `FOR_COD`

**Campos conhecidos:** `FOR_COD`, `FOR_NOME`, `FOR_RAZAO`, `FOR_CPF`, `FOR_CGC`, `FOR_FONE`, `FOR_CEL`, `FOR_MAIL`, `FOR_CID`, `FOR_END`, `FOR_BAI`, `FOR_CEP`

### `DSIAF030` — Produtos / Fornecedor / Referências

**Finalidade:** Tabela usada para vínculos/referências de produtos, especialmente referência de fornecedor e importação/vínculo por referência.

**Chave provável:** `pendente_validacao`

**Campos conhecidos:** `PRO_COD`, `FOR_COD`, `PRO_REF`, `referência de fornecedor - nomes exatos pendentes de validação`

**Observações:** Quando houver vínculo/referência incorreta de produto, validar DSIAF030 antes de excluir ou alterar. Usar backup, SELECT prévio e WHERE específico.

---

## 28. Relacionamentos conhecidos

### Cliente como eixo comercial e financeiro

**Tabela Base:** `DSIAF010`

**Campo Base:** `CLI_COD`

**Relaciona Com:** `DSIAF015`, `DSIAF036`, `DSIAF400`, `DSIAF402`, `DSIAF504`, `DSIAF506`

**Uso Suporte:** `Localizar vendas/notas por cliente`, `Conferir contas a receber`, `Conferir cadastro fiscal do cliente`, `Verificar bloqueio/limite/classe`, `Conferir prestações de PDV`

### Produto como eixo de estoque, fiscal e vendas

**Tabela Base:** `DSIAF006`

**Campo Base:** `PRO_COD`

**Relaciona Com:** `DSIAF012`, `DSIAF014`, `DSIAF037`, `DSIAF401`

**Uso Suporte:** `Conferir estoque`, `Conferir preço`, `Conferir NCM/CEST/tributação`, `Rastrear movimentação/venda`, `Conferir itens de nota e PDV`

### NF-e de saída

**Cabecalho:** `DSIAF036`

**Itens:** `DSIAF037`

**Campos Chave:** `SAI_SER`, `SAI_PED`

**Uso Suporte:** `Buscar nota pelo número`, `Conferir chave/protocolo/lote/autorização`, `Verificar contingência pelo SAI_DPECPEND`, `Conferir cliente e itens`, `Conferir fiscal do item`

### PDV / NFC-e

**Cabecalho:** `DSIAF400`

**Itens:** `DSIAF401`

**Financeiro:** `DSIAF402`

**Campos Chave:** `ID`, `PDV_COD`

**Uso Suporte:** `Localizar venda balcão`, `Conferir itens do PDV`, `Conferir prestações`, `Conferir chave NFC-e`, `Verificar status/cancelamento`

### Entrada de fornecedor

**Cabecalho:** `DSIAF011`

**Itens:** `DSIAF012`

**Campos Chave:** `ENT_NOTA`, `FOR_COD`

**Uso Suporte:** `Conferir lançamento de entrada`, `Conferir produtos da entrada`, `Conferir atualização de custo/estoque`, `Conferir chave da NF de entrada`

### Usuários, grupos e permissões

**Usuarios:** `DSIAF050`

**Grupos:** `DSIAF053`

**Permissoes:** `DSIAF051`

**Programas:** `DSIAF052`

**Campos Chave:** `USU_COD`, `GRU_USU`, `PROG_DESC`

**Uso Suporte:** `Usuário sem acesso`, `Usuário não consegue incluir/alterar/excluir/imprimir`, `Conferir grupo do usuário`, `Conferir permissões por programa`

### Impressoras, formulários e etiquetas

**Elementos:** `Configurações do Sistema > Impressoras`, `Configurações do Sistema > Parametrização Formulários`, `Relatórios > Diversos > Etiquetas`

**Uso Suporte:** `Diagnosticar etiqueta que não imprime, trava, sai em preview, usa modelo errado ou apresenta layout desalinhado.`, `Conferir padrão de impressora, formulário, portas por computador/usuário e layout.`

### Contas a Receber e duplicatas de clientes

**Tabela Base:** `DSIAF015`

**Campo Base:** `REC_DUP`

**Relaciona Com:** `DSIAF010`, `DSIAF036`, `DSIAF400`, `Caixa Diário`, `Tipos de Venda`, `Tipos de Pagamento`

**Uso Suporte:** `Localizar duplicata.`, `Baixar ou retirar baixa.`, `Conferir juros/multa/desconto.`, `Conferir vínculo com venda/nota/cupom.`, `Conferir lançamento no fluxo de caixa.`

### Caixa Diário Transferência

**Tabela Base:** `DSIAF136`

**Campos Chave:** `TRANS_COD`, `CAI_COD`, `CAI_COD2`, `CAI_DATA`, `CAI_DATA2`, `CAI_VAL`, `CEN_COD`, `ATU_USUA`

**Relaciona Com:** `DSIAF017`, `DSIAF018`, `DSIAF008`, `DSIAF024`

**Uso Suporte:** `Auditar transferências entre caixas`, `Verificar usuário que lançou/alterou`, `Conferir origem, destino, data e valor`

### Cadastro do cliente em rejeições fiscais

**Tabela Base:** `DSIAF010`

**Campo Base:** `CLI_COD`

**Campos Chave:** `CLI_EST`, `CLI_TIPOCOMP`, `CLI_TIPOCONTRIB`, `CLI_CPF`, `CLI_CGC`, `CLI_CODIBGE`

**Relaciona Com:** `DSIAF036`, `DSIAF037`, `DSIAF400`, `DSIAF401`

**Uso Suporte:** `Rejeição 732 em nota para cliente de outro estado`, `Conferir Tipo de Comprador e UF antes de alterar produto/CFOP`

### Tipo de Venda/Pagamento como eixo do financeiro e caixa

**Tabelas Base:** `DSIAF025`, `DSIAF026`

**Relaciona Com:** `DSIAF015`, `DSIAF016`, `DSIAF017`, `DSIAF018`, `DSIAF035`, `DSIAF036`, `DSIAF400`, `DSIAF402`

**Uso Suporte:** `Venda não gerou duplicata`, `Venda/nota caiu no caixa errado`, `Baixa financeira incorreta`, `Pedido importado para NF-e gerou financeiro indevido`, `Comissão/estoque/contas a receber/pagar com comportamento errado`

### Empresa Licenciada como eixo de configuração fiscal

**Tabela Base:** `DSIAF001/DSIAF095 e parâmetros relacionados`

**Relaciona Com:** `NF-e`, `NFC-e`, `SPED PIS/COFINS`, `SPED Fiscal`, `Monitor Fiscal`, `Certificado`, `CSC/Token`, `Regime Tributário`, `Módulos`

**Uso Suporte:** `NF-e/NFC-e não habilitada`, `Ambiente/certificado incorreto`, `SPED não gera registros`, `Reforma Tributária não aparece`, `DANFE/XML por e-mail não envia`

### Cadastros fiscais auxiliares de CFOP, Natureza da Receita, Serviço e IBS/CBS

**Telas Base:** `CFOP`, `Natureza da Receita`, `Código Serviço SPED`, `Classificação IBS/CBS`

**Relaciona Com:** `Produtos`, `Nota Fiscal de Entrada`, `Nota Fiscal de Saída`, `Monitor Fiscal`, `SPED`, `Reforma Tributária`

**Uso Suporte:** `Rejeições fiscais`, `SPED PIS/COFINS`, `SPED Fiscal`, `PIS/COFINS/Nat. Rec.`, `IBS/CBS/Classe Tributária`, `CFOP/CST/CSOSN incompatível`

### Usuários, grupos e permissões detalhadas por Grupo X Programas

**Usuarios:** `DSIAF050`

**Grupos:** `DSIAF053`

**Permissoes:** `DSIAF051`

**Programas:** `DSIAF052`

**Campos Chave:** `USU_COD`, `USU_NOME`, `GRU_USU`, `GRU_DUSU`, `PROG_MOD`, `PROG_IND`, `PROG_DESC`

**Campos Permissao:** {'PROG_ACE': 'Acesso', 'PROG_INC': 'Inclusão', 'PROG_ALT': 'Alteração', 'PROG_EXC': 'Exclusão', 'PROG_IMP': 'Impressão'}

**Fluxo Diagnostico:** `Identificar o usuário em DSIAF050.`, `Verificar o GRU_USU vinculado ao usuário.`, `Conferir a descrição do grupo em DSIAF053.`, `Pesquisar a rotina/programa na DSIAF051 por PROG_DESC, PROG_MOD ou PROG_IND.`, `Validar se a permissão necessária está como S em PROG_ACE/INC/ALT/EXC/IMP.`, `Se alterar pela tela, acessar Arquivos > Controle de Acesso > Grupos X Programas, marcar a permissão e gravar.`

**Uso Suporte:** `Usuário sem acesso a uma tela.`, `Botão bloqueado ou desabilitado.`, `Usuário não consegue incluir, alterar, excluir ou imprimir.`, `Rotina aparece para um usuário e não para outro.`, `Permissão específica de produto, cliente, fiscal, contas a receber ou PDV NFC-e.`

### Fornecedor e referência de produto

**Tabela Base:** `DSIAF009`

**Campo Base:** `FOR_COD`

**Relaciona Com:** `DSIAF002`, `DSIAF011`, `DSIAF012`, `DSIAF030`, `DSIAF006`

**Uso Suporte:** `Conferir fornecedor de NF de entrada`, `Validar vínculos de referência de produto por fornecedor`, `Corrigir produto vinculado incorretamente em importação de XML/NF-e.`

### Campos de troco em NF-e, PDV e Contas a Receber

**Campos Chave:** `DSIAF036.SAI_TROCO`, `DSIAF400.PDV_TROCO`, `DSIAF015.REC_TROCO`

**Uso Suporte:** `Diagnosticar divergência de troco`, `Separar origem NF-e x PDV x Contas a Receber`, `Evitar correções em tabela errada.`

---

## 29. Biblioteca de SQL conhecida

Os SQLs abaixo devem ser importados como templates com nível de risco. Os comandos de correção não devem ser liberados no MVP.

| ID | Título | Tipo/Risco | Tabelas |
|---|---|---|---|
| `sql_consultar_nfe_contingencia_por_sai_ped` | Consultar NF-e em contingência por número | `consulta` | `DSIAF036` |
| `sql_retirar_nfe_contingencia_por_sai_ped` | Retirar NF-e de contingência | `correcao` | `DSIAF036` |
| `sql_buscar_nfe_saida_por_numero` | Buscar NF-e de saída por número | `consulta` | `DSIAF036` |
| `sql_buscar_itens_nfe_saida_por_numero` | Buscar itens de NF-e de saída por número | `consulta` | `DSIAF037` |
| `sql_buscar_cliente_por_codigo_nome_documento` | Buscar cliente por código, nome, CPF ou CNPJ | `consulta` | `DSIAF010` |
| `sql_buscar_produto_por_codigo_barra_nome` | Buscar produto por código, barra ou nome | `consulta` | `DSIAF006` |
| `sql_relatorio_produto_nfe_saida_por_periodo` | Consultar vendas de produto em NF-e de saída por período | `consulta` | `DSIAF036`, `DSIAF037` |
| `sql_manutencao_zerar_estoque_produtos` | Exemplo documental: zerar estoque de produtos | `manutencao` | `DSIAF006` |
| `sql_manutencao_produtos_st_por_grupo` | Exemplo documental: alterar PRO_ST por grupo | `manutencao` | `DSIAF006` |
| `sql_manutencao_ref_igual_barra` | Exemplo documental: copiar código de barras para referência | `manutencao` | `DSIAF006` |
| `sql_verificar_produto_tabela_grade_140` | Verificar produto na tabela de grade 140 | `consulta` | `DSIAF140` |
| `sql_remover_produto_grade_140_com_cuidado` | Remover produto da tabela de grade 140 quando cliente não usa grade | `correcao_perigosa` | `DSIAF140` |
| `sql_consultar_transferencias_caixa_por_usuario` | Consultar transferências entre caixas por usuário | `consulta` | `DSIAF136` |
| `sql_consultar_grade_produto_tabela_140_antes_delete` | Consultar registros de grade do produto antes de DELETE | `consulta_segura` | `DSIAF140` |
| `sql_diagnostico_permissoes_usuario_grupo_programa` | Diagnosticar permissões do usuário por grupo e programa | `consulta` | `DSIAF050`, `DSIAF053`, `DSIAF051` |
| `sql_buscar_permissao_por_programa_grupo` | Buscar permissão por descrição de programa e grupo | `consulta` | `DSIAF051`, `DSIAF053` |
| `sql_validar_voutros_total_nota` | Somar VOutros da nota pelos itens | `consulta` | `DSIAF037` |
| `sql_validar_voutros_total_nota_serie` | Somar VOutros da nota por série | `consulta` | `DSIAF037` |
| `sql_listar_itens_nfe_para_ajuste_voutros_sem_icms` | Listar itens da NF-e para escolher item sem ICMS antes de ajustar VOutros | `consulta` | `DSIAF037` |
| `sql_ajustar_voutros_diminuir_centavo` | Diminuir 0,01 do VOutros de item específico | `correcao_sensivel` | `DSIAF037` |
| `sql_ajustar_voutros_aumentar_centavo` | Aumentar 0,01 do VOutros de item específico | `correcao_sensivel` | `DSIAF037` |
| `sql_consultar_nfe_saida_por_periodo_intervalo_numero` | Consultar NF-e de saída por período e intervalo de numeração | `consulta` | `DSIAF036` |
| `sql_consultar_nfe_saida_sem_chave_por_data` | Consultar NF-e de saída sem chave a partir de uma data | `consulta` | `DSIAF036` |
| `sql_consultar_nfe_contingencia_por_data` | Selecionar notas em contingência por data | `consulta` | `DSIAF036` |
| `sql_limpar_chave_nfe_contingencia_por_data` | Limpar chave de notas em contingência por data | `correcao_sensivel` | `DSIAF036` |
| `sql_tirar_nfe_contingencia_por_data` | Tirar notas da contingência por data | `correcao_sensivel` | `DSIAF036` |
| `sql_limpar_referencia_origem_devolucao_dsiaf037` | Limpar referência de nota original em erro de devolução | `correcao_sensivel` | `DSIAF037` |
| `sql_validar_referencia_origem_devolucao_dsiaf037` | Validar referência de origem em itens de devolução | `consulta` | `DSIAF037` |
| `sql_corrigir_cst_dsiaf037_cfop_5405` | Corrigir CST do item para CFOP 5.405 | `correcao_sensivel` | `DSIAF037` |
| `sql_corrigir_csosn_produto_cfop_5405` | Corrigir CSOSN do produto para CFOP 5.405 | `correcao_sensivel` | `DSIAF006` |
| `sql_mudar_ncm_por_grupo_produtos` | Alterar NCM por grupo de produtos | `correcao_sensivel` | `DSIAF006` |
| `sql_validar_produtos_por_grupo_ncm` | Validar produtos por grupo antes de alterar NCM | `consulta` | `DSIAF006` |
| `sql_corrigir_sai_troco_notas_contingencia` | Limpar SAI_TROCO em notas com DPEC/contingência pendente | `correcao_sensivel` | `DSIAF036` |
| `sql_limpar_sai_dpecpend_todas_notas_alto_risco` | Limpar SAI_DPECPEND de todas as notas (alto risco) | `correcao_altissimo_risco` | `DSIAF036` |
| `sql_limpar_gtin_todos_produtos_alto_risco` | Limpar PRO_GTIN de todos os produtos (alto risco) | `correcao_altissimo_risco` | `DSIAF006` |
| `sql_fechar_todos_pedidos_pendentes` | Fechar todos os pedidos pendentes/abertos | `correcao_sensivel` | `DSIAF057` |
| `sql_consultar_pedidos_pendentes` | Consultar pedidos pendentes/abertos | `consulta` | `DSIAF057` |
| `sql_analisar_erro_pis_cofins_nfe_saida` | Analisar erro de PIS/COFINS em NF-e de saída | `consulta` | `DSIAF037` |
| `sql_colocar_todos_clientes_classe_r_alto_risco` | Colocar todos os clientes na classe R (alto risco) | `correcao_altissimo_risco` | `DSIAF010` |
| `sql_atualizar_terminal_pdv_por_id` | Atualizar terminal no PDV por ID | `correcao_sensivel` | `DSIAF400` |
| `sql_alterar_status_pdv_por_id` | Alterar status do PDV por ID | `correcao_sensivel` | `DSIAF400` |
| `sql_reforma_tributaria_preencher_campos_produtos_ibs_cbs` | Preencher campos provisórios IBS/CBS em todos os produtos | `correcao_sensivel` | `DSIAF006` |
| `sql_validar_produtos_estoque_zerado` | Validar produtos com estoque zerado antes de desativar | `consulta` | `DSIAF006` |
| `sql_desativar_produtos_estoque_zerado` | Desativar produtos com estoque zerado | `correcao_sensivel` | `DSIAF006` |
| `sql_desativar_produtos_estoque_nulo_ou_zerado` | Desativar produtos com estoque nulo ou zerado | `correcao_sensivel_opcional` | `DSIAF006` |
| `sql_validar_nfe_total_pagamento_sai_recebe` | Validar total do pagamento menor que total da nota na DSIAF036 | `consulta` | `DSIAF036` |
| `sql_corrigir_nfe_sai_recebe_total_nota` | Corrigir SAI_RECEBE para igualar ao total da nota | `correcao` | `DSIAF036` |
| `sql_validar_referencia_produto_dsiaf030` | Validar referência de produto na DSIAF030 antes de exclusão/alteração | `consulta` | `DSIAF030` |
| `sql_excluir_referencia_produto_dsiaf030_com_cuidado` | Excluir referência incorreta de produto na DSIAF030 | `correcao` | `DSIAF030` |
| `sql_consultar_permissao_baixa_retroativa_contas_receber` | Consultar permissão de baixa retroativa em Contas a Receber | `consulta` | `DSIAF050`, `DSIAF051`, `DSIAF053` |
| `sql_consultar_permissao_contas_receber_exclusao_prog_exc` | Consultar permissão de exclusão em Contas a Receber por grupo | `consulta` | `DSIAF051`, `DSIAF053` |

### Classificação sugerida

| Tipo atual | Tratamento na ferramenta |
|---|---|
| consulta / consulta_segura | Pode entrar no módulo de leitura após validação |
| correcao | Operação controlada, prévia e auditoria |
| correcao_sensivel | Exigir backup e confirmação reforçada |
| correcao_altissimo_risco | Bloqueada por padrão; somente modo técnico autorizado |
| manutencao | Apenas documentação até validação do procedimento |

---

## 30. Catálogo de soluções conhecidas

### Banco de Dados / Firebird / Ferramentas

- `banco_firebird_dbeaver_unsupported_ods_fdb` — Erro ao abrir banco .FDB no DBeaver por incompatibilidade de estrutura/ODS ou driver Firebird

### Cadastros / Clientes

- `cadastros_diversos_clientes_validacoes` — Validações e bloqueios em cadastro de clientes

### Cadastros / Tipos de Pagamento

- `cadastros_tipos_pagamento` — Configurar Tipos de Pagamento

### Cadastros / Tipos de Vendas

- `cadastros_tipos_venda` — Configurar Tipos de Venda

### Caixa Diário / Permissões / Atualização

- `permissoes_consultar_lancamentos_outros_caixas_atualizacao_versao` — Usuário sem permissão para consultar lançamentos de outros caixas

### Comercial / Financeiro / Comissão

- `comercial_financeiro_comissao_parametros_relatorios` — Entender, configurar ou validar cálculo de comissão no SIAF.

### Configurações / Empresa Licenciada / Email

- `empresa_licenciada_config_email_danfe_xml` — DANFE/XML não envia por e-mail ou e-mail fiscal não chega

### Entrada / Nota Fiscal de Entrada

- `entrada_nota_fiscal_entrada` — Lançar Nota Fiscal de Entrada

### Entrada / Nota Fiscal de Entrada / ICMS

- `entrada_nota_fiscal_diferenca_icms_acrescimo_minimo` — Nota de entrada com diferença mínima de ICMS por arredondamento

### Estoque / Reprocessa Produtos / Nota Fiscal de Entrada

- `estoque_zerar_estoque_positivo_negativo_inv` — Zerar produtos com estoque positivo ou negativo.

### Financeiro / Boletos / Contas a Receber

- `financeiro_boletos_configuracao_emissao_segunda_via` — Configurar, emitir, visualizar ou reemitir boleto/duplicata no SIAF.

### Financeiro / Cadastros / Tipos de Pagamentos

- `financeiro_tipos_pagamentos_cadastro_comportamentos` — Cadastrar/configurar tipo de pagamento e seus comportamentos no SIAF.

### Financeiro / Comercial / Tipos de Vendas

- `financeiro_tipos_vendas_configuracao_dfe_pos_pix` — Cadastrar/configurar tipo de venda para parcelas, vencimento, juros, desconto, DF-e, cartão/POS e Pix.

### Financeiro / Contas a Receber / Permissões

- `contas_receber_baixa_retroativa_permissao_grupos_programas` — Usuário não consegue baixar duplicata com data retroativa
- `contas_receber_bloquear_exclusao_permissao_prog_exc` — Bloquear exclusão de contas a receber para determinado grupo

### Financeiro / Funcionários

- `lancamentos_controle_funcionarios` — Controle de Funcionários para débitos, créditos, vales e adiantamentos

### Financeiro / NF-e / PDV / Contas a Receber

- `financeiro_zerar_troco_campos_documentos` — Conferir/zerar troco gravado em documentos ou contas quando houver divergência

### Financeiro / Tipos de Pagamento e Tipos de Venda

- `financeiro_tipo_pagamento_venda_comportamento_indevido` — Venda, pedido ou nota gerou comportamento financeiro/estoque/caixa indevido

### Fiscal / CFOP

- `fiscal_cfop_cadastro_padrao_tributacao` — CFOP, natureza da operação ou tributação padrão incorreta na nota/SPED

### Fiscal / Certificado Digital / NFC-e

- `fiscal_certificado_a3_erro_ssl_tls_2146893815` — Certificado digital A3 apresenta erro interno -2146893815 ou 2148073481 ao emitir NFC-e.

### Fiscal / Financeiro / Nota Fiscal de Saída

- `fiscal_nfe_troco_ajuste_desconto_item_pro_vdesc` — Corrigir ausência de troco ou divergência de valor ajustando desconto por item.

### Fiscal / NF-e

- `fiscal_nfe_contingencia_sai_dpecpend` — Nota fiscal de saída presa em contingência/DPEC pendente
- `fiscal_nfe_substituicao_tributaria` — Emitir NF-e com substituição tributária
- `fiscal_nfe_ajuste_imposto` — Emitir Nota Fiscal de Ajuste de Imposto
- `fiscal_nfe_complementar_valor` — Emitir Nota Fiscal Complementar de Valor
- `fiscal_nfe_complementar_impostos_st_ipi` — Emitir Nota Fiscal Complementar de Impostos/ST/IPI
- `fiscal_nfe_carta_correcao_cce` — Emitir Carta de Correção Eletrônica - CC-e
- `fiscal_nfe_devolucao` — Emitir nota de devolução
- `fiscal_nfe_estorno_devolucao` — Nota de estorno de devolução
- `fiscal_nfe_remessa_garantia` — Nota de remessa de garantia
- `fiscal_nfe_rejeicao_732_cfop_exterior_iddest` — Rejeição 732 - CFOP de operação com Exterior e idDest <> 2

### Fiscal / NF-e / Devolução / IPI

- `fiscal_ipi_devolvido_danfe_empresa_comercial` — Valor de IPI não aparece destacado no campo específico de IPI no DANFE em devolução feita por empresa comercial.

### Fiscal / NF-e / Inutilização de Numeração

- `fiscal_nfe_inutilizar_numeracao_emitida_errada` — Excluir e inutilizar numeração de NF-e emitida errada.

### Fiscal / NF-e / NFC-e

- `fiscal_rejeicao_386_cfop_csosn` — Rejeição 386 - CFOP não permitido para o CSOSN informado
- `fiscal_cancelamento_documento_monitor_fiscal` — Cancelar documento fiscal pelo Monitor Fiscal

### Fiscal / NF-e / NFC-e / Reforma Tributária

- `fiscal_reforma_tributaria_rejeicao_818_atualiza_reforma` — Rejeição 818 - Total da BC do IBS e da CBS difere da soma dos itens

### Fiscal / NF-e / Nota Fiscal de Saída

- `fiscal_nfe_saida_existe_cupom_importar_nfce` — Emitir NF-e modelo 55 quando já existe NFC-e/cupom modelo 65 sem duplicar valores ou estoque
- `fiscal_nfe_total_pagamento_menor_sai_recebe` — Erro: Total do pagamento está menor que o total da nota

### Fiscal / NF-e / Nota Referenciada

- `fiscal_nfe_nfref_modelo_invalido_chave_acesso_ctrl_shift_f8` — Falha na validação da nota: TAG ide/NFref/refNFe - Modelo de documento inválido

### Fiscal / NF-e / VOutros

- `fiscal_nfe_voutros_ajuste_centavo_item_sem_icms` — Ajustar diferença de centavos no VOutros da Nota Fiscal de Saída escolhendo item sem ICMS.

### Fiscal / Nota Fiscal de Entrada

- `fiscal_nfe_entrada_produto_sem_cadastro_shift_f1` — Lançar Nota Fiscal de Entrada com produto de uso/consumo, ativo imobilizado ou brinde não destinado à revenda.

### Fiscal / Nota Fiscal de Entrada / Importação de NF-e

- `fiscal_nfe_entrada_produto_vinculado_errado_referencia_fornecedor` — Produtos sendo vinculados/filtrados incorretamente ao importar NF-e de entrada.

### Fiscal / Nota Fiscal de Entrada / Produtos

- `fiscal_nfe_entrada_serie_inv_nao_atualiza_custo` — Nota Fiscal de Entrada não atualiza custo/valor dos produtos

### Fiscal / Nota Fiscal de Entrada / Uso e Consumo

- `fiscal_nfe_entrada_uso_consumo_xml_inv_sem_debito` — Orientar entrada de nota de uso e consumo, ativo imobilizado ou produto não destinado à revenda.

### Fiscal / Nota de Devolução / Anulação

- `fiscal_anulacao_saida_devolucao_por_entrada_normal` — Anular nota quando a nota original foi SAÍDA - DEVOLUÇÃO

### Fiscal / Nota de Devolução / ICMS

- `fiscal_nota_devolucao_base_icms_ctrl_shift_f7_cso900` — Base de cálculo do ICMS não aparece na nota de devolução.

### Fiscal / Pedido / NF-e

- `fiscal_importacao_pedido_ja_importado_nfe_tipo_pagamento_especial` — Importação de pedido para NF-e quando o pedido já havia sido importado

### Fiscal / Reforma Tributária / IBS-CBS

- `fiscal_reforma_tributaria_atualizacao_campos_ibs_cbs` — Atualizar cliente e cadastros para contemplar a Reforma Tributária no SIAF.

### Indústria / Produção

- `industria_modulo_industria_fluxo_inicial` — Orientar ativação e fluxo inicial do Módulo Indústria no SIAF.

### PDV / Impressoras / Gaveta de Dinheiro

- `pdv_gaveta_impressora_nao_fiscal_comandos` — Configurar abertura de gaveta em impressora não fiscal e comandos ESC/POS.

### PDV / Produtos / Grade

- `pdv_produto_nao_cadastrado_tabela_grade` — Produto não cadastrado no PDV

### Produtos / Controle de Acesso

- `cadastro_produtos_familia_subfamilia_permissao_desativada` — Não era possível cadastrar Família/Subfamília no cadastro de produtos.

### Produtos / Estoque

- `estoque_inventario_estoque` — Gerar inventário de estoque
- `produtos_reprocessa_produtos` — Reprocessa Produtos para atualizar estoque/custos

### Produtos / Estoque / Movimento de Produtos

- `produtos_movimento_erro_sp_movimento_ibqsp_movimento` — Erro SP_MOVIMENTO ou IBQSP_MOVIMENTO ao consultar Movimento de Produtos.

### Produtos / Estoque / SQL

- `produtos_desativar_estoque_zerado_sql` — Desativar produtos com estoque zerado.

### Produtos / Referência / Importação NF-e

- `produtos_exclusao_referencia_dsiaf030` — Excluir referência incorreta de produto

### Proteção / Licenciamento

- `protecao_erros_licenciamento` — Erros de proteção/licenciamento

### Relatórios / Diversos / Etiquetas

- `etiquetas_siaf_nao_respondendo_ao_imprimir` — SIAFW não está respondendo ao tentar imprimir etiqueta

### Relatórios / Produtos / NF-e

- `relatorio_produto_nota_saida_mes` — Emitir relatório do mês de nota fiscal de saída de um produto

### Serviços / Ordem de Serviço

- `servicos_modulo_servico_os_fluxo_inicial` — Entender ativação, permissões e rotinas principais do Módulo de Serviço no SIAF.

### Suporte SIAFW / Impressoras

- `suporte_siafw_impressora_padrao_access_violation_printer_invalid` — Erro ao imprimir: Access Violation ou Printer Selected is not valid

### Suporte SIAFW / Instalação / Acesso

- `suporte_siafw_nao_abre_interbase_siafw_ads_computador` — SIAFW não abre ou não entra no sistema

### Suporte Windows / .NET / ASP.NET

- `windows_dotnet_temporary_aspnet_files_sem_permissao` — Erro de acesso/gravação na pasta Temporary ASP.NET Files

### TEF / PDV / Integração de Cartão

- `tef_indisponivel_todos_terminais_gsufr` — TEF fora/indisponível em todos os terminais.

### Terminais / Licenciamento / Rede

- `terminais_numero_maximo_conectados_loopback` — Erro: Número máximo de terminais conectados

---

## 31. Conhecimentos operacionais críticos já validados

- NF-e em contingência: DSIAF036, campo SAI_DPECPEND; qualquer correção exige SELECT, backup e filtro específico.
- NF-e de saída: cabeçalho DSIAF036 e itens DSIAF037, geralmente ligados por SAI_SER e SAI_PED.
- PDV/NFC-e: DSIAF400/401/402.
- Nota de entrada: DSIAF011/012 e prestações DSIAF002.
- Produtos: DSIAF006; fornecedor/referência DSIAF030; grade DSIAF140.
- Permissões: DSIAF050/051/052/053.
- Série INV pode impedir atualização de custo na entrada.
- Nota de uso e consumo pode utilizar procedimento específico de importação/entrada sem cadastro de produto normal, sujeito a validação fiscal.
- Referência de NF-e inválida pode estar relacionada à ausência de chave no documento referenciado.
- Anulação de SAÍDA–DEVOLUÇÃO foi orientada por ENTRADA–NORMAL com CFOP 1.949/2.949, sempre com validação fiscal/contábil.
- Alterações de estoque, fiscal, financeiro e documentos nunca devem ser tratadas como simples atualização de um único campo sem analisar vínculos.

---

## 32. Definition of Done da versão 1.0

- Executável Windows abre sem console e sem Python instalado.
- Compatibilidade comprovada com Firebird 2.5.7 32 bits.
- Conecta em SIAFLOJA e SIAFW local/remoto.
- Consultas não congelam a interface.
- Bases grandes são processadas em lotes.
- Consultas e relatórios principais estão validados em casos reais.
- Comparação entre lojas não altera dados.
- Operações controladas possuem prévia, backup, confirmação, transação, rollback e auditoria.
- Logs não expõem dados sensíveis.
- Testes automatizados e matriz de homologação aprovados.
- Documentação de instalação, uso, riscos e suporte concluída.
- CHANGELOG e versão do executável atualizados.

---

## 33. Fontes internas consolidadas

- `siaf_base_conhecimento_completa_v1_0.json`
- `03_tabelas_siafloja.json`
- `02_tabelas_siafw.json`
- `01_menus.json`
- `04_relacionamentos.json`
- `05_solucoes.json`
- `06_sqls.json`
- `07_parametros_documentos.json`
- `09_mapa_rapido_atendimento.json`
- Casos reais, prints, documentos e procedimentos consolidados na base v1.0.

> Observação final: a base de conhecimento contém informações com diferentes níveis de confiança. A ferramenta deve tratar o catálogo como referência e validar a estrutura real antes de qualquer consulta ou operação crítica.
