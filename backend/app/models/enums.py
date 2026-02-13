import enum


class RoleName(str, enum.Enum):
    admin = "admin"
    fund_accountant = "fund_accountant"
    advisor = "advisor"
    investor = "investor"
    # legacy roles kept for backward compatibility during migration
    manager = "manager"
    analyst = "analyst"
    viewer = "viewer"


class PeriodStatus(str, enum.Enum):
    draft = "draft"
    review = "review"
    closed = "closed"


class LedgerEntryType(str, enum.Enum):
    contribution = "contribution"
    withdrawal = "withdrawal"
    income = "income"
    expense = "expense"
    adjustment = "adjustment"


class ReportType(str, enum.Enum):
    monthly_club = "monthly_club"
    investor_statement = "investor_statement"
