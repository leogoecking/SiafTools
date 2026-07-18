# Matriz de compatibilidade — Fase 0

| Cenário | Estado | Evidência necessária |
|---|---|---|
| Desenvolvimento em Python 3.11 x64 | Verificado | Testes unitários e diagnóstico degradado |
| Build Python 3.11 x86 | Verificado | Python 3.11.9 x86, PyInstaller 6.21.0 e artefato `onedir` |
| Windows 10 x64 executando app x86 | Pendente | Execução em máquina de homologação |
| Windows 11 x64 executando app x86 | Pendente | Execução em máquina de homologação |
| Firebird 2.5.7 x86 local | Parcial | Versão, serviços/processos, DLL e duas bases detectados; conexão pendente |
| Terminal com SIAF aberto | Pendente | Processo e conexão TCP remota correlacionada |
| SIAFW.FDB de teste | Pendente | Conexão e assinatura de esquema |
| SIAFLOJA.FDB de teste | Pendente | Conexão e assinatura de esquema |
| Máquina sem Python | Verificado | Diretório `dist` executado com sucesso no Windows Sandbox |
| DLL x64 em processo x86 | Automatizado | Detector marca incompatibilidade antes da carga |
| DLL x86 em processo x64 | Verificado | `fbclient.dll` encontrada e bloqueada por incompatibilidade |
| psutil em Python 3.11 x86 | Verificado | Versão 5.9.8 usa wheel `cp37-abi3-win32` sem compilador C++ |
| Execução do EXE x86 nesta máquina | Verificado | Processo permaneceu ativo; descoberta concluiu e `errors.log` ficou vazio |
| Usuário sem administrador | Parcial | Falhas de serviço/rede aparecem como avisos não fatais |

## Encerramento da Fase 0

Os quatro requisitos foram comprovados: build produzido por Python x86, biblioteca cliente
x86 carregada, conexão às duas bases de teste e execução no Windows Sandbox sem Python.
