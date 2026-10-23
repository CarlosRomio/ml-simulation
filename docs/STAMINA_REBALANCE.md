# Rebalanceamento e política adaptativa de estamina

## 1. Objetivo e escopo

A mecânica de estamina regula a capacidade dos agentes de realizar ações exigentes, especialmente corrida e ataque, e controla a recuperação durante espera, repouso e sono.

A implementação combina três responsabilidades:

- **Configuração fisiológica:** define custos, taxas de recuperação e limiares.
- **Política adaptativa:** decide quando correr, descansar e aplicar recuperação adaptativa.
- **Integração com a simulação:** aplica as decisões e atualiza o estado dos agentes durante cada passo.

Os valores são unidades abstratas do simulador. Como cada passo corresponde a um minuto simulado, as taxas são interpretadas nessa escala. Não representam medidas fisiológicas reais.

## 2. Custos e recuperação

Os valores atuais estão definidos em `configuration/physiology_config.py`, na configuração padrão `DEFAULT_PHYSIOLOGY_CONFIG`.

| Parâmetro | Valor anterior documentado | Valor atual |
|---|---:|---:|
| Custo de corrida | 8 | 5 |
| Custo de ataque | 8 | 5 |
| Estamina mínima absoluta para correr | 20 | 15 |
| Recuperação durante espera | 0,5 | 1,5 |
| Recuperação durante repouso | 2 | 4 |
| Recuperação durante sono | 1 | 4 |
| Recuperação durante repouso em abrigo | 8 | 10 |

Os valores anteriores são registros históricos do rebalanceamento, não parâmetros da execução atual.

O custo de movimento pode depender da espécie, da distância percorrida e do caminho de execução. Em particular, o consumo de estamina dos carnívoros durante o deslocamento é proporcional à distância, conforme a implementação da simulação.

A recuperação adaptativa pode aumentar a recuperação-base quando a reserva está baixa. A energia recuperada não deve ultrapassar `max_energy`.

## 3. Capacidades-base por espécie

Os construtores normais definem as seguintes capacidades-base:

| Espécie | Capacidade-base | Implementação |
|---|---:|---|
| Humanos | 100 | `agents/factory.py` |
| Herbívoros | 80 | `animals/herbivore.py` |
| Carnívoros | 110 | `animals/carnivore.py` |

Esses valores não são necessariamente a capacidade efetiva de cada indivíduo. A capacidade é ajustada pelo multiplicador hereditário do atributo `endurance`:

- Humanos: `100 × endurance`.
- Herbívoros: `80 × endurance`.
- Carnívoros: `110 × endurance`.

A capacidade efetiva deve ser consultada em `max_energy`. Testes e cenários específicos podem fornecer um objeto `AgentNeeds` com valores explícitos, diferentes dos padrões dos construtores.

## 4. Política adaptativa de corrida

A política está implementada em `agents/stamina_policy.py`, na função `should_run()`.

A proporção de estamina é calculada dividindo a energia atual pela capacidade máxima e limitando o resultado ao intervalo de 0 a 1. Quando a capacidade máxima é menor ou igual a zero, a proporção retornada é zero.

### 4.1 Limiares

| Parâmetro | Valor | Função |
|---|---:|---|
| `stamina_run_minimum` | 15 unidades | Limite absoluto para correr |
| `stamina_run_start_ratio` | 0,50 | Limiar para iniciar uma corrida normal |
| `stamina_run_continue_ratio` | 0,30 | Limiar para continuar uma corrida normal |
| `stamina_urgent_run_ratio` | 0,18 | Limiar proporcional para corrida urgente |

### 4.2 Regras de decisão

1. A corrida é impedida quando a energia está abaixo de `stamina_run_minimum`.
2. Quando a fadiga é igual ou superior a 85, a corrida é impedida se não houver urgência.
3. Em situação urgente, a corrida é permitida quando a proporção de estamina atinge `stamina_urgent_run_ratio`, respeitado também o limite absoluto.
4. Fora de situações urgentes:
   - Se o agente já está correndo, aplica-se `stamina_run_continue_ratio`.
   - Caso contrário, aplica-se `stamina_run_start_ratio`.
5. Na corrida normal, a fadiga precisa permanecer abaixo de 70.

A diferença entre os limiares de início e continuidade introduz histerese, reduzindo a alternância frequente entre corrida e caminhada.

**Ressalva:** o caminho urgente não aplica os mesmos limites de fadiga utilizados na corrida normal. Isso descreve o comportamento implementado; não demonstra, por si só, que essa decisão seja a melhor para o modelo ecológico.

## 5. Política adaptativa de descanso

A função `should_rest_for_stamina()` considera a reserva atual e o esforço previsto para a próxima ação exigente.

### 5.1 Limiares

| Parâmetro | Valor |
|---|---:|
| `stamina_rest_start_ratio` | 0,22 |
| `stamina_rest_resume_ratio` | 0,55 |
| `stamina_reserve_ratio` | 0,30 |

### 5.2 Regras de decisão

- Em situação urgente, a política de estamina não exige descanso.
- Se o agente ainda não está descansando, o limiar de início é o maior entre 22% da capacidade máxima e o limiar antecipatório do esforço previsto.
- Se o agente já está descansando, o limiar de retomada é o maior entre 55% da capacidade máxima e o limiar antecipatório.
- Se houver esforço previsto positivo, a política considera o custo estimado dessa ação e uma reserva adicional.

O cálculo do limiar antecipatório é:

1. Reserva adicional = `max_energy × stamina_reserve_ratio`.
2. Limiar antecipatório = `min(max_energy, reserva adicional + expected_effort)`.

Quando não há esforço previsto positivo, o limiar antecipatório é zero.

Essa política pode iniciar ou prolongar o descanso antes de atingir os limiares proporcionais isolados. A intenção é preservar energia suficiente para ações exigentes previstas.

## 6. Recuperação adaptativa

A função `recovery_amount()` ajusta a recuperação de acordo com a reserva atual.

| Parâmetro | Valor |
|---|---:|
| `stamina_low_recovery_ratio` | 0,30 |
| `stamina_low_recovery_bonus` | 0,75 |

Quando a proporção de estamina é igual ou superior a 30%, não há bônus adaptativo.

Abaixo desse limite, o bônus aumenta proporcionalmente ao déficit de estamina. Com a reserva zerada, o bônus alcança 75% sobre a recuperação-base.

A fórmula implementada é:

`recuperação = recuperação-base × (1 + bônus × déficit proporcional)`

Se a recuperação-base for menor ou igual a zero, a função retorna zero. A aplicação da recuperação ao estado do agente deve respeitar `max_energy`.

O bônus não aumenta a capacidade máxima do agente; altera somente a quantidade recuperada naquele passo.

## 7. Separação de responsabilidades

| Arquivo | Responsabilidade |
|---|---|
| `configuration/physiology_config.py` | Define e valida os parâmetros fisiológicos |
| `agents/stamina_policy.py` | Calcula proporções e toma decisões sobre corrida, descanso e recuperação adaptativa |
| `agents/factory.py` | Inicializa agentes humanos com capacidade-base de energia ajustada por `endurance` |
| `animals/herbivore.py` | Define a capacidade-base dos herbívoros e aplica o multiplicador hereditário |
| `animals/carnivore.py` | Define a capacidade-base dos carnívoros e aplica o multiplicador hereditário |
| `simulation/simulation.py` | Integra os parâmetros e a política ao ciclo de simulação e às ações dos agentes |

A configuração padrão é representada por `DEFAULT_PHYSIOLOGY_CONFIG`. A classe `PhysiologyConfig` é um `dataclass` imutável e valida restrições dos parâmetros, incluindo relações entre limiares.

A validação estrutural dos parâmetros não garante, por si só, plausibilidade biológica nem desempenho ecológico ótimo.

## 8. Interação entre recuperação e combate

No fluxo de ataque de carnívoros em `simulation/simulation.py`, um carnívoro cuja última atividade registrada é `RESTING` ou `SLEEPING` não pode atacar naquele passo.

Essa restrição impede que a recuperação associada ao passo atual seja utilizada para financiar um ataque simultâneo. O ataque poderá ocorrer em um passo posterior, conforme as demais condições de decisão e disponibilidade de energia.

**O escopo dessa regra é o fluxo de ataque de carnívoros verificado.** Ela não deve ser generalizada automaticamente para todos os ataques ou todas as espécies sem uma análise específica dos respectivos caminhos de execução.

## 9. Validação e evidências experimentais

Os registros históricos de desenvolvimento incluem:

| Registro | Resultado documentado |
|---|---|
| Rebalanceamento inicial | 322 testes aprovados e 2 ignorados |
| Atualização da política adaptativa | 325 testes aprovados e 2 ignorados |
| Auditoria curta do rebalanceamento | Uma execução de 100 passos em mundo de 100 × 100 |
| Auditoria curta da política adaptativa | Duas réplicas de 100 passos em mundo de 30 × 30, com dois workers |

Esses resultados são históricos e correspondem a versões anteriores do projeto.

Na validação mais recente registrada para a implementação, em 23/10/2026, a suíte completa apresentou:

- **361 testes aprovados**.
- Tempo de execução: 1,66 segundo.
- Nenhuma ocorrência das constantes obsoletas `RUN_STAMINA_COST` e `ATTACK_STAMINA_COST` após sua remoção.
- `git diff --check` sem erros.

Essa validação cobre a suíte automatizada, mas não substitui uma avaliação experimental do impacto ecológico da política. O teste de regressão confirma os comportamentos cobertos pelos testes, não a superioridade da política em termos de sobrevivência ou equilíbrio do ecossistema.

### 9.1 Métricas recomendadas

Para avaliar o efeito da política sobre a dinâmica do ecossistema, comparar versões com as mesmas sementes e condições iniciais, observando:

- Estamina média e distribuição de estamina por espécie.
- Tempo em repouso e sono.
- Frequência e duração das corridas.
- Distância explorada.
- Frequência de ataques e presas abatidas.
- Frequência de exaustão e de recuperação adaptativa.
- Mortalidade e sobrevivência por espécie.

As comparações devem utilizar múltiplas réplicas e medidas de variabilidade, evitando conclusões baseadas em uma única execução.

## 10. Próximas etapas

1. Manter os testes automatizados como verificação de regressão após alterações na política.
2. Executar auditorias comparativas com sementes e condições controladas antes de recalibrar os parâmetros.
3. Avaliar os resultados por espécie e por réplica, incluindo as métricas de estamina, repouso, corrida e sobrevivência.
4. Atualizar este documento sempre que os parâmetros ou as regras de decisão forem alterados.

Este arquivo é a referência central para os custos, a recuperação e a política adaptativa de estamina. Registros históricos de implementação devem permanecer separados apenas quando preservarem informações relevantes que não estejam representadas aqui.
