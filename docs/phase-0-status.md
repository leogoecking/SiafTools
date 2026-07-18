# Fase 0 concluída — 2026-07-18

Todos os critérios de aceite definidos no roadmap foram atendidos.

## Implementado

- Verificação da arquitetura do processo e de arquivos PE/DLL.
- Modelos de descoberta com evidências, pontuação e erros não fatais.
- Detecção de processos SIAF e Firebird/InterBase.
- Detecção de serviços Firebird/InterBase sem nome fixo.
- Leitura das visões 32 e 64 bits do Registro do Windows.
- Detecção limitada de `SIAFW.EXE`, `fbclient.dll`, `gds32.dll`, `SIAFW.FDB` e
  `SIAFLOJA.FDB`.
- Leitura de `aliases.conf`, porta em `firebird.conf` e conexões TCP do processo SIAF.
- Classificação inicial da máquina e classificação posterior da base por assinatura do esquema.
- Prova de conexão somente leitura implementada com `fetchmany` para metadados.
- Janela mínima com descoberta em worker e atualização segura pelo loop do Tk.
- Build PyInstaller `onedir` protegido por verificação obrigatória de Python 3.11 x86.

## Evidência desta máquina

- Runtime de build: Python 3.11.9 x86 em `.venv`, confirmado como processo de 32 bits.
- Runtime x64 anterior foi preservado e continua separado do ambiente de build.
- Firebird detectado: 2.5.7.27050 Win32.
- Serviços ativos: `FirebirdGuardianDefaultInstance` e `FirebirdServerDefaultInstance`.
- Processos ativos: `fbguard.exe` e `fbserver.exe`.
- Cliente detectado: `fbclient.dll` x86, compatível com o novo processo x86.
- SIAF em execução: não encontrado.
- Base geral candidata: `C:\SIAFW\SIAFW.FDB`.
- Base de loja candidata: `C:\SIAFW\LOJA1\SIAFLOJA.FDB`.
- `aliases.conf`: sem aliases ativos para bases SIAF.
- Testes automatizados: 42 aprovados após a estabilização pós-fase.
- Ruff: aprovado sem ocorrências.
- Cobertura automatizada: 73% no total; conexão Firebird 88% e orquestrador 80%.
- Build: `dist\SIAFSupportToolbox\SIAFSupportToolbox.exe`, formato PE x86.
- Smoke test: executável permaneceu ativo, concluiu descoberta com duas bases e não registrou erro.
- `fbclient.dll` x86 carregada com sucesso pela biblioteca `fdb`.
- Prova de conexão interativa disponível em `scripts/probe_discovered_databases.py`; senha é
  solicitada com entrada oculta e não é recebida por argumento.
- Conexão somente leitura validada nas duas bases descobertas, ambas classificadas com 100%
  de confiança pelo esquema.
- Pacote `onedir` executado com sucesso pelo usuário no Windows Sandbox sem Python instalado.

## Critérios de aceite

- Aplicação comprova arquitetura 32 bits: **aprovado**.
- Conexão abre as duas bases de teste: **aprovado**.
- Build funciona sem Python instalado: **aprovado no Windows Sandbox**.

Nenhuma credencial foi persistida nesta etapa. Cenários adicionais de terminal remoto,
múltiplas lojas e matriz ampliada Windows 10/11 continuam como homologações futuras, mas não
bloqueiam o aceite definido para a Fase 0.

## Estabilização pós-fase

A revisão posterior corrigiu falsos positivos de esquema e modo da máquina, isolamento de
falhas dos detectores, agrupamento de configurações Firebird, resolução de atalhos e execução
do build fora da raiz. O novo executável x86 concluiu o smoke test com duas bases e zero
avisos ou erros.
