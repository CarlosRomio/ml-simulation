# Auditoria de acesso a recursos

## Objetivo

Separar disponibilidade global de recursos de acesso efetivo por indivíduo, sem alterar as decisões ou regras ecológicas.

## Campos adicionados aos registros de atividade

- `resource_need_priority`: necessidade predominante segundo os limiares operacionais atuais.
- `nearest_water_distance_manhattan`, `nearest_mature_plant_distance_manhattan`, `nearest_food_distance_manhattan`: distância Manhattan até recursos atualmente presentes. A distância não garante uma rota caminhável.
- `water_sources_in_vision`, `mature_plants_in_vision`, `food_sources_in_vision`: quantidade de recursos dentro do raio de visão medido por distância Manhattan.
- `nearest_prey_distance_manhattan`, `prey_in_vision`: contexto de presas para carnívoros.
- `selected_target_kind`, `selected_target_x`, `selected_target_y`, `selected_target_distance_manhattan`, `selected_target_path_steps`, `selected_target_path_available`: alvo atual e evidência de rota já selecionada. `selected_target_path_available` descreve a rota/alvo mantido pelo agente, não uma busca global por caminho para cada recurso.
- `at_water_source`, `at_food_source`, `water_consumption_succeeded`, `food_acquisition_succeeded`, `food_consumption_succeeded`.
- `urgent_thirst_without_water_in_vision`, `urgent_hunger_without_food_in_vision`, `resource_access_outcome`.

## Arquivos

- `activity_sampled.csv`: inclui contexto de acesso nos passos amostrados.
- `activity_events.csv`: inclui mudanças de resultado de acesso, consumo e necessidades urgentes sem recurso visível.
- `resource_access_summary.csv`: agregação por execução e espécie usando os registros completos.

## Interpretação e limitações

- Distância Manhattan e quantidade de recursos no campo de visão não provam alcançabilidade; obstáculos podem impedir o caminho.
- Coleta/aquisição de alimento é separada de consumo de alimento para humanos.
- A instrumentação é observacional. Testes de regressão com semente fixa confirmam que população, ecologia, ações e estados principais permanecem idênticos à versão anterior.

## Navegação dinâmica e bloqueios

A navegação humana agora calcula rotas evitando as posições ocupadas conhecidas no início da decisão. Se o próximo passo ficar ocupado entre o planejamento e a resolução do movimento, o objetivo de recurso é preservado e a rota é recalculada no passo seguinte. Se o bloqueio vier de um obstáculo do mapa, a rota é invalidada para permitir novo planejamento.

Os registros de atividade incluem `movement_block_reason`, com os valores `AGENT`, `ANIMAL`, `OBSTACLE` ou vazio quando não houve bloqueio observado. Em corridas, esse campo também pode indicar bloqueio parcial depois de um primeiro deslocamento bem-sucedido. `activity_sampled.csv` e `activity_events.csv` exportam esse campo junto com necessidades, alvo e distâncias relevantes; `resource_access_summary.csv` agrega as observações de bloqueio por espécie.

A ocupação é um retrato do início do passo: como todos os agentes decidem antes de se moverem, o planejador evita conservadoramente células ocupadas mesmo quando outro indivíduo pode sair delas no mesmo passo. A rota é recalculada nos passos seguintes; não há teletransporte nem alteração das regras fisiológicas ou ecológicas.


## Latência de acesso a recursos

A auditoria também exporta `resource_access_episodes.csv`, com um registro por episódio contínuo em que um agente mantém um alvo de água ou alimento. O episódio registra os passos entre o primeiro alvo observado e o consumo/aquisição bem-sucedidos, distância inicial/final/mínima, bloqueios por tipo e condição fisiológica. Episódios sem sucesso são classificados como `TARGET_LOST`, `TARGET_CHANGED`, `AGENT_DIED` ou `SIMULATION_END`; os casos encerrados pelo fim da execução são censurados, não assumidos como falha definitiva.

`resource_access_episode_summary.csv` agrega episódios por execução, espécie e tipo de recurso, com taxa de sucesso, latência média/mediana e bloqueios médios. Um episódio só começa quando o alvo selecionado é compatível com a necessidade prioritária (`WATER` + `THIRST`, ou `FOOD` + `HUNGER`). Se a prioridade deixa de estar ativa, o episódio termina como `NEED_NO_LONGER_PRIORITY`; esse resultado e episódios censurados por `SIMULATION_END` ficam fora do denominador da taxa de sucesso. `active_search_steps` conta observações em que a necessidade correspondente permaneceu prioritária. Alvos genéricos `FOOD` de carnívoros são excluídos desta métrica porque a caça é instrumentada separadamente em `carnivore_hunt_history.csv`.

## Alinhamento do ciclo de alimentação dos herbívoros

A partir da revisão de instrumentação, os registros dos herbívoros capturam o tipo e as coordenadas do alvo **antes do movimento e do consumo**. Isso evita perder a identidade da planta quando ela é removida no mesmo passo em que é consumida. `resource_need_priority_before_action` registra a necessidade que orientava a ação, enquanto `resource_need_priority` continua descrevendo o estado fisiológico após a ação.

No resumo, `food_acquisition_successes` e `food_consumption_successes` são contagens de eventos por passo, não contagens de episódios de busca. Para herbívoros, os campos `food_*_events_with_matching_priority_target` e `food_*_events_without_matching_priority_target` dividem esses eventos conforme havia ou não alvo `FOOD` e prioridade `HUNGER` antes da ação. Esses campos ficam vazios para outras espécies nesta etapa, porque o alvo pré-ação ainda não é capturado de forma equivalente para elas.

O rastreador de episódios usa a prioridade pré-ação quando disponível e aceita o evento de consumo como sucesso mesmo que a prioridade caia após comer ou que a planta deixe de existir no mundo pós-ação. Alimentar-se por oportunidade (por exemplo, cruzar uma planta enquanto explorava) continua sendo um evento alimentar válido, mas não é confundido com uma busca iniciada por prioridade de fome.


## Navegação dinâmica de herbívoros

A navegação dos herbívoros considera posições ocupadas por humanos, outros herbívoros e carnívoros ao planejar rotas para água e plantas maduras. Se a rota estática mais curta atravessa uma célula ocupada, o planejador recalcula a rota evitando essas posições. Se uma fonte estiver ocupada ou não houver rota viável, tenta outra fonte da mesma categoria e, quando aplicável, a outra necessidade urgente antes de explorar.

Os registros distinguem `movement_block_reason` (tentativa de movimento efetivamente bloqueada) de `navigation_block_reason` (bloqueio detectado durante o planejamento e evitado por replanejamento/seleção alternativa). Os valores possíveis são `AGENT`, `ANIMAL` e `OBSTACLE`. Os CSVs de resumo agregam ambos os tipos de ocorrência separadamente; não devem ser somados como se representassem tentativas físicas equivalentes.
