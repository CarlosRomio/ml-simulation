# ml-simulation — Plano técnico de refatoração

**Versão:** 0.1  
**Status:** Proposta de execução — ainda não iniciada  
**Base:** Auditoria estática do pacote `simulation(7).zip` e execução da suíte de testes disponível nesse pacote  
**Restrição:** Nenhuma alteração no código do projeto foi realizada como parte da elaboração deste plano.

## 1. Objetivo

Evoluir o `ml-simulation` para uma arquitetura modular, testável e reproduzível, preservando o comportamento científico existente sempre que não houver uma decisão explícita e validada para alterá-lo.

O plano começa com a higiene do repositório. Em seguida, estabelece uma linha de base comportamental, formaliza contratos de integridade e configuração, decompõe o motor, separa as responsabilidades dos agentes e interações e, por fim, prepara a observabilidade, os checkpoints e possíveis otimizações.

## 2. Princípios de execução

- Não misturar limpeza, refatoração estrutural e mudanças científicas no mesmo commit.
- Não remover arquivos sem verificar sua finalidade, referências e conteúdo relevante.
- Preservar contratos, dados e resultados experimentais que ainda tenham valor.
- Fazer alterações pequenas, com testes direcionados após cada mudança.
- Executar a suíte completa nos marcos definidos.
- Comparar resultados experimentais antes e depois de refatorações relevantes.
- Manter a execução sequencial determinística como referência.
- Não migrar componentes para C++ sem evidência de desempenho e contratos estáveis.
- Não modificar o código durante a fase de planejamento e inventário.

## 3. Visão geral das etapas

| Etapa | Objetivo |
|---|---|
| 0 | Higiene do repositório e inventário de arquivos |
| 1 | Linha de base e contratos atuais |
| 2 | Integridade, identidade e configuração |
| 3 | Decomposição do motor de simulação |
| 4 | Decisão, agentes e interações |
| 5 | Observabilidade e experimentação |
| 6 | Desempenho, checkpoints e avaliação de C++ |

---

## Etapa 0 — Higiene do repositório

### Objetivo

Reduzir o ruído do repositório sem perder documentação arquitetural, contratos de comportamento ou evidências científicas.

### 0.1. Classificar arquivos Markdown

Classificar os documentos em quatro grupos:

1. **Documentação permanente:** README e documento de arquitetura de referência.
2. **Contratos ativos:** documentos que descrevem regras ou interfaces ainda vigentes.
3. **Registros históricos:** relatórios de auditoria, experimentos e justificativas que sustentam decisões.
4. **Notas temporárias ou obsoletas:** registros de etapas concluídas, duplicados ou incompatíveis com a arquitetura atual.

Para cada arquivo candidato, registrar:
- Finalidade atual.
- Referências no código, testes, README e outros documentos.
- Decisões ou resultados que precisam ser preservados.
- Recomendação: `manter`, `consolidar`, `arquivar` ou `remover`.
- Justificativa objetiva.

**Não excluir todos os `.md` em lote.** A exclusão só será proposta depois da classificação individual.

### 0.2. Candidatos iniciais para revisão

Os nomes abaixo são candidatos a análise, não exclusões já aprovadas:

- `ANALISE_E_PROXIMA_ETAPA.md`
- `CORRECAO_INSTRUMENTACAO_ALVOS.md`
- `HUNTING_RISK_AND_ACCOUNTING_UPDATE.md`
- `STAMINA_POLICY_UPDATE.md`
- `ADAPTIVE_STAMINA_AND_HUNTING_UPDATE.md`

Comparar esses documentos com `README.md`, `documento_de_arquitetura_de_referência.md` e os documentos de `docs/`. Consolidar decisões duradouras antes de remover notas redundantes.

Documentos como `ECOLOGY_LEDGER.md`, `GENOTYPE_AND_PHENOTYPE.md`, `NAVIGATION_SERVICE.md` e `WATER_TARGET_NAVIGATION_CONTRACT.md` não devem ser removidos sem verificar se ainda representam contratos válidos.

### 0.3. Artefatos gerados

- Identificar `__pycache__/` e arquivos `.pyc` versionados.
- Confirmar que `.gitignore` cobre `__pycache__/` e `*.py[cod]`.
- Localizar resultados, gráficos, arquivos temporários e caches gerados.
- Preservar dados de referência necessários para reproduzir experimentos.
- Remover apenas artefatos comprovadamente regeneráveis e desnecessários ao repositório.

### 0.4. Scripts e testes

- Identificar scripts de experimento redundantes ou abandonados.
- Verificar se os scripts ainda funcionam e quais relatórios consomem seus resultados.
- Identificar testes obsoletos, duplicados ou desconectados do comportamento atual.
- Não remover testes só porque parecem semelhantes: comparar o cenário e as garantias que cada um cobre.
- Documentar os pontos de entrada relevantes no README.

### 0.5. Sequência operacional

1. Registrar o inventário inicial.
2. Classificar arquivos candidatos.
3. Verificar referências e conteúdo relevante.
4. Consolidar informações duradouras.
5. Apresentar a lista de exclusões propostas.
6. Executar somente as exclusões aprovadas.
7. Rodar a suíte de testes e verificar os pontos de entrada.
8. Registrar a limpeza em um commit independente.

### Critério de conclusão

Repositório sem artefatos gerados desnecessários, documentação com hierarquia clara e nenhuma perda de contratos ou evidências experimentais.

---

## Etapa 1 — Linha de base e contratos atuais

### Objetivo

Documentar o comportamento efetivo antes de alterar o motor.

### Trabalho previsto

- Mapear o fluxo completo de `Simulation.step()`.
- Identificar quais dados cada bloco lê e modifica.
- Registrar a ordem atual de movimento, alimentação, caça, defesa, fisiologia, reprodução e remoção.
- Identificar geradores aleatórios e pontos de consumo.
- Registrar métricas, relatórios e ferramentas de auditoria relevantes.
- Selecionar experimentos de referência com sementes fixas.

### Locais prioritários

| Local | Responsabilidade a investigar |
|---|---|
| `Simulation.__init__()` — aproximadamente linhas 153–361 | Inicialização do mundo, agentes, métricas e estado auxiliar |
| `_advance_environment()` — aproximadamente linhas 864–890 | Atualização ambiental |
| `_resolve_movements()` — aproximadamente linhas 892–1008 | Resolução de movimentos |
| `_resolve_herbivore_movement()` — aproximadamente linhas 1010–1059 | Movimento específico de herbívoros |
| `step()` — aproximadamente linhas 1146–2645 | Fluxo completo e dependências entre fases |
| `run()` — aproximadamente linhas 2647–2669 | Controle da execução |

Os intervalos são referências da versão inspecionada e podem mudar. Confirmar os locais antes de iniciar qualquer alteração.

### Critérios de aceitação

- Ordem atual das operações documentada.
- Métricas de referência registradas.
- Configuração efetiva e sementes identificadas.
- Diferença entre intenção e resultado confirmado documentada.
- Testes relevantes associados às responsabilidades identificadas.

---

## Etapa 2 — Integridade, identidade e configuração

### Objetivo

Formalizar os contratos que devem ser preservados durante a refatoração.

### Trabalho previsto

- Definir a configuração efetiva e imutável de cada réplica.
- Verificar a identidade estável dos agentes.
- Identificar invariantes locais e globais.
- Definir a auditoria global executada ao final de cada passo.
- Especificar a política de falha quando uma invariante for violada.

### Pontos de atenção

- `SimulationConfig` é mutável; localizar consumidores que modificam seus campos antes de introduzir imutabilidade.
- Separar IDs persistentes do domínio de referências técnicas como `id(obj)`.
- Tratar índices espaciais como estruturas derivadas.
- Não reparar silenciosamente inconsistências globais.

### Critério de aceitação

Configurações inválidas impedem a inicialização; invariantes globais são verificadas em cada limite de passo; testes demonstram a detecção de inconsistências.

---

## Etapa 3 — Decomposição de `Simulation.step()`

### Objetivo

Transformar o método extenso de orquestração em uma coordenação explícita de fases e serviços, preservando inicialmente a semântica atual.

### Agrupamento funcional preliminar

| Bloco aproximado | Responsabilidade identificada | Direção de extração |
|---|---|---|
| 1146–1162 | Preparação do passo e estado social | Contexto do passo e atualização social |
| 1164–1346 | Decisões, observações, seleção de objetivos e corrida | Política de decisão e produção de intenções |
| 1347–1367 | Captura de alvos e controle manual | Coordenação de comandos e rastreamento de intenção |
| 1368–1654 | Movimento humano, coleta, consumo, fisiologia e métricas | Resolver movimento, interações com recursos, fisiologia e métricas |
| 1655–1694 | Ataques humanos | Serviço de interação ofensiva |
| 1695–1949 | Decisões e ações dos herbívoros | Política de herbívoros, navegação e interações com recursos |
| 1950–2425 | Decisões, navegação, corrida e exploração dos carnívoros | Política de carnívoros e serviços especializados |
| 2426–2559 | Defesa humana e ataques de carnívoros | Resolução de combate, defesa e dano |
| 2560–2645 | Amostras, diagnósticos e registros finais | Observabilidade, métricas e finalização do passo |

Esses intervalos são aproximações funcionais da versão inspecionada. Não são limites definitivos de extração; alguns blocos misturam responsabilidades e exigem análise detalhada.

### Ordem recomendada

1. Isolar a coleta de métricas, preservando os dados atuais.
2. Extrair o contexto e os resultados intermediários do passo.
3. Separar produção de intenções da execução das ações.
4. Isolar movimento e resolução de conflitos.
5. Separar interações ecológicas e consequências.
6. Formalizar as fases do motor e seus contratos.
7. Executar testes de regressão após cada extração.

Não criar uma classe para cada bloco. Manter uma extração apenas quando ela estabelecer uma responsabilidade independente, com entradas, saídas e testes claros.

### Critério de aceitação

`Simulation.step()` coordena fases sem concentrar as regras de todos os subsistemas. Alterações comportamentais não justificadas são tratadas como regressões.

---

## Etapa 4 — Decisão, agentes e interações

### Objetivo

Reduzir responsabilidades de `Agent` e formalizar as operações ecológicas.

### Trabalho previsto

- Mapear os métodos extensos de `agents/agent.py`.
- Separar estado do agente de política comportamental.
- Reutilizar serviços existentes de navegação e seleção de alvos quando apropriado.
- Distinguir observações, memória e estado real do mundo.
- Formalizar a resolução de conflitos entre intenções.
- Definir a confirmação lógica de operações que envolvem múltiplas entidades.

### Critério de aceitação

Políticas produzem intenções; resolvers determinam resultados; serviços confirmam transições coerentes; eventos são registrados somente após a confirmação.

A arquitetura deve permitir substituir políticas sem duplicar regras fisiológicas ou de navegação.

---

## Etapa 5 — Observabilidade e experimentação

### Objetivo

Separar a evolução do mundo da coleta, análise e persistência dos resultados.

### Trabalho previsto

- Desacoplar serviços de domínio de `SimulationMetrics`.
- Definir políticas de coleta por execução.
- Registrar configuração efetiva, semente, versão do modelo e revisão do código.
- Diferenciar eventos de domínio de métricas agregadas.
- Formalizar resultados de cada réplica, incluindo falhas.

### Critério de aceitação

Alterar a política de coleta não altera o resultado científico da execução, e cada réplica pode ser rastreada até sua configuração e versão do modelo.

---

## Etapa 6 — Desempenho, checkpoints e C++

### Objetivo

Preparar otimizações com base em evidências, sem migrar componentes prematuramente.

### Trabalho previsto

- Medir o custo das fases após a refatoração.
- Investigar gargalos com profiling.
- Otimizar algoritmos e estruturas de dados antes de mudar de linguagem.
- Definir o estado necessário para checkpoints.
- Testar equivalência entre execução contínua e retomada.
- Selecionar candidatos à implementação em C++ somente com evidência de benefício.

### Critério de aceitação

Cada otimização tem benchmark, testes de integridade e evidência de preservação da semântica. A migração para C++ permanece opcional e localizada.

---

## 7. Regras de execução do plano

- Um commit independente para a limpeza.
- Um commit por mudança arquitetural coerente.
- Testes direcionados após cada extração e suíte completa nos marcos definidos.
- Experimentos de referência para detectar mudanças nas métricas.
- Documentação atualizada quando contratos ou decisões mudarem.
- Nenhuma exclusão sem classificação e justificativa.
- Nenhuma mudança de semântica apenas para simplificar a implementação.

## 8. Próxima ação concreta

Produzir um inventário de limpeza contendo, para cada candidato:

- Caminho do arquivo.
- Finalidade atual.
- Referências encontradas.
- Conteúdo que precisa ser preservado.
- Recomendação (`manter`, `consolidar`, `arquivar` ou `remover`).
- Justificativa.

Após aprovar o inventário, executar a limpeza isoladamente. Só então estabelecer a linha de base comportamental e iniciar a decomposição do motor.

A primeira alteração no repositório deve ser um commit de limpeza independente, sem misturar exclusões de documentação com refatoração da simulação.
