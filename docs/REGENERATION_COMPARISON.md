# Experimento controlado: taxa de regeneração de plantas

## Pergunta

Como a quantidade de sementes solicitadas por atualização (`seed_spawn_count`) altera a trajetória do estoque de plantas, o tempo até atingir o limite, a coleta de alimento e os bloqueios de regeneração em um ecossistema com humanos, herbívoros e carnívoros?

## Correção de desenho experimental

A primeira versão do experimento tinha duas limitações que impediam interpretá-la como uma comparação ecológica completa:

1. `SimulationConfig` manteve os defaults de uma pessoa e nenhuma fauna (`agent_count=1`, `herbivore_count=0`, `carnivore_count=0`).
2. O cenário começava sem entidades `Plant`; o tratamento de regeneração zero era, portanto, um mundo sem plantas, em vez de um controle sem regeneração a partir de um estoque inicial comum.

A versão atual corrige ambas as questões. Todos os tratamentos começam com 54 plantas maduras, 18 itens de alimento estático, 18 fontes de água, 9 obstáculos e uma população de 5 humanos, 8 herbívoros e 3 carnívoros. As plantas iniciais são colocadas em células distintas de comida, água, obstáculos e posição inicial. As regras dos agentes e a fisiologia não são alteradas.

Assim, o tratamento `seed_spawn_count=0` mede o esgotamento do estoque vegetal inicial sem regeneração; os tratamentos 1 e 2 medem a mesma dinâmica com reposição. Essa é uma comparação mais útil para o ecossistema atual.

## Desenho experimental

- Tratamentos: `seed_spawn_count = 0`, `1` e `2`.
- 20 execuções por tratamento, com sementes de execução pareadas (`42` a `61`).
- 300 passos por execução.
- Mundo de `30 x 30`, mesmo cenário inicial nos três tratamentos.
- 54 plantas maduras iniciais e limite de 100 entidades `Plant`.
- 18 itens estáticos `Food` e 18 fontes de água permanentes.
- População inicial: 5 humanos, 8 herbívoros, 3 carnívoros.
- A única variável experimental alterada é a quantidade solicitada de sementes por atualização.
- Sobrevivência é métrica secundária; não é objetivo de otimização.

## Execução

```powershell
py -3.13 -m pytest -q
py -3.13 run_regeneration_comparison.py
```

O experimento usa até quatro processos. A entrada principal está protegida por `if __name__ == "__main__"` para compatibilidade com o modelo de processos do Windows.

Arquivos produzidos em `results/regeneration_comparison/`:

- `regeneration_comparison.csv`: uma linha por tratamento.
- `regeneration_runs.csv`: uma linha por execução, com semente e métricas da população.
- `regeneration_ecology_history.csv`: estoques e eventos ecológicos por passo, execução e tratamento.

## Métricas e convenções

- `mean_final_plant_count` e `mean_plant_count_over_time`: estoque vegetal final e médio.
- `runs_reaching_plant_cap` e `mean_step_reaching_plant_cap`: frequência e tempo até atingir o teto rígido.
- `seed_spawn_requests_total`, `seeds_spawned_total`, `seed_spawn_success_rate`: pedidos, criação efetiva e razão entre ambos. Essa razão diminui quando o teto bloqueia pedidos; não deve ser interpretada como probabilidade biológica de germinação.
- `seeds_blocked_by_plant_cap_total` e `seeds_blocked_by_space_total`: motivo pelo qual uma semente solicitada não foi criada.
- `seed_to_growing_total`, `growing_to_mature_total`: transições no ciclo de vida.
- `plants_collected_by_humans_total` e `plants_collected_by_herbivores_total`: remoções de plantas.
- `mean_population_food_collected`: total médio de itens alimentares coletados pelos humanos por execução.
- `mean_food_collected_per_human`: média individual de alimento coletado, agregada sobre todos os humanos e execuções.
- `human_agent_survival_rate_secondary`: fração de humanos iniciais que sobreviveu até o horizonte, sem ser usada como alvo de ajuste.

Métricas `first_human_*` em `regeneration_runs.csv` identificam explicitamente o primeiro humano, evitando confundir o indivíduo observado com a população inteira.

## Resultados de referência desta versão

| Métrica | 0 sementes/atualização | 1 semente/atualização | 2 sementes/atualização |
|---|---:|---:|---:|
| Plantas finais médias | 0,00 | 94,55 | 99,80 |
| Estoque vegetal médio ao longo do tempo | 6,31 | 78,44 | 96,40 |
| Execuções que atingiram o limite | 0/20 | 14/20 | 20/20 |
| Passo médio de saturação | — | 206,93 | 42,75 |
| Sementes solicitadas | 0 | 6.000 | 12.000 |
| Sementes criadas | 0 | 5.707 | 6.601 |
| Bloqueadas pelo limite | 0 | 293 | 5.399 |
| Plantas coletadas por humanos | 938 | 4.431 | 5.209 |
| Plantas coletadas por herbívoros | 142 | 465 | 476 |
| Alimento total coletado pelos humanos, média por execução | 64,90 | 239,20 | 278,25 |

Esses resultados são uma execução de referência no ambiente de desenvolvimento; devem ser reproduzidos na máquina do usuário. Eles mostram que, neste cenário, uma semente por atualização não leva todas as execuções ao teto em 300 passos, enquanto duas sementes levam todas ao teto em média por volta do passo 43. A maior taxa também gera mais pedidos bloqueados. Isso aponta para o teto rígido como forte determinante do estoque, mas não demonstra que 100 seja uma capacidade ecológica realista.

O tratamento sem regeneração esgota as 54 plantas iniciais até o final do horizonte. Esse resultado é coerente com um controle sem reposição e não representa, por si só, um erro.

## Limitações conhecidas

1. O limite de plantas é um teto rígido, não uma capacidade de suporte derivada de nutrientes, luz, água ou competição.
2. A falta de espaço não bloqueou sementes nesta configuração; o teto de plantas foi o fator limitante nos tratamentos regenerativos.
3. `water_drinks_*` conta eventos de reposição por passo quando um indivíduo está sobre água e tem sede positiva. Não equivale necessariamente a viagens distintas até uma fonte.
4. A taxa de regeneração é uma variável experimental, não uma calibração biológica.
5. A população animal usa as políticas atuais; este experimento mede a ecologia sob essas políticas, não uma política ótima de sobrevivência.

## Próxima decisão

Usar os CSVs da execução do usuário para confirmar os balanços, comparar as trajetórias pareadas e decidir o próximo incremento. A prioridade provável é estudar a capacidade de suporte vegetal (teto e ocupação espacial) antes de introduzir nutrientes, sazonalidade ou outros fatores ambientais. Não alterar simultaneamente a fisiologia nem a política dos agentes.
