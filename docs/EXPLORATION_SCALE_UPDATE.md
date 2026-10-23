# Escala de exploração e deslocamento

## Alterações

- A configuração usada em `main.py` aumentou o raio-base de visão de 6 para 14 células. A variação individual por atributo é mantida; no perfil atual, o raio expresso tende a ficar entre 12 e 16 células no perfil padrão, com piso explícito de 12 células.
- `SimulationConfig` passou a usar raio-base 12 por padrão para experimentos e chamadas que não substituem explicitamente o parâmetro.
- As fábricas de herbívoros e carnívoros usam raio-base 12 quando chamadas sem configuração explícita.
- A distância de corrida foi ampliada: humanos e herbívoros percorrem até 3 ou 4 células por passo; carnívoros, até 4 ou 5. O movimento continua ortogonal e verifica obstáculos e ocupação a cada célula.
- Humanos, herbívoros e carnívoros escolhem waypoints de exploração distantes, priorizando regiões pouco visitadas. A escolha considera a novidade local, a distância e a existência de uma rota alcançável.
- Humanos mantêm o waypoint e seguem a rota durante corridas, com sincronização do caminho após movimentos de vários passos. O deslocamento por rota é limitado ao número de passos restantes para evitar ultrapassar o destino.
- Herbívoros e carnívoros mantêm patrulhas exploratórias persistentes quando não há necessidade prioritária, ameaça ou presa que altere o comportamento.

## Validação

- Testes unitários de waypoint: distância, alcançabilidade, continuidade ortogonal e persistência do alvo.
- Suíte completa: `313 passed, 2 skipped`.
- Auditoria de fumaça: 1 execução, 100 passos, mundo 100x100, 20 humanos, 40 herbívoros e 8 carnívoros concluída em 6,80 segundos após a integração do seletor de waypoints às três espécies.

Os valores são uma configuração experimental mais agressiva, não uma calibração biológica. O próximo experimento deve comparar cobertura espacial, repetição de visitas, custo energético e localização de recursos com as mesmas sementes da versão anterior.
