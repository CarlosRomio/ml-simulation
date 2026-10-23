# ML Simulation

> **Tempo simulado:** cada passo equivale a um minuto do mundo. Consulte `docs/TEMPORAL_PHYSIOLOGY_STAGE1.md` e `docs/PHYSIOLOGY_STAGE2.md` para a convenção temporal, sono, corrida, estamina e resultados de calibração.
 — auditoria fisiológica e ecológica

Projeto de simulação em grade para estudar sobrevivência de humanos e interações com herbívoros e carnívoros. A arquitetura está migrando gradualmente de prioridades rígidas para decisões avaliadas. A simulação ainda não treina um modelo de ML nem atualiza recompensas automaticamente; consulte `docs/AGENT_COGNITION.md` para o estado exato desta etapa.

## Executar

```powershell
py -3.13 -m pytest -q
py -3.13 run_ecosystem_experiment.py
py -3.13 run_physiology_experiment.py
```

## Calibração de sono, corrida e metabolismo

Para executar o lote de calibração fisiológica (8 sementes, 900 passos/15 horas simuladas por execução):

```powershell
py -3.13 run_physiology_experiment.py
```

O experimento gera `results/physiology_calibration/runs.csv`, `activity_history.csv` e `activity_summary.csv`. O histórico inclui atividades, decisões humanas, distância percorrida, estamina gasta em movimento e combate, recuperação efetiva, custos metabólicos brutos, fadiga, fome, sede, saúde e interrupções do sono. Consulte `docs/PHYSIOLOGY_STAGE2.md` para interpretar os parâmetros e os resultados iniciais.

## Comparação controlada do comportamento social

Para comparar as regras sociais sem confundir as condições com cenários aleatórios diferentes, execute:

```powershell
py -3.13 run_social_comparison.py
```

Por padrão, o comparador usa paralelismo por processos automaticamente: até 8 processos, limitados ao número de réplicas, deixando um processador lógico livre quando possível. Para controlar a carga, use `--workers 1` para execução sequencial ou `--workers 4` para limitar a quatro processos.

O padrão é 30 réplicas pareadas por condição, 1.000 passos, 5 humanos, 8 herbívoros e 3 carnívoros. As três condições são:

- `A_CONTROLE`: sociabilidade, afinidade e memória espacial atuais.
- `B_SEM_INFLUENCIA_SOCIAL`: aproximação e reencontro social desativados; as métricas de proximidade e afinidade continuam sendo observadas.
- `C_SEM_MEMORIA`: aproximação social e afinidade ativas, mas sem memória espacial nem busca de reencontro.

Cada réplica usa o mesmo cenário e a mesma semente nas três condições. A diferença entre condições é a política social. Os resultados são gravados em `results/social_comparison/`: `runs.csv` (execução individual), `summary.csv` (médias, desvios-padrão e IC95% aproximados), `paired_deltas.csv` (diferença por semente), `paired_summary.csv` (média e IC95% das diferenças pareadas), `group_history.csv` (grupos por passo) e `group_events.csv` (formação, dissolução e mudanças de composição), e `agent_activity_history.csv` (uma linha por humano/passo, com decisão social, movimento, coleta de alimento, consumo, água e necessidades fisiológicas) e `activity_interval_summary.csv` (agregação temporal, por execução, em janelas de 100 passos; alterável com `--interval-steps`). `runs.csv` e `summary.csv` também incluem movimento social/não social, passos ociosos, coleta/consumo de alimento, ingestão de água, passos em necessidades críticas e prioridades fisiológicas que impediram uma decisão social. O limiar de afinidade para definir um grupo é 0,5 e pode ser alterado com `--affinity-threshold`.

Para validar rapidamente a execução antes de rodar o experimento completo:

```powershell
py -3.13 run_social_comparison.py --runs 2 --steps 30 --workers 1
```

Os grupos são componentes conectados de relações com afinidade igual ou superior ao limiar; só componentes com pelo menos dois integrantes contam como grupos. Afinidade e proximidade não equivalem a cooperação. O sucesso de reencontro é contado apenas quando o agente-alvo real aparece a até três células dentro da janela de 30 passos após o início da tentativa, não quando o agente apenas chega à posição lembrada.

O experimento ecológico usa 20 sementes reproduzíveis, 300 passos por execução e as configurações declaradas em `run_ecosystem_experiment.py`. Os CSVs são gerados em `results/ecosystem_experiment/`:

- `runs.csv`: uma linha por execução, com mortalidade, necessidades, alimentação, ataques e estado final das populações.
- `humans.csv`: uma linha por humano, incluindo métricas individuais e causa de encerramento.
- `population_history.csv`: uma linha por passo e execução, com população e médias fisiológicas.
- `human_physiology_history.csv`: uma linha por humano e passo, com posição, ação, estado fisiológico antes/depois, gasto/recuperação de estamina e dano por causa.

## Comparação controlada da regeneração

Para medir o efeito da regeneração sem alterar a política dos agentes, execute:

```powershell
py -3.13 run_regeneration_comparison.py
```

O experimento compara 0, 1 e 2 sementes solicitadas por atualização, com 20 execuções pareadas por tratamento e 300 passos. Cada tratamento começa com 54 plantas maduras, 18 itens de alimento estático, 18 fontes de água, 9 obstáculos e 5 humanos, 8 herbívoros e 3 carnívoros. Apenas `seed_spawn_count` muda entre tratamentos. Usa até quatro processos. Os CSVs são gravados em `results/regeneration_comparison/`. Consulte `docs/REGENERATION_COMPARISON.md` para o desenho experimental, a semântica das métricas e as limitações conhecidas.


## Arquitetura cognitiva dos agentes (primeira etapa)

Os humanos recebem traços individuais reproduzíveis quando são criados pela `AgentFactory`: curiosidade, aversão ao risco, sociabilidade, agressividade, persistência e sensibilidade à recompensa. Os traços ficam entre 0 e 1 e são registrados em `social_agents_history.csv`; a barra lateral também mostra o perfil do humano selecionado. Traços são preferências, não comandos diretos de comportamento.

`agents/cognition/decision.py` define `ActionCandidate`, `DecisionEngine` e o registro explicável dos valores que compõem uma decisão. Nesta primeira etapa, o seletor é usado na escolha entre contatos sociais elegíveis e nos movimentos de exploração. Necessidades fisiológicas, construção, caça e outros comportamentos ainda mantêm partes da política anterior por prioridade; a migração será gradual para evitar alterar simultaneamente muitas regras.

`agents/cognition/experience.py` fornece uma memória incremental de resultados por tipo de ação. A atualização é explícita por `agent.record_action_outcome(reward)`, com recompensa normalizada entre -1 e 1, e só pode ser aplicada a uma decisão cognitiva recém-selecionada. O simulador ainda não calcula recompensas automaticamente: antes disso precisamos definir atribuição de crédito para ações que duram vários passos, para não ensinar ao agente uma relação causal incorreta.

Veja `docs/AGENT_COGNITION.md` para o contrato das ações, a função de avaliação, os limites atuais e a sequência planejada.

## Convenções fisiológicas

Os números são **unidades abstratas do simulador**, não medidas fisiológicas reais.

- **Saúde (`health`)**: condição física. Chegar a zero significa morte.
- **Energia (`energy`)**: estamina para movimentação e ações exigentes. Chegar a zero não mata; impede corrida por falta de estamina e pode ser recuperada ao descansar ou comer.
- **Fome (`hunger`)** e **sede (`thirst`)**: escalas de necessidade em que zero representa necessidade satisfeita e o limite máximo representa necessidade extrema.
- Fome e sede aumentam por passo. Ao alcançar seus limiares críticos, aplicam dano à saúde a cada passo enquanto permanecerem críticas, salvo se o dano configurado for zero.
- Uma causa de dano só é contabilizada quando reduz efetivamente a saúde. Se fome e sede causarem dano no mesmo passo, ambas ficam registradas; se a primeira já zerar a saúde, a segunda não é contabilizada como dano efetivo.
- A causa da morte é determinada pelo dano efetivo, nunca por estamina zero. `STARVATION_AND_DEHYDRATION` significa que ambos os mecanismos causaram dano efetivo no passo letal.
- Médias `*_mean_*` em `population_history.csv` descrevem os indivíduos **vivos**. Colunas `*_all_mean_*` descrevem toda a coorte, incluindo indivíduos mortos, cujas necessidades ficam no estado em que estavam quando morreram.
- `water_units_consumed` é compatibilidade histórica: registra a redução efetiva da sede atribuível à água, não uma medida física independente de volume.

## Regras de interpretação

1. Uma execução reproduzível não prova, por si só, que a regra ecológica esteja correta; testes controlados validam regras específicas.
2. Sobrevivência, mortalidade por causa, níveis fisiológicos, recursos e comportamento devem ser lidos em conjunto.
3. Ao comparar versões, mantenha configuração, número de passos e sementes iguais. Alterações nas regras de movimento/estamina mudam os resultados e devem ser tratadas como mudança de modelo, não como simples correção de relatório.
4. `ExperimentSummary.starvation_runs` é mantido por compatibilidade e historicamente representa execuções sem sobreviventes; o nome correto dessa métrica é `extinction_runs`. Mortes individuais por fome ficam em `average_deaths_by_starvation`.

## Testes

A suíte cobre as necessidades, limites fisiológicos, causas de dano, consumo/recuperação de estamina, métricas agregadas, histórico individual e exportação CSV. Ao introduzir uma nova mecânica, adicione primeiro testes unitários e um cenário de experimento controlado antes de alterar parâmetros globais.


## Recursos materiais e inventário

O mundo agora pode conter depósitos coletáveis de madeira e pedra. Cada depósito tem uma quantidade variável, pode ser recolhido parcialmente e permanece na célula até acabar. Humanos têm inventário com capacidade limitada por peso: madeira pesa 1 unidade por item, pedra pesa 2 e fibra (reservada para extensões futuras) pesa 0,5. A coleta de material não é tratada como alimentação nem altera diretamente fome/energia. A política humana agora pode procurar madeira e pedra quando não há abrigo próximo, desde que fome e sede não estejam exigindo atenção prioritária. Com 5 madeiras e 2 pedras, procura um local livre afastado de outros abrigos e constrói autonomamente.

Densidades configuráveis: `wood_density` e `stone_density` em `SimulationConfig`. O histórico `human_physiology_history.csv` registra o inventário por passo; `humans.csv` inclui o inventário final de cada indivíduo; `ecology_history.csv` registra o estoque no mundo e as unidades coletadas.

Consulte `docs/RESOURCE_INVENTORY.md` para as regras e os limites atuais.

## Interface visual

A barra lateral foi reorganizada em seções: mundo, vegetação, materiais, agente observado e interações. O conteúdo central é rolável pela roda do mouse quando não cabe na altura disponível; o cabeçalho e os controles permanecem fixos. A roda do mouse sobre o mapa continua controlando o zoom.

A janela abre em tamanho compacto (1100 × 700) e pode ser redimensionada. A área do mapa acompanha o tamanho da janela; o zoom continua disponível pela roda do mouse. A janela mantém um mínimo de 800 × 480 para preservar a usabilidade do painel.

A barra lateral mostra as quantidades do inventário do humano selecionado. Para selecionar outro humano, clique nele no mapa.

#### Controle manual para validação

- Clique em um humano para selecioná-lo.
- Pressione **M** para alternar entre controle manual e IA autônoma.
- Com o controle manual ativo, use **WASD** ou as **setas** para comandar um movimento por tecla pressionada. O movimento continua respeitando obstáculos, outros agentes e animais.
- Pressione **M** novamente para devolver o humano à IA. Ao selecionar outro humano enquanto o controle manual está ativo, o controle acompanha a seleção.
- **B** constrói um abrigo se o humano selecionado tiver materiais suficientes.
- **Espaço** pausa/retoma; **1**, **2** e **3** alteram a velocidade; **Esc** fecha a janela.

### Correção de renderização da barra lateral

A chamada de desenho das barras fisiológicas passa explicitamente a cor e a coordenada vertical ao renderizador. Foi adicionado um teste de regressão que desenha a barra lateral completa, incluindo estamina, fome e sede, para detectar incompatibilidades na assinatura de `_draw_bar`.


## Abrigos compartilhados e inventário alimentar

Os cenários de simulação e a interface principal colocam um abrigo compartilhado na posição inicial do mundo. O abrigo substitui o antigo depósito isolado: é uma estrutura de descanso, proteção e armazenamento, e não bloqueia movimento. Armazena alimento, madeira, pedra e fibra, com capacidade de 500 unidades de peso. Abrigos construídos autonomamente também têm armazenamento compartilhado.

O inventário individual também carrega alimento (peso 1 por porção). Humanos coletam plantas maduras para o inventário e consomem uma porção quando a fome chega a 35. Ao permanecer sobre o depósito, depositam materiais e alimento excedente, preservando uma porção portátil; se estiverem com fome e sem alimento no inventário, retiram uma porção do estoque compartilhado. As transferências são registradas em `ecology_history.csv` e no histórico fisiológico individual.

Ao passar por um abrigo, humanos depositam materiais e alimento excedente; se estiverem com fome e sem alimento no inventário, retiram uma porção do estoque. A busca por abrigo também pode ocorrer quando a energia fica baixa. A transferência de materiais acontece ao visitar o abrigo; a política ainda não planeja rotas exclusivamente para descarregar recursos.

### Simulação visual: carnívoros e abrigos

O `main.py` agora cria 3 carnívoros (vermelhos), além dos 8 herbívoros
(verdes), utilizando as mesmas entidades e lógica do experimento.

Pressione **B** para construir um abrigo na posição do humano observado.
O custo é de **5 madeiras e 2 pedras** no inventário desse humano; a
célula deve estar livre de recursos, obstáculos e outras estruturas.
O abrigo persiste no mapa. Um humano dentro dele pode descansar quando sua energia está abaixo de 70, recuperando 8 unidades por passo em vez de 2 no repouso comum. Se fome (35) ou sede (40) ficarem altas, essas necessidades voltam a ter prioridade. O abrigo também reduz o dano de predação para 25% do dano normal (de 35 para 8,75 por ataque); não oferece invulnerabilidade nem recuperação de saúde.

## Validação visual de abrigos e predadores

- `M`: ativa/desativa o controle manual do humano selecionado.
- `WASD` ou setas: move o humano sob controle manual.
- `B`: constrói um abrigo na célula atual, se houver 5 madeiras e 2 pedras.
- `F`: cria um carnívoro de teste em uma célula adjacente livre, focado no humano selecionado. Esse predador tem saúde ampliada e necessidades lentas para facilitar a validação; isso não altera os parâmetros dos carnívoros normais nem os experimentos.
- `Espaço`: pausa/retoma a simulação.

Enquanto o humano ocupa uma célula com abrigo, o dano de predação é reduzido a 25% do dano normal (de 35 para 8,75 por ataque). O abrigo não concede invulnerabilidade. Fora dele, o dano normal continua valendo. A barra fixa no topo da lateral mostra a saúde atual do humano selecionado e o último dano recebido; a seção “DANO / COMBATE”, no conteúdo rolável, mostra danos acumulados por causa e os três últimos ataques registrados.

Para testar: selecione um humano, ative `M`, construa o abrigo com `B`, pressione `F` e retome a simulação com `Espaço` se ela estiver pausada. O carnívoro de teste persegue especificamente esse humano, evitando que herbívoros próximos desviem o teste.


### Abrigos compartilhados e construção autônoma

- O abrigo inicial também funciona como armazenamento compartilhado. Abrigos construídos pelos agentes têm a mesma capacidade de 500 unidades de peso.
- Humanos cansados procuram abrigos livres quando energia cai abaixo de 50 e fome/sede não são urgentes; permanecem descansando até energia alcançar 70. Um abrigo ocupado por outro humano é temporariamente ignorado.
- Quando não há abrigo a até 8 células de distância, agentes com fome abaixo de 25 e sede abaixo de 25 procuram madeira e pedra para construção.
- O custo é 5 unidades de madeira e 2 de pedra. Ao reunir os materiais, o agente procura uma célula livre, sem recurso/obstáculo/estrutura, e constrói se o local estiver a mais de 8 células de outro abrigo.
- O comportamento é baseado em regras explícitas, não em aprendizado de máquina. O controle manual desativa a construção autônoma para o humano controlado.

### Etapa 1 de comportamento social: proximidade espontânea

Cada humano possui um traço estável de `sociability` entre 0 e 1. A fábrica atribui valores individuais reproduzíveis quando a simulação recebe uma seed; o traço não é recalculado a cada passo. Agentes com sociabilidade abaixo de 0,35 não procuram ativamente outros humanos. Os demais podem escolher uma célula livre próxima de outro humano quando fome e sede estão abaixo de 25 e a energia está acima de 25.

A distância desejada depende do traço: sociabilidade alta tende a aproximar mais o agente; valores médios e baixos mantêm mais espaço. Se já existe outro humano dentro dessa distância, o agente não continua perseguindo pessoas e pode retomar exploração. A interação social tem prioridade inferior a caça ativa, construção, busca de abrigo e coleta de materiais necessários, e não substitui a procura de alimento/água quando as necessidades ficam relevantes. Humanos sob controle manual não recebem decisões autônomas de movimento social.

Na lateral, a seção **SOCIAL** exibe a sociabilidade do humano selecionado e a quantidade de humanos a até três células. Isso é um indicador de proximidade, não uma relação social ou cooperação estabelecida. Nesta etapa não há amizade, memória de indivíduos, comunicação, compartilhamento deliberado nem aprendizagem: o objetivo é observar se a atração espacial moderada já produz agrupamentos espontâneos.


## Identificação e auditoria social

Cada humano recebe um identificador estável dentro da execução (`H001`, `H002`, ...). O ID aparece na barra lateral do humano selecionado e, quando o zoom é suficiente, como rótulo sobre os agentes no mapa. Os mesmos IDs são usados nos arquivos CSV, permitindo relacionar a observação visual aos dados exportados.

A afinidade social é mantida por par de humanos e varia entre 0 e 1. Permanecer a até três células de distância aumenta a afinidade lentamente; ficar a mais de seis células reduz a afinidade de forma gradual. A memória da posição de um contato é atualizada apenas quando ele é percebido e expira após um prazo configurável; a afinidade pode persistir durante o afastamento. Com afinidade suficiente, o agente pode navegar até a última posição conhecida para tentar reencontrar o indivíduo, sem conhecer sua posição atual fora do alcance de percepção. Isso não cria amizade consciente nem cooperação automática.

Ao executar `py -3.13 run_ecosystem_experiment.py`, a pasta `results/ecosystem_experiment/` inclui também:

- `social_history.csv`: uma linha por par vivo e passo, com IDs, posições, distância Manhattan, afinidade anterior/atual, variação, encontros próximos acumulados e evento.
- `social_agents_history.csv`: estado social individual por passo, incluindo ID, sociabilidade, posição, humanos próximos, quantidade de relações relevantes e afinidade mais alta.
- `social_relationships_final.csv`: último registro disponível de cada par em cada execução. Se um agente morrer antes do fim, o último registro pode ser anterior ao passo final.
- `social_decisions_history.csv`: decisão social de cada humano por passo, alvo, afinidade, idade da última observação, motivo, posições antes/depois e se houve movimento.

Os parâmetros podem ser ajustados em `configuration/social_behavior_config.py` por meio de `SocialBehaviorConfig`: ganho de afinidade, decaimento, limiar de reencontro, duração da memória espacial e distância máxima de busca. Para alterar a configuração de uma simulação criada por código, passe `social_config=...` ao construtor de `Simulation`.

`population_history.csv` e `runs.csv` incluem indicadores agregados de proximidade e afinidade. Os valores são instrumentação descritiva: proximidade não deve ser interpretada automaticamente como cooperação ou amizade.

## Auditoria experimental do ecossistema

Para validar a instrumentação e gerar dados reproduzíveis, execute primeiro o piloto e depois a auditoria completa:

```powershell
py -3.13 -m pytest -q
py -3.13 run_ecosystem_audit.py --profile pilot --workers 4
py -3.13 run_ecosystem_audit.py --profile full --workers 4
```

O pipeline paralelo e a descrição dos CSVs estão em `docs/ecosystem_audit.md`. A auditoria também gera `carnivore_hunt_history.csv` e `carnivore_hunt_summary.csv` para investigar mortes por fome: distância e visibilidade de presas, estamina, tentativas de ataque, abates, alimentação e causa de encerramento. Essa instrumentação é apenas observacional e não altera as regras da simulação.

## Shared navigation contract

See [`docs/NAVIGATION_SERVICE.md`](docs/NAVIGATION_SERVICE.md) for the route-planning contract shared by humans, herbivores, and carnivores.

## Escala do mundo e capacidade vegetal

`configuration/simulation_config.py` concentra as densidades iniciais de plantas, água, obstáculos, madeira e pedra. As quantidades iniciais são derivadas da área (`width * height`) multiplicada pela densidade de cada recurso; ao mudar as dimensões, as densidades permanecem constantes, salvo configuração explícita.

O limite de plantas regeneradas também é proporcional à área e usa uma referência configurável: por padrão, 300 plantas para um mundo de 60×60. A capacidade padrão é calculada por `SimulationConfig.max_plants_capacity`; por exemplo, 80×80 resulta em 533, 100×100 em 833 e 200×200 em 3333. `max_plants` explícito continua disponível para experimentos que precisam controlar essa variável deliberadamente. O manifesto da auditoria registra a referência e a capacidade efetiva.


## Atributos individuais

O modelo inicial de atributos biológicos, perfis por espécie, variação individual e capacidades derivadas está documentado em [`docs/AGENT_ATTRIBUTES.md`](docs/AGENT_ATTRIBUTES.md). A variação pode ser controlada por `SimulationConfig.attribute_variation` ou pela opção `--attribute-variation` da auditoria.
## Observabilidade biológica e retirada de carnívoros

As regras puras de retirada e recuperação de saúde ficam em `simulation/carnivore_decisions.py` e `simulation/health_recovery.py`. Os campos novos de auditoria e a semântica dos denominadores estão documentados em [`docs/OBSERVABILIDADE_BIOLOGICA_E_DECISOES.md`](docs/OBSERVABILIDADE_BIOLOGICA_E_DECISOES.md). Para evitar que resultados de auditorias com cópias de testes sejam coletados como testes do projeto, `pytest.ini` limita a descoberta ao diretório `tests/`.
