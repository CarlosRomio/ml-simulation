# Tempo simulado e fisiologia — etapa 1

## Convenção temporal

- Um passo da simulação equivale a **1 minuto simulado**.
- 60 passos equivalem a uma hora; 1.440 passos equivalem a um dia.
- A velocidade de execução é controlada pela interface. O parâmetro legado `step_duration_seconds` permanece por compatibilidade, mas não altera o relógio do mundo.
- `Simulation.simulated_minutes` e `Simulation.simulated_time_label` expõem o tempo simulado. Métricas em segundos representam tempo do mundo (`passos × 60`), não tempo de parede.

## Estado fisiológico

- Saúde: integridade física.
- Fome e sede: necessidades acumuladas, com custo basal existente e custo adicional por atividade.
- Estamina (`energy`): reserva para esforço imediato; esgotá-la não mata o agente.
- Fadiga: acumula durante espera, caminhada e corrida; nesta etapa, descanso reduz a taxa de acúmulo, mas ainda não há sono persistente.

## Atividades explícitas

- `WAITING`: permanece no lugar, com recuperação pequena de estamina.
- `WALKING`: deslocamento normal, com custo moderado.
- `RUNNING`: esforço de corrida/perseguição, com maior custo de estamina, fome, sede e fadiga.
- `RESTING`: ação selecionada explicitamente para recuperar estamina; o abrigo oferece recuperação maior.

A corrida ainda não aumenta a distância percorrida por passo; nesta etapa ela representa maior esforço metabólico e de estamina. A velocidade espacial distinta e o sono persistente ficam para etapas posteriores.

## Calibração

Os valores em `configuration/physiology_config.py` são parâmetros abstratos iniciais, centralizados para experimentação. Não devem ser interpretados como medidas fisiológicas reais. A próxima etapa deverá introduzir sono persistente, duração de sono e interrupções por perigo ou necessidades críticas.
