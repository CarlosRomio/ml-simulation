# Arquitetura cognitiva dos agentes — etapas 1 e 2

## Objetivo

Migrar gradualmente de prioridades rígidas para uma seleção auditável entre ações viáveis. A personalidade modula a avaliação; a memória de experiência pode influenciar o valor esperado quando resultados são registrados explicitamente. Esta arquitetura ainda não é uma política treinada por ML.

## Componentes

### `Personality`

`agents/cognition/personality.py` define seis traços normalizados entre 0 e 1: curiosidade, aversão ao risco, sociabilidade, agressividade, persistência e sensibilidade à recompensa. A fábrica gera perfis reproduzíveis usando RNGs separados para posição, personalidade e decisões.

### `ActionCandidate` e `DecisionEngine`

`agents/cognition/decision.py` representa ações possíveis com benefício esperado, urgência, oportunidade, custo, risco, preferências sociais/exploratórias/agressivas e persistência de objetivo. O seletor calcula uma pontuação por componentes e registra a ação escolhida, sua pontuação e as alternativas avaliadas.

A elegibilidade permanece explícita: ações fisicamente impossíveis não entram na lista de candidatos. A seleção entre pontuações empatadas usa o RNG do agente.

### `ExperienceMemory`

`agents/cognition/experience.py` mantém a quantidade de observações e a recompensa média por `action_id`. `Agent.record_action_outcome(reward)` aceita valores entre -1 e 1, desde que exista uma decisão cognitiva elegível e ainda não avaliada. A simulação ainda não atribui recompensas automaticamente: a atribuição de crédito para planos que duram vários passos precisa ser definida antes de habilitar aprendizagem automática.

## Ações que já usam a seleção cognitiva

1. **Exploração:** movimentos adjacentes viáveis competem usando novidade local, oportunidade, custo e curiosidade.
2. **Busca de alimento:** a alternativa considera fome, quantidade de alimento já carregada, distância, oportunidade e custo/risco aproximados do deslocamento.
3. **Busca de água:** pode entrar como alternativa a partir de sede moderada; sua urgência cresce com a sede.
4. **Repouso:** compete com as necessidades quando a energia está baixa. Em abrigo, o benefício estimado é maior, pois a simulação recupera mais energia por passo.
5. **Aproximação social e reencontro:** candidatos sociais elegíveis são comparados pelo seletor existente.

As decisões fisiológicas são reavaliadas ao iniciar um novo objetivo e, durante deslocamentos para alimento/água, periodicamente a cada cinco chamadas de decisão. Isso permite abandonar um plano se o contexto mudar, sem recalcular rotas em todo passo.

## Regras que continuam explícitas

Construção de abrigos, coleta de materiais para construção, algumas interações com armazenamento, caça/combate e necessidades críticas ainda contêm políticas específicas. A migração é incremental. Estar próximo de outro indivíduo ou possuir afinidade não equivale a cooperar.

## Interpretação e limites

- A pontuação é um baseline interpretável, não uma medida científica validada de utilidade.
- Distância funciona como aproximação de custo e risco de deslocamento; ainda não há percepção integrada de ameaça na pontuação de alimento/água.
- Personalidade modula preferências, mas não é inteligência nem aprendizagem.
- A memória de experiência só muda escolhas quando o código registra explicitamente recompensas.
- Não há rede neural, Q-learning ou política treinada.
- A função de seleção pode produzir estratégias diferentes, mas comportamentos emergentes dependem de oportunidades reais no ambiente.

## Próximas etapas

1. Definir consequências e atribuição de crédito por ação, incluindo ações que duram vários passos.
2. Conectar risco às ameaças percebidas e custos às mecânicas reais de movimento.
3. Introduzir corrida, resistência, fuga e perseguição como ações com custos e consequências.
4. Implementar uma primeira cooperação funcional, sem forçá-la pela personalidade.
5. Comparar a política sem aprendizagem com uma variante que aprende a partir de recompensas observadas.

## Testes

`tests/test_agent_cognition.py` cobre validação e reprodutibilidade dos perfis, variação individual, ranking de risco, atualização de recompensa, influência da experiência e seleção de alimento/água/repouso/exploração.
