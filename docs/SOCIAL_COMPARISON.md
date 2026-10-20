# Comparação experimental do comportamento social

## Perguntas

1. As regras sociais atuais alteram os padrões de proximidade, afinidade, grupos e sobrevivência em relação a decisões sem influência social?
2. A memória espacial contribui para reencontros observáveis além da aproximação social geral?
3. Os grupos persistem ao longo do tempo ou aparecem apenas em momentos isolados?

## Condições

- **A_CONTROLE** — comportamento social e memória espacial habilitados.
- **B_SEM_INFLUENCIA_SOCIAL** — influência social e memória espacial desabilitadas; as afinidades ainda são calculadas para observação analítica, não para orientar decisões.
- **C_SEM_MEMORIA** — aproximação social geral habilitada, sem memória de posições anteriores e sem busca de reencontro.

As três condições compartilham a mesma configuração, semente da réplica e cenário inicial. Como as decisões divergentes consomem aleatoriedade de forma potencialmente diferente ao longo do tempo, o pareamento controla as condições iniciais, mas não garante trajetórias idênticas depois que os agentes começam a agir de forma diferente.

## Execução

```powershell
py -3.13 -m pytest -q
py -3.13 run_social_comparison.py --runs 2 --steps 30 --workers 1
py -3.13 run_social_comparison.py
```

Padrão: 30 réplicas por condição, 1.000 passos, 5 humanos, 8 herbívoros e 3 carnívoros. A primeira execução curta serve apenas como smoke test; não deve ser interpretada como resultado científico.

## Arquivos gerados

- `runs.csv`: uma linha por réplica e condição.
- `summary.csv`: média, desvio-padrão e intervalo de confiança aproximado de 95% por condição.
- `paired_deltas.csv`: diferença de cada réplica em relação a `A_CONTROLE`.
- `paired_summary.csv`: média e intervalo de confiança aproximado de 95% das diferenças pareadas.
- `group_history.csv`: componentes conectados com pelo menos dois humanos, por passo.
- `group_events.csv`: formação, dissolução e alteração de composição dos grupos.

## Definição operacional de grupo

Uma aresta conecta dois humanos quando a afinidade entre eles é maior ou igual ao limiar configurado (padrão 0,5). Um grupo é um componente conectado com pelo menos dois membros. Portanto, dois indivíduos podem pertencer ao mesmo grupo por uma cadeia de relações, mesmo que a afinidade direta entre eles seja inferior ao limiar. A definição deve ser tratada como instrumento analítico e pode ser refinada após inspecionar a distribuição das afinidades.

## Limitações e interpretação

- O IC95% é uma aproximação normal (`média ± 1,96 × erro-padrão`); para amostras pequenas ou distribuições assimétricas, pode ser impreciso.
- Trinta réplicas são uma primeira amostra, não uma garantia de poder estatístico. A variabilidade observada deve orientar a ampliação da amostra.
- A sobrevivência é descritiva, não o objetivo da simulação. Afinidade, proximidade e grupo não provam amizade, cooperação ou intenção.
- Um reencontro bem-sucedido exige proximidade do indivíduo-alvo real (distância Manhattan <= 3) em até 30 passos após o início da tentativa. Alcançar apenas a posição lembrada não conta como sucesso.
- A condição B continua atualizando as métricas de afinidade a partir dos encontros observados, mas essas afinidades não influenciam a escolha de ações. Isso mantém a instrumentação comparável sem permitir que a política social altere as decisões.

## Auditoria de atividade e fisiologia

`agent_activity_history.csv` registra uma linha por humano vivo no início de cada passo. A linha inclui decisão social, intenção operacional do agente, deslocamento, coleta, consumo, água e estados fisiológicos antes/depois. Um humano que morre durante o passo ainda tem a linha desse passo, pois participou das ações antes da atualização fisiológica final.

### Coleta e busca por alimento

- `food_collection_events`: número de passos em que ocorreu uma coleta de alimento; cada evento conta uma vez, independentemente da quantidade coletada.
- `food_units_collected`: quantidade efetivamente adicionada ao inventário, distinta do número de eventos. Plantas normalmente representam uma unidade; recursos `Food` podem conter quantidades diferentes.
- `food_search_agent_steps`: passos-agente em que a intenção operacional registrada era `SEEK_FOOD`, sem coleta naquele passo. É uma aproximação do esforço de busca, não uma medição de distância até recursos nem uma garantia de que havia recurso acessível.
- Métricas `*_per_100_agent_steps` normalizam pelo total de linhas de atividade da execução, ou seja, passos-agente observados, incluindo o passo em que um agente morreu.

### Intenção operacional

`behavior_intent` registra a intenção associada ao alvo atual, preservada enquanto o agente navega para ele. Valores incluem `SEEK_FOOD`, `SEEK_WATER`, `GATHER_MATERIAL`, `BUILD_SHELTER`, `SEEK_SHELTER`, `HUNT`, `SOCIAL_APPROACH`, `SOCIAL_REUNION`, `EXPLORATION` e ações locais como `DRINK_WATER` ou `REST_IN_SHELTER`. Essa variável descreve a intenção da política, não necessariamente uma ação concluída com sucesso.

### Decisões sociais bloqueadas

`SOCIAL_SKIPPED_PRIORITY` só é registrado quando a política do agente efetivamente avalia contatos sociais e marca uma prioridade fisiológica como motivo para não prosseguir. Fome, sede ou energia elevadas, isoladamente, não são suficientes para afirmar que uma decisão social elegível foi bloqueada. Isso evita contagens artificiais na condição `B_SEM_INFLUENCIA_SOCIAL`, em que a influência social está desativada.

### Evolução fisiológica

O histórico registra `health`, `hunger`, `thirst` e `energy` antes/depois, suas variações por passo e causas de dano. Os resumos temporais incluem médias entre agentes vivos e variações médias por passo. Os valores normalizados ajudam a comparar execuções com durações de vida diferentes, mas não substituem análises pareadas por semente.
