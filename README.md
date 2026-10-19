# ML Simulation — auditoria fisiológica e ecológica

Projeto de simulação em grade para estudar sobrevivência de humanos e interações com herbívoros e carnívoros. Nesta etapa, os agentes usam regras explícitas; não há aprendizado de máquina treinado.

## Executar

```powershell
py -3.13 -m pytest -q
py -3.13 run_ecosystem_experiment.py
```

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

A afinidade social é mantida por par de humanos e varia entre 0 e 1. Permanecer a até três células de distância aumenta a afinidade lentamente; ficar a mais de seis células reduz a afinidade de forma gradual. A afinidade influencia qual humano visível o agente prefere procurar, mas não cria amizade instantânea nem cooperação automática.

Ao executar `py -3.13 run_ecosystem_experiment.py`, a pasta `results/ecosystem_experiment/` inclui também:

- `social_history.csv`: uma linha por par vivo e passo, com IDs, posições, distância Manhattan, afinidade anterior/atual, variação, encontros próximos acumulados e evento.
- `social_agents_history.csv`: estado social individual por passo, incluindo ID, sociabilidade, posição, humanos próximos, quantidade de relações relevantes e afinidade mais alta.
- `social_relationships_final.csv`: último registro disponível de cada par em cada execução. Se um agente morrer antes do fim, o último registro pode ser anterior ao passo final.

`population_history.csv` e `runs.csv` incluem indicadores agregados de proximidade e afinidade. Os valores são instrumentação descritiva: proximidade não deve ser interpretada automaticamente como cooperação ou amizade.
