# ML Simulation — análise do estado atual e primeira evolução do contrato de navegação

## Escopo

Análise do snapshot recebido (`ml-simulation(10).zip`) em relação ao relatório de arquitetura. A análise é estática, complementada pela execução da suíte de testes; não substitui profiling nem auditoria ecológica longa.

## Linha de base antes das alterações

- `pytest --collect-only -q`: 256 testes coletados.
- `pytest -q`: **256 passed, 1 skipped**.
- O projeto já possui `NavigationService`, testes de caracterização da busca por água e documentação da separação entre infraestrutura e políticas de espécie.

## Constatações

### O que já está alinhado

- A navegação está parcialmente centralizada em `agents/navigation/service.py`.
- Humanos, herbívoros e carnívoros mantêm políticas de seleção e prioridades distintas.
- `tests/test_water_search_characterization.py` fixa diferenças relevantes: limiares de sede, prioridade entre água e caça, reavaliação de alvos e geometrias de percepção.
- A API antiga `agents.navigation.bfs.find_path` continua disponível, reduzindo risco de migração.

### Lacuna principal

A API original retorna apenas uma rota ou `None`. Assim, o chamador não consegue distinguir diretamente:

- destino inválido/não transitável;
- destino temporariamente ocupado;
- rota estruturalmente inexistente;
- agente que já chegou ao destino.

Isso é insuficiente para o contrato proposto no relatório, que pede motivo de indisponibilidade e distinção entre bloqueio temporário e alvo inválido.

### Limitações que permanecem deliberadamente abertas

- As políticas de busca por água ainda estão implementadas separadamente por espécie; esta alteração não tenta unificá-las.
- A percepção ainda usa geometrias diferentes em `Perception.observe()` e `World.get_nearby_cells()`; a caracterização existente registra essa diferença.
- A nova API foi integrada apenas à busca por água do herbívoro. Humanos, carnívoros e a busca por alimento do herbívoro mantêm os fluxos anteriores nesta etapa.
- Não foi feito profiling. Portanto, nenhuma afirmação sobre gargalos ou ganhos de desempenho é apresentada.

## Alteração implementada

Foi adicionada uma API aditiva `NavigationService.plan_route(...)`, sem remover nem mudar a assinatura de `find_path(...)`.

Ela retorna `NavigationResult`, com `status`, `path`, `reason` e propriedade `succeeded`. Os estados são:

- `PATH_FOUND`
- `ALREADY_AT_GOAL`
- `INVALID_START`
- `INVALID_GOAL`
- `TEMPORARILY_BLOCKED`
- `UNREACHABLE`

Quando a busca com bloqueios dinâmicos falha, o serviço faz uma busca adicional sem esses bloqueios para verificar se existe rota estrutural. Essa verificação adicional só ocorre no caso de falha com bloqueios. Para destino explicitamente ocupado, retorna `TEMPORARILY_BLOCKED` sem busca adicional.

A API e os tipos foram exportados por `agents.navigation`. Foram adicionados três testes para validar os estados novos.

## Validação depois da integração e da instrumentação

- `pytest -q`: **261 passed, 1 skipped**.
- `compileall` concluiu sem erros de sintaxe.
- Auditoria de fumaça de 1 execução por 30 passos concluiu; o período curto não gerou tentativas de planejamento de água, portanto não valida a distribuição dos status em cenário ecológico prolongado.
- Foi acrescentada instrumentação por tentativa de `plan_route()`: status e motivo da última tentativa, contadores por status no passo e agregação de tentativas no `resource_access_summary.csv`.
- Um teste cobre o caso em que a fonte mais próxima está temporariamente bloqueada e uma alternativa é encontrada no mesmo passo. Outro testa a agregação dos status sem confundir tentativas com observações por passo.

## Próxima etapa recomendada

1. Executar a auditoria completa de oito sementes na versão instrumentada para obter contagens reais de `PATH_FOUND`, `TEMPORARILY_BLOCKED`, `INVALID_GOAL` e `UNREACHABLE`.
2. Comparar os novos contadores com a linha de base, lembrando que a linha de base antiga não tinha essa instrumentação e, portanto, não terá valores diretamente comparáveis para esses campos.
3. Examinar as divergências de comportamento e confirmar que a instrumentação não altera decisões.
4. Após validar os dados, avançar para um contrato de seleção/validação de objetivos, sem impor uma política universal às espécies.

A etapa atual preserva as alterações estruturais. Não há recomendação de revertê-las: a prioridade é aumentar a observabilidade e usar evidências para guiar a próxima extração arquitetural.

## Etapa seguinte: configuração de escala do mundo

A capacidade vegetal de referência foi movida para `SimulationConfig`, junto das densidades iniciais de recursos. O limite padrão é proporcional à área, calibrado em 300 plantas para 60×60. `run_ecosystem_audit.py`, `run_single_simulation`, `ExperimentRunner` e a inicialização visual passam a consultar a configuração quando não há um limite explícito. Overrides explícitos continuam válidos para experimentos controlados.

Validação desta alteração: `pytest -q` — 281 testes passaram e 1 foi ignorado. A próxima etapa é instrumentar a cadeia de decisão e progresso do alvo sem mudar as políticas comportamentais: necessidade → alvo selecionado → rota → progresso espacial → chegada/abandono → necessidade satisfeita.
