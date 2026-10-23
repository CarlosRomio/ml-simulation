# Reprodução e ciclo de vida — etapa 1

## Escopo

Esta etapa liga o genótipo hereditário já existente ao ciclo de vida e à reprodução. Não altera diretamente os parâmetros de caça nem o modelo de mutação existente.

## Modelo implementado

- Cada indivíduo recebe um `LifeHistoryState` com identificador, sexo, idade em passos simulados, geração, progenitores, período de recuperação reprodutiva e estado de gestação/incubação.
- Fundadores iniciam como adultos para que experimentos de duração curta possam observar acasalamentos. Os descendentes começam com idade zero.
- A busca por parceiros só pode substituir a exploração quando o indivíduo está elegível e suas necessidades não são urgentes.
- A busca por parceiro é específica por espécie e requer dois indivíduos vivos, maduros, elegíveis e de sexos diferentes.
- O acasalamento armazena o genótipo do segundo progenitor; o nascimento combina os dois genótipos via `IndividualGenotype.inherit()`.
- O recém-nascido recebe um ID único dentro da espécie, geração parental + 1 e referências aos progenitores.
- O nascimento só ocorre em uma célula adjacente livre e caminhável. Se não houver espaço, o nascimento é adiado.
- Há custo energético no acasalamento, período de recuperação reprodutiva e morte por idade máxima.
- Eventos de acasalamento, nascimento e morte por idade são registrados em `reproduction_events.csv` durante a auditoria ecológica. Eventos de nascimento incluem os valores genéticos do descendente.

## Escalas temporais de prototipagem

As durações são medidas em passos simulados e foram comprimidas para permitir observar o ciclo em experimentos curtos. Não representam idades, gestações ou longevidades biológicas reais.

| Espécie | Maturidade | Gestação/incubação | Recuperação reprodutiva | Idade máxima |
|---|---:|---:|---:|---:|
| Humano | 500 passos | 240 passos | 180 passos | 6.000 passos |
| Herbívoro | 220 passos | 90 passos | 100 passos | 6.000 passos |
| Carnívoro | 280 passos | 130 passos | 140 passos | 6.000 passos |

Esses parâmetros devem migrar para configuração externa antes de estudos científicos sistemáticos. Os valores atuais são uma calibração inicial de protótipo.

## Limitações conhecidas

- Sexo é binário (`F`/`M`) e atribuído de forma simplificada; não há genética sexual.
- Não há escolha de parceiro por parentesco, compatibilidade genética, afinidade ou condição territorial.
- A busca por parceiro usa navegação por caminho até uma célula adjacente, mas ainda não possui coordenação de pares nem prevenção explícita de múltiplos indivíduos perseguirem o mesmo parceiro.
- Não há custo energético contínuo de gestação/incubação nem cuidado parental.
- O fenótipo é expresso diretamente a partir dos valores genéticos; nem todos os nove traços hereditários influenciam ainda decisões comportamentais.
- A seleção natural ainda não é medida como aptidão completa por indivíduo; os eventos e a genealogia são a base para construir essa análise.
- A morte por idade máxima é uma regra abstrata e aparece nos eventos reprodutivos como `DEATH_OLD_AGE`.

## Validação

A suíte de testes desta etapa cobre fundadores adultos, acasalamento por proximidade, elegibilidade fisiológica, movimento de busca, nascimento, genealogia, registro de métricas para humanos e reprodução das três espécies. A auditoria curta verifica a exportação de `reproduction_events.csv` e os campos genéticos iniciais.
