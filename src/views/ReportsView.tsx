import { useEffect, useState } from 'react';
import {
  FileText,
  Calendar,
  Download,
  FileDown,
  Users,
  BarChart3,
  Shield,
  AlertCircle,
  Clock,
  CheckCircle2,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { usePlatform } from '@/context/PlatformContext';
import { extractApiErrorMessage } from '@/lib/feedback';
import {
  fetchInvestors,
  generateInvestorReport,
  generateMonthlyReport,
  getCsvExportUrl,
  getExcelExportUrl,
  listReports,
} from '@/lib/api';
import type { ReportSnapshot } from '@/types/platform';

const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8000/api/v1';

export function ReportsView() {
  const { selectedClubId, selectedPeriodId, status, refresh } = usePlatform();
  const [reports, setReports] = useState<ReportSnapshot[]>([]);
  const [investors, setInvestors] = useState<Array<{ id: number; name: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function load() {
    if (!selectedClubId || !selectedPeriodId) {
      setReports([]);
      setInvestors([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const [reportRows, investorRows] = await Promise.all([
        listReports(selectedClubId, selectedPeriodId),
        fetchInvestors(selectedClubId),
      ]);
      setReports(reportRows);
      setInvestors(investorRows);
      setError(null);
    } catch (err) {
      setError(extractApiErrorMessage(err, 'Failed to load reports.'));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [selectedClubId, selectedPeriodId]);

  async function handleGenerateMonthly() {
    if (!selectedClubId || !selectedPeriodId) return;
    setWorking(true);
    setMessage(null);
    setError(null);
    try {
      await generateMonthlyReport(selectedClubId, selectedPeriodId);
      await Promise.all([load(), refresh()]);
      setMessage('Monthly club report generated and stored from immutable snapshot.');
    } catch (err) {
      const detail = extractApiErrorMessage(err, 'Failed to generate monthly report.');
      setError(`${detail} Close the period first, then generate.`);
    } finally {
      setWorking(false);
    }
  }

  async function handleGenerateInvestorStatements() {
    if (!selectedClubId || !selectedPeriodId || investors.length === 0) return;
    setWorking(true);
    setMessage(null);
    setError(null);
    try {
      await Promise.all(
        investors.map((investor) => generateInvestorReport(selectedClubId, selectedPeriodId, investor.id)),
      );
      await Promise.all([load(), refresh()]);
      setMessage(`Generated ${investors.length} investor statements from closed snapshot data.`);
    } catch (err) {
      const detail = extractApiErrorMessage(err, 'Failed to generate investor statements.');
      setError(`${detail} Ensure period is closed and investors exist.`);
    } finally {
      setWorking(false);
    }
  }

  const closed = status === 'closed';

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-slate-800">Reports</h1>
          <p className="text-sm text-slate-500 mt-0.5">Generate and manage financial reports</p>
        </div>
        {selectedClubId && selectedPeriodId && (
          <div className="flex items-center gap-2">
            <a
              href={getCsvExportUrl(selectedClubId, selectedPeriodId)}
              className="inline-flex items-center gap-2 px-3 py-2 text-sm rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 transition-colors"
              target="_blank"
              rel="noreferrer"
            >
              <Download className="w-4 h-4" />
              Export CSV
            </a>
            <a
              href={getExcelExportUrl(selectedClubId, selectedPeriodId)}
              className="inline-flex items-center gap-2 px-3 py-2 text-sm rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 transition-colors"
              target="_blank"
              rel="noreferrer"
            >
              <Download className="w-4 h-4" />
              Export Excel
            </a>
          </div>
        )}
      </div>

      {!closed && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5" />
          <div>
            <p className="text-sm font-medium text-amber-800">Closed Snapshot Required</p>
            <p className="text-sm text-amber-700">
              PDF generation is enabled only when period status is Closed.
            </p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 hover:shadow-md hover:border-blue-300 transition-all">
          <div className="flex items-start justify-between mb-4">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-blue-100">
              <BarChart3 className="w-6 h-6 text-blue-600" />
            </div>
            <button className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">
              <Download className="w-4 h-4" />
            </button>
          </div>
          <h4 className="font-semibold text-slate-800 mb-1">Club NAV Report</h4>
          <p className="text-sm text-slate-500 mb-4">Monthly NAV movement and breakdown from closed snapshot</p>
          <Button
            size="sm"
            className="bg-blue-600 hover:bg-blue-700 text-white"
            onClick={handleGenerateMonthly}
            disabled={!closed || working || !selectedClubId || !selectedPeriodId}
          >
            <FileDown className="w-4 h-4 mr-2" />
            Generate
          </Button>
        </div>

        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5 hover:shadow-md hover:border-blue-300 transition-all">
          <div className="flex items-start justify-between mb-4">
            <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-emerald-100">
              <Users className="w-6 h-6 text-emerald-600" />
            </div>
            <button className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition-colors">
              <Download className="w-4 h-4" />
            </button>
          </div>
          <h4 className="font-semibold text-slate-800 mb-1">Investor Statements</h4>
          <p className="text-sm text-slate-500 mb-4">Generate investor-level closed period statements</p>
          <Button
            size="sm"
            className="bg-blue-600 hover:bg-blue-700 text-white"
            onClick={handleGenerateInvestorStatements}
            disabled={!closed || working || investors.length === 0}
          >
            <FileDown className="w-4 h-4 mr-2" />
            Generate All
          </Button>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-semibold text-slate-800">Stored PDF Snapshots</h3>
            <p className="text-xs text-slate-500">Immutable report files generated from closed periods</p>
          </div>
          <div className="text-sm text-slate-500">
            {loading ? 'Loading...' : `${reports.length} files`}
          </div>
        </div>

        {error && <p className="text-sm text-red-600 mb-3">{error}</p>}
        {message && <p className="text-sm text-emerald-600 mb-3">{message}</p>}

        {loading ? (
          <p className="text-sm text-slate-500">Loading report snapshots...</p>
        ) : reports.length === 0 ? (
          <div className="p-4 bg-slate-50 rounded-xl text-sm text-slate-500">
            No reports generated yet for this period.
          </div>
        ) : (
          <div className="space-y-3">
            {reports.map((report) => (
              <div key={report.id} className="flex items-center justify-between p-4 bg-slate-50 rounded-xl">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 bg-white rounded-lg flex items-center justify-center shadow-sm">
                    {report.report_type === 'monthly_club' ? (
                      <Shield className="w-5 h-5 text-slate-500" />
                    ) : (
                      <FileText className="w-5 h-5 text-slate-500" />
                    )}
                  </div>
                  <div>
                    <p className="font-medium text-slate-800">{report.file_name}</p>
                    <p className="text-xs text-slate-500">
                      {report.report_type} | hash {report.file_hash.slice(0, 10)}...
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="text-xs text-slate-500">Generated</p>
                    <p className="text-sm text-slate-700">{new Date(report.created_at).toLocaleString()}</p>
                  </div>
                  <a
                    href={`${API_BASE}/reports/${report.id}/download`}
                    className="inline-flex items-center gap-2 px-3 py-2 text-sm rounded-lg border border-slate-200 text-slate-600 hover:bg-slate-100 transition-colors"
                    target="_blank"
                    rel="noreferrer"
                  >
                    <Download className="w-4 h-4" />
                    Download
                  </a>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-semibold text-slate-800">Workflow Status</h3>
            <p className="text-xs text-slate-500">Reporting pipeline status for current period</p>
          </div>
        </div>
        <div className="space-y-3">
          <div className="flex items-center justify-between p-4 bg-slate-50 rounded-xl">
            <div className="flex items-center gap-3">
              <Clock className="w-5 h-5 text-slate-500" />
              <p className="text-sm text-slate-700">Period Status</p>
            </div>
            <span className="text-sm font-medium text-slate-700 uppercase">{status}</span>
          </div>
          <div className="flex items-center justify-between p-4 bg-slate-50 rounded-xl">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              <p className="text-sm text-slate-700">Snapshot Integrity</p>
            </div>
            <span className="text-sm font-medium text-emerald-600">Immutable</span>
          </div>
          <div className="flex items-center justify-between p-4 bg-slate-50 rounded-xl">
            <div className="flex items-center gap-3">
              <Calendar className="w-5 h-5 text-slate-500" />
              <p className="text-sm text-slate-700">Available Files</p>
            </div>
            <span className="text-sm font-medium text-slate-700">{reports.length}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
