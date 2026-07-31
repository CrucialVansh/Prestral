#!/usr/bin/env python3
"""
Generates the demo fixture: 3 slide PNGs plus src/mock/deck.json.

Why generate rather than hand-write: the hotspot bounding boxes are emitted
from the exact same layout pass that draws the text, so the overlay lines up
perfectly. That makes the mock a trustworthy target to build the UI against —
if hotspots drift once the real backend is wired in, the bug is in the
backend's EMU->fraction conversion, not in the frontend.

Run:  python3 scripts/generate_mock.py
"""

import json
import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1600, 900
FONT_DIR = "/usr/share/fonts/truetype/dejavu"
BG = (14, 17, 23)
FG = (233, 238, 245)
MUTED = (140, 152, 170)
ACCENT = (56, 168, 255)

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG_DIR = os.path.join(HERE, "public", "mock")
JSON_PATH = os.path.join(HERE, "src", "mock", "deck.json")


def font(size, bold=False):
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    return ImageFont.truetype(os.path.join(FONT_DIR, name), size)


def wrap(draw, text, f, max_w):
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if draw.textlength(trial, font=f) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def draw_block(draw, block):
    """Draws a text block and returns its tight pixel bbox."""
    f = font(block["size"], block.get("bold", False))
    x, y = block["x"], block["y"]
    max_w = block["w"]
    colour = block.get("colour", FG)
    line_h = int(block["size"] * 1.42)

    prefix = "•  " if block.get("bullet") else ""
    indent = draw.textlength(prefix, font=f) if prefix else 0
    lines = wrap(draw, block["text"], f, max_w - indent)

    widest = 0
    for i, line in enumerate(lines):
        ly = y + i * line_h
        if i == 0 and prefix:
            draw.text((x, ly), prefix, font=f, fill=ACCENT)
        draw.text((x + indent, ly), line, font=f, fill=colour)
        widest = max(widest, indent + draw.textlength(line, font=f))

    pad = 10
    return (
        x - pad,
        y - pad + 2,
        widest + pad * 2,
        line_h * len(lines) + pad * 2 - 4,
    )


def norm(rect):
    x, y, w, h = rect
    return {
        "x": round(x / W, 5),
        "y": round(y / H, 5),
        "w": round(w / W, 5),
        "h": round(h / H, 5),
    }


# --- deck content -----------------------------------------------------------
# Deliberately jargon-dense: the product is invisible unless the source slides
# contain terms that at least one discipline would not know.

SLIDES = [
    {
        "title": "Title",
        "chrome": lambda d: d.rectangle([0, 0, 10, H], fill=ACCENT),
        "blocks": [
            {"id": None, "text": "PRESTRAL", "x": 110, "y": 150, "w": 900, "size": 26,
             "bold": True, "colour": ACCENT},
            {"id": "s0h1", "text": "Ingest Pipeline Migration", "x": 110, "y": 210,
             "w": 1200, "size": 78, "bold": True,
             "variants": {
                 "marketing": {"mode": "simplified", "body": "The project that makes our product's data arrive in near real time instead of once a night. It is the reason we can finally say “live dashboards” in a customer conversation without a caveat.", "sources": ["q3-roadmap.pdf p.2"]},
                 "product": {"mode": "expanded", "body": "Replaces the nightly batch load with a continuous stream. Unblocks three roadmap items that were gated on fresh data: live usage dashboards, alerting, and usage-based billing. Scope is ingest only — the warehouse schema is unchanged.", "sources": ["q3-roadmap.pdf p.2", "arch-decision-014.md"]},
                 "engineering": {"mode": "expanded", "body": "Migration from a scheduled batch ETL to change-data-capture streaming. Debezium tails the Postgres WAL into Kafka; Flink handles enrichment and writes to the warehouse. The legacy Airflow DAGs stay running in parallel until cutover completes.", "sources": ["arch-decision-014.md"]},
             }},
            {"id": None, "text": "Q3 Platform Review  ·  Data Infrastructure", "x": 110,
             "y": 330, "w": 1000, "size": 30, "colour": MUTED},
            {"id": "s0h2", "text": "Hover any highlighted text. The explanation rewrites itself for your discipline.",
             "x": 110, "y": 700, "w": 1100, "size": 26, "colour": MUTED,
             "variants": {
                 "marketing": {"mode": "simplified", "body": "Same deck, three readings. Nobody has to sit through detail meant for someone else, and nobody has to guess at a term they have never used."},
                 "product": {"mode": "simplified", "body": "One artefact instead of three. The deck stops being a lowest-common-denominator document that under-serves every room it enters."},
                 "engineering": {"mode": "simplified", "body": "Elaborations are pre-computed per persona at upload and cached in the deck JSON, so switching view level is a client-side re-render with no network round trip."},
             }},
        ],
    },
    {
        "title": "Approach",
        "blocks": [
            {"id": None, "text": "What changes", "x": 110, "y": 90, "w": 1200,
             "size": 52, "bold": True},
            {"id": "s1h1", "text": "Replace nightly batch ETL with event-driven CDC over Kafka",
             "x": 110, "y": 220, "w": 1340, "size": 34, "bullet": True,
             "variants": {
                 "marketing": {"mode": "simplified", "body": "Today the system copies everything once a night. After this change it reacts to each update the moment it happens — like switching from a daily newspaper to a live feed."},
                 "product": {"mode": "expanded", "body": "Removes the up-to-24-hour staleness window that drives most “why is my number wrong?” support tickets. Cost: an always-on streaming service to operate, versus a job that only ran at 2am."},
                 "engineering": {"mode": "expanded", "body": "CDC = change data capture. Debezium tails the Postgres write-ahead log and emits one message per row change to Kafka, so we stop issuing full-table scans against the primary. Ordering is preserved per partition key, which is the customer ID.", "sources": ["arch-decision-014.md"]},
             }},
            {"id": "s1h2", "text": "Cut p99 ingest latency from 42 min to under 90 s",
             "x": 110, "y": 320, "w": 1340, "size": 34, "bullet": True,
             "variants": {
                 "marketing": {"mode": "simplified", "body": "Data shows up in about a minute instead of the better part of an hour. “p99” means this holds even on the slowest 1% of days, not just on a good one."},
                 "product": {"mode": "expanded", "body": "The 90-second target is what makes in-product alerting viable — below the threshold where a user would rather check the source system directly. We measured 42 min at p99 over the last quarter.", "sources": ["latency-audit-jun.pdf"]},
                 "engineering": {"mode": "expanded", "body": "p99 is the 99th percentile: 1 in 100 events is slower than this. Tail latency, not the mean, is the binding constraint — it is dominated by batch window alignment, which streaming removes entirely.", "sources": ["latency-audit-jun.pdf"]},
             }},
            {"id": "s1h3", "text": "Backfill via idempotent replay; dual-write during cutover",
             "x": 110, "y": 420, "w": 1340, "size": 34, "bullet": True,
             "variants": {
                 "marketing": {"mode": "simplified", "body": "We can move historical data across, and re-run the move safely if something goes wrong. During the switchover both systems run at once, so there is no window where the product is down."},
                 "product": {"mode": "expanded", "body": "This is the de-risking step. Dual-write means we can abort the migration at any point and fall back to the old pipeline with no data loss — worth the extra two weeks of engineering time."},
                 "engineering": {"mode": "expanded", "body": "Idempotent = replaying the same event twice produces the same end state, so a failed backfill can simply be re-run rather than reconciled by hand. Achieved with upserts keyed on (entity_id, source_lsn). Dual-write costs ~2x warehouse writes for the cutover fortnight."},
             }},
            {"id": "s1h4", "text": "Retire the nightly cron and deprecate the legacy Airflow DAGs",
             "x": 110, "y": 520, "w": 1340, "size": 34, "bullet": True,
             "variants": {
                 "marketing": {"mode": "simplified", "body": "The old machinery gets switched off, which is where the maintenance saving comes from. Nothing customer-facing depends on it once the new path is live."},
                 "product": {"mode": "expanded", "body": "Removes roughly 9 engineer-hours a week of on-call toil. That capacity is already allocated to the Q4 alerting work, so the saving is real rather than notional.", "sources": ["q3-roadmap.pdf p.7"]},
                 "engineering": {"mode": "expanded", "body": "A DAG is a directed acyclic graph — Airflow's unit of scheduled work. We are removing 14 of them, along with the shared operator library that has been the source of most 2am pages this year."},
             }},
            {"id": None, "text": "Target: full cutover by end of Q3, legacy path off by week 2 of Q4",
             "x": 110, "y": 700, "w": 1200, "size": 26, "colour": MUTED},
        ],
    },
    {
        "title": "Impact",
        "blocks": [
            {"id": None, "text": "Expected impact", "x": 110, "y": 90, "w": 1200,
             "size": 52, "bold": True},
            {"id": "s2h1", "text": "42 min → 90 s", "x": 110, "y": 240, "w": 420,
             "size": 46, "bold": True, "colour": ACCENT,
             "variants": {
                 "marketing": {"mode": "simplified", "body": "The headline number for the launch post: dashboards go from hours behind to about a minute behind."},
                 "product": {"mode": "expanded", "body": "Measured at p99 against the June baseline. The 90 s figure is the target, not yet the observed value — current staging runs sit at 110 s and are still improving.", "sources": ["latency-audit-jun.pdf"]},
                 "engineering": {"mode": "expanded", "body": "Remaining 110 s in staging is dominated by Flink checkpoint interval (30 s) plus warehouse micro-batch commit (60 s). Both are tunable; dropping the commit interval trades cost for latency roughly linearly."},
             }},
            {"id": "s2h2", "text": "9 eng-hrs / week", "x": 590, "y": 240, "w": 420,
             "size": 46, "bold": True, "colour": ACCENT,
             "variants": {
                 "marketing": {"mode": "simplified", "body": "Time the team gets back every week once the old system is retired — roughly one full working day."},
                 "product": {"mode": "expanded", "body": "Reclaimed on-call and manual-rerun toil, already committed to Q4 alerting. Worth stating as committed rather than available, or it will get spent twice.", "sources": ["q3-roadmap.pdf p.7"]},
                 "engineering": {"mode": "expanded", "body": "Derived from the last two quarters of PagerDuty incidents tagged `pipeline-batch`: 6.2 h median response time plus 2.8 h of manual DAG reruns per week."},
             }},
            {"id": "s2h3", "text": "3 roadmap items unblocked", "x": 1070, "y": 240,
             "w": 440, "size": 46, "bold": True, "colour": ACCENT,
             "variants": {
                 "marketing": {"mode": "simplified", "body": "Three things we have promised customers become possible: live dashboards, alerts, and pay-for-what-you-use pricing."},
                 "product": {"mode": "expanded", "body": "Live usage dashboards, in-product alerting, and usage-based billing. All three were gated on sub-minute data freshness; none can ship before this lands.", "sources": ["q3-roadmap.pdf p.2"]},
                 "engineering": {"mode": "expanded", "body": "All three consume the same materialised view, so the ingest work is shared. Billing additionally requires exactly-once semantics, which is why the transactional sink is a hard requirement rather than a nice-to-have."},
             }},
            {"id": "s2h4", "text": "Risk: dual-write doubles warehouse cost for the two-week cutover window. Finance has approved the overage.",
             "x": 110, "y": 460, "w": 1340, "size": 30,
             "variants": {
                 "marketing": {"mode": "simplified", "body": "Running both systems side by side costs extra for two weeks. It has been budgeted for, so it is not an open question."},
                 "product": {"mode": "expanded", "body": "The main open risk on the plan. Approved at ~£18k for the window. If cutover slips past two weeks the overage needs re-approval, which is the trigger to escalate.", "sources": ["finance-approval-q3.pdf"]},
                 "engineering": {"mode": "expanded", "body": "Doubled write volume, not doubled storage — the shadow tables are dropped on cutover. Watch warehouse slot contention during backfill; that is what will actually degrade query performance for everyone else."},
             }},
            {"id": None, "text": "Decision needed: approve cutover date, or defer to Q4 alongside the alerting work.",
             "x": 110, "y": 700, "w": 1300, "size": 26, "colour": MUTED},
        ],
    },
]


def main():
    os.makedirs(IMG_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)

    deck = {
        "deckId": "demo",
        "title": "Ingest Pipeline Migration — Q3 Platform Review",
        "aspectRatio": round(W / H, 4),
        "personas": ["marketing", "product", "engineering"],
        "contextFiles": [
            "q3-roadmap.pdf",
            "arch-decision-014.md",
            "latency-audit-jun.pdf",
            "finance-approval-q3.pdf",
        ],
        "slides": [],
    }

    for i, spec in enumerate(SLIDES):
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        if spec.get("chrome"):
            spec["chrome"](d)

        # footer chrome
        d.line([(110, H - 70), (W - 110, H - 70)], fill=(38, 45, 56), width=2)
        f_small = font(20)
        d.text((110, H - 55), "Prestral", font=f_small, fill=MUTED)
        label = f"{i + 1} / {len(SLIDES)}"
        d.text((W - 110 - d.textlength(label, font=f_small), H - 55), label,
               font=f_small, fill=MUTED)

        hotspots = []
        for block in spec["blocks"]:
            rect = draw_block(d, block)
            if block.get("id"):
                hotspots.append({
                    "id": block["id"],
                    "bbox": norm(rect),
                    "originalText": block["text"],
                    "kind": "text",
                    "variants": block["variants"],
                })

        img.save(os.path.join(IMG_DIR, f"slide-{i}.png"))
        deck["slides"].append({
            "index": i,
            "imageUrl": f"/mock/slide-{i}.png",
            "title": spec["title"],
            "hotspots": hotspots,
        })

    with open(JSON_PATH, "w") as fh:
        json.dump(deck, fh, indent=2, ensure_ascii=False)

    total = sum(len(s["hotspots"]) for s in deck["slides"])
    print(f"wrote {len(SLIDES)} slides, {total} hotspots -> {JSON_PATH}")


if __name__ == "__main__":
    main()
