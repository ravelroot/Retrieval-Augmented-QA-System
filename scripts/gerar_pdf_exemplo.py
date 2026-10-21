from __future__ import annotations

import sys
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate

PAGES = [
    ("1. Instalação", "Conecte o cabo de energia de 12 V na porta DC IN localizada na parte traseira. O LED de energia fica verde em até 30 segundos. Não utilize fontes com tensão diferente de 12 V, pois isso danifica o circuito de proteção."),
    ("2. Redefinição de fábrica", "Para restaurar as configurações de fábrica, mantenha o botão RESET pressionado por 15 segundos com o aparelho ligado. O LED de status pisca em laranja três vezes e o roteador reinicia. Todas as senhas voltam ao padrão impresso na etiqueta inferior."),
    ("3. Rede sem fio", "A rede de 5 GHz suporta canais de 36 a 165. Para reduzir interferência em ambientes com muitos vizinhos, escolha canais acima de 100 e largura de banda de 80 MHz. A potência de transmissão pode ser ajustada entre 10% e 100% no menu Wi-Fi Avançado."),
    ("4. Atualização de firmware", "Baixe o firmware pelo menu Sistema > Atualização. Nunca desligue o equipamento durante a gravação, que leva cerca de 4 minutos. Se a atualização falhar, o roteador entra em modo de recuperação e o LED de status fica vermelho fixo."),
    ("5. Especificações", "Temperatura de operação: 0 °C a 40 °C. Umidade: 10% a 90% sem condensação. Consumo máximo: 18 W. Portas: 4 LAN Gigabit e 1 WAN 2,5 Gigabit."),
]


def main() -> None:
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "manual-exemplo.pdf")
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(str(out), pagesize=A4, title="Manual do Roteador Fictício RX-200")
    story = []
    for title, body in PAGES:
        extra = body.replace(".", ";", 1) + " Consulte o suporte técnico se o problema persistir."
        story += [Paragraph(title, styles["Heading1"]), Paragraph(body, styles["BodyText"]),
                  Paragraph(extra, styles["BodyText"]), PageBreak()]
    doc.build(story)
    print(f"PDF de exemplo criado em {out}")


if __name__ == "__main__":
    main()
