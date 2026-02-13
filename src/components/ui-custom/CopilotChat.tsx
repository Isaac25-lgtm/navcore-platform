import { useMemo, useState } from 'react';
import { Bot, Send, Sparkles, Shield } from 'lucide-react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { extractApiErrorMessage } from '@/lib/feedback';
import { chatCopilot } from '@/lib/api';
import { formatCurrency } from '@/lib/utils';
import type { CopilotChatResponse } from '@/types/platform';

interface CopilotChatProps {
  clubId: number | null;
  periodId: number | null;
  periodLabel: string;
}

interface SectionRow {
  label: string;
  value: string;
}

interface ParsedSection {
  title: string;
  rows: SectionRow[];
  bullets: string[];
  paragraphs: string[];
}

interface DriverRow {
  name: string;
  value: number;
  tone: 'positive' | 'negative';
}

const QUICK_ACTIONS = [
  { id: 'nav', label: 'Explain NAV change', prompt: 'Explain NAV change for this period.' },
  { id: 'alloc', label: 'Explain allocations', prompt: 'Explain allocations for investors in this period.' },
  { id: 'update', label: 'Draft investor update', prompt: 'Draft an investor update using this period data only.' },
  {
    id: 'guide',
    label: 'Explain app sections',
    prompt: 'Explain each app section, where it is located, and the workflow from entry to analysis.',
  },
  {
    id: 'advice',
    label: 'Investment guidance',
    prompt: 'Give investment guidance based only on this club and period data, including risks and next actions.',
  },
];

function cleanMarkdown(text: string): string {
  return text
    .replace(/\*\*(.*?)\*\*/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\s+/g, ' ')
    .trim();
}

function ensureSection(sections: ParsedSection[]): ParsedSection {
  if (sections.length === 0) {
    sections.push({ title: 'Summary', rows: [], bullets: [], paragraphs: [] });
  }
  return sections[sections.length - 1];
}

function parseStructuredResponse(raw: string): ParsedSection[] {
  const lines = raw.replace(/\r/g, '').split('\n');
  const sections: ParsedSection[] = [];

  for (const rawLine of lines) {
    const line = rawLine.trim();
    if (!line) continue;

    const sectionMatch = line.match(/^\d+\.\s*\*\*(.+?)\*\*$/) ?? line.match(/^\d+\.\s+(.+)$/);
    if (sectionMatch) {
      sections.push({
        title: cleanMarkdown(sectionMatch[1]),
        rows: [],
        bullets: [],
        paragraphs: [],
      });
      continue;
    }

    const rowMatch =
      line.match(/^[-*]\s*\*\*(.+?)\*\*:\s*(.+)$/) ??
      line.match(/^[-*]\s*([^:]{2,40}):\s*(.+)$/);
    if (rowMatch) {
      const section = ensureSection(sections);
      section.rows.push({
        label: cleanMarkdown(rowMatch[1]),
        value: cleanMarkdown(rowMatch[2]),
      });
      continue;
    }

    const bulletMatch = line.match(/^[-*]\s+(.+)$/);
    if (bulletMatch) {
      const section = ensureSection(sections);
      section.bullets.push(cleanMarkdown(bulletMatch[1]));
      continue;
    }

    const section = ensureSection(sections);
    section.paragraphs.push(cleanMarkdown(line));
  }

  return sections;
}

function parseDriverRows(raw: string): DriverRow[] {
  const labels = [
    { name: 'Contributions', tone: 'positive' as const },
    { name: 'Withdrawals', tone: 'negative' as const },
    { name: 'Income', tone: 'positive' as const },
    { name: 'Expenses', tone: 'negative' as const },
  ];

  const rows: DriverRow[] = [];
  for (const label of labels) {
    const matcher = new RegExp(`${label.name}[^\\n]*?UGX\\s*([0-9,]+(?:\\.[0-9]+)?)`, 'i');
    const match = raw.match(matcher);
    if (!match) continue;
    const numeric = Number(match[1].replaceAll(',', ''));
    if (!Number.isFinite(numeric) || numeric <= 0) continue;
    rows.push({ name: label.name, value: numeric, tone: label.tone });
  }
  return rows;
}

export function CopilotChat({ clubId, periodId, periodLabel }: CopilotChatProps) {
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [answer, setAnswer] = useState<CopilotChatResponse | null>(null);

  const disabled = useMemo(() => !clubId || !periodId || busy, [busy, clubId, periodId]);
  const parsedSections = useMemo(
    () => (answer?.response ? parseStructuredResponse(answer.response) : []),
    [answer?.response],
  );
  const driverRows = useMemo(
    () => (answer?.response ? parseDriverRows(answer.response) : []),
    [answer?.response],
  );

  async function runPrompt(prompt: string) {
    if (!clubId || !periodId) return;
    setBusy(true);
    setError(null);
    try {
      const payload = await chatCopilot(clubId, periodId, prompt);
      setAnswer(payload);
    } catch (err) {
      setError(extractApiErrorMessage(err, 'Failed to fetch copilot response.'));
    } finally {
      setBusy(false);
    }
  }

  async function handleSubmit() {
    const cleaned = query.trim();
    if (!cleaned) return;
    await runPrompt(cleaned);
  }

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h3 className="text-base font-semibold text-slate-800 flex items-center gap-2">
              <Bot className="w-4 h-4 text-blue-600" />
              Copilot
            </h3>
            <p className="text-xs text-slate-500 mt-1">
              Read-only and scoped to selected context: {periodLabel}. Ask about any section, workflow, rationale, or data-grounded investment guidance.
            </p>
          </div>
          <span className="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-700 font-medium flex items-center gap-1">
            <Shield className="w-3 h-3" />
            Guardrails On
          </span>
        </div>

        <div className="flex items-center gap-2 mt-4">
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Ask anything: section flow, NAV rationale, investor allocations, guidance..."
            className="bg-white border-slate-200"
            disabled={disabled}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                void handleSubmit();
              }
            }}
          />
          <Button className="bg-blue-600 hover:bg-blue-700 text-white" disabled={disabled} onClick={() => void handleSubmit()}>
            <Send className="w-4 h-4 mr-1.5" />
            Ask
          </Button>
        </div>

        <div className="flex flex-wrap gap-2 mt-3">
          {QUICK_ACTIONS.map((action) => (
            <button
              key={action.id}
              onClick={() => void runPrompt(action.prompt)}
              disabled={disabled}
              className="text-xs px-3 py-2 rounded-lg border border-slate-200 bg-slate-50 text-slate-700 hover:bg-slate-100 transition-colors"
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <h4 className="text-sm font-semibold text-slate-800 flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-blue-500" />
          Response
        </h4>
        {error && <p className="text-sm text-red-600 mt-3">{error}</p>}
        {!error && !answer && (
          <p className="text-sm text-slate-500 mt-3">
            Ask a question or use a quick action to receive a scoped answer.
          </p>
        )}
        {answer && (
          <div className="space-y-4 mt-3">
            {driverRows.length > 0 && (
              <div className="p-4 rounded-xl bg-gradient-to-r from-blue-50 to-slate-50 border border-blue-100">
                <p className="text-xs font-semibold text-slate-700 mb-2">NAV Driver Breakdown</p>
                <div className="h-[170px]">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={driverRows} layout="vertical" margin={{ top: 10, right: 16, left: 10, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" horizontal={false} />
                      <XAxis type="number" hide />
                      <YAxis type="category" dataKey="name" tick={{ fill: '#334155', fontSize: 12 }} tickLine={false} axisLine={false} />
                      <Tooltip
                        contentStyle={{ backgroundColor: 'white', border: '1px solid #e2e8f0', borderRadius: '8px', padding: '10px' }}
                        formatter={(value: number) => [formatCurrency(value), 'Amount']}
                      />
                      <Bar dataKey="value" radius={[6, 6, 6, 6]}>
                        {driverRows.map((row, index) => (
                          <Cell key={`${row.name}-${index}`} fill={row.tone === 'positive' ? '#10b981' : '#ef4444'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {parsedSections.length > 0 ? (
              <div className="space-y-3">
                {parsedSections.map((section, index) => (
                  <div
                    key={`${section.title}-${index}`}
                    className="p-4 rounded-xl border border-slate-200 bg-gradient-to-br from-white to-slate-50"
                  >
                    <h5 className="text-sm font-semibold text-blue-700 mb-2">{section.title}</h5>
                    {section.rows.length > 0 && (
                      <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mb-2">
                        {section.rows.map((row, rowIndex) => (
                          <div key={`${row.label}-${rowIndex}`} className="p-2 rounded-lg bg-white border border-slate-100">
                            <p className="text-[11px] uppercase tracking-wide text-slate-500">{row.label}</p>
                            <p className="text-xs text-slate-700 mt-0.5">{row.value}</p>
                          </div>
                        ))}
                      </div>
                    )}
                    {section.paragraphs.map((paragraph, paragraphIndex) => (
                      <p key={`${section.title}-p-${paragraphIndex}`} className="text-sm text-slate-700 mb-1.5">
                        {paragraph}
                      </p>
                    ))}
                    {section.bullets.length > 0 && (
                      <div className="space-y-1.5 mt-1.5">
                        {section.bullets.map((bullet, bulletIndex) => (
                          <div key={`${section.title}-b-${bulletIndex}`} className="flex items-start gap-2">
                            <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-blue-500" />
                            <p className="text-sm text-slate-700">{bullet}</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200">
                <p className="text-sm text-slate-700 whitespace-pre-wrap">{cleanMarkdown(answer.response)}</p>
              </div>
            )}

            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Sources used</p>
              <div className="flex flex-wrap gap-2">
                {answer.sources.length === 0 ? (
                  <span className="text-xs text-slate-500">No sources returned.</span>
                ) : (
                  answer.sources.map((source, idx) => (
                    <span
                      key={`${source.type}-${source.ref}-${idx}`}
                      className="text-xs px-2 py-1 rounded-full bg-slate-100 text-slate-600"
                    >
                      {source.type}: {source.ref}
                    </span>
                  ))
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
