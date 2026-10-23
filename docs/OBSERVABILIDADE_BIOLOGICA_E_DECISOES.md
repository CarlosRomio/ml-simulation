# Observabilidade biológica e decisões de carnívoros

## Objetivo

A instrumentação mede os mecanismos biológicos e comportamentais sem alterar seus parâmetros. O objetivo é permitir comparar decisões e resultados entre sementes fixas antes de ajustar as regras do ecossistema.

## Recuperação de saúde

A regra comum está em `simulation/health_recovery.py`. Humanos e herbívoros mantêm a taxa `0.25 + 0.5 * constitution`; carnívoros mantêm `0.35 + 0.65 * constitution`. A recuperação só ocorre durante `RESTING` ou `SLEEPING`, sem dano recebido no passo e com fome e sede abaixo de 70. A cura é limitada à saúde máxima.

Cada registro de atividade contém:

- `health_recovered_this_step`: cura efetiva neste passo, não a variação líquida de saúde;
- `health_recovery_source`: atividade que permitiu a cura (`RESTING`, `SLEEPING` ou `NONE`);
- `health_recovery_block_reason`: `NOT_RESTING`, `DAMAGE_THIS_STEP`, `CRITICAL_NEED`, `HEALTH_FULL` ou `RECOVERED`.

## Retirada dos carnívoros

A avaliação determinística foi extraída para `simulation/carnivore_decisions.py`. Ela preserva os limiares existentes e retorna um motivo explicável. O movimento de fuga permanece na orquestração da simulação, pois depende de ocupação e navegabilidade do mundo.

`carnivore_hunt_history.csv` passa a registrar:

- `retreat_decision`: a regra recomendou retirada;
- `retreat_reason`: condição que disparou a decisão ou ausência de condição;
- `retreat_attempted`: havia ao menos uma célula segura e a ação de retirada foi aplicada;
- `retreat_success`: a distância Manhattan mínima aos humanos considerados aumentou após o movimento;
- `human_threat_count_within_2` e `human_threat_count_adjacent`;
- `health_fraction_before_action`.

A taxa de sucesso de retirada usa apenas tentativas efetivas como denominador. Decisões sem rota segura são contabilizadas como decisões, mas não como tentativas.

## Resumos

`carnivore_hunt_summary.csv` agrega decisões, tentativas e sucessos de retirada, total de saúde recuperada, passos com cura e bloqueios por dano/necessidades críticas. `activity_summary.csv` agrega a cura por espécie e atividade. `activity_events.csv` inclui eventos `HEALTH_RECOVERY`.

## Semântica de episódios de caça

`carnivore_hunt_summary.hunt_episodes` agrupa sequências de registros que mantêm o mesmo `selected_prey_id` por indivíduo. `target_progress_summary.episodes_total` agrupa sequências de alvo/intenção conforme o contrato genérico de progresso, que pode incluir alvos de exploração e outras intenções. Os dois valores têm unidades e critérios diferentes e não devem ser comparados como se fossem a mesma contagem.

## Validação recomendada

1. `py -3.13 -m pytest -q`
2. Auditoria curta com sementes fixas, por exemplo 2 execuções de 300 passos.
3. Comparação entre a versão-base e a variante alterada com as mesmas sementes; comparar taxa de sucesso de retirada, cura total por indivíduo, dano defensivo, sucesso da caça e sobrevivência.

A instrumentação é observacional: não deve mudar escolhas, limiares ou taxas fisiológicas.
