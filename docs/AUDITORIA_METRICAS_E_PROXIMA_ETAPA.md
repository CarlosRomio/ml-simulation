# Auditoria das métricas e próxima etapa do ambiente

## O que os CSVs da execução anterior mostraram

1. `humans.csv` misturava o horizonte completo da simulação (`steps=300`, `simulated_time_seconds=300`) com a duração real observada de cada agente. Um agente morto no passo 18 aparecia como se tivesse vivido 300 passos. O exportador agora escreve `steps` como duração individual, mantém `agent_lifetime_steps` como campo explícito e adiciona `experiment_steps` para o horizonte global. O tempo simulado individual é calculado com a duração por passo inferida da execução.
2. As médias finais agregadas incluíam a coorte inicial inteira, inclusive mortos. Isso é útil para balanço de coorte, mas não equivale à média dos sobreviventes. `runs.csv` agora explicita ambas as populações e informa `human_survivors_count_for_final_means`; o resumo de console também mostra ambas.
3. A taxa de sobrevivência não é usada como objetivo de otimização nesta etapa. Ela é uma medida descritiva para entender o que ocorreu no mundo.

## Leitura correta das métricas existentes

- `human_mean_*` em `population_history.csv`: média entre humanos vivos naquele passo.
- `human_all_mean_*`: média entre toda a coorte inicial; mortos permanecem incluídos.
- `human_mean_final_*_all_cohort` em `runs.csv`: média final entre todos os humanos iniciais.
- `human_mean_final_*_survivors`: média final somente entre humanos com saúde maior que zero.
- `steps` em `runs.csv`: duração da execução; `steps` em `humans.csv`: duração individual observada. `experiment_steps` em `humans.csv` é o horizonte da execução.
- `seeds_spawned` é um total cumulativo de sementes geradas. Pode ultrapassar `max_plants` ao longo do tempo porque plantas são consumidas/removidas e abrem capacidade para novas sementes. Não significa que a população simultânea de plantas excedeu o limite.
- `plants_reached_limit_step` é o primeiro passo em que uma execução atingiu o limite de plantas; valores agregados devem ser lidos junto de `runs_reached_plant_limit`, pois nem todas as execuções atingem o limite.

## O que os resultados atuais indicam (sem tratar sobrevivência como objetivo)

- As 43 mortes humanas registradas foram atribuídas a predação; não houve morte humana por fome ou desidratação nas 20 execuções. Isso sugere que as regras fisiológicas atuais não estão impondo uma pressão letal relevante por fome/sede no horizonte testado. Não é, por si só, um defeito: a questão é verificar se a mecânica representa o fenômeno pretendido.
- A média de sede da coorte é maior que a dos sobreviventes, porque a coorte também inclui indivíduos que morreram com níveis de sede mais altos. Os dois números respondem perguntas diferentes.
- A estamina final é alta para sobreviventes, mas isso não prova que seu custo esteja calibrado incorretamente. É preciso observar custo por ação, recuperação, frequência de repouso e estados em que ações ficam indisponíveis.
- O número de ataques não equivale ao número de encontros, nem ao sucesso da caça. Devemos registrar separadamente encontros, tentativas, acertos, falhas, dano e recurso alimentar obtido.

## Próxima evolução proposta: contabilidade de recursos do ambiente

A próxima implementação deve ampliar a observabilidade ecológica e preparar o ambiente para um modelo de recursos mais geral, sem introduzir ainda inventário, agricultura, construções ou aprendizado de máquina.

Registrar por passo e por execução:

- estoque inicial/final e contagem por estágio de plantas;
- plantas consumidas/coletadas, removidas por outras causas e sementes geradas;
- tentativas de geração de sementes recusadas por limite, falta de célula elegível ou ocupação;
- fontes de água disponíveis e consumo de água por agente;
- encontros com recursos, tentativas de coleta e coletas bem-sucedidas;
- disponibilidade de alimento e água ao longo do tempo, incluindo proporção de células acessíveis;
- balanços e invariantes verificáveis (contagens não negativas, limite simultâneo de plantas, eventos de consumo compatíveis com a mudança de estoque).

Essa etapa não deve alterar a estratégia dos agentes para fazê-los sobreviver melhor. O objetivo é saber se o mundo produz e consome recursos de forma rastreável.

A primeira versão do ledger foi implementada em `ecology_history.csv`. Ela registra estoque de plantas por estágio, fontes de água, transições de crescimento, coleta de plantas por humanos/herbívoros, eventos de água por espécie e solicitações de regeneração discriminadas por limite de plantas ou falta de espaço. As definições e limitações estão em `docs/ECOLOGY_LEDGER.md`.

O ledger valida três invariantes:
- `total = seeds + growing + mature`;
- `seeds_spawn_requested = seeds_spawned + seeds_blocked_by_plant_cap + seeds_blocked_by_space`;
- variação do estoque de plantas = sementes geradas - plantas coletadas por humanos - plantas coletadas por herbívoros.

Os testes e a execução completa devem continuar sendo a validação de referência. O próximo passo, depois de inspecionar os novos CSVs, será decidir se o ledger está suficiente ou se precisamos adicionar contagens de recursos acessíveis, tentativas de coleta e motivos de falha antes de modelar quantidades/capacidade.

## Execução de validação

```powershell
py -3.13 -m pytest -q
py -3.13 run_ecosystem_experiment.py
```

Enviar os cinco CSVs gerados em `results/ecosystem_experiment/` para a próxima auditoria:
`runs.csv`, `humans.csv`, `population_history.csv`, `human_physiology_history.csv` e `ecology_history.csv`.

## Utilidade inicial dos abrigos

- Um humano que esteja sobre um abrigo e com energia abaixo de 70 pode permanecer ali para descansar, desde que fome esteja abaixo de 35 e sede abaixo de 40.
- O repouso recupera até 8 unidades de energia por passo no abrigo; o repouso comum continua recuperando 2.
- Fome e sede continuam tendo prioridade: o abrigo não impede o agente de procurar recursos quando essas necessidades ultrapassam os limites definidos.
- Esta etapa não adiciona proteção contra ataques, recuperação de saúde, ocupação compartilhada ou construção automática.


## Auditoria de afinidades sociais

Os humanos recebem IDs estáveis (`H001`, `H002`, ...) por execução. A simulação mantém afinidade persistente por par, registra a distância e as alterações da afinidade por passo, e gera um histórico social individual. A proximidade (distância Manhattan <= 3) incrementa afinidade de forma lenta, ponderada pela sociabilidade dos dois agentes; separação superior a seis células reduz a afinidade lentamente. A escolha social favorece indivíduos visíveis com maior afinidade, com distância como critério secundário.

Os logs sociais são exportados por `run_ecosystem_experiment.py` para `social_history.csv`, `social_agents_history.csv` e `social_relationships_final.csv`. Esses dados permitem diferenciar encontros ocasionais de relações recorrentes; não são, por si só, evidência de cooperação.
