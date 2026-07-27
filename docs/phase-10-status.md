# Fase 10 iniciada — Assistente de devolução ao fornecedor

**Início:** 2026-07-26
**Estado:** em desenvolvimento
**Modo operacional:** somente leitura

## Problema real priorizado

Empresas precisam emitir NF-e de devolução de compra para fornecedores. O fornecedor costuma
enviar uma nota espelho por mensagem ou imagem, e o atendente informa os dados manualmente no
SIAF. Valores podem divergir por alteração posterior no cadastro do fornecedor ou do produto,
vínculo incorreto, arredondamento ou diferença entre os dados originais e os solicitados no
espelho.

O SIAF Support Toolbox deve reduzir a conferência manual sem decidir sozinho a tributação. O
diagnóstico separará o que veio do XML original, o que o fornecedor informou e o que existe no
cadastro atual.

## MVP aprovado

1. Importar localmente o XML modelo 55 da nota de entrada.
2. Extrair emitente, destinatário, chave, itens, valores, tributos e totais.
3. Criar um espelho pré-preenchido com os valores do XML.
4. Permitir que o atendente altere manualmente somente os campos informados pelo fornecedor.
5. Comparar XML original, espelho manual e, em incremento posterior, cadastro atual do SIAF.
6. Classificar diferenças, ausências e correspondências ambíguas.
7. Exibir evidências e gerar uma ficha de preparação da devolução.
8. Não criar, alterar, autorizar nem transmitir NF-e.

## Incremento 10.1 — núcleo XML e comparação

Implementado:

- leitura de XML `nfeProc` autorizado ou elemento `NFe` isolado;
- bloqueio de documentos diferentes do modelo 55;
- validação da chave de acesso com 44 dígitos;
- limite padrão de 20 MB;
- rejeição de DTD e entidades XML;
- extração de emitente, destinatário, identificação, produtos e totais;
- extração dinâmica dos campos tributários, inclusive grupos novos ainda não interpretados;
- representação de valores monetários e quantidades com `Decimal`;
- criação do espelho manual pré-preenchido;
- alteração imutável de um campo do espelho;
- comparação por item e por total;
- comparação decimal sem falso positivo causado apenas por quantidade diferente de zeros;
- estados `igual`, `divergente`, `ausente_no_espelho` e `item_ausente_no_espelho`;
- bloqueio de espelho associado a outra chave de acesso.

O conteúdo do XML não é persistido nem enviado para logs. Mensagens de erro não incluem nomes,
documentos, produtos, valores ou o caminho completo do arquivo.

## Incremento 10.2 — seleção e visualização do XML

Implementado:

- página funcional **Diagnósticos — Devolução ao fornecedor**;
- seletor local restrito inicialmente a arquivos XML;
- nome do arquivo exibido sem revelar o caminho completo;
- resumo com chave, número, série, modelo, fornecedor, empresa e quantidade de itens;
- grade com item, código do fornecedor, descrição, NCM, CFOP, unidade, quantidade e valor;
- painel de detalhes com valores comerciais e todos os campos tributários encontrados no item;
- valores decimais apresentados com separador brasileiro sem alterar o valor original;
- limpeza explícita da sessão;
- limpeza automática do documento anterior antes de tentar carregar outro XML;
- erro de validação exibido na própria página sem colocar dados fiscais ou caminho no texto;
- aplicação consistente dos temas claro e escuro;
- smoke da interface cobrindo carregamento, navegação e remoção de resultado obsoleto.

## Incremento 10.3 — edição manual do espelho

Implementado:

- espelho criado automaticamente e mantido somente em memória após carregar o XML;
- diálogo rolável com campo, valor original e valor do espelho lado a lado;
- edição manual de todos os campos comerciais e tributários presentes em cada item;
- edição separada dos totais encontrados no XML;
- aceitação de vírgula decimal na interface e normalização interna sem perda de precisão;
- rejeição de texto inválido em campos numéricos;
- atualização imediata da quantidade de divergências por item e no total da nota;
- indicação `Igual ao XML` ou quantidade de divergências na grade;
- painel do item mostra o valor original e o valor informado em cada diferença;
- restauração integral dos valores originais do XML;
- confirmação obrigatória antes de limpar ou substituir um espelho com alterações manuais;
- valores digitados não são classificados como corretos e recebem aviso de conferência fiscal.
- suíte completa com 215 testes e Ruff aprovada no Python 3.11.9 x86.

## Incremento 10.4 — protocolo autorizado e campos próprios da devolução

Implementado:

- aceitação somente de `nfeProc` NF-e 4.00 no namespace oficial;
- exigência de protocolo SEFAZ com `cStat` autorizado (`100` ou `150`);
- correspondência obrigatória entre a chave da NF-e e a chave presente no protocolo;
- validação estrutural do número do protocolo e presença da data de recebimento;
- exibição do protocolo validado no resumo da nota;
- bloqueio de XML isolado, sem protocolo, rejeitado, com namespace estranho ou versão não
  suportada;
- leitura dos campos de `impostoDevol` quando já existirem no item;
- esquema manual versão 1.0 independente do XML de entrada, com `indDevol`, `pDevol` e
  `vIPIDevol`;
- apresentação explícita de valor informado somente no espelho, sem classificá-lo como correto.

Esta validação confirma a coerência estrutural do protocolo incorporado ao arquivo. Ela não
consulta a situação atual da chave na SEFAZ e, portanto, não detecta um cancelamento ocorrido
depois da geração do XML.

Validação automatizada atual: 226 testes não visuais aprovados e Ruff sem apontamentos. O smoke
Tkinter permanece pendente neste computador porque o `.venv` referencia um Python 3.11.9 x86
cujo executável não está mais instalado; o runtime auxiliar disponível possui Tcl incompatível
com o teste visual.

## Incremento 10.5 — preparação manual e análise orientada

Implementado:

- seleção explícita dos itens que serão devolvidos;
- quantidade devolvida limitada à quantidade presente na nota de entrada;
- edição manual de quantidade, preço unitário, ICMS, redução e IPI por item;
- colunas independentes para o valor recebido no espelho e o valor calculado no SIAF;
- formulário de totais com mercadoria, desconto, frete, seguro, embalagem, despesas acessórias,
  acréscimo, bonificação, complemento, ICMS, IPI, substituição/retido e total da nota;
- cálculo da mercadoria selecionada e comparação centavo a centavo;
- inferência aproximada da base do ICMS e validação da composição pelo cálculo direto do imposto;
- reconciliação aritmética do total informado, sem interpretar a soma como regra fiscal;
- orientação com localização visual comprovada nas telas fornecidas do SIAF;
- separação entre divergência comprovada, possível causa e pendência de confirmação;
- armazenamento somente em memória e confirmação antes de descartar a preparação.

As telas fornecidas confirmam a localização visual das colunas `%RED.`, `%ICMS` e `%IPI`, dos
totais `Vr. Merc.`, `Base ICMS`, `Vr. ICMS`, `Base Subst.`, `Vr. Subst.` e `Total Nota`, além
da configuração por UF com MVA, ICMS débito e ICMS substituição. A representação de embalagem
como `Desp.Acess.` ou `Acréscimo` permanece hipótese até um teste operacional no SIAF.

Correções da estabilização:

- o valor integral do item preserva o `vProd` do XML mesmo quando quantidade multiplicada pelo
  preço unitário produz diferença de arredondamento;
- devoluções parciais são recalculadas e aceitam o total manual do item recebido no espelho;
- base e valor de ICMS são calculados por item, aplicando a redução antes da alíquota;
- alíquotas diferentes não são agregadas e despesas adicionais sem rateio conhecido geram
  pendência de confirmação;
- qualquer alteração em item ou total invalida imediatamente a análise exibida;
- totais do XML completo e da seleção atual aparecem em colunas separadas;
- embalagem não é mais apresentada como campo editável do SIAF e direciona a conferência para
  `Desp.Acess.` ou `Acréscimo`.

Validação automatizada atual: 243 testes não visuais aprovados e Ruff sem apontamentos. O smoke
Tkinter foi ampliado para cobrir o novo diálogo, mas continua pendente neste computador devido
à ausência do executável Python x86 associado ao `.venv`.

## Limites atuais

- O cadastro atual de fornecedor e produtos ainda não participa da comparação.
- Referências do fornecedor ainda não são reconciliadas com `DSIAF030`.
- A análise realiza cálculos e reconciliações aritméticas, mas não interpreta nem confirma regra
  tributária.
- Não existe exportação da ficha de diagnóstico.
- XML de NFC-e, evento, cancelamento, carta de correção ou documento diferente da NF-e modelo 55
  não é aceito.
- O parser ainda precisa ser homologado com XML real anonimizado do ambiente do cliente.
- O esquema manual 1.0 cobre os campos próprios de devolução priorizados neste incremento.
  Outros grupos tributários ausentes no XML só serão adicionados após validação em uma nota
  espelho real, para evitar inventar combinações fiscais.
- A situação atual da NF-e não é consultada on-line na SEFAZ; o diagnóstico valida apenas o
  protocolo incorporado ao XML.

## Próximo incremento

Consultar `DSIAF009`, `DSIAF006` e `DSIAF030` para comparar o XML e o espelho com o cadastro
atual do fornecedor e dos produtos. A consulta será somente leitura e só poderá ser criada
depois que o snapshot real confirmar os campos, chaves e relacionamentos necessários.

O incremento também deverá:

- bloquear vínculo automático quando código, barra ou referência apontarem para mais de um
  produto;
- separar diferença comprovada de possível causa cadastral;
- mostrar quais campos atuais podem ter influenciado o preenchimento feito pelo SIAF;
- continuar sem alterar cadastro, nota ou configuração.

## Critérios de aceite da fase

- Um XML real anonimizado é lido sem perda dos campos necessários.
- O atendente consegue alterar manualmente o espelho sem redigitar todos os itens.
- Uma divergência conhecida de valor ou alíquota é localizada no campo e item corretos.
- Correspondências ambíguas de produto são bloqueadas.
- O diagnóstico distingue fato observado de hipótese cadastral ou decisão fiscal.
- XML e dados sensíveis não aparecem nos logs.
- Nenhuma operação de escrita é aberta durante todo o fluxo.
