"""
LangGraph pipeline for personalized client portfolio report generation.

Graph: gather_context -> generate_report -> format_html -> END

The final product is a self-contained HTML string ready for email delivery.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, TypedDict

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END

from config import GEMINI_API_KEY, GEMINI_MODEL

logger = logging.getLogger("report_graph")


# ── State ─────────────────────────────────────────────────────────────────

class ReportState(TypedDict):
    client:          Dict[str, Any]
    portfolio:       Dict[str, Any]
    market_analysis: Dict[str, Any]
    news:            list
    metrics:         Dict[str, Any]
    report_sections: Dict[str, Any]
    report_html:     str
    error:           str


# ── LLM singleton ─────────────────────────────────────────────────────────

_llm: ChatGoogleGenerativeAI | None = None


def _get_llm() -> ChatGoogleGenerativeAI | None:
    global _llm
    if _llm is not None:
        return _llm
    if not GEMINI_API_KEY:
        return None
    try:
        _llm = ChatGoogleGenerativeAI(
            model=GEMINI_MODEL,
            google_api_key=GEMINI_API_KEY,
            temperature=0.4,
        )
        return _llm
    except Exception as e:
        logger.error("Report LLM init failed: %s", e)
        return None


def _fmt_inr(amount: float) -> str:
    try:
        return "Rs.{:,.0f}".format(amount)
    except Exception:
        return "Rs.0"


# ── Nodes ─────────────────────────────────────────────────────────────────

def gather_context(state: ReportState) -> ReportState:
    p = state.get("portfolio", {})
    total_deposited   = p.get("total_deposited", 0) or 0
    current_value     = p.get("current_value", 0) or 0
    total_invested    = p.get("total_invested", 0) or 0
    available_cash    = p.get("available_cash", 0) or 0
    unrealized_pnl    = p.get("unrealized_pnl", 0) or 0
    realized_pnl      = p.get("realized_pnl", 0) or 0
    open_inv          = p.get("open_investments", [])
    closed_inv        = p.get("closed_investments", [])

    total_return_pct  = (
        (current_value - total_deposited) / total_deposited * 100
        if total_deposited > 0 else 0
    )
    cash_pct = (available_cash / total_deposited * 100) if total_deposited > 0 else 0
    best  = max(open_inv, key=lambda x: x.get("pnl_pct", 0), default=None)
    worst = min(open_inv, key=lambda x: x.get("pnl_pct", 0), default=None)

    allocation: dict[str, float] = {}
    for inv in open_inv:
        atype = inv.get("asset_type", "other")
        val   = inv.get("current_value") or (inv.get("quantity", 0) * inv.get("buy_price", 0))
        allocation[atype] = allocation.get(atype, 0) + val

    holdings_summary = []
    for inv in open_inv[:10]:
        holdings_summary.append({
            "name":          inv.get("asset_name"),
            "symbol":        inv.get("symbol"),
            "type":          inv.get("asset_type"),
            "qty":           inv.get("quantity"),
            "buy_price":     inv.get("buy_price"),
            "current_price": inv.get("current_price"),
            "current_value": inv.get("current_value"),
            "pnl":           inv.get("pnl"),
            "pnl_pct":       inv.get("pnl_pct"),
        })

    state["metrics"] = {
        "total_deposited":   total_deposited,
        "current_value":     current_value,
        "total_invested":    total_invested,
        "available_cash":    available_cash,
        "unrealized_pnl":    unrealized_pnl,
        "realized_pnl":      realized_pnl,
        "total_return_pct":  round(total_return_pct, 2),
        "cash_pct":          round(cash_pct, 2),
        "open_positions":    len(open_inv),
        "closed_positions":  len(closed_inv),
        "best_performer":    {"name": best.get("asset_name"), "pnl_pct": best.get("pnl_pct")} if best else None,
        "worst_performer":   {"name": worst.get("asset_name"), "pnl_pct": worst.get("pnl_pct")} if worst else None,
        "allocation":        allocation,
        "holdings_summary":  holdings_summary,
    }
    return state


def generate_report(state: ReportState) -> ReportState:
    llm = _get_llm()
    if not llm:
        state["error"] = "LLM unavailable"
        state["report_sections"] = _fallback_sections(state)
        return state

    client  = state.get("client", {})
    metrics = state.get("metrics", {})
    market  = state.get("market_analysis", {})
    news    = state.get("news", [])

    news_text        = "\n".join("  - " + n.get("title", "") for n in news[:5]) or "  (No recent news)"
    market_sentiment = market.get("sentiment", "neutral")
    market_summary   = market.get("summary", "Market data unavailable.")

    prompt = (
        "You are a senior financial advisor at WealthWatch, a premium wealth management firm.\n"
        "Generate a comprehensive, professional portfolio report for the following client.\n\n"
        "CLIENT PROFILE:\n"
        "  Name: {name}\n"
        "  Risk Profile: {risk}\n"
        "  Member Since: {joined}\n\n"
        "PORTFOLIO METRICS:\n"
        "  Total Deposited:   Rs.{deposited:,.0f}\n"
        "  Current Value:     Rs.{current:,.0f}\n"
        "  Unrealized P&L:    Rs.{upnl:,.0f} ({ret:.2f}%)\n"
        "  Realized P&L:      Rs.{rpnl:,.0f}\n"
        "  Available Cash:    Rs.{cash:,.0f} ({cashpct:.1f}%)\n"
        "  Open Positions:    {openp}\n"
        "  Closed Positions:  {closedp}\n"
        "  Best Performer:    {best}\n"
        "  Worst Performer:   {worst}\n\n"
        "HOLDINGS:\n{holdings}\n\n"
        "CURRENT MARKET:\n"
        "  Sentiment: {sentiment}\n"
        "  {summary}\n\n"
        "RECENT NEWS:\n{news}\n\n"
        "Generate a professional portfolio report as JSON with EXACTLY these keys:\n"
        "{{\n"
        '  "executive_summary": "3-4 paragraph overview",\n'
        '  "portfolio_performance": "2-3 paragraphs on the numbers",\n'
        '  "holdings_analysis": "detailed commentary on key positions",\n'
        '  "risk_assessment": "2-3 paragraphs on risk exposure",\n'
        '  "market_context": "1-2 paragraphs connecting market to this portfolio",\n'
        '  "recommendations": ["5 specific, actionable recommendations"]\n'
        "}}\n\n"
        "Be specific, use actual portfolio data, write in a professional but warm tone.\n"
        "Return ONLY valid JSON, no markdown fences."
    ).format(
        name=client.get("name", "Valued Client"),
        risk=client.get("risk_profile", "moderate"),
        joined=client.get("joined_date", "N/A"),
        deposited=metrics.get("total_deposited", 0),
        current=metrics.get("current_value", 0),
        upnl=metrics.get("unrealized_pnl", 0),
        ret=metrics.get("total_return_pct", 0),
        rpnl=metrics.get("realized_pnl", 0),
        cash=metrics.get("available_cash", 0),
        cashpct=metrics.get("cash_pct", 0),
        openp=metrics.get("open_positions", 0),
        closedp=metrics.get("closed_positions", 0),
        best=metrics.get("best_performer") or "N/A",
        worst=metrics.get("worst_performer") or "N/A",
        holdings=json.dumps(metrics.get("holdings_summary", []), indent=2),
        sentiment=market_sentiment,
        summary=market_summary,
        news=news_text,
    )

    try:
        response = llm.invoke([
            SystemMessage(content="You are a professional financial advisor. Always respond with valid JSON only."),
            HumanMessage(content=prompt),
        ])
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.lower().startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        state["report_sections"] = json.loads(raw)
        state["error"] = ""
        logger.info("Report sections generated for %s", client.get("name"))
    except json.JSONDecodeError:
        logger.warning("Report LLM returned invalid JSON — using fallback")
        state["report_sections"] = _fallback_sections(state)
    except Exception as exc:
        logger.error("Report generation failed: %s", exc)
        state["error"] = str(exc)
        state["report_sections"] = _fallback_sections(state)

    return state


def _cell(label: str, value: str) -> str:
    return (
        '<div style="background:#0b0f1a;border-radius:8px;padding:16px;">'
        '<div style="font-size:11px;color:#64748b;text-transform:uppercase;'
        'letter-spacing:0.5px;margin-bottom:4px;">' + label + "</div>"
        '<div style="font-size:22px;font-weight:700;color:#f1f5f9;">' + value + "</div>"
        "</div>"
    )


def _colored_cell(label: str, value: str, color: str) -> str:
    return (
        '<div style="background:#0b0f1a;border-radius:8px;padding:16px;">'
        '<div style="font-size:11px;color:#64748b;text-transform:uppercase;'
        'letter-spacing:0.5px;margin-bottom:4px;">' + label + "</div>"
        '<div style="font-size:22px;font-weight:700;color:' + color + ';">' + value + "</div>"
        "</div>"
    )


def _section(title: str, content: str) -> str:
    paras = [
        '<p style="margin:0 0 12px;color:#cbd5e1;line-height:1.7;">' + p.strip() + "</p>"
        for p in (content or "").split("\n") if p.strip()
    ]
    inner = "".join(paras) if paras else '<p style="color:#94a3b8;margin:0;">No content available.</p>'
    return (
        '<div style="background:#161b27;border:1px solid #1e293b;border-radius:12px;'
        "padding:24px;margin-bottom:20px;\">"
        '<h2 style="margin:0 0 16px;font-size:16px;font-weight:600;color:#f1f5f9;">'
        + title + "</h2>"
        + inner + "</div>"
    )


def _holdings_table(holdings: list) -> str:
    if not holdings:
        return ""
    rows = ""
    for h in holdings:
        h_pnl     = h.get("pnl") or 0
        h_pnl_pct = h.get("pnl_pct") or 0
        h_color   = "#22c55e" if h_pnl >= 0 else "#ef4444"
        h_sign    = "+" if h_pnl >= 0 else ""
        rows += (
            "<tr>"
            '<td style="padding:10px 14px;border-bottom:1px solid #2d2d2d;">'
            '<strong style="color:#f1f5f9;">' + str(h.get("asset_name", "")) + "</strong>"
            '<div style="font-size:11px;color:#94a3b8;">' + str(h.get("symbol", "")) + "</div></td>"
            '<td style="padding:10px 14px;border-bottom:1px solid #2d2d2d;text-align:center;">'
            '<span style="background:#1e293b;color:#94a3b8;padding:2px 8px;border-radius:4px;font-size:11px;">'
            + str(h.get("type", "")) + "</span></td>"
            '<td style="padding:10px 14px;border-bottom:1px solid #2d2d2d;text-align:right;color:#f1f5f9;">'
            + str(h.get("qty", "")) + "</td>"
            '<td style="padding:10px 14px;border-bottom:1px solid #2d2d2d;text-align:right;color:#94a3b8;">'
            + _fmt_inr(h.get("buy_price") or 0) + "</td>"
            '<td style="padding:10px 14px;border-bottom:1px solid #2d2d2d;text-align:right;color:#f1f5f9;">'
            + (_fmt_inr(h.get("current_price") or 0) if h.get("current_price") else "—") + "</td>"
            '<td style="padding:10px 14px;border-bottom:1px solid #2d2d2d;text-align:right;color:'
            + h_color + ';font-weight:600;">' + h_sign + _fmt_inr(h_pnl)
            + '<div style="font-size:11px;">' + h_sign + "{:.2f}".format(h_pnl_pct) + "%</div></td>"
            "</tr>"
        )
    thead = (
        '<table style="width:100%;border-collapse:collapse;font-size:13px;">'
        '<thead><tr style="background:#0b0f1a;">'
        '<th style="padding:10px 14px;text-align:left;color:#64748b;border-bottom:1px solid #2d2d2d;">Asset</th>'
        '<th style="padding:10px 14px;text-align:center;color:#64748b;border-bottom:1px solid #2d2d2d;">Type</th>'
        '<th style="padding:10px 14px;text-align:right;color:#64748b;border-bottom:1px solid #2d2d2d;">Qty</th>'
        '<th style="padding:10px 14px;text-align:right;color:#64748b;border-bottom:1px solid #2d2d2d;">Buy</th>'
        '<th style="padding:10px 14px;text-align:right;color:#64748b;border-bottom:1px solid #2d2d2d;">Current</th>'
        '<th style="padding:10px 14px;text-align:right;color:#64748b;border-bottom:1px solid #2d2d2d;">P&amp;L</th>'
        "</tr></thead><tbody>" + rows + "</tbody></table>"
    )
    return (
        '<div style="background:#161b27;border:1px solid #1e293b;border-radius:12px;'
        "padding:24px;margin-bottom:20px;overflow-x:auto;\">"
        '<h2 style="margin:0 0 16px;font-size:16px;font-weight:600;color:#f1f5f9;">Open Positions</h2>'
        + thead + "</div>"
    )


def format_html(state: ReportState) -> ReportState:
    client   = state.get("client", {})
    metrics  = state.get("metrics", {})
    sections = state.get("report_sections", {})
    now      = datetime.now(tz=timezone.utc).strftime("%B %d, %Y at %H:%M UTC")

    name          = client.get("name", "Valued Client")
    risk_profile  = (client.get("risk_profile") or "moderate").title()
    pnl_val       = metrics.get("unrealized_pnl", 0)
    ret_pct       = metrics.get("total_return_pct", 0)
    pnl_color     = "#22c55e" if pnl_val >= 0 else "#ef4444"
    pnl_sign      = "+" if pnl_val >= 0 else ""
    pnl_str       = pnl_sign + _fmt_inr(pnl_val) + " (" + pnl_sign + "{:.2f}".format(ret_pct) + "%)"

    risk_colors   = {"conservative": "#22c55e", "moderate": "#f59e0b", "aggressive": "#ef4444"}
    risk_color    = risk_colors.get(client.get("risk_profile", "moderate"), "#f59e0b")

    # Recommendations
    recs_html = ""
    for i, rec in enumerate(sections.get("recommendations", []), 1):
        recs_html += (
            '<div style="display:flex;gap:12px;align-items:flex-start;margin-bottom:12px;">'
            '<div style="min-width:28px;height:28px;'
            "background:linear-gradient(135deg,#6366f1,#8b5cf6);"
            "border-radius:50%;display:flex;align-items:center;justify-content:center;"
            'font-weight:700;font-size:13px;color:#fff;">' + str(i) + "</div>"
            '<p style="margin:0;color:#cbd5e1;line-height:1.6;padding-top:4px;">' + str(rec) + "</p>"
            "</div>"
        )
    if not recs_html:
        recs_html = '<p style="color:#94a3b8;margin:0;">No recommendations available.</p>'

    html = (
        "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1.0\">"
        "<title>WealthWatch Portfolio Report</title></head>"
        "<body style=\"margin:0;padding:0;background:#0b0f1a;"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;\">"
        "<div style=\"max-width:680px;margin:0 auto;background:#0b0f1a;\">"

        # Header
        "<div style=\"background:linear-gradient(135deg,#1e1b4b 0%,#312e81 50%,#4c1d95 100%);padding:40px 32px;\">"
        "<div style=\"display:flex;align-items:center;gap:12px;margin-bottom:24px;\">"
        "<div style=\"width:40px;height:40px;background:linear-gradient(135deg,#6366f1,#8b5cf6);"
        "border-radius:10px;font-weight:800;font-size:20px;color:#fff;"
        "display:flex;align-items:center;justify-content:center;\">W</div>"
        "<div><div style=\"font-size:20px;font-weight:700;color:#fff;\">WealthWatch</div>"
        "<div style=\"font-size:12px;color:#a5b4fc;\">AI-Powered Portfolio Management</div></div></div>"
        "<h1 style=\"margin:0 0 8px;font-size:28px;font-weight:700;color:#fff;\">Portfolio Report</h1>"
        "<p style=\"margin:0;color:#c7d2fe;font-size:14px;\">Dear " + name + " &nbsp;&middot;&nbsp; Generated " + now + "</p>"
        "</div>"

        # Body
        "<div style=\"padding:32px;\">"
        "<div style=\"margin-bottom:24px;\">"
        "<span style=\"background:" + risk_color + "22;color:" + risk_color + ";"
        "border:1px solid " + risk_color + "44;"
        "padding:4px 14px;border-radius:20px;font-size:12px;font-weight:600;\">"
        + risk_profile + " Risk Profile</span></div>"

        # Snapshot
        "<div style=\"background:#161b27;border:1px solid #1e293b;border-radius:12px;padding:24px;margin-bottom:20px;\">"
        "<h2 style=\"margin:0 0 20px;font-size:16px;font-weight:600;color:#f1f5f9;\">Portfolio Snapshot</h2>"
        "<div style=\"display:grid;grid-template-columns:1fr 1fr;gap:12px;\">"
        + _cell("Total Deposited", _fmt_inr(metrics.get("total_deposited", 0)))
        + _cell("Current Value",   _fmt_inr(metrics.get("current_value", 0)))
        + _colored_cell("Unrealized P&amp;L", pnl_str, pnl_color)
        + _cell("Available Cash",  _fmt_inr(metrics.get("available_cash", 0)))
        + "</div>"
        "<div style=\"margin-top:12px;padding:12px 16px;background:#0b0f1a;border-radius:8px;"
        "display:flex;justify-content:space-between;\">"
        "<span style=\"color:#64748b;font-size:13px;\">Realized P&amp;L (closed positions)</span>"
        "<span style=\"color:#94a3b8;font-weight:600;font-size:13px;\">"
        + _fmt_inr(metrics.get("realized_pnl", 0)) + "</span></div>"
        "</div>"

        # AI sections
        + _section("Executive Summary",            sections.get("executive_summary", ""))
        + _section("Portfolio Performance Analysis", sections.get("portfolio_performance", ""))
        + _section("Holdings Analysis",             sections.get("holdings_analysis", ""))
        + _holdings_table(metrics.get("holdings_summary", []))
        + _section("Risk Assessment",               sections.get("risk_assessment", ""))
        + _section("Market Context",                sections.get("market_context", ""))

        # Recommendations
        + "<div style=\"background:#161b27;border:1px solid #1e293b;border-radius:12px;padding:24px;margin-bottom:20px;\">"
        + "<h2 style=\"margin:0 0 20px;font-size:16px;font-weight:600;color:#f1f5f9;\">Recommendations</h2>"
        + recs_html + "</div>"

        # Footer
        + "<div style=\"border-top:1px solid #1e293b;padding-top:24px;text-align:center;\">"
        + "<div style=\"font-size:12px;color:#475569;line-height:1.6;\">"
        + "<p style=\"margin:0 0 8px;\">This report is AI-generated and for <strong>informational purposes only</strong>.</p>"
        + "<p style=\"margin:0 0 8px;\">WealthWatch 2.0 &nbsp;&middot;&nbsp; usay.dewani.dev@gmail.com</p>"
        + "<p style=\"margin:0;color:#334155;\">&copy; " + str(datetime.now().year) + " WealthWatch.</p>"
        + "</div></div>"
        + "</div></div></body></html>"
    )

    state["report_html"] = html
    return state


def _fallback_sections(state: ReportState) -> dict:
    metrics = state.get("metrics", {})
    client  = state.get("client", {})
    ret_pct = metrics.get("total_return_pct", 0)
    direction = "positive" if ret_pct >= 0 else "negative"
    return {
        "executive_summary": (
            "Your portfolio is showing a " + direction + " return of "
            + "{:.2f}".format(ret_pct) + "% since inception. "
            "You have " + str(metrics.get("open_positions", 0)) + " open positions and "
            + str(metrics.get("closed_positions", 0)) + " closed positions. "
            "Live AI analysis is temporarily unavailable."
        ),
        "portfolio_performance": (
            "Total capital deployed: " + _fmt_inr(metrics.get("total_invested", 0))
            + " out of " + _fmt_inr(metrics.get("total_deposited", 0)) + " deposited. "
            "Available cash: " + _fmt_inr(metrics.get("available_cash", 0)) + "."
        ),
        "holdings_analysis":  "Detailed holdings analysis unavailable at this time.",
        "risk_assessment":    "Risk profile: " + client.get("risk_profile", "moderate").title() + ". Detailed risk analysis unavailable.",
        "market_context":     "Current market context unavailable.",
        "recommendations": [
            "Review your portfolio allocation against your risk profile",
            "Consider rebalancing if any single position exceeds 20% of the total portfolio",
            "Maintain adequate cash reserves for new opportunities",
            "Monitor market conditions and scheduled economic events",
            "Consult with your wealth manager for personalized advice",
        ],
    }


# ── Graph ─────────────────────────────────────────────────────────────────

def _build_report_graph():
    g = StateGraph(ReportState)
    g.add_node("gather_context",  gather_context)
    g.add_node("generate_report", generate_report)
    g.add_node("format_html",     format_html)
    g.set_entry_point("gather_context")
    g.add_edge("gather_context",  "generate_report")
    g.add_edge("generate_report", "format_html")
    g.add_edge("format_html",     END)
    return g.compile()


_report_graph = None


def _get_report_graph():
    global _report_graph
    if _report_graph is None:
        _report_graph = _build_report_graph()
    return _report_graph


# ── Public API ────────────────────────────────────────────────────────────

async def run_report(
    client:          dict,
    portfolio:       dict,
    market_analysis: dict,
    news:            list,
) -> str:
    import asyncio
    graph = _get_report_graph()
    initial: ReportState = {
        "client":          client,
        "portfolio":       portfolio,
        "market_analysis": market_analysis,
        "news":            news,
        "metrics":         {},
        "report_sections": {},
        "report_html":     "",
        "error":           "",
    }
    try:
        result = await asyncio.to_thread(graph.invoke, initial)
        html = result.get("report_html", "")
        return html if html else "<p>Report generation failed. Please try again.</p>"
    except Exception as exc:
        logger.error("Report graph execution failed: %s", exc)
        return "<p>Report generation failed: " + str(exc) + "</p>"
