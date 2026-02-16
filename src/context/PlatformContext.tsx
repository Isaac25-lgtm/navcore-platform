import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
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
  refreshing: boolean;
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
const EMPTY_INSIGHTS: InsightsResponse = { mode: 'basic', items: [], anomalies: [] };

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
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Refs let the refresh function read latest state without being recreated on every change.
  // This breaks the cascade: state change → new callback ref → effect fires → refetch.
  const selectedClubIdRef = useRef(selectedClubId);
  const selectedPeriodIdRef = useRef(selectedPeriodId);
  const modeRef = useRef(mode);
  selectedClubIdRef.current = selectedClubId;
  selectedPeriodIdRef.current = selectedPeriodId;
  modeRef.current = mode;

  // Monotonic counter: when a newer refresh starts, older in-flight ones bail out.
  const fetchGenRef = useRef(0);

  const selectedClub = useMemo(
    () => clubs.find((club) => club.id === selectedClubId) ?? null,
    [clubs, selectedClubId],
  );
  const selectedPeriod = useMemo(
    () => periods.find((period) => period.id === selectedPeriodId) ?? null,
    [periods, selectedPeriodId],
  );

  const clearPeriodData = useCallback(() => {
    setPeriodState(null);
    setReconciliation(null);
    setReconciliationDetails(null);
    setChecklist(null);
    setInsights(EMPTY_INSIGHTS);
  }, []);

  // ── Core refresh — stable reference, reads state through refs ──
  const refresh = useCallback(async () => {
    const gen = ++fetchGenRef.current;
    const stale = () => fetchGenRef.current !== gen;

    setRefreshing(true);
    setError(null);

    try {
      // 1. Clubs
      const clubList = await fetchClubs();
      if (stale()) return;
      setClubs(clubList);

      const curClub = selectedClubIdRef.current;
      const clubId =
        curClub && clubList.some((c) => c.id === curClub)
          ? curClub
          : clubList[0]?.id ?? null;

      if (clubId !== selectedClubIdRef.current) {
        setSelectedClubIdState(clubId);
        selectedClubIdRef.current = clubId;
      }

      if (!clubId) {
        setPeriods([]);
        setSelectedPeriodIdState(null);
        selectedPeriodIdRef.current = null;
        clearPeriodData();
        return;
      }

      // 2. Periods
      const periodList = await fetchPeriods(clubId);
      if (stale()) return;
      setPeriods(periodList);

      const curPeriod = selectedPeriodIdRef.current;
      const periodId =
        curPeriod && periodList.some((p) => p.id === curPeriod)
          ? curPeriod
          : periodList[0]?.id ?? null;

      if (periodId !== selectedPeriodIdRef.current) {
        setSelectedPeriodIdState(periodId);
        selectedPeriodIdRef.current = periodId;
      }

      if (!periodId) {
        clearPeriodData();
        return;
      }

      // 3. Period data — all five in parallel
      const currentMode = modeRef.current;
      const [state, stamp, detail, closeChecklist, insightData] = await Promise.all([
        fetchPeriodState(clubId, periodId),
        fetchReconciliation(clubId, periodId),
        fetchReconciliationDetails(clubId, periodId),
        fetchCloseChecklist(clubId, periodId),
        fetchInsights(clubId, periodId, currentMode),
      ]);
      if (stale()) return;

      setPeriodState(state);
      setReconciliation(stamp);
      setReconciliationDetails(detail);
      setChecklist(closeChecklist);
      setInsights(insightData);
    } catch (err) {
      if (!stale()) {
        setError(err instanceof Error ? err.message : 'Failed to load platform data.');
      }
    } finally {
      if (!stale()) {
        setRefreshing(false);
        setInitialLoading(false);
      }
    }
  }, [clearPeriodData]); // stable — no state deps

  // ── Triggers ──

  // 1. Boot
  const booted = useRef(false);
  useEffect(() => {
    if (booted.current) return;
    booted.current = true;
    void refresh();
  }, [refresh]);

  // 2. Club changed → full refresh (new periods list needed)
  const prevClubId = useRef<number | null>(null);
  useEffect(() => {
    if (selectedClubId === prevClubId.current) return;
    const isInitial = prevClubId.current === null;
    prevClubId.current = selectedClubId;
    if (isInitial) return; // boot already handles first load
    void refresh();
  }, [selectedClubId, refresh]);

  // 3. Period or mode changed → only reload period data (skip clubs+periods fetch)
  const prevPeriodId = useRef<number | null>(null);
  const prevMode = useRef<Mode>(mode);
  useEffect(() => {
    const periodChanged = selectedPeriodId !== prevPeriodId.current;
    const modeChanged = mode !== prevMode.current;
    prevPeriodId.current = selectedPeriodId;
    prevMode.current = mode;

    if (!periodChanged && !modeChanged) return;
    // Skip if this is the first value being set (boot handles it)
    if (!selectedClubId || !selectedPeriodId) return;

    const gen = ++fetchGenRef.current;
    const stale = () => fetchGenRef.current !== gen;

    setRefreshing(true);
    setError(null);

    Promise.all([
      fetchPeriodState(selectedClubId, selectedPeriodId),
      fetchReconciliation(selectedClubId, selectedPeriodId),
      fetchReconciliationDetails(selectedClubId, selectedPeriodId),
      fetchCloseChecklist(selectedClubId, selectedPeriodId),
      fetchInsights(selectedClubId, selectedPeriodId, mode),
    ])
      .then(([state, stamp, detail, closeChecklist, insightData]) => {
        if (stale()) return;
        setPeriodState(state);
        setReconciliation(stamp);
        setReconciliationDetails(detail);
        setChecklist(closeChecklist);
        setInsights(insightData);
      })
      .catch((err) => {
        if (!stale()) {
          setError(err instanceof Error ? err.message : 'Failed to load period data.');
        }
      })
      .finally(() => {
        if (!stale()) {
          setRefreshing(false);
          setInitialLoading(false);
        }
      });
  }, [selectedClubId, selectedPeriodId, mode]);

  // ── Public setters ──

  const setSelectedClubId = useCallback((clubId: number) => {
    setSelectedClubIdState(clubId);
    setSelectedPeriodIdState(null);
    selectedPeriodIdRef.current = null;
  }, []);

  const setSelectedPeriodId = useCallback((periodId: number) => {
    setSelectedPeriodIdState(periodId);
  }, []);

  // ── Derived state ──

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
      loading: initialLoading,
      refreshing,
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
      initialLoading,
      insights,
      locked,
      mode,
      periodState,
      periods,
      reconciliation,
      reconciliationDetails,
      refresh,
      refreshing,
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
