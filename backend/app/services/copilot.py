from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
from pathlib import Path
import re
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.investor import Investor
from app.models.ledger import LedgerEntry
from app.models.nav import InvestorBalance, NavSnapshot
from app.models.period import AccountingPeriod, InvestorPosition
from app.models.report import ReportSnapshot
from app.services.analytics import generate_metrics
from app.services.nav_engine import compute_monthly_nav
from app.utils.decimal_math import money


@dataclass(frozen=True)
class SourceRef:
    type: str
    ref: str


@dataclass(frozen=True)
class CopilotAnswer:
    response: str
    sources: list[SourceRef]


SECTION_GUIDES: list[dict[str, str]] = [
    {
        "section": "Overview",
        "location": "Top navigation: Overview",
        "purpose": "High-level NAV, cash flow, growth, and key risk indicators for selected club+period.",
        "flow": "Review trends -> inspect metrics -> jump to Clubs/Investors/Ledger for deeper actions.",
    },
    {
        "section": "Clubs",
        "location": "Top navigation: Clubs",
        "purpose": "Create/manage clubs and compare performance at club level.",
        "flow": "Create club -> create periods -> monitor NAV and status progression.",
    },
    {
        "section": "Investors",
        "location": "Top navigation: Investors",
        "purpose": "Maintain investor records and review ownership/balance outcomes by period.",
        "flow": "Add/edit investor -> post contributions/withdrawals in Ledger -> review allocations.",
    },
    {
        "section": "Ledger",
        "location": "Top navigation: Ledger",
        "purpose": "Post contribution/withdrawal/income/expense/adjustment transactions.",
        "flow": "Enter transactions -> validate reconciliation -> submit review/close when ready.",
    },
    {
        "section": "Close Month",
        "location": "Top navigation: Close Month",
        "purpose": "Run checklist gate, verify reconciliation, and lock period with immutable snapshot.",
        "flow": "Submit for review -> pass checklist -> run close -> generate reports.",
    },
    {
        "section": "Reports",
        "location": "Top navigation: Reports",
        "purpose": "Generate and download PDFs and regulator exports from closed snapshots.",
        "flow": "Close period -> generate monthly/investor reports -> download PDF/CSV/Excel.",
    },
    {
        "section": "Analysis",
        "location": "Top navigation: Analysis (Intelligent mode)",
        "purpose": "Insights, anomalies, and scenario simulation from period data.",
        "flow": "Review drivers -> inspect anomaly flags -> run deterministic scenario projections.",
    },
    {
        "section": "Copilot",
        "location": "Top navigation: Copilot (Intelligent mode)",
        "purpose": "Read-only assistant scoped to one club+period with cited sources.",
        "flow": "Ask question -> review answer + sources -> take actions in operational screens.",
    },
]


COPILOT_SYSTEM_PROMPT = """
You are NAVFund Copilot, an expert fintech assistant for a multi-club NAV platform.

Hard guardrails:
- Scope only to the provided club_id and period_id context.
- Never use or infer data from other clubs or periods not provided.
- Read-only assistant. Refuse any request to modify records, reopen closed periods, or alter NAV.
- If data is missing, say you cannot answer without data and request exact missing items.
- Use only provided context, internal docs, and source references.

Behavior requirements:
- Explain app sections, where they are located, and step-by-step workflow when asked.
- Provide rationale for formulas and accounting flow in plain language.
- For investment advice, provide data-grounded guidance with assumptions and risks.
- Never promise returns; do not invent figures.
- Keep answers concise, practical, and auditable.

Output style:
- Start with direct answer.
- Add a short "Why" rationale.
- Add a short "Where to do this in app" section when relevant.
- If advice is requested, include: signal, risk, and next action.
""".strip()


def _serialize(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    return value


def _dedupe_sources(sources: list[SourceRef]) -> list[SourceRef]:
    seen: set[tuple[str, str]] = set()
    rows: list[SourceRef] = []
    for source in sources:
        key = (source.type, source.ref)
        if key in seen:
            continue
        seen.add(key)
        rows.append(source)
    return rows


def get_nav_snapshot(db: Session, club_id: int, period_id: int) -> tuple[dict, list[SourceRef]]:
    snapshot = db.scalar(
        select(NavSnapshot).where(NavSnapshot.club_id == club_id, NavSnapshot.period_id == period_id)
    )
    if snapshot is None:
        preview = compute_monthly_nav(club_id, period_id, db=db)
        return (
            {
                "opening_nav": money(preview.opening_nav),
                "closing_nav": money(preview.closing_nav),
                "contributions_total": money(preview.contributions_total),
                "withdrawals_total": money(preview.withdrawals_total),
                "income_total": money(preview.income_total),
                "expenses_total": money(preview.expenses_total),
                "status": "preview",
            },
            [SourceRef(type="period_id", ref=str(period_id))],
        )
    return (
        {
            "snapshot_id": snapshot.id,
            "opening_nav": money(snapshot.opening_nav),
            "closing_nav": money(snapshot.closing_nav),
            "contributions_total": money(snapshot.contributions_total),
            "withdrawals_total": money(snapshot.withdrawals_total),
            "income_total": money(snapshot.income_total),
            "expenses_total": money(snapshot.expenses_total),
            "status": "closed_snapshot",
        },
        [
            SourceRef(type="snapshot_id", ref=str(snapshot.id)),
            SourceRef(type="period_id", ref=str(period_id)),
        ],
    )


def list_transactions(db: Session, club_id: int, period_id: int, limit: int = 50) -> tuple[list[dict], list[SourceRef]]:
    rows = list(
        db.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.club_id == club_id, LedgerEntry.period_id == period_id)
            .order_by(LedgerEntry.tx_date.desc(), LedgerEntry.id.desc())
            .limit(max(1, min(limit, 500)))
        ).all()
    )
    data = [
        {
            "id": row.id,
            "type": row.entry_type.value,
            "amount": money(row.amount),
            "date": row.tx_date.isoformat(),
            "reference": row.reference,
            "investor_id": row.investor_id,
            "description": row.description,
            "category": row.category,
        }
        for row in rows
    ]
    refs = [SourceRef(type="transaction_ref", ref=row.reference or f"tx:{row.id}") for row in rows[:10]]
    refs.append(SourceRef(type="period_id", ref=str(period_id)))
    return data, refs


def get_investor_statement(
    db: Session,
    club_id: int,
    period_id: int,
    investor_id: int,
) -> tuple[dict | None, list[SourceRef]]:
    investor = db.scalar(
        select(Investor).where(
            Investor.id == investor_id,
            Investor.club_id == club_id,
        )
    )
    row = db.scalar(
        select(InvestorBalance).where(
            InvestorBalance.club_id == club_id,
            InvestorBalance.period_id == period_id,
            InvestorBalance.investor_id == investor_id,
        )
    )
    refs = [SourceRef(type="investor_id", ref=str(investor_id)), SourceRef(type="period_id", ref=str(period_id))]
    if investor is not None:
        refs.append(SourceRef(type="investor_code", ref=investor.investor_code))
    if row is None:
        return None, refs
    refs.append(SourceRef(type="snapshot_id", ref=str(row.snapshot_id)))
    return (
        {
            "investor_id": row.investor_id,
            "investor_code": investor.investor_code if investor else None,
            "investor_name": investor.name if investor else None,
            "opening_balance": money(row.opening_balance),
            "ownership_pct": row.ownership_pct,
            "income_alloc": money(row.income_alloc),
            "expense_alloc": money(row.expense_alloc),
            "net_alloc": money(row.net_alloc),
            "contributions": money(row.contributions),
            "withdrawals": money(row.withdrawals),
            "closing_balance": money(row.closing_balance),
        },
        refs,
    )


def get_insights(db: Session, club_id: int, period_id: int) -> tuple[dict, list[SourceRef]]:
    payload = generate_metrics(db, club_id, period_id)
    return (
        {
            "metrics": payload.metrics,
            "insights": payload.insights,
            "anomalies": payload.anomalies,
        },
        [SourceRef(type="period_id", ref=str(period_id))],
    )


def _rag_docs(query: str) -> list[SourceRef]:
    docs_root = Path(__file__).resolve().parents[2] / "docs"
    refs: list[SourceRef] = []
    if not docs_root.exists():
        return refs
    lowered = query.lower()
    for path in docs_root.glob("*.md"):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        if any(token in content.lower() for token in lowered.split()[:8]):
            refs.append(SourceRef(type="doc", ref=path.name))
    return refs[:5]


def _pdf_report_sources(db: Session, club_id: int, period_id: int) -> list[SourceRef]:
    rows = list(
        db.scalars(
            select(ReportSnapshot)
            .where(ReportSnapshot.club_id == club_id, ReportSnapshot.period_id == period_id)
            .order_by(ReportSnapshot.created_at.desc())
            .limit(5)
        ).all()
    )
    return [SourceRef(type="pdf_report", ref=row.file_name) for row in rows]


def _extract_requested_investor_ids(message: str) -> list[int]:
    rows = set(int(match.group(1)) for match in re.finditer(r"\binvestor(?:_id)?\s*[:=]?\s*(\d+)\b", message.lower()))
    return sorted(rows)


def _build_context(
    db: Session,
    *,
    club_id: int,
    period_id: int,
    message: str,
) -> tuple[dict, list[SourceRef]]:
    period = db.scalar(
        select(AccountingPeriod).where(AccountingPeriod.id == period_id, AccountingPeriod.club_id == club_id)
    )
    if period is None:
        return (
            {
                "error": "Period not found in this club scope.",
            },
            [SourceRef(type="period_id", ref=str(period_id))],
        )

    snapshot, snapshot_sources = get_nav_snapshot(db, club_id, period_id)
    tx_rows, tx_sources = list_transactions(db, club_id, period_id, limit=25)
    insights_payload, insight_sources = get_insights(db, club_id, period_id)
    rag_sources = _rag_docs(message)
    report_sources = _pdf_report_sources(db, club_id, period_id)

    position_rows = list(
        db.scalars(
            select(InvestorPosition).where(InvestorPosition.period_id == period_id).order_by(InvestorPosition.investor_id)
        ).all()
    )
    investor_rows = list(
        db.scalars(
            select(Investor).where(Investor.club_id == club_id, Investor.is_active.is_(True)).order_by(Investor.id)
        ).all()
    )
    investor_name_map = {row.id: row.name for row in investor_rows}
    investor_code_map = {row.id: row.investor_code for row in investor_rows}

    balances = list(
        db.scalars(
            select(InvestorBalance).where(InvestorBalance.club_id == club_id, InvestorBalance.period_id == period_id)
            .order_by(InvestorBalance.closing_balance.desc())
            .limit(50)
        ).all()
    )
    balance_rows = [
        {
            "investor_id": row.investor_id,
            "investor_name": investor_name_map.get(row.investor_id),
            "investor_code": investor_code_map.get(row.investor_id),
            "opening_balance": money(row.opening_balance),
            "ownership_pct": row.ownership_pct,
            "income_alloc": money(row.income_alloc),
            "expense_alloc": money(row.expense_alloc),
            "net_alloc": money(row.net_alloc),
            "contributions": money(row.contributions),
            "withdrawals": money(row.withdrawals),
            "closing_balance": money(row.closing_balance),
        }
        for row in balances
    ]

    if not balance_rows:
        preview = compute_monthly_nav(club_id, period_id, db=db)
        balance_rows = [
            {
                "investor_id": row.investor_id,
                "investor_name": investor_name_map.get(row.investor_id),
                "investor_code": investor_code_map.get(row.investor_id),
                "opening_balance": money(row.opening_balance),
                "ownership_pct": row.ownership_pct,
                "income_alloc": money(row.income_share),
                "expense_alloc": money(row.expense_share),
                "net_alloc": money(row.net_alloc),
                "contributions": money(row.contributions),
                "withdrawals": money(row.withdrawals),
                "closing_balance": money(row.closing_balance),
            }
            for row in preview.allocations
        ]

    requested_ids = _extract_requested_investor_ids(message)
    requested_statements: list[dict] = []
    statement_sources: list[SourceRef] = []
    for investor_id in requested_ids[:5]:
        statement, refs = get_investor_statement(db, club_id, period_id, investor_id)
        statement_sources.extend(refs)
        if statement is not None:
            requested_statements.append(statement)

    context = {
        "scope": {
            "club_id": club_id,
            "period_id": period_id,
            "period_status": period.status.value,
            "year_month": f"{period.year:04d}-{period.month:02d}",
        },
        "app_sections": SECTION_GUIDES,
        "snapshot": snapshot,
        "positions_count": len(position_rows),
        "active_investors": len(investor_rows),
        "transactions_count": len(tx_rows),
        "recent_transactions": tx_rows[:15],
        "investor_balances": balance_rows[:20],
        "requested_investor_statements": requested_statements,
        "analytics": insights_payload,
    }

    sources = (
        [SourceRef(type="period_id", ref=str(period_id))]
        + snapshot_sources
        + tx_sources
        + insight_sources
        + statement_sources
        + rag_sources
        + report_sources
    )
    return context, _dedupe_sources(sources)


def _extract_gemini_text(payload: dict[str, Any]) -> str | None:
    candidates = payload.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    first = candidates[0] if isinstance(candidates[0], dict) else {}
    content = first.get("content") if isinstance(first, dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        return None
    chunks: list[str] = []
    for part in parts:
        if isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                chunks.append(text.strip())
    if not chunks:
        return None
    return "\n".join(chunks).strip()


def _gemini_call(
    *,
    model: str,
    api_key: str,
    base_url: str,
    temperature: float,
    max_output_tokens: int,
    user_prompt: str,
) -> str | None:
    url = f"{base_url}/models/{model}:generateContent"
    payload = {
        "systemInstruction": {
            "parts": [{"text": COPILOT_SYSTEM_PROMPT}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            }
        ],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
        },
    }

    with httpx.Client(timeout=45.0) as client:
        response = client.post(
            url,
            params={"key": api_key},
            headers={"Content-Type": "application/json"},
            json=payload,
        )
    if response.status_code >= 400:
        raise httpx.HTTPStatusError(
            message=f"Gemini request failed with status {response.status_code}",
            request=response.request,
            response=response,
        )
    response_json = response.json()
    return _extract_gemini_text(response_json)


def _call_gemini(message: str, context: dict[str, Any]) -> tuple[str | None, str | None]:
    settings = get_settings()
    api_key = settings.gemini_api_key.strip()
    if not api_key:
        return None, None

    user_prompt = (
        "User request:\n"
        f"{message.strip()}\n\n"
        "Scoped app data context (JSON):\n"
        f"{json.dumps(_serialize(context), ensure_ascii=True, indent=2)}\n\n"
        "Answer using only this context. If data is missing, clearly say what is missing."
    )
    models_to_try = [settings.gemini_model.strip(), "gemini-2.5-flash", "gemini-2.0-flash"]
    tried: set[str] = set()
    for model in models_to_try:
        if not model or model in tried:
            continue
        tried.add(model)
        try:
            answer = _gemini_call(
                model=model,
                api_key=api_key,
                base_url=settings.gemini_base_url.rstrip("/"),
                temperature=settings.copilot_temperature,
                max_output_tokens=settings.copilot_max_output_tokens,
                user_prompt=user_prompt,
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in {404, 400}:
                continue
            return None, None
        except Exception:
            return None, None
        if answer:
            return answer, model
    return None, None


def _answer_rule_based(
    *,
    context: dict[str, Any],
    message: str,
) -> str:
    lowered = message.lower().strip()
    snapshot = context.get("snapshot", {})
    transactions = context.get("recent_transactions", [])
    analytics = context.get("analytics", {})

    if any(token in lowered for token in ["where", "how", "section", "navigate", "screen", "page"]):
        rows = context.get("app_sections", [])
        if not rows:
            return "I cannot answer section navigation details because app section metadata is missing."
        guidance = "\n".join(
            f"- {row['section']}: {row['location']} | {row['flow']}" for row in rows
        )
        return f"Here is how to navigate the app sections:\n{guidance}"

    if "nav" in lowered or "change" in lowered:
        return (
            f"Opening NAV is UGX {snapshot.get('opening_nav', 0)}, closing NAV is UGX {snapshot.get('closing_nav', 0)}. "
            f"Drivers: contributions UGX {snapshot.get('contributions_total', 0)}, "
            f"withdrawals UGX {snapshot.get('withdrawals_total', 0)}, "
            f"income UGX {snapshot.get('income_total', 0)}, expenses UGX {snapshot.get('expenses_total', 0)}."
        )

    if any(token in lowered for token in ["advice", "invest", "strategy", "recommend"]):
        metrics = analytics.get("metrics", {})
        insights = analytics.get("insights", [])
        signal = insights[0]["description"] if insights else "No insight signal available for this period."
        return (
            f"Data-grounded signal: {signal} "
            f"Current closing NAV is UGX {metrics.get('closing_nav', 0)} with mismatch {metrics.get('mismatch', 0)}. "
            "Suggested next action: review expense trend and net inflows before increasing risk exposure. "
            "Risk note: this is informational guidance, not guaranteed return advice."
        )

    if any(token in lowered for token in ["allocation", "investor"]):
        balances = context.get("investor_balances", [])
        if not balances:
            return "I cannot answer allocation details because investor balance data is missing."
        top = balances[0]
        return (
            f"Top investor by closing balance is {top.get('investor_name') or top.get('investor_id')} "
            f"at UGX {top.get('closing_balance')}. "
            "Use Investors screen to inspect ownership%, allocations, and closing balances line by line."
        )

    if not transactions:
        return "I cannot answer with confidence because no transactions were found for this scoped period."
    return (
        f"I found {len(transactions)} recent transactions in this scoped period. "
        "Ask me about NAV change, section flow, allocation rationale, or investment guidance based on this data."
    )


def answer_chat(
    db: Session,
    *,
    club_id: int,
    period_id: int,
    message: str,
) -> CopilotAnswer:
    period = db.scalar(
        select(AccountingPeriod).where(AccountingPeriod.id == period_id, AccountingPeriod.club_id == club_id)
    )
    if period is None:
        return CopilotAnswer(
            response="I cannot answer because this club/period context was not found.",
            sources=[SourceRef(type="period_id", ref=str(period_id))],
        )

    lowered = message.lower().strip()
    if any(word in lowered for word in ["close", "edit", "update", "delete", "post", "modify", "reopen", "alter"]):
        return CopilotAnswer(
            response=(
                "I am read-only and cannot modify accounting records or alter NAV. "
                "Closed periods are immutable; corrections must be posted as adjustments in a later open period."
            ),
            sources=[SourceRef(type="period_id", ref=str(period_id))],
        )

    context, context_sources = _build_context(db, club_id=club_id, period_id=period_id, message=message)
    if context.get("error"):
        return CopilotAnswer(
            response="I cannot answer because scoped context could not be loaded.",
            sources=context_sources,
        )

    gemini_answer, model_used = _call_gemini(message, context)
    sources = list(context_sources)
    if model_used:
        sources.append(SourceRef(type="model", ref=model_used))
    sources = _dedupe_sources(sources)

    if gemini_answer:
        return CopilotAnswer(response=gemini_answer, sources=sources)

    fallback = _answer_rule_based(context=context, message=message)
    return CopilotAnswer(response=fallback, sources=sources)
