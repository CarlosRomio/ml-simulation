# Rebalanceamento de estamina

Esta alteração torna a estamina menos restritiva sem alterar as taxas de fadiga, fome ou sede.
Os valores são unidades abstratas por passo/minuto simulado e devem ser calibrados por auditorias.

## Custos e recuperação globais

| Parâmetro | Antes | Atual |
|---|---:|---:|
| Custo de corrida por ação | 8 | 5 |
| Custo de ataque | 8 | 5 |
| Estamina mínima para iniciar corrida | 20 | 15 |
| Recuperação parado/esperando | 0,5 | 1,5 |
| Recuperação em repouso | 2 | 4 |
| Recuperação durante sono | 1 | 4 |
| Recuperação de repouso em abrigo | 8 | 10 |

## Reservas máximas por espécie

- Humanos: 100, sem alteração da reserva-base.
- Herbívoros: 60 -> 80.
- Carnívoros: 80 -> 110.

Os multiplicadores individuais de resistência continuam aplicados às reservas dos animais. A recuperação nunca ultrapassa `max_energy`.

## Validação

- `python -m pytest -q`: 322 aprovados, 2 ignorados.
- Auditoria de fumaça: 1 execução, 100 passos, mundo 100x100, concluída.

A auditoria curta verifica execução e integração, não comprova sozinha melhora na sobrevivência. Para medir impacto ecológico, comparar as mesmas sementes e condições com a versão anterior, observando estamina média, tempo em descanso/sono, distância explorada, presas abatidas e mortalidade.
