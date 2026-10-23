# Modelo inicial de atributos dos indivíduos

O modelo separa quatro conceitos:

- **Perfil de espécie:** médias abstratas que distinguem humanos, herbívoros e carnívoros.
- **Genótipo (`IndividualGenotype`):** valores hereditários normalizados de 0 a 1, inicialmente amostrados ao redor da média da espécie.
- **Fenótipo (`IndividualAttributes`):** atributos expressos que as mecânicas usam; por enquanto correspondem diretamente ao genótipo.
- **Condição atual:** saúde, estamina, fome, sede e fadiga, mantidas em `AgentNeeds`.
- **Personalidade:** curiosidade, aversão ao risco, sociabilidade, agressividade, persistência e sensibilidade à recompensa, mantidas em `Personality`.

## Atributos atuais

`strength`, `agility`, `constitution`, `endurance`, `vision`, `olfaction`, `intelligence`, `memory` e `metabolic_efficiency`.

A variação inicial é controlada por `SimulationConfig.attribute_variation` (desvio-padrão, padrão `0.12`). O valor `0.0` desativa a variação e atribui a média da espécie a todos os indivíduos. As fábricas usam RNGs derivados da seed para que a geração do genótipo seja reproduzível sem consumir a sequência aleatória usada para posicionamento ou decisões.

A base genética e a expressão fenotípica estão separadas. `IndividualGenotype.inherit(...)` já implementa uma herança simplificada: média dos valores parentais e mutações gaussianas ocasionais (`mutation_rate=0.02`, `mutation_strength=0.04`). Esse método ainda não é usado na simulação porque a reprodução não foi implementada. O modelo é uma aproximação quantitativa deliberadamente simples, não genética mendeliana.

## Integrações ativas nesta etapa

- Constituição escala a saúde máxima em torno do valor-base da espécie.
- Resistência escala a estamina máxima em torno do valor-base da espécie.
- Agilidade pode alterar a distância máxima de uma corrida: humanos e herbívoros percorrem até duas células; carnívoros até três. Indivíduos abaixo do limiar usam uma célula a menos.
- Visão ajusta discretamente o raio de percepção relativo à média da espécie.
- Força modula dano de ataque e dano de defesa em torno do valor-base, sem mudar a calibração média de cada espécie.

Inteligência, memória, olfato e eficiência metabólica já são registrados como atributos individuais, mas ainda não modificam decisões ou fisiologia. Serão conectados a mecânicas quando essas capacidades forem implementadas, evitando efeitos fictícios sem comportamento correspondente.

## Limites deliberados

Os perfis são parâmetros de design do simulador, não dados empíricos sobre espécies reais. A variação inicial é independente entre atributos; correlações genéticas, maturação e envelhecimento ficam para etapas futuras. Agentes construídos diretamente sem passar atributos explícitos recebem o perfil médio da espécie, preservando testes e cenários que criam entidades manualmente; as fábricas de população geram genótipos fundadores com variação individual por padrão.
