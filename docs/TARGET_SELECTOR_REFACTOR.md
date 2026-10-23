# Refatoração incremental: seleção de objetivos

## Objetivo

Separar a escolha e a validação de candidatos do planejamento de rotas, sem mudar as prioridades comportamentais das espécies nem a ordem temporal da simulação.

## Mudanças

- `agents/target_selector.py` agora contém `TargetSelector`.
- `TargetSelector.is_valid_goal()` verifica limites do mundo e transitabilidade do destino no estado atual.
- `TargetSelector.nearest_reachable_target()` preserva a ordenação por distância Manhattan, com desempate por `y` e depois `x`, ignora a posição atual e consulta o pathfinder para confirmar que existe uma rota com movimento.
- `agents/agent.py` delega a seleção de destinos de alimento e água ao seletor.
- `NavigationService` continua responsável pelo planejamento e mantém sua validação defensiva. Isso é necessário porque o mundo pode mudar entre a seleção do alvo e o uso da rota.
- Foram adicionados testes para candidatos fora dos limites, destinos não transitáveis, fallback para candidatos alcançáveis, posição inicial que deixou de ser transitável e alvo coincidente com a posição atual.

## Compatibilidade esperada

A ordem dos candidatos e o critério de aceitação de uma rota foram preservados. A mudança intencional é rejeitar explicitamente candidatos inválidos antes de chamar o pathfinder, em vez de depender exclusivamente da implementação do pathfinder para rejeitá-los.

Não foram alterados limiares de fome/sede, pesos de `ActionCandidate`, política de exploração, comportamento de herbívoros/carnívoros ou sequência de `Simulation.step()`.

## Validação

- Suíte: `python -m pytest -q` — **266 passed, 1 skipped**.
- Auditoria piloto: 2 execuções de 300 passos concluídas com sucesso.
- Auditoria completa de 8 execuções × 3.000 passos: não concluída neste ambiente de trabalho; a execução excedeu o limite de tempo disponível. É necessário executar a auditoria completa no ambiente local antes de considerar a refatoração validada em escala.

Comando de validação completa recomendado no Windows:

```powershell
py -3.13 -m pytest -q
py -3.13 run_ecosystem_audit.py --profile full --runs 8 --steps 3000 --seed 7200 --workers 4 --sample-every 20 --output results/ecosystem_audit_target_selector_refactor
```
