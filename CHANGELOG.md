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

### Limitações conhecidas

- Atalhos `.lnk` são identificados como evidência, mas seu destino ainda não é resolvido.
- Cenários de terminal remoto e matriz ampliada Windows 10/11 ainda não homologados.

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
