# Base de teste

Arquivos fictícios sobre o Roteador RX-200 para testar o Nexo sem precisar dos seus documentos. Cada um usa um formato diferente, para conferir a leitura de todos eles:

| Arquivo | Formato | Conteúdo |
|---|---|---|
| `manual-roteador-rx200.pdf` | PDF | Manual com instalação, redefinição, Wi-Fi, firmware e especificações |
| `garantia.md` | Markdown | Prazo, cobertura e como acionar a garantia |
| `perguntas-frequentes.html` | HTML | Senha do Wi-Fi, limite de aparelhos, operadoras e rede de convidados |
| `planos-de-suporte.csv` | CSV | Planos, preços e visitas técnicas |
| `horario-de-atendimento.txt` | Texto | Horários do chat, do e-mail e do telefone |
| `especificacoes.json` | JSON | Ficha técnica do aparelho |

## Como criar a base

- Pela tela: em **Bases de conhecimento**, clique em **Criar base de teste**.
- Pela linha de comando, com o servidor parado: `python -m nexo base-de-teste`.

Os dois caminhos criam a base **Base de teste** com esses arquivos e o agente **Agente de teste**, que já vem com perguntas sugeridas. Se a base já existir, nada é duplicado.

## Perguntas para experimentar

- Como restaurar as configurações de fábrica?
- Quanto tempo dura a garantia?
- Quantos aparelhos posso conectar ao mesmo tempo?
- Quanto custa o plano Plus?
- O suporte atende aos sábados?
- Quantas portas LAN o roteador tem?
- Qual a previsão do tempo para amanhã? (fora do conteúdo: o agente diz que não encontrou)

Para medir o acerto da busca nessa base: `python scripts/avaliar.py exemplos/base-de-teste/perguntas-de-teste.jsonl --detalhes`.
