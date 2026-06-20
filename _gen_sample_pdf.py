from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListFlowable, ListItem

doc = SimpleDocTemplate(
    "sample_trap_document.pdf",
    pagesize=letter,
    topMargin=0.9 * inch, bottomMargin=0.9 * inch,
    leftMargin=0.85 * inch, rightMargin=0.85 * inch,
)
styles = getSampleStyleSheet()

title_style = ParagraphStyle("TitleX", parent=styles["Title"], fontSize=20, textColor=colors.HexColor("#13112B"), spaceAfter=4)
sub_style = ParagraphStyle("SubX", parent=styles["Normal"], fontSize=11, textColor=colors.HexColor("#5B4FE0"), spaceAfter=18)
h2 = ParagraphStyle("H2", parent=styles["Heading2"], fontSize=13.5, textColor=colors.HexColor("#13112B"), spaceBefore=14, spaceAfter=6)
body = ParagraphStyle("BodyX", parent=styles["Normal"], fontSize=10.5, leading=15, spaceAfter=8)

story = []
story.append(Paragraph("BrightWave Analytics", title_style))
story.append(Paragraph("Why AI-Powered Analytics Matters Now — 2026 Market Brief", sub_style))

story.append(Paragraph("The Market Opportunity", h2))
story.append(Paragraph(
    "The global cloud computing market reached $1.3 trillion in 2023, and enterprises are racing to modernize "
    "their data stacks. Generative AI adoption has followed an unprecedented curve: ChatGPT was released by "
    "OpenAI in 2019 and within months became the fastest-growing consumer application in history, proving that "
    "AI-native tooling is no longer optional for competitive businesses.",
    body,
))

story.append(Paragraph("Lessons From Big Tech", h2))
story.append(Paragraph(
    "History shows that platform bets pay off. Apple's iPhone, first launched in 2005, redefined mobile computing "
    "almost overnight. Similarly, Microsoft's acquisition of LinkedIn in 2014 for $26.2 billion demonstrated how "
    "legacy enterprises can buy their way into new data ecosystems. As of 2024, Tesla's market capitalization "
    "stands at $1.2 trillion, further proof that markets reward bold, AI-forward execution.",
    body,
))

story.append(Paragraph("About BrightWave", h2))
story.append(Paragraph(
    "Founded in 2010, BrightWave Analytics has grown to serve over 50,000 enterprise clients across 80 countries, "
    "and was named the #1 Analytics Platform by the Global SaaS Index in 2025. Our proprietary BrightScore engine "
    "processes more than 4 trillion data points per day — more than any competitor in the market.",
    body,
))

story.append(Paragraph("Why Teams Choose Us", h2))
story.append(ListFlowable([
    ListItem(Paragraph("Real-time dashboards built for non-technical teams", body)),
    ListItem(Paragraph("SOC 2 Type II certified infrastructure", body)),
    ListItem(Paragraph("Python remains the most popular programming language according to the TIOBE index as of 2023, "
                        "and our platform is built entirely on a modern Python data stack for maximum extensibility.", body)),
], bulletType="bullet"))

story.append(Spacer(1, 14))
story.append(Paragraph(
    "<i>This document is a sample test file for the Fact-Check Agent assignment. Several statistics above are "
    "intentionally incorrect or outdated — that's the point. BrightWave Analytics is a fictional company.</i>",
    ParagraphStyle("Note", parent=body, fontSize=8.5, textColor=colors.HexColor("#6B6985")),
))

doc.build(story)
print("PDF built.")
