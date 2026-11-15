"""Create the three IJDAR vector figures locally. Run from any directory."""
import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
from matplotlib import pyplot as plt
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


HERE = Path(__file__).resolve().parent
FONT = HERE / "fonts"
pdfmetrics.registerFont(TTFont("Diagram", str(FONT / "NotoSans-Regular.ttf")))
pdfmetrics.registerFont(TTFont("DiagramBold", str(FONT / "NotoSans-Bold.ttf")))
INK = HexColor("#172629")
ACCENT = HexColor("#205860")
RULE = HexColor("#758388")
PALE = HexColor("#edf3f3")
WIDTH = 454


def new_canvas(filename, height, title):
    c = canvas.Canvas(str(HERE / filename), pagesize=(WIDTH, height),
                      invariant=1, initialFontName="Diagram", initialFontSize=9)
    c.setTitle(title)
    c.setAuthor("")
    return c


def label(c, x, y, text, *, size=9, bold=False, color=INK, maxwidth=None, centered=False):
    font = "DiagramBold" if bold else "Diagram"
    if maxwidth is not None and pdfmetrics.stringWidth(text, font, size) > maxwidth:
        raise ValueError(f"Label exceeds its allocated width: {text}")
    c.setFillColor(color)
    c.setFont(font, size)
    if centered:
        c.drawCentredString(x, y, text)
    else:
        c.drawString(x, y, text)


def step(c, x, y, width, title, detail):
    c.setFillColor(white)
    c.setStrokeColor(RULE)
    c.setLineWidth(.65)
    c.roundRect(x, y, width, 31, 2, fill=1)
    label(c, x+width/2, y+18, title, size=9.6, bold=True, maxwidth=width-10, centered=True)
    label(c, x+width/2, y+6, detail, maxwidth=width-10, centered=True)


def arrow(c, start, stop, y):
    c.setStrokeColor(INK)
    c.setLineWidth(.9)
    c.line(start, y, stop, y)
    c.line(stop-3.3, y+2.3, stop, y)
    c.line(stop-3.3, y-2.3, stop, y)


def workflow():
    c = new_canvas("Fig1_pipeline.pdf", 181, "Source conditions and evaluation design")
    label(c, 3, 168, "Transcription", size=12, bold=True)
    label(c, 90, 168, "Archived OCR and vision-language model outputs", color=ACCENT)
    lanes = [
        (130, [("A   Poetry", "Seven scanned pages"), ("Vary the reference", "Supplied or single-copy draft"),
               ("Reference sensitivity", "OCR and scorer held fixed")]),
        (93, [("B   Prose", "Common 72-page scan"), ("Vary the representation", "Digital reference held fixed"),
              ("Reference agreement", "DeepSeek and DP-2-mini")]),
        (35, [("Queries from reference", "Content or ordinal terms"), ("BM25 ranking", "Sections or token windows"),
              ("Positional target", "Credit follows chunk index")]),
    ]
    label(c, 3, 73, "Retrieval", size=12, bold=True)
    label(c, 90, 73, "Archived protocols on the prose collection", color=ACCENT)
    gap = 18
    box_width = (448 - 2*gap)/3
    for y, cards in lanes:
        for column, (title, detail) in enumerate(cards):
            x = 3 + column*(box_width + gap)
            step(c, x, y, box_width, title, detail)
            if column < 2:
                end = x + box_width
                arrow(c, end+2, end+gap-2, y+15.5)
    c.setDash(3, 2)
    c.setLineWidth(.7)
    c.setStrokeColor(RULE)
    c.roundRect(3, 4, 448, 23, 2)
    c.setDash()
    title = "Prospective design only"
    detail = "Independent common queries and content-based judgments"
    title_width = pdfmetrics.stringWidth(title, "DiagramBold", 9.6)
    detail_width = pdfmetrics.stringWidth(detail, "Diagram", 9)
    x = (WIDTH - title_width - 10 - detail_width)/2
    label(c, x, 12, title, size=9.6, bold=True, color=ACCENT)
    label(c, x+title_width+10, 12, detail)
    c.save()


def poetry():
    with (HERE / "Fig2_reference_values.csv").open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    s = [100*float(row["legacy_reference_CER"]) for row in rows]
    d = [100*float(row["single_copy_CER"]) for row in rows]
    matplotlib.font_manager.fontManager.addfont(FONT / "NotoSans-Regular.ttf")
    plt.rcParams.update({"pdf.fonttype": 42, "font.family": "Noto Sans", "font.size": 8.5,
                         "axes.spines.top":False,"axes.spines.right":False, "hatch.linewidth":.55})
    fig, ax = plt.subplots(figsize=(WIDTH/72, 1.96))
    width = .34
    mark_s = ax.bar([i-width/2 for i in range(len(rows))], s, width, color="white",
                    edgecolor="#354448", linewidth=.8, hatch="///", label="Supplied reference (S)")
    mark_d = ax.bar([i+width/2 for i in range(len(rows))], d, width, color="#21616a",
                    edgecolor="#21616a", linewidth=.8, label="Single-copy draft (D)")
    assert [bar.get_height() for bar in mark_s] == s and [bar.get_height() for bar in mark_d] == d
    ax.set_axisbelow(True)
    ax.grid(axis="y", color="#d4dadb", linewidth=.5)
    ax.set_ylim(0, 30)
    ax.set_yticks(range(0,31,5))
    ax.set_ylabel("CER (%)")
    ax.set_xticks(range(len(rows)), [r["system"] for r in rows])
    ax.tick_params(length=2.5)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.015), ncol=2, borderaxespad=0, frameon=False)
    fig.subplots_adjust(left=.103, right=.993, top=.805, bottom=.19)
    fig.savefig(HERE / "Fig2_reference_sensitivity.pdf",
                metadata={"CreationDate":None,"ModDate":None,"Title":"One output, two poetry references"})
    plt.close(fig)


def heading_trace():
    c = new_canvas("Fig3_positional_target.pdf", 110, "DeepSeek title query and its assigned passage")
    # The two headings share a baseline. Keep the original text continuous so
    # the boundary can be placed at its measured glyph position.
    left, right = 102, WIDTH-102
    for x, context, section in [(left, "Reference-derived title query", "Section 8"),
                                (right, "Heading in the DeepSeek output", "Section 18")]:
        label(c, x, 100, context, size=9, color=ACCENT, centered=True)
        label(c, x, 83, section, size=12, bold=True, centered=True)
    prefix = "Он "
    phrase = "сегізінші сөз"
    text_size, baseline = 15, 59
    heading_x = right - pdfmetrics.stringWidth(prefix + phrase, "Diagram", text_size)/2
    start = heading_x + pdfmetrics.stringWidth(prefix, "Diagram", text_size)
    stop = start + pdfmetrics.stringWidth(phrase, "Diagram", text_size)
    c.setFillColor(PALE)
    c.rect(start, baseline-3.5, stop-start, 19, stroke=0, fill=1)
    label(c, left, baseline, phrase, size=text_size, centered=True)
    arrow(c, WIDTH/2-25, WIDTH/2+25, baseline+4)
    label(c, heading_x, baseline, prefix + phrase, size=text_size)
    # The underline starts at the accepted suffix. Its left edge continues
    # directly to the boundary annotation, independently of the tint.
    c.setStrokeColor(ACCENT)
    c.setLineWidth(.9)
    c.line(start, baseline-3.5, stop, baseline-3.5)
    c.line(start, baseline-3.5, start, 43)
    c.line(start, 43, start+6, 43)
    label(c, start+9, 40, "Chunk 8 begins here", size=9, color=ACCENT)

    # Place the evaluator record on its own baseline below the text evidence.
    c.setFillColor(PALE)
    c.rect(1, 1, 452, 30, stroke=0, fill=1)
    c.setStrokeColor(RULE)
    c.setLineWidth(.55)
    for x in (1+452/3, 1+2*452/3):
        c.line(x, 6, x, 26)
    groups = [("Assigned positional target", "Chunk 8"), ("Observed rank", "1"),
              ("Evaluator credit", "Top-ranked hit")]
    for i, (field, value) in enumerate(groups):
        x = 1 + (i+.5)*452/3
        label(c, x, 20, field, size=8.6, centered=True)
        label(c, x, 6, value, size=10.5, bold=True, centered=True)
    c.save()


if __name__ == "__main__":
    workflow()
    poetry()
    heading_trace()
