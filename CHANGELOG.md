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

### Limitações conhecidas

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
- Fundação da Fase 1 encerrada com 50 testes automatizados e cobertura total mantida em 73%.

### Corrigido após a Fase 1

- Sanitização passa a abranger o texto final formatado, incluindo traceback e stack trace.
- Valores sensíveis com aspas escapadas são removidos integralmente.
- Reconfigurar o diretório de logs fecha os handlers anteriores e passa a escrever somente no
  novo destino.
- `%LOCALAPPDATA%` vazio ou relativo usa o diretório pessoal como fallback absoluto.
- Suíte ampliada para 55 testes e cobertura total elevada para 74%.
- Executável x86 reconstruído e aprovado em smoke test com duas bases e log de erros vazio.
