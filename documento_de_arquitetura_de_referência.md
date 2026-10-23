# ml-simulation
## Documento de Arquitetura de Referência

**Versão:** 0.1 — proposta arquitetural  
**Status:** Base conceitual consolidada; pendente de validação contra a implementação existente  
**Linguagem atual:** Python  
**Visualização atual:** Pygame  
**Direção futura:** Possível migração seletiva de componentes para C++

---

## 1. Objetivo e escopo

O `ml-simulation` é um simulador de ecossistema baseado em agentes, desenvolvido para investigar interações ecológicas, fisiologia, comportamento, navegação, reprodução, genética e sobrevivência em um ambiente espacial discreto.

O projeto deve evoluir de uma implementação experimental para uma plataforma de simulação capaz de sustentar experimentos reproduzíveis, comparação de políticas comportamentais, análise estatística e futuras otimizações de desempenho.

Este documento estabelece a arquitetura-alvo e os critérios que deverão orientar a análise e a evolução do código.

### Objetivos arquiteturais

1. Preservar a integridade e a consistência do estado do mundo.
2. Tornar explícitas as regras que determinam a evolução da simulação.
3. Permitir substituir políticas e algoritmos sem reescrever o motor.
4. Garantir reprodutibilidade experimental e rastreabilidade dos resultados.
5. Separar domínio, execução, experimentação, persistência e visualização.
6. Permitir otimizações localizadas sem comprometer a semântica científica.
7. Facilitar testes unitários, testes de integração e auditorias de longo prazo.

### Fora do escopo imediato

- Implementar um ECS completo.
- Dividir o sistema em microsserviços.
- Migrar imediatamente a simulação para C++.
- Escolher um algoritmo de aprendizado específico.
- Alterar regras ecológicas sem evidência e validação.
- Introduzir abstrações genéricas antes de demonstrar sua necessidade.

---

## 2. Princípios fundamentais

### 2.1. Monólito modular

O sistema será organizado como um monólito modular, com fronteiras internas explícitas.

Os módulos podem ser executados no mesmo processo, mas devem possuir responsabilidades e dependências bem definidas.

### 2.2. Separação entre domínio e infraestrutura

As regras do ecossistema não devem depender de Pygame, formatos CSV, bibliotecas de análise estatística ou mecanismos de persistência.

A visualização representa o estado da simulação; não é responsável por determinar esse estado.

### 2.3. Entidades enxutas e serviços especializados

Entidades representam identidade e estado. Serviços de domínio implementam regras que coordenam uma ou mais entidades. O motor determina a ordem de execução.

Funções puras devem ser utilizadas quando um cálculo puder ser realizado sem alterar o estado.

### 2.4. Estado autoritativo único

Cada fato mutável deve possuir uma única fonte autoritativa.

Índices espaciais, caches e estatísticas derivadas não podem funcionar como fontes independentes de verdade.

### 2.5. Execução sequencial como referência

A semântica da simulação deve ser definida independentemente da estratégia de paralelismo.

A primeira referência é a execução sequencial determinística. O paralelismo poderá ser introduzido em réplicas independentes ou em componentes específicos após análise de desempenho e dependências.

### 2.6. Evolução baseada em evidências

Uma abstração ou otimização deve ser justificada por uma necessidade identificada, um contrato verificável ou uma medição de desempenho.

A arquitetura não deve ser orientada apenas por preferências de estilo.

---

## 3. Visão geral dos módulos

A organização conceitual proposta é a seguinte:

```text
ml-simulation
│
├── domain
│   ├── agents
│   ├── physiology
│   ├── cognition
│   ├── ecology
│   ├── reproduction
│   ├── environment
│   ├── resources
│   └── spatial
│
├── simulation
│   ├── engine
│   ├── phases
│   ├── action_resolution
│   ├── lifecycle
│   └── world_audit
│
├── experimentation
│   ├── experiment_definition
│   ├── replication
│   ├── parameter_sweeps
│   └── comparison
│
├── observability
│   ├── domain_events
│   ├── metrics
│   └── diagnostics
│
├── persistence
│   ├── result_export
│   ├── checkpoint
│   └── schemas
│
├── adapters
│   ├── visualization
│   ├── csv
│   └── external_integrations
│
└── applications
    ├── visualization_runner
    ├── experiment_runner
    └── audit_runner
```

Os nomes representam responsabilidades lógicas, não necessariamente diretórios que devam ser criados literalmente.

A estrutura final deverá ser adaptada ao código real. Não se deve mover arquivos indiscriminadamente apenas para reproduzir esse diagrama.

### 3.1. Dependências permitidas

- O domínio não depende do motor, de Pygame ou da persistência.
- O motor depende dos contratos dos serviços de domínio.
- A resolução de ações depende das regras de interação e do estado necessário para validar e confirmar resultados.
- A experimentação instancia e configura execuções, mas não altera diretamente o estado de agentes.
- A observabilidade recebe fatos e amostras, sem controlar as decisões dos agentes.
- A persistência serializa resultados e checkpoints por meio de contratos explícitos.
- A visualização consome dados da simulação e envia comandos autorizados, sem modificar diretamente as entidades.
- Os pontos de entrada conectam configuração, motor, coletores e adaptadores.

A dependência deve apontar para a responsabilidade que define o contrato, e não para uma implementação concreta desnecessária.

---

## 4. Modelo de domínio

### 4.1. Agentes e identidade

Cada agente possui um identificador estável, independente de sua posição em listas, vetores ou índices espaciais.

O domínio deve distinguir:

- Identidade do agente.
- Estado biológico e comportamental.
- Espécie e características herdadas.
- Capacidades disponíveis.
- Memória e estado cognitivo.
- Localização atual.
- Estado do ciclo de vida.

O agente não deve concentrar toda a lógica de fisiologia, navegação, combate, reprodução e sobrevivência em uma única classe.

### 4.2. Fisiologia

A fisiologia representa o estado biológico e suas transições: fome, sede, saúde, energia, envelhecimento, recuperação e outras variáveis que venham a ser confirmadas no modelo.

As regras fisiológicas pertencem a serviços especializados, enquanto o agente mantém o estado correspondente.

### 4.3. Cognição e decisão

O pipeline conceitual é:

```text
Estado observável do mundo
          ↓
Percepção
          ↓
Observações
          ↓
Memória e objetivos
          ↓
Política de decisão
          ↓
Intenções de ação
```

A política escolhe entre alternativas segundo necessidades, objetivos, capacidades, memória e regras de decisão.

A decisão não equivale à execução. Uma intenção pode ser recusada, invalidada ou derrotada em um conflito.

### 4.4. Ecologia e interações

As interações ecológicas abrangem predação, defesa, alimentação, competição e outras relações confirmadas pelo modelo.

Cada interação relevante deve possuir um contrato que defina:

1. Participantes e pré-condições.
2. Informações necessárias.
3. Regras de resolução.
4. Alterações autorizadas no estado.
5. Eventos produzidos após a confirmação.

### 4.5. Reprodução e evolução

A reprodução e a evolução devem distinguir:

- Elegibilidade reprodutiva.
- Seleção de parceiros.
- Herança de características.
- Mutação.
- Nascimento.
- Sobrevivência e seleção ao longo das gerações.

A arquitetura deve permitir alterar as regras evolutivas sem exigir mudanças no motor, exceto quando houver impacto real no ciclo de vida ou na ordem das fases.

---

## 5. Espécies, capacidades e especialização

A estratégia padrão será composição de capacidades, com especializações quando houver diferenças reais de comportamento ou regras.

### 5.1. Princípio

Uma espécie não deve exigir uma hierarquia própria de classes apenas para representar diferenças de parâmetros.

Diferenças quantitativas, como velocidade, alcance sensorial ou eficiência metabólica, devem ser representadas por características ou configurações quando isso for suficiente.

Diferenças qualitativas de comportamento podem exigir capacidades especializadas e, em casos justificados, implementações distintas.

### 5.2. Critério para criar uma capacidade

Uma capacidade merece uma abstração própria quando possui:

- Responsabilidade identificável.
- Regras ou dados próprios.
- Contrato que possa ser testado independentemente.
- Potencial real de reutilização ou substituição.

Não se deve criar uma classe para cada ação ou característica apenas por uniformidade.

### 5.3. Regra de dependência

Os serviços devem consultar as capacidades e características pertinentes por meio de contratos estáveis. Não devem depender de verificações espalhadas por todo o código, como uma sucessão de condicionais que reconhecem nomes concretos de espécies.

Especializações são permitidas quando a regra é efetivamente diferente, e não apenas porque duas espécies possuem nomes distintos.

---

## 6. Parâmetros e configuração

A arquitetura distingue três categorias.

### 6.1. Parâmetros da execução

São definidos e validados antes de iniciar a réplica e permanecem imutáveis durante ela.

Exemplos incluem dimensões do mundo, população inicial, regras de execução e parâmetros experimentais fixos.

A configuração resolvida deve ser registrada integralmente, incluindo valores padrão relevantes.

### 6.2. Características dos agentes

Características herdadas ou atribuídas na criação pertencem ao modelo do agente.

Seu valor inicial pode depender da espécie, genética, parâmetros da execução ou regras de inicialização. Eventuais alterações durante a vida do agente devem obedecer às regras explícitas do domínio.

### 6.3. Estado dinâmico

Representa fatos que evoluem durante a execução, como condições ambientais, recursos disponíveis, necessidades e população.

Esses valores não são parâmetros imutáveis só porque influenciam o comportamento. São parte do estado autoritativo do mundo.

### 6.4. Configuração validada

A configuração deve ser validada antes da inicialização. Uma configuração inválida impede o início da réplica.

Valores derivados devem ser calculados de maneira consistente e não devem criar cópias mutáveis divergentes dos parâmetros originais.

---

## 7. Motor e ciclo de vida da simulação

O motor é responsável por:

- Inicializar o estado.
- Controlar o relógio lógico.
- Executar as fases na ordem definida.
- Coordenar serviços e resolvers.
- Aplicar políticas de falha.
- Executar auditorias globais.
- Finalizar a réplica e produzir seu resultado.

Nenhum subsistema avança o relógio lógico ou inicia o próximo passo por conta própria.

### 7.1. Ordem de referência das fases

A ordem abaixo é uma proposta a ser validada contra as regras atuais:

1. Preparação dos agentes ativos.
2. Atualização fisiológica e ambiental.
3. Percepção.
4. Decisão.
5. Resolução das intenções e dos conflitos.
6. Aplicação de consequências confirmadas.
7. Reprodução e registro de nascimentos pendentes.
8. Limpeza e remoções físicas autorizadas.
9. Auditoria global, métricas e conclusão do passo.

A ordem definitiva deverá ser registrada como parte da semântica científica do modelo.

### 7.2. Contrato das fases

Cada fase deve possuir:

- Responsabilidade explícita.
- Pré-condições.
- Dados que pode consultar.
- Alterações que pode confirmar.
- Resultados produzidos.
- Pós-condições.
- Política de falha.

Nem todas as fases precisam de uma classe ou interface própria. A abstração será definida a partir das necessidades reais do projeto.

### 7.3. Nascimento e morte

O nascimento é uma transição confirmada durante a reprodução, mas o novo agente só participa das decisões a partir do próximo passo completo.

A morte é uma transição de ciclo de vida. A remoção física ocorre no ponto definido de limpeza, após o processamento das consequências necessárias.

Um agente morto não inicia novas ações normais. A conclusão de ações já iniciadas depende de regras explícitas.

---

## 8. Resolução de ações e conflitos

As ações são intenções até que sejam validadas, resolvidas e confirmadas.

### 8.1. Protocolo geral

1. Coletar as intenções relevantes.
2. Validar suas pré-condições.
3. Agrupar conflitos por entidade, posição ou recurso.
4. Resolver os conflitos segundo regras específicas da interação.
5. Confirmar os resultados.
6. Registrar fatos correspondentes.

A resolução pode ocorrer em execução sequencial. A simultaneidade é uma propriedade da semântica de resolução, não uma exigência de execução paralela.

### 8.2. Regras específicas

Movimento, caça, fuga, ataque, alimentação e construção não devem ser forçados a compartilhar uma única regra universal de prioridade.

Cada categoria deve definir suas regras de concorrência, precedência e desempate.

Quando a aleatoriedade for necessária, ela deverá utilizar o gerador controlado da execução.

### 8.3. Atomicidade lógica

Operações que envolvem múltiplas entidades devem ser coordenadas por um serviço especializado e confirmadas como uma única transição lógica.

O protocolo é:

- Validar pré-condições.
- Calcular o resultado.
- Preparar as alterações.
- Confirmar as alterações coerentemente.
- Publicar os eventos correspondentes.

Não é necessário um sistema genérico de transações ou um banco de dados. É necessário impedir estados parcialmente atualizados.

A estratégia para falhas durante a confirmação deve ser definida por operação. Não se deve pressupor que todas as alterações em memória possam ser revertidas automaticamente.

---

## 9. Espaço e navegação

O mundo utiliza uma grade regular, com limites explícitos e oito direções de vizinhança.

### 9.1. Topologia e ocupação

As responsabilidades espaciais são separadas conceitualmente:

- Topologia: dimensões, limites, células válidas e vizinhança.
- Índice espacial: consulta de agentes, recursos e obstáculos.
- Navegação: objetivos e acompanhamento de rotas.
- Pathfinder: cálculo de caminhos.
- Resolução de movimento: validação e resolução dos deslocamentos.

O índice espacial é uma estrutura derivada do estado autoritativo e deve ser atualizado após mudanças confirmadas.

### 9.2. Movimento

O modelo deve definir:

- Capacidade de ocupação por tipo de entidade.
- Resolução de destinos concorridos.
- Entrada em células que serão desocupadas por movimentos aceitos.
- Trocas de posição.
- Impedimento de corte diagonal de cantos bloqueados.
- Custos ortogonais e diagonais compatíveis com o algoritmo de busca.

A* é a opção de referência. Com custo ortogonal igual a 1 e diagonal igual a √2, a distância octil é uma heurística admissível para a grade sem considerar obstáculos adicionais.

Distância geométrica e custo de caminho são medidas distintas e não devem ser confundidas.

### 9.3. Navegação e decisão

A política escolhe o objetivo. O pathfinder calcula a rota. O serviço de navegação acompanha progresso e invalidação. O resolver determina se o movimento solicitado pode ser executado.

A rota pode ser reutilizada enquanto o objetivo permanecer válido e o próximo movimento continuar possível. Mecanismos sofisticados de cache só devem ser adicionados se necessários.

---

## 10. Invariantes e falhas

Todas as invariantes globais devem ser verificadas ao final de cada passo.

Exemplos:

- Identificadores únicos.
- Estados de vida coerentes.
- Posições dentro dos limites do mundo.
- Índices espaciais consistentes.
- Recursos não negativos e consumo dentro da disponibilidade.
- Ausência de referências autoritativas a entidades removidas.
- Eventos de transição coerentes com fatos confirmados.

As operações devem manter suas invariantes locais. As verificações globais são executadas no limite do passo.

### Política de falha

Uma ação inválida segundo as regras do domínio pode ser recusada normalmente. Uma configuração inválida impede a inicialização. Uma falha de integridade ou de fase interrompe a réplica e preserva os diagnósticos.

Não deve haver correção silenciosa de inconsistências globais.

As verificações completas são obrigatórias após cada passo, conforme decisão aprovada. A implementação poderá ser otimizada sem reduzir a cobertura sem uma decisão explícita.

---

## 11. Eventos, métricas e observabilidade

Eventos de domínio representam fatos confirmados. Métricas são observações ou agregações desses fatos e do estado.

Exemplos de fatos:

- Ataque resolvido.
- Recurso consumido.
- Agente morto.
- Nascimento confirmado.
- Agente removido.

Intenções não devem ser confundidas com resultados. `HuntRequested`, por exemplo, não significa que a caça foi bem-sucedida.

### 11.1. Política de coleta

Os coletores podem ser configurados conforme o objetivo da execução:

- Visualização.
- Experimento em lote.
- Auditoria científica.
- Diagnóstico de falhas.

Desativar um coletor não pode alterar a evolução do mundo.

A persistência deve ser desacoplada dos serviços de domínio. Uma falha de escrita não pode silenciosamente mudar regras ecológicas; seu tratamento deve seguir uma política explícita de falha ou degradação do registro.

---

## 12. Reprodutibilidade, versionamento e checkpoints

### 12.1. Identificadores independentes

Cada execução registra:

- Versão semântica do modelo.
- Revisão do código.
- Versão do esquema de dados.
- Configuração resolvida.
- Semente e estado dos geradores aleatórios relevantes.
- Identificador da réplica.
- Estado final e situação da execução.

A versão científica muda quando muda a semântica do modelo, não a cada alteração de arquivo.

### 12.2. Checkpoints

Checkpoints são opcionais e só podem ser criados entre passos completos.

Devem preservar o estado necessário para continuar a execução, incluindo estado aleatório, relógio lógico e qualquer informação pendente que afete o futuro.

Índices espaciais e caches podem ser reconstruídos quando forem derivados e sua reconstrução não alterar o comportamento.

### 12.3. Teste de retomada

Para um cenário determinístico, executar continuamente até o passo N deve produzir os mesmos resultados que executar até o passo K, salvar, retomar e continuar até N.

Essa equivalência precisa ser testada explicitamente.

---

## 13. Experimentação e resultados

A arquitetura deve separar uma execução individual de um experimento composto por várias réplicas.

### 13.1. Configuração da simulação

Define as condições de uma réplica.

### 13.2. Configuração do experimento

Define o conjunto de réplicas, sementes, variações de parâmetros e políticas de coleta.

### 13.3. Contexto da execução

Mantém a configuração resolvida, identificação da réplica, relógio lógico, versão do modelo e informações necessárias para rastreabilidade.

### 13.4. Execução de réplicas

O paralelismo deve começar por réplicas independentes, com sementes distintas e controle explícito da atribuição de sementes.

A comparação de experimentos deve separar métricas por réplica de estatísticas agregadas. A análise estatística não deve ser incorporada ao motor.

---

## 14. Estratégia de testes

A validação será organizada por níveis.

### Testes unitários

Regras fisiológicas, cálculos, navegação, seleção de objetivos e decisões isoladas.

### Testes de serviço

Operações que coordenam entidades, recursos, transições de estado e eventos.

### Testes de integração

Interação entre fases, índices espaciais, ciclo de vida e resolvers.

### Testes de invariantes

Auditoria global ao final de cada passo e cenários deliberadamente inválidos.

### Testes de determinismo

Comparação de execuções com a mesma configuração e semente.

### Testes de checkpoint

Equivalência entre execução contínua e execução retomada.

### Testes de arquitetura

Verificação de que o domínio não importa infraestrutura e de que as dependências seguem as fronteiras estabelecidas.

### Testes de equivalência entre implementações

Quando houver migração para C++, comparar resultados e invariantes usando cenários controlados, respeitando as tolerâncias numéricas explicitamente definidas.

---

## 15. Estratégia de desempenho e possível migração para C++

Python continua sendo a linguagem de referência até que medições demonstrem onde estão os gargalos.

A ordem recomendada é:

1. Estabelecer benchmarks reproduzíveis.
2. Perfilar o custo por fase e por subsistema.
3. Reduzir trabalho redundante e corrigir algoritmos ineficientes.
4. Identificar estruturas de dados e operações de alto volume.
5. Definir contratos estáveis para componentes candidatos à migração.
6. Implementar alternativas em C++ apenas quando houver benefício demonstrável.
7. Comparar desempenho, memória, determinismo e equivalência comportamental.

A arquitetura deve permitir que Python continue responsável pela orquestração experimental, análise e visualização, enquanto componentes de cálculo intensivo possam ser substituídos.

Não há decisão de migrar módulos específicos neste momento.

---

## 16. Questões científicas ainda não resolvidas

Estas decisões pertencem ao modelo científico e não podem ser determinadas apenas por conveniência arquitetural.

1. Ordem exata dos efeitos fisiológicos, percepção e decisão.
2. Semântica temporal de ataques, fugas e movimentos simultâneos.
3. Regras de cooperação, disputa e compartilhamento de recursos.
4. Critérios de elegibilidade e sucesso reprodutivo.
5. Modelo de herança, mutação e aprendizagem.
6. Regras de conclusão ou cancelamento de ações já iniciadas após a morte de um agente.
7. Tolerâncias numéricas e critérios de equivalência entre implementações.
8. Quais métricas e eventos devem ser coletados em cada perfil de experimento.

Cada mudança nessas regras deve ser documentada e validada com testes ou experimentos adequados.

---

## 17. Critérios para aprovação da arquitetura-alvo

A arquitetura será considerada suficientemente definida para orientar a refatoração quando:

- As responsabilidades e dependências dos módulos estiverem documentadas.
- A ordem e a semântica das fases estiverem estabelecidas.
- Os contratos de estado, intenção, resolução e evento estiverem definidos.
- As invariantes globais tiverem critérios verificáveis.
- A política de determinismo e as sementes estiverem especificadas.
- A persistência e a retomada tiverem requisitos explícitos.
- As questões científicas relevantes estiverem separadas das decisões de implementação.
- Existir uma estratégia de migração incremental com critérios de aceitação.

---

## 18. Próxima etapa: auditoria da implementação atual

O próximo trabalho será comparar o código existente com este documento, sem modificar arquivos.

A auditoria deverá produzir:

1. **Mapa da arquitetura atual:** módulos, dependências e pontos de entrada.
2. **Matriz de aderência:** decisões aprovadas, parcialmente implementadas, ausentes ou conflitantes.
3. **Mapa de riscos:** inconsistências de estado, acoplamentos, regras duplicadas e dependências circulares.
4. **Análise de desempenho:** evidências existentes e necessidade de profiling adicional.
5. **Plano de migração:** etapas pequenas, dependências, testes de regressão e critérios de conclusão.
6. **Lista de questões abertas:** somente as decisões que dependem de evidências do código ou de validação científica.

Nenhuma alteração será feita durante essa auditoria. Qualquer proposta de modificação será apresentada com justificativa, impacto esperado, riscos e testes necessários antes da implementação.

**Princípio final:** a arquitetura de referência orienta a evolução do `ml-simulation`, mas não justifica refatorar componentes que já atendam aos contratos. A migração deve preservar comportamentos válidos, corrigir problemas demonstráveis e introduzir mudanças científicas somente quando forem explicitamente justificadas e validadas.
