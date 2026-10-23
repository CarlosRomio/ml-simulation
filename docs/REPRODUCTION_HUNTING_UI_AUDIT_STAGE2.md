# Auditoria e instrumentação — reprodução, caça e inspeção visual (fase 2)

## Correções

- `_update_social_relationships()` usa `social_pair_encounters.get(pair, 0)` ao serializar contadores. Pares criados dinamicamente, por exemplo após nascimento, deixam de provocar `KeyError` quando ainda não possuem contador inicializado.
- Carnívoros mantêm histórico curto de posições durante a caça, medem repetição/oscilação e expõem contadores de estagnação e troca de alvo.
- A rota de caça termina numa célula adjacente à presa, em vez de planejar até a célula ocupada pela presa. Durante estagnação, rotas que reutilizam células recentes recebem penalidade para favorecer aproximação alternativa.
- A interface permite selecionar humanos, herbívoros e carnívoros vivos. `observed_individual` é separado de `observed_agent`, para não passar animais a ações exclusivas de humanos.
- A barra lateral de animais exibe fisiologia, fenótipo, genótipo, ciclo de vida, reprodução, alvo e métricas de caça. O indivíduo selecionado fica destacado no mapa.
- Os controles B/F/M informam que são exclusivos para humanos quando um animal está selecionado.

## Instrumentação reprodutiva

`reproduction_diagnostics.csv` registra uma linha por espécie e passo, incluindo:

- população viva e elegibilidade reprodutiva;
- quantidade de fêmeas e machos elegíveis;
- imaturidade, cooldown e gestações/incubações em andamento;
- bloqueios por fome, sede, energia e saúde;
- indivíduos com intenção `SEEK_MATE`;
- acasalamentos, nascimentos, nascimentos bloqueados e mortes por idade.

`reproduction_events.csv` foi ampliado com posições dos progenitores, distância, custo energético observado, duração de gestação/incubação e cooldown. Nascimentos impedidos emitem `BIRTH_BLOCKED` com motivo explícito (`NO_FREE_ADJACENT_CELL` ou `MISSING_PARTNER_GENOTYPE`).

`carnivore_hunt_history.csv` inclui `hunt_stagnation_steps`, `hunt_target_switches`, `hunt_position_history_size` e as coordenadas do alvo espacial da caça.

## Validação local

- `python -m pytest -q`: **313 passed, 2 skipped**.
- `python -m py_compile` nos módulos modificados: aprovado.
- Auditoria de integração: `--profile full --runs 1 --steps 10 --seed 7200 --workers 1 --sample-every 2 --width 30 --height 30 --attribute-variation 0.12`: concluída; `reproduction_diagnostics.csv` e os novos campos de caça foram exportados.

Os dois testes ignorados dependem de Pygame, que não está instalado neste ambiente de execução; por isso, o caminho visual não foi renderizado aqui. Os testes de lógica não dependentes de Pygame passaram. Recomenda-se validar a seleção visual no Windows onde Pygame 2.6.1 já está instalado.

## Limitações deliberadas

- A persistência do alvo de caça é espacial porque o contrato legado de `choose_action()` recebe coordenadas, não objetos de presa. Em cenários densos, duas presas próximas ainda podem ser confundidas; a instrumentação torna esse comportamento observável.
- A penalidade de rota recente é heurística. Deve ser avaliada em auditoria prolongada antes de ajustar os pesos ou alterar os custos fisiológicos.
- Os contadores de reprodução são agregados por espécie e passo; os eventos detalhados continuam sendo registrados separadamente.
