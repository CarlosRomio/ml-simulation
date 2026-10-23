# Revisão arquitetural — Fase 1

**Escopo:** diagnóstico do estado atual, comparação dos mecanismos de busca por água e proposta incremental de fronteiras arquiteturais.  
**Base inspecionada:** `ml-simulation-herbivore-dynamic-navigation.zip` e auditoria `ecosystem_audit_herbivore_navigation_3000`.  
**Mudanças de comportamento nesta fase:** nenhuma. Este documento registra o diagnóstico; não implementa a refatoração.

## 1. Objetivos e restrições

O projeto deve continuar evoluindo como uma simulação experimental em Python. Uma eventual migração seletiva para C++ é uma possibilidade futura, não uma meta desta fase. Para preservar essa opção, os componentes devem caminhar para contratos explícitos e dados de entrada/saída claros, mas não se deve introduzir agora FFI, bindings, processos separados ou uma divisão prematura em repositórios.

Princípios:

1. Preservar as regras atuais salvo quando uma alteração comportamental for explicitamente intencional.
2. Compartilhar mecanismos e contratos, não forçar todas as espécies a tomar as mesmas decisões.
3. Fazer mudanças pequenas, com testes de regressão e comparação de auditorias com sementes fixas.
4. Separar simulação, interface, experimentos e exportação de métricas.
5. Não interpretar a mortalidade dos herbívoros como defeito automaticamente: sua vulnerabilidade é parte do modelo atual. A avaliação deve considerar se o comportamento e as causas das mortes são coerentes com as regras definidas.

## 2. Mapa atual de módulos

| Área | Arquivos principais | Responsabilidade atual | Observação |
|---|---|---|---|
| Entidade humana e decisão cognitiva | `agents/agent.py`, `agents/needs.py`, `agents/cognition/*`, `agents/inventory.py` | Estado, necessidades, seleção e avaliação de ações, memória de experiência | `Agent` ainda concentra fisiologia, seleção de alvos, exploração e execução de decisões. |
| Entidades animais | `animals/herbivore.py`, `animals/carnivore.py` | Políticas de decisão e métodos de alimentação/hidratação | Algoritmos próprios; compartilham parte da representação de necessidades, mas não um contrato comum explícito de política. |
| Mundo e recursos | `environment/world.py`, `environment/cell.py`, `environment/resources.py`, `environment/obstacles.py`, `environment/shelter.py`, `environment/storage.py` | Grade, recursos, estruturas, movimento e consultas espaciais | Consultas de recursos e percepção estão distribuídas; algumas rotinas varrem o grid. |
| Navegação | `agents/navigation/bfs.py` | Busca de caminho BFS, com posições bloqueadas opcionais | `agents/navigation/pathfinder.py` está vazio; o arquivo ativo é `bfs.py`. |
| Percepção | `agents/perception.py`, `environment/world.py`, lógica em `simulation/simulation.py` | Células visíveis, linha de visão e proximidade de entidades | Há geometrias e caminhos de percepção diferentes. |
| Orquestração | `simulation/simulation.py` | Ordem de decisão, movimento, interações, fisiologia, ecologia e métricas | Classe `Simulation` com cerca de 2.091 linhas; `step()` ocupa aproximadamente as linhas 977–2067. |
| Configuração | `configuration/*` | Configuração fisiológica, social e geral | Alguns limiares comportamentais permanecem hardcoded nas políticas. |
| Métricas e auditoria | `metrics/*`, `run_ecosystem_audit.py` | Registro, agregação e exportação de CSVs | A auditoria é detalhada, mas parte do enriquecimento de registros ocorre dentro do caminho da simulação. |
| Experimentos e cenários | `experiments/*`, `scenarios/*`, scripts `run_*.py` | Construção de cenários, repetição e comparação experimental | Scripts de entrada distintos são úteis; é importante evitar duplicar lógica de execução. |
| Interface | `visualization/*`, `main.py` | Renderização, câmera, entrada e controle visual | A separação existe parcialmente; `input_handler.py` e `simulation_controller.py` estão vazios. |

## 3. Fluxo temporal de `Simulation.step()`

A ordem observada em `simulation/simulation.py` é importante para a semântica do modelo:

1. Inicializa eventos do passo e captura o conjunto de entidades vivas e estados fisiológicos anteriores.
2. Atualiza relações sociais e prepara estado contextual dos agentes.
3. Cada humano seleciona uma ação usando o estado pré-movimento; entidades em controle manual ignoram a decisão autônoma.
4. Resolve movimentos dos humanos e registra decisões sociais/movimento.
5. Resolve coleta de recursos e interações de inventário/armazenamento após o movimento.
6. Aplica custos fisiológicos, atualizações de necessidades e ações específicas dos humanos, incluindo caça/defesa.
7. Move herbívoros com informação de ameaças e ocupação dinâmica.
8. Move carnívoros e resolve perseguição/ataques.
9. Corrige/amostra estados fisiológicos após combate, atualiza atividade e registra métricas.
10. Avança o ambiente e recursos, atualiza histórico/população e incrementa o relógio da simulação.

Esta lista é um mapa funcional, não uma proposta para reordenar as fases. A primeira refatoração de `step()` deve extrair fases mantendo exatamente a ordem e os pontos de observação atuais. Alterar a ordem de decisão, movimento, consumo ou combate pode alterar resultados emergentes mesmo que todos os métodos continuem passando nos testes unitários.

## 4. Busca por água: mecanismos atuais

### 4.1 Humanos (`Agent`)

- A busca por água entra na lista de candidatos quando `thirst >= 12` em `_select_needs_or_exploration_target()` (`agents/agent.py`).
- Água compete com alimento, descanso, sono, espera e exploração por meio de `DecisionEngine` e `ActionCandidate`.
- O alvo de água é escolhido por `TargetSelector.nearest_reachable_target()` (`agents/target_selector.py`), que ordena e valida candidatos antes de consultar o serviço de navegação; a rota é guardada no estado do agente.
- A persistência é representada em parte por `target_intent`/`continues_current_goal`; ainda existem regras adicionais de limpeza/reavaliação de alvo em outras partes de `Agent`.
- A simulação prepara `occupied_positions` para os humanos; o movimento é resolvido centralmente.

**Implicação:** a água pode ser escolhida preventivamente e sua prioridade é gradual, não um único limiar rígido. A lógica é expressiva, mas está acoplada à seleção de muitas outras ações dentro de `Agent`.

### 4.2 Herbívoros (`Herbivore`)

- A busca por água é adicionada a `resource_groups` quando `thirst >= 45`.
- O agente ordena fontes por distância Manhattan e tenta encontrar uma rota com BFS.
- Recebe posições ocupadas de agentes e animais; pode recalcular o caminho com `blocked_positions` e tentar fontes alternativas.
- A fuga de ameaças é avaliada antes da busca por recursos.
- A política pode acrescentar alimento como alternativa se `hunger >= 35`.
- `choose_action()` mantém a política de ameaça, seleção de recurso, rota e exploração em um método relativamente curto, porém com lógica de navegação embutida na política.

**Implicação:** a política reavalia e ordena fontes a cada decisão. Isso pode ser apropriado para uma presa, mas pode causar troca excessiva de alvo se a persistência não for uma regra explícita separada da seleção inicial.

### 4.3 Carnívoros (`Carnivore`)

- Se estiver sobre água e tiver sede (`thirst >= 1`), permanece para beber.
- Se `thirst >= 50`, tenta água primeiro.
- Caso não haja candidato nessa etapa e `hunger >= 30`, prioriza a busca por presas.
- Se não houver candidato de caça e `thirst >= 35`, tenta água como alternativa.
- Ordena candidatos pela distância Manhattan e usa `find_path()` sem passar o conjunto de ocupação dinâmica para a BFS.
- Ao alcançar distância adjacente de uma presa, pode parar para que o sistema de combate resolva o ataque; para água, precisa alcançar a própria célula.

**Implicação:** a busca por água está subordinada a uma sequência de prioridades (sede alta → caça → água com sede moderada), diferente da competição de candidatos dos humanos e da política por grupos dos herbívoros.

## 5. Comparação empírica da água

Dados agregados dos episódios no arquivo `resource_access_episodes.csv` da auditoria de oito execuções, 3.000 passos por execução, sementes 7200–7207:

| Espécie | Episódios de água | Sucessos | Taxa entre episódios resolvidos | Latência média dos sucessos | Mediana | Máximo |
|---|---:|---:|---:|---:|---:|---:|
| Humanos | 908 | 833 | 91,9% | 4,05 passos | 3 | 182 |
| Herbívoros | 1.224 | 857 | 70,1% | 7,88 passos | 5 | 215 |
| Carnívoros | 149 | 102 | 68,5% | 6,53 passos | 5 | 29 |

A taxa foi calculada como `SUCCESS / episódios resolvidos`, excluindo `SIMULATION_END` e outros resultados explicitamente censurados, quando presentes. As espécies têm volumes de episódios diferentes; em particular, a amostra de carnívoros é muito menor. Esses números descrevem a implementação atual, não provam que uma política seja intrinsecamente melhor.

Pontos que merecem investigação:

- Herbívoros têm 346 episódios encerrados por `TARGET_CHANGED` de 1.224 episódios de água. Isso é compatível com alternância de alvo, mas a causa da troca ainda precisa ser distinguida (alvo bloqueado, alvo perdido, reavaliação legítima ou mudança de prioridade).
- O episódio de água mais longo dos herbívoros dura 215 passos, partindo de distância 9 e terminando na célula de água. `blocked_by_agent`, `blocked_by_animal`, `blocked_by_obstacle` e `path_unavailable_observations` aparecem como zero nesse episódio, apesar da duração extrema. A instrumentação atual não explica a demora; não se deve inferir a causa apenas desses campos.
- Os humanos também têm um máximo de 182 passos, embora a mediana seja 3. Portanto, episódios extremos não são exclusivos dos herbívoros e devem ser examinados por trajetória e causa de interrupção.
- O caminho de navegação do carnívoro não recebe ocupação dinâmica, diferente do caminho do herbívoro. Essa diferença é concreta e pode ser mantida intencionalmente ou unificada como serviço com opções, mas precisa ser explicitada.

## 6. Inconsistências e riscos arquiteturais observados

### Prioridade alta

1. **Orquestrador monolítico:** `Simulation.step()` cobre aproximadamente 1.091 linhas e mistura coordenação de fases, comportamento, interações e métricas. A extração em métodos/fases testáveis deve preservar ordem temporal.
2. **Políticas específicas com mecanismos duplicados:** humanos, herbívoros e carnívoros implementam seleção de água, ordenação de alvos e navegação em pontos diferentes. Compartilhar um serviço de navegação/seleção não exige compartilhar a política de prioridade.
3. **Percepção não unificada:** `Perception.observe()` usa distância euclidiana circular com linha de visão; `World.get_nearby_cells()` percorre uma janela quadrada com linha de visão; `Simulation.step()` também usa distância Manhattan para animais visíveis e vizinhos sociais. A regra de percepção deve declarar quais tipos de observação são usados para cada finalidade.
4. **Instrumentação dentro do caminho crítico:** `_enrich_resource_access_records()` ocupa muitas linhas de `Simulation` e faz trabalho de enriquecimento/varredura. Deve ser medida por profiler e separada do núcleo de atualização quando possível, sem perder a observabilidade experimental.

### Prioridade média

5. **Parâmetros de comportamento dispersos:** limiares como sede humana 12, sede herbívora 45, sede carnívora 50/35 e fome carnívora 30 estão codificados nas políticas. Não devem necessariamente ser iguais, mas devem ser nomeados, documentados e configuráveis por política.
6. **Estado interno mutável entre camadas:** `Simulation` escreve atributos dos agentes, incluindo campos internos com `_`, como `_sleep_blocked_this_step`. Isso cria dependências implícitas entre orquestrador e entidades. Preferir contexto explícito de decisão/resultado e métodos de transição bem definidos.
7. **Módulos vazios:** `agents/navigation/pathfinder.py`, `agents/policies/rule_based_policy.py`, `agents/policies/random_policy.py`, `visualization/input_handler.py` e `visualization/simulation_controller.py` estavam vazios no pacote inspecionado. `agents/target_selector.py` foi preenchido na etapa seguinte para isolar a seleção/validação de objetivos; os demais módulos ainda precisam de decisão explícita antes de serem preenchidos ou removidos.
8. **Testes sem `assert` direto:** uma varredura sintática encontrou funções de teste sem `assert` explícito; várias podem ser testes de exceção via `pytest.raises`, portanto isso não é automaticamente um defeito. A revisão deve verificar que cada teste valida um resultado ou uma exceção e remover testes que apenas executam código.

### Desempenho e reprodutibilidade

9. **Busca global de recursos:** o humano cria listas de alimento percorrendo toda a grade em `_select_needs_or_exploration_target()`. Há também buscas de candidatos de exploração e outros percursos do grid. Medir custos antes de introduzir índices espaciais ou cache.
10. **Instrumentação configurável:** avaliar um modo de auditoria detalhado e um modo de simulação sem coleta detalhada. A equivalência do estado simulado entre modos deve ser testada com sementes fixas; os eventos não devem influenciar decisões.
11. **Reprodutibilidade visual:** verificar se `main.py`/factory semeia tanto a geração do mundo quanto a das entidades. Experimentos e interface precisam de contratos claros para sementes, embora a execução visual não precise usar sempre uma semente fixa.

## 7. Arquitetura-alvo incremental

Não se recomenda criar uma classe base genérica que contenha todas as decisões de todas as espécies. Recomenda-se compartilhar mecanismos e manter políticas específicas:

- **Estado/entidades:** necessidades, saúde, energia, posição, inventário e capacidades.
- **Percepção:** serviço que produz observações com geometria, alcance e linha de visão explícitos; perfis podem variar por espécie/finalidade.
- **Objetivos/alvos:** tipo de objetivo, posição, validade, motivo de seleção e regras de persistência/abandono.
- **Navegação:** serviço que recebe mundo, origem, destino e restrições de movimento/ocupação; devolve rota e motivo de indisponibilidade.
- **Políticas:** regras humanas cognitivas, herbívoro presa e carnívoro predador; cada política decide prioridades e quando trocar de objetivo.
- **Execução/resolução:** simulação aplica ações, resolve conflitos de movimento e interação, atualiza necessidades e ambiente numa ordem determinística explícita.
- **Eventos/métricas:** eventos estruturados emitidos pelas fases; exportadores e auditorias consomem esses eventos sem participar da decisão.
- **Interface:** renderização e input dependem de uma API de controle, não da implementação interna das fases.

### Contrato conceitual de navegação

A primeira interface compartilhada deve receber, de forma explícita:

- posição inicial e alvo;
- mundo/células transitáveis;
- conjunto de posições bloqueadas no instante da decisão;
- política de movimento (por exemplo, ortogonal; restrições por entidade);
- informação de validade do alvo.

E devolver:

- rota ou indisponibilidade;
- próximo movimento recomendado;
- motivo estruturado quando não houver rota (fora do mundo, obstáculo estático, ocupação dinâmica, alvo inválido etc.).

A navegação não decide se o agente deve beber ou caçar. A política escolhe o objetivo; a navegação responde como alcançá-lo. Isso é uma fronteira reutilizável também em uma eventual implementação em C++.

## 8. Plano de trabalho recomendado

### Fase 1 — diagnóstico (este documento)

- Mapear responsabilidades e dependências.
- Registrar os mecanismos de água das três espécies e seus resultados atuais.
- Não mudar comportamento.

### Fase 2 — testes de caracterização

- Criar testes que fixem o comportamento atual de seleção de água por espécie em cenários mínimos.
- Criar testes de percepção para células diagonais, obstáculos, entidade atrás de obstáculo e alcance de cada perfil.
- Validar a persistência de alvo e as condições exatas de troca/abandono.
- Medir tempo de execução por fase e custo da auditoria antes de otimizar.

### Fase 3 — primeira extração de baixo risco

- Definir contrato de alvo e serviço de navegação.
- Migrar uma espécie por vez, começando por herbívoro, sem alterar limiares ou prioridades.
- Preservar API pública e manter testes de regressão.

### Fase 4 — extração de fases de `Simulation.step()`

- Extrair fases mantendo a ordem atual.
- Comparar resultados pareados com sementes fixas e validar diferenças esperadas.

### Fase 5 — percepção e instrumentação

- Unificar o mecanismo de linha de visão e tornar as geometrias/perfis explícitos.
- Separar medição detalhada do caminho crítico da simulação, com um teste que confirme que habilitar/desabilitar a instrumentação não altera decisões.

### Fase 6 — preparação para expansão e possível migração

- Manter Python como implementação de referência.
- Estabilizar tipos de dados e contratos entre módulos.
- Só considerar C++ quando profiler identificar gargalos estáveis e isoláveis; medir o custo de integração antes de portar qualquer módulo.
- Não dividir em repositórios até existirem limites de domínio, ciclo de release e necessidades de implantação que justifiquem isso.

## 9. Critérios de aceitação para refatorações futuras

- Testes unitários cobrem resultado e falhas esperadas.
- Ordem temporal de decisão/movimento/interação é documentada e preservada, salvo mudança intencional.
- Auditorias pareadas usam as mesmas sementes e configuração.
- Diferenças de resultado são explicadas; não basta que os testes passem.
- Navegação reporta motivos de bloqueio de forma consistente entre espécies.
- A política de cada espécie pode variar sem duplicar BFS, validação de rota ou semântica de alvo.
- Instrumentação detalhada pode ser ativada/desativada sem alterar o estado final da simulação.
- O núcleo não importa Pygame; visualização consome a simulação por interface pública.
- Nenhuma abstração é criada sem pelo menos dois usos concretos ou um requisito claro de extensão.

## 10. Decisões ainda em aberto

1. Se a percepção será baseada em um único perfil geométrico configurável ou em perfis explícitos (visão de células, detecção de entidades, interação social).
2. Se persistência de alvo será uma política comum com parâmetros ou uma decisão explícita de cada política de espécie.
3. Se eventos serão objetos tipados internos, registros imutáveis ou estruturas simples serializáveis. A decisão deve considerar volume de dados e custo de execução.
4. Quais métricas devem ser produzidas em todos os passos e quais só em auditoria detalhada.
5. Quais comportamentos são requisitos do modelo biológico e quais são heurísticas provisórias.

Essas decisões devem ser fechadas com testes e pequenos experimentos, não por preferência abstrata de design.

## Fase 2 — primeiro contrato compartilhado: navegação

Foi introduzido `agents.navigation.service.NavigationService` como fachada
compartilhada para planejamento de rotas e obtenção do próximo deslocamento.
O serviço não seleciona objetivos nem decide prioridades: essas responsabilidades
continuam nas políticas de cada espécie.

- `Agent` passa seu `pathfinder` injetável pelo contrato de navegação, mantendo
  compatibilidade com seletores e testes existentes.
- `Herbivore` usa o serviço para rotas estáticas e rotas que evitam posições
  dinamicamente ocupadas.
- `Carnivore` usa o mesmo serviço para alvos de água, presas e exploração.
- `find_path` permanece disponível como API de baixo nível e compatibilidade.
- `NavigationService.next_step` define uma forma comum de converter uma rota em
  deslocamento, sem exigir que todas as políticas sejam migradas de uma vez.

Esta etapa é estrutural: não unifica os limiares de sede, a seleção de alvos,
a persistência ou as prioridades comportamentais. O objetivo é introduzir uma
fronteira pequena, testável e substituível antes de ampliar o contrato.
