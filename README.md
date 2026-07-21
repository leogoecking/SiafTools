# SIAF Support Toolbox

Aplicação desktop Windows para descobrir com segurança um ambiente SIAF/Firebird e, após
validação, oferecer consultas de suporte em modo somente leitura.

As **Fases 0 a 8 estão concluídas e a Fase 9 está em homologação**. A entrega atual
cobre a fundação do repositório, a interface desktop, o SQLite interno, a descoberta
automática: arquitetura do processo, processos/serviços, Registro do Windows, configurações
próximas ao SIAF, bibliotecas cliente Firebird, conexões TCP e candidatos limitados a
`SIAFW.FDB` e `SIAFLOJA.FDB`.

Na página **Ambiente detectado**, o botão **Validar conexão** solicita usuário e senha apenas
para a tentativa atual, prepara os endpoints automaticamente e classifica a base pelo catálogo
antes de aceitá-la. A validação também exige Firebird 2.5.7 e ODS 11.2. **Opções avançadas** é
um fallback para ambientes que não puderam ser resolvidos automaticamente; se outra DLL já
estiver carregada, o aplicativo solicita uma reinicialização em vez de ignorar silenciosamente
a biblioteca selecionada. O diagnóstico técnico pode ser exportado pela mesma página com
caminhos mascarados e sem credenciais.

Depois de validar uma ou mais bases, o botão **Inspecionar estrutura** solicita a credencial
somente para a sessão atual e lê relações, campos, índices, chaves primárias, triggers,
procedures e generators. Cada base usa uma conexão Firebird própria, transação read-only e
leitura em lotes. O resultado fica em cache no SQLite e serve para bloquear templates cujos
requisitos de tabelas ou campos não estejam presentes. O cache possui um snapshot completo
vinculado à validação atual; uma nova validação o invalida e exige nova inspeção antes de
autorizar consultas.

Configurações do SIAF e do Firebird são lidas em UTF-8, UTF-16 ou CP1252 para preservar
caminhos acentuados de instalações antigas. Portas TCP observadas fora da faixa convencional
são correlacionadas com referências de base quando há evidência suficiente; caso contrário,
aparecem separadamente como candidatas para confirmação assistida.

Dados, logs e exportações são armazenados no perfil do usuário em
`%LOCALAPPDATA%\SIAF Support Toolbox`. A variável `SIAF_TOOLBOX_HOME` permite usar outro
diretório em desenvolvimento e testes. Os logs têm rotação automática e sanitização de
credenciais conhecidas.

O banco `data\siaf-support-toolbox.sqlite3` é criado automaticamente e mantém ambientes,
bases descobertas, perfis manuais de contingência, histórico, templates, cache de estrutura e
base de conhecimento. Ele não possui campo de senha; credenciais continuam restritas à sessão.

A interface possui menu lateral com as áreas previstas no roadmap, temas claro e escuro e
persistência de tamanho, posição, estado e última página. Validação e inspeção rodam fora da
thread da interface e cada worker abre sua própria conexão Firebird somente leitura. A página
**Consultas** executa somente templates validados, com parâmetros vinculados, `fetchmany`,
cancelamento nativo da operação Firebird quando suportado pela DLL e paginação em cache
temporário. Durante a execução, a tela mostra uma previsão de conclusão baseada no histórico
completo do mesmo template e da mesma base e mantém a opção de cancelamento disponível. A Fase
7 acrescenta buscas validadas
de produtos, clientes e fornecedores, painel de detalhes e exportação progressiva CSV/XLSX em
worker; datas e decimais preservam seus tipos no XLSX e prefixos de fórmula, inclusive caracteres
de controle e variantes Unicode, são neutralizados. Operações de escrita continuam fora da
entrega e bloqueadas pelo modo padrão.

A Fase 8 acrescenta consultas somente leitura de NF-e de saída, entradas de fornecedor e
PDV/NFC-e. Cabeçalhos, itens e pagamentos usam os relacionamentos comprovados no snapshot real,
exigem ao menos um filtro e exibem códigos de status exatamente como armazenados, sem inferir
significados fiscais ou operacionais. Datas são informadas e exibidas como `DD/MM/AAAA`.
Os templates padrão não aplicam corte fixo de registros: consultas extensas continuam sendo
lidas com `fetchmany`, gravadas no cache paginado e exportadas progressivamente. Filtros
obrigatórios permanecem ativos nas áreas operacionais, financeiras e de permissões. O cache
preserva uma reserva de 256 MB no disco e encerra a consulta com orientação específica antes
de consumir esse espaço. Resultados interrompidos que já possuam linhas são identificados como
parciais em tela, no histórico e no nome da exportação. Arquivos XLSX maiores que o limite de
1.048.576 linhas do Excel são divididos automaticamente em abas sucessivas.

A Fase 9 acrescenta consultas somente leitura de contas a receber, contas a pagar, caixa diário,
transferências, tipos de venda/pagamento e diagnóstico de permissões por usuário, grupo e
programa. Os templates financeiros exigem a `SIAFLOJA.FDB`; usuários e permissões exigem a
`SIAFW.FDB`. O campo `DSIAF050.USU_SENHA` é deliberadamente excluído das consultas e exportações.

## Requisito de arquitetura

O build homologado exige **Python 3.11 x86 (32 bits)**. É permitido executar os testes de
desenvolvimento em Python 64 bits, mas `scripts/check_runtime.py --require-x86` e o script de
build recusam esse ambiente para impedir a geração de um artefato com arquitetura incorreta.

## Preparação do ambiente x86

No PowerShell aberto com um Python 3.11 x86 explícito:

```powershell
C:\caminho\python-x86.exe -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts\check_runtime.py --require-x86
```

Não use apenas o nome `python` sem confirmar o executável e sua arquitetura.

## Executar

```powershell
$env:PYTHONPATH = "src"
python -m siaf_support_toolbox
```

A análise é executada fora da thread da interface. Falhas parciais são exibidas como avisos e
não encerram a aplicação.

## Testes e diagnóstico

```powershell
python -m pytest
python scripts\check_runtime.py
python scripts\diagnose.py --json
python scripts\ui_smoke.py
```

O diagnóstico de linha de comando não solicita nem registra credenciais. A exportação pela
interface mascara caminhos em campos próprios, DSNs, mensagens, comandos, valores do Registro,
variáveis de ambiente e compartilhamentos UNC; ainda assim, revise o JSON antes de anexá-lo a
tickets.

Para validar as bases descobertas sem colocar senha na linha de comando ou em arquivos:

```powershell
.\.venv\Scripts\python.exe scripts\probe_discovered_databases.py
```

O script solicita a credencial somente na sessão e executa apenas leitura de
`RDB$DATABASE` e metadados.

Também é possível abrir [Validar_Bases.cmd](Validar_Bases.cmd) com duplo clique. Essa versão
mantém a janela aberta e grava o resultado sem credenciais na pasta `exports`.

## Build de homologação

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build.ps1
```

O build é `onedir` e `windowed`. Validações em terminal remoto e bases reais são realizadas
como homologação de campo, diretamente no computador do cliente.

O primeiro artefato local é criado em:

```text
dist\SIAFSupportToolbox\SIAFSupportToolbox.exe
```
