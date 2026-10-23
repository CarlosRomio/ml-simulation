# Política adaptativa de estamina

## Objetivo

Reduzir ciclos de exaustão e preservar reserva para fuga, perseguição e combate em humanos, herbívoros e carnívoros.

## Regras

- Corrida normal começa com pelo menos 50% da reserva máxima.
- Uma corrida em andamento pode continuar até 30% da reserva, evitando alternância entre corrida e caminhada a cada passo.
- Em urgências, a corrida pode ocorrer a partir de 18% da reserva, respeitando também o limite absoluto `stamina_run_minimum`.
- Descanso começa quando a reserva cai para 22% ou menos, desde que não exista urgência.
- Um agente que começou a descansar retoma a atividade quando alcança 55% da reserva, salvo se uma necessidade urgente alterar a decisão.
- A recuperação recebe um bônus gradual abaixo de 30% da reserva: até 75% adicional quando a estamina está zerada. A capacidade máxima continua sendo respeitada.
- Um carnívoro que recuperou estamina neste mesmo passo não pode gastar essa recuperação para atacar simultaneamente; o ataque ocorre em um passo posterior se ainda houver reserva suficiente.

## Configuração

Os limiares e o bônus estão em `configuration/physiology_config.py` e podem ser calibrados sem modificar a política central em `agents/stamina_policy.py`.

## Validação

- `python -m pytest -q`: 325 aprovados, 2 ignorados.
- Auditoria curta: 2 réplicas, 100 passos, mundo 30x30, 2 workers; concluída.

A auditoria curta verifica execução e instrumentação, não comprova por si só melhoria estatística de sobrevivência. Para avaliar impacto ecológico, comparar réplicas longas com as mesmas sementes antes/depois.
