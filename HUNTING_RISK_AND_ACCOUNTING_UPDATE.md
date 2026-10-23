# Atualização: caça sensível a risco, fuga e contabilidade de abates

## Mudanças

- A seleção de presas usa distância, saúde relativa e presença de humanos próximos como estimativa determinística de risco.
- Carnívoros preferem presas herbívoras isoladas quando isso é razoável; humanos agrupados deixam de ser alvos rotineiros quando a fome não é crítica (limiar de 80).
- A identidade da presa atual tem histerese: só é substituída quando uma alternativa melhora suficientemente a pontuação, reduzindo trocas por pequenas diferenças de distância.
- Se um carnívoro fica adjacente a um grupo humano e não tem um herbívoro ao alcance, recua quando a fome não é crítica ou a saúde está baixa. Isso evita absorver vários ataques defensivos antes de conseguir agir no mesmo passo.
- A política de exploração dá mais peso à novidade local e considera uma vizinhança maior (raio Manhattan 6 em vez de 4) ao estimar visitas anteriores.
- A auditoria exporta os fatores de risco/seleção e separa herbívoros mortos por caça humana dos mortos por carnívoros.

## Contabilidade de abates

`herbivores_killed` é o total de herbívoros mortos por caça humana e por predação. As novas colunas `herbivores_killed_by_humans` e `herbivores_killed_by_carnivores` separam esses mecanismos.

`carnivore_prey_killed_from_hunt_history` conta `prey_killed` no histórico individual de caça. `carnivore_prey_killed_from_death_causes` conta mortes terminais humanas e herbívoras cuja causa primária é `PREDATION`. `carnivore_kill_accounting_delta` deve ser zero; qualquer valor diferente de zero indica uma divergência de instrumentação a investigar.

## Validação

- Suíte completa: 335 testes aprovados, 2 ignorados.
- Auditoria de fumaça: 2 réplicas, 80 passos, mundo 30 × 30, 2 workers.
- Nas duas réplicas de fumaça, a diferença de contabilidade de abates foi zero.

A auditoria curta valida a execução e os contratos de instrumentação, não comprova melhoria ecológica em longo prazo. A eficácia deve ser medida com réplicas maiores e comparação com a versão anterior.
