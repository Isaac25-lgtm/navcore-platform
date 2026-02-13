import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from 'react';
import {
  fetchClubs,
  fetchCloseChecklist,
  fetchInsights,
  fetchReconciliationDetails,
  fetchPeriodState,
  fetchPeriods,
  fetchReconciliation,
} from '@/lib/api';
import type {
  ClubSummary,
  CloseChecklist,
  InsightsResponse,
  Mode,
  PeriodState,
  PeriodStatus,
  PeriodSummary,
  ReconciliationDetails,
  ReconciliationStamp,
} from '@/types/platform';

interface PlatformContextValue {
  clubs: ClubSummary[];
  periods: PeriodSummary[];
  selectedClubId: number | null;
  selectedPeriodId: number | null;
  selectedClub: ClubSummary | null;
  selectedPeriod: PeriodSummary | null;
  periodState: PeriodState | null;
  reconciliation: ReconciliationStamp | null;
  reconciliationDetails: ReconciliationDetails | null;
  checklist: CloseChecklist | null;
  insights: InsightsResponse | null;
  mode: Mode;
  loading: boolean;
  error: string | null;
  locked: boolean;
  status: PeriodStatus;
  setMode: (mode: Mode) => void;
  setSelectedClubId: (clubId: number) => void;
  setSelectedPeriodId: (periodId: number) => void;
  refresh: () => Promise<void>;
}

const PlatformContext = createContext<PlatformContextValue | null>(null);

const DEFAULT_STATUS: PeriodStatus = 'draft';

export function PlatformProvider({ children }: PropsWithChildren) {
  const [clubs, setClubs] = useState<ClubSummary[]>([]);
  const [periods, setPeriods] = useState<PeriodSummary[]>([]);
  const [selectedClubId, setSelectedClubIdState] = useState<number | null>(null);
  const [selectedPeriodId, setSelectedPeriodIdState] = useState<number | null>(null);
  const [periodState, setPeriodState] = useState<PeriodState | null>(null);
  const [reconciliation, setReconciliation] = useState<ReconciliationStamp | null>(null);
  const [reconciliationDetails, setReconciliationDetails] = useState<ReconciliationDetails | null>(null);
  const [checklist, setChecklist] = useState<CloseChecklist | null>(null);
  const [insights, setInsights] = useState<InsightsResponse | null>(null);
  const [mode, setMode] = useState<Mode>('basic');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const selectedClub = useMemo(
    () => clubs.find((club) => club.id === selectedClubId) ?? null,
    [clubs, selectedClubId],
  );
  const selectedPeriod = useMemo(
    () => periods.find((period) => period.id === selectedPeriodId) ?? null,
    [periods, selectedPeriodId],
  );

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const clubList = await fetchClubs();
      setClubs(clubList);
      const selectedClubExists = selectedClubId
        ? clubList.some((club) => club.id === selectedClubId)
        : false;
      const clubId = selectedClubExists ? selectedClubId : clubList[0]?.id ?? null;
      if (!clubId) {
        setPeriods([]);
        setSelectedClubIdState(null);
        setSelectedPeriodIdState(null);
        setPeriodState(null);
        setReconciliation(null);
        setReconciliationDetails(null);
        setChecklist(null);
        setInsights({ mode, items: [], anomalies: [] });
        return;
      }
      setSelectedClubIdState(clubId);
      const periodList = await fetchPeriods(clubId);
      setPeriods(periodList);
      const selectedPeriodExists = selectedPeriodId
        ? periodList.some((period) => period.id === selectedPeriodId)
        : false;
      const periodId = selectedPeriodExists ? selectedPeriodId : periodList[0]?.id ?? null;
      setSelectedPeriodIdState(periodId);

      if (!periodId) {
        setPeriodState(null);
        setReconciliation(null);
        setReconciliationDetails(null);
        setChecklist(null);
        setInsights({ mode, items: [], anomalies: [] });
        return;
      }

      const [state, stamp, detail, closeChecklist, insightData] = await Promise.all([
        fetchPeriodState(clubId, periodId),
        fetchReconciliation(clubId, periodId),
        fetchReconciliationDetails(clubId, periodId),
        fetchCloseChecklist(clubId, periodId),
        fetchInsights(clubId, periodId, mode),
      ]);
      setPeriodState(state);
      setReconciliation(stamp);
      setReconciliationDetails(detail);
      setChecklist(closeChecklist);
      setInsights(insightData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load platform data.');
    } finally {
      setLoading(false);
    }
  }, [mode, selectedClubId, selectedPeriodId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const setSelectedClubId = useCallback((clubId: number) => {
    setSelectedClubIdState(clubId);
    setSelectedPeriodIdState(null);
  }, []);

  const setSelectedPeriodId = useCallback((periodId: number) => {
    setSelectedPeriodIdState(periodId);
  }, []);

  const locked = selectedPeriod?.status === 'closed' || periodState?.status === 'closed';
  const status = (selectedPeriod?.status ?? periodState?.status ?? DEFAULT_STATUS) as PeriodStatus;

  const value = useMemo<PlatformContextValue>(
    () => ({
      clubs,
      periods,
      selectedClubId,
      selectedPeriodId,
      selectedClub,
      selectedPeriod,
      periodState,
      reconciliation,
      reconciliationDetails,
      checklist,
      insights,
      mode,
      loading,
      error,
      locked: Boolean(locked),
      status,
      setMode,
      setSelectedClubId,
      setSelectedPeriodId,
      refresh,
    }),
    [
      checklist,
      clubs,
      error,
      insights,
      loading,
      locked,
      mode,
      periodState,
      periods,
      reconciliation,
      reconciliationDetails,
      refresh,
      selectedClub,
      selectedClubId,
      selectedPeriod,
      selectedPeriodId,
      setSelectedClubId,
      setSelectedPeriodId,
      status,
    ],
  );

  return <PlatformContext.Provider value={value}>{children}</PlatformContext.Provider>;
}

export function usePlatform() {
  const context = useContext(PlatformContext);
  if (!context) {
    throw new Error('usePlatform must be used within PlatformProvider.');
  }
  return context;
}
