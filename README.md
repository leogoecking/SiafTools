# SIAF Support Toolbox

Aplicação desktop Windows para descobrir com segurança um ambiente SIAF/Firebird e, após
validação, oferecer consultas de suporte em modo somente leitura.

As **Fases 0, 1, 2 e 3 estão concluídas** e a **Fase 4 está em homologação**. A entrega atual
cobre a fundação do repositório, a interface desktop, o SQLite interno e a descoberta
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

Dados, logs e exportações são armazenados no perfil do usuário em
`%LOCALAPPDATA%\SIAF Support Toolbox`. A variável `SIAF_TOOLBOX_HOME` permite usar outro
diretório em desenvolvimento e testes. Os logs têm rotação automática e sanitização de
credenciais conhecidas.

O banco `data\siaf-support-toolbox.sqlite3` é criado automaticamente e mantém ambientes,
bases descobertas, perfis manuais de contingência, histórico, templates, cache de estrutura e
base de conhecimento. Ele não possui campo de senha; credenciais continuam restritas à sessão.

A interface possui menu lateral com as áreas previstas no roadmap, temas claro e escuro e
persistência de tamanho, posição, estado e última página. A validação de conexão roda fora da
thread da interface e cada worker abre sua própria conexão Firebird somente leitura. Consultas
funcionais e operações de escrita ainda não fazem parte da entrega.

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
interface também mascara caminhos conhecidos; ainda assim, revise o JSON antes de anexá-lo a
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

O build inicial é `onedir` e `windowed`. A homologação ainda exige testes em Windows 10 e 11,
máquina sem Python, Firebird 2.5.7 x86, servidor local e terminal remoto.

O primeiro artefato local é criado em:

```text
dist\SIAFSupportToolbox\SIAFSupportToolbox.exe
```
