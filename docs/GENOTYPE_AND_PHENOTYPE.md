# Genótipo e fenótipo dos agentes

A simulação agora separa os valores hereditários dos atributos expressos:

- **`IndividualGenotype`** guarda os valores genéticos normalizados em `[0, 1]`.
- **`IndividualAttributes`** representa o fenótipo atual utilizado pelas mecânicas existentes.
- **`IndividualGenotype.species_founder(...)`** cria indivíduos iniciais ao redor do perfil médio da espécie, usando a variação configurada.
- **`IndividualGenotype.inherit(parent_a, parent_b, rng, ...)`** combina os valores dos dois progenitores e aplica mutações ocasionais e limitadas.
- **`genotype.express()`** produz o fenótipo. Nesta primeira etapa, a expressão é direta; idade e ambiente ainda não alteram os atributos.

## Modelo de herança atual

Para cada característica, o valor herdado começa pela média dos valores parentais. Com probabilidade `mutation_rate`, é somado um ruído gaussiano de desvio-padrão `mutation_strength`; o resultado é limitado a `[0, 1]`.

Os parâmetros padrão do método são `mutation_rate=0.02` e `mutation_strength=0.04`. A herança já pode ser testada, mas a reprodução ainda não está conectada ao mundo, portanto o método não é chamado durante as auditorias comuns.

Este é um modelo quantitativo simplificado, não uma simulação de alelos diploides ou genética mendeliana. Ele foi escolhido para criar uma base evolutiva simples e fácil de experimentar antes da implementação da reprodução.

## Compatibilidade e observabilidade

As fábricas de humanos, herbívoros e carnívoros criam genótipo fundador e expressam seus atributos a partir dele. Agentes construídos diretamente por código legado recebem um genótipo compatível com os atributos fornecidos ou o perfil médio da espécie.

`initial_states.csv` exporta tanto `attribute_*` (fenótipo) quanto `gene_*` (genótipo). Por enquanto, os valores devem coincidir. A separação permitirá que idade, maturidade, condição física ou ambiente modifiquem o fenótipo sem alterar diretamente os valores hereditários.

Os perfis e valores continuam sendo parâmetros de design do simulador, não estimativas empíricas de espécies reais.
