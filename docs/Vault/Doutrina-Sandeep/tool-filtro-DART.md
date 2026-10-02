# Ferramenta: Filtro DART (Diagnóstico de Complexidade)

**Propósito:** Impedir que o usuário resolva o problema certo usando a ferramenta errada (ex: usar um checklist para criar um adolescente ou mudar uma cultura corporativa).

**Gatilho:** Quando o usuário trouxer um "Problema a ser resolvido" ou pedir para bolar um plano estratégico.

## Instruções de Execução (Roteiro do Agente)

Antes de propor qualquer solução, o agente DEVE classificar a natureza do problema apresentando o resultado da matriz Cynefin. O acrônimo DART (Deconstruct, Analyze, Recognize, Test) é o processo.

### 1. DECONSTRUCT (Desconstrução)
O agente quebra o problema do usuário em partes e avalia: "As partes são estáveis ou estão em constante mudança?"

### 2. ANALYZE (Análise de Causa e Efeito)
O agente classifica o problema em um de 4 quadrantes:

- **SISTEMA CLARO (Clear):** Causa e efeito são óbvios (ex: receita médica). 
  - *Resposta do Agente:* "Use um Checklist. Não inove. Siga o processo."
- **SISTEMA COMPLICADO (Complicated):** Causa e efeito existem, mas exigem perícia (ex: arquitetura de software, planejamento financeiro). 
  - *Resposta do Agente:* "Desacelere. Traga um especialista. Faça análise profunda."
- **SISTEMA COMPLEXO (Complex):** Causa e efeito só são visíveis em retrospectiva. Humanos e cultura envolvidos (ex: integração de empresas, lançamento de produto inovador). 
  - *Resposta do Agente:* "Não crie um plano de 5 anos. Faça experimentos pequenos (Test/Sense) e ajuste a direção em tempo real."
- **SISTEMA CAÓTICO (Chaotic):** Link entre causa e efeito está quebrado. Cenário de crise profunda. 
  - *Resposta do Agente:* "Ação imediata. Estabilize o sistema primeiro. Pare o sangramento antes de tentar entender o que aconteceu. Análise gera paralisia aqui."

### 3. RECOGNIZE & TEST
O agente valida se já viu um padrão semelhante no Vault (Recognize) e propõe o menor teste possível (Test).

**Comando de Saída do Agente:** "Pelo diagnóstico DART, você está lidando com um problema [CLARO / COMPLICADO / COMPLEXO / CAÓTICO]. O seu plano original estava usando a abordagem errada. Faça X."
