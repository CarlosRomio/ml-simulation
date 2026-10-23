# Integração do contrato de navegação na busca por água do herbívoro

## Escopo

A busca por recursos do `Herbivore` passou a usar `NavigationService.plan_route()` para planejar a rota até cada candidato. Esta etapa não altera a política de seleção do herbívoro nem migra humanos ou carnívoros.

## Comportamento preservado

- Busca por água quando `thirst >= 45`.
- Ordenação dos candidatos por distância Manhattan, com desempate por coordenadas.
- Consideração de posições ocupadas dinamicamente.
- Tentativa de candidatos subsequentes quando uma fonte está ocupada ou não tem rota.
- Movimento para a rota calculada ou espera quando já está sobre o recurso.
- Instrumentação do tipo de bloqueador (`AGENT`, `ANIMAL` ou `OBSTACLE`), inclusive quando a rota alternativa consegue contornar a posição ocupada.

## Mudança estrutural

A decisão de viabilidade da rota usa agora o resultado explícito do serviço (`NavigationResult` e `NavigationStatus`) em vez de interpretar somente `None` ou uma lista de posições. A política da espécie continua responsável pela ordem dos alvos e pela escolha da próxima fonte.

A busca estática anterior é mantida apenas para preservar a classificação histórica de bloqueios na instrumentação; a rota efetivamente adotada vem de `plan_route()`.

## Observabilidade do contrato

Cada chamada a `plan_route()` agora é contabilizada por status durante a decisão do herbívoro. A simulação exporta, por observação, o status/motivo da última tentativa e contadores de tentativas para cada resultado (`PATH_FOUND`, `ALREADY_AT_GOAL`, `TEMPORARILY_BLOCKED`, `INVALID_START`, `INVALID_GOAL` e `UNREACHABLE`). O resumo da auditoria agrega esses contadores como tentativas de planejamento, não como observações por passo.

Isso permite identificar casos em que uma fonte foi bloqueada, mas uma fonte alternativa foi encontrada no mesmo passo — situação que se perderia ao observar somente o status final.

## Validação

- `pytest -q`: **261 passed, 1 skipped**.
- `python -m compileall -q agents animals simulation environment tests`: concluído sem erros.
- `git diff --check`: concluído sem erros.
- Auditoria de fumaça: 2 execuções de 100 passos, sementes iniciadas em 7200, concluídas anteriormente. Esta execução valida o fluxo do runner, mas não é evidência suficiente para inferir equivalência ecológica de longo prazo.
- Novo teste: confirma que uma fonte temporariamente bloqueada e uma alternativa encontrada no mesmo passo são ambas contabilizadas.
- Novo teste: confirma que o resumo agrega tentativas por status sem confundi-las com observações.

## Próximo passo

Executar uma auditoria curta e verificar se as novas colunas aparecem no `activity_summary.csv`. Depois, repetir a auditoria completa de oito sementes para construir uma linha de base com a instrumentação explícita. Só então avaliar a extração do contrato de objetivos ou a migração de outra espécie.
