import { Link } from 'react-router-dom';
import { Cpu, Eraser, Info, MapPin, Play, Route, Scale, Warehouse, Zap } from 'lucide-react';
import { Alert, Card, EmptyState, PageHeader, Spinner } from '../components/ui.jsx';
import MatrixTable from '../components/MatrixTable.jsx';
import ResultCard from '../components/ResultCard.jsx';
import { useApp } from '../context/AppContext.jsx';
import { useOptimizer } from '../hooks/useOptimizer';
import { buildMatrixStrings } from '../utils/validation';
import { getComparison, formatDistance, formatPercent } from '../utils/format';

export default function RouteOptimizer() {
  const { warehouse, deliveries, locations, distances, results, clearResults, health } = useApp();
  const { run, loading, error, clearError } = useOptimizer();

  const busy = loading !== null;
  const maxBB = health.maxBB;
  const tooLargeForBB = locations.length > maxBB;
  const ready = warehouse && deliveries.length >= 2;
  const comparison = getComparison(results);

  const stale =
    results &&
    JSON.stringify(results.problem.locations) !== JSON.stringify(locations.map((l) => l.name));

  if (!ready) {
    return (
      <>
        <PageHeader title="Route Optimizer" subtitle="Run Greedy Nearest Neighbour and Branch and Bound on your distance matrix." />
        <EmptyState icon={Route} title="Nothing to optimize yet" action={<Link to="/locations" className="btn btn-primary"><MapPin size={16} /> Add locations</Link>}>
          You need a warehouse and at least two delivery locations, plus all pairwise distances.
        </EmptyState>
      </>
    );
  }

  const names = locations.map((l) => l.name);
  const preview = buildMatrixStrings(locations, distances);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Route Optimizer"
        subtitle="Both algorithms receive exactly the same distance matrix, and every result below is computed by the Flask backend."
      />

      {!health.online && !health.checking && (
        <Alert tone="error" title="Backend not reachable" onClose={health.refresh}>
          {health.error} (Dismiss to re-check.)
        </Alert>
      )}

      <div className="grid gap-4 sm:grid-cols-3">
        <Card className="!p-4">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500"><Warehouse size={14} /> Starting warehouse</div>
          <div className="mt-1 text-lg font-bold text-navy">{warehouse.name}</div>
        </Card>
        <Card className="!p-4">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500"><MapPin size={14} /> Delivery locations</div>
          <div className="mt-1 text-lg font-bold text-navy">{deliveries.length}</div>
        </Card>
        <Card className="!p-4">
          <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500"><Cpu size={14} /> Branch and Bound limit</div>
          <div className="mt-1 text-lg font-bold text-navy">{maxBB} locations</div>
        </Card>
      </div>

      <Card>
        <h2 className="mb-3 text-base font-bold text-navy">Distance matrix preview</h2>
        <MatrixTable names={names} matrix={preview} />
      </Card>

      <Alert tone={tooLargeForBB ? 'warning' : 'info'} title="Why is Branch and Bound limited in size?">
        Branch and Bound is exact, but in the worst case it explores O(n!) routes. Pruning removes most of them in practice, yet
        the running time can still explode as locations are added. To keep the server responsive it is capped at {maxBB} locations
        (warehouse included); this limit is configurable on the backend (<code>MAX_BB_LOCATIONS</code>). Greedy has no such limit.
        {tooLargeForBB && ` You currently have ${locations.length} locations, so only Greedy can run.`}
      </Alert>

      <Card>
        <div className="flex flex-wrap gap-3">
          <button className="btn btn-warning" disabled={busy} onClick={() => run('greedy')}>
            {loading === 'greedy' ? <Spinner /> : <Play size={16} />} Run Greedy
          </button>
          <button className="btn btn-primary" disabled={busy || tooLargeForBB} onClick={() => run('bb')}>
            {loading === 'bb' ? <Spinner /> : <Play size={16} />} Run Branch and Bound
          </button>
          <button className="btn btn-navy" disabled={busy || tooLargeForBB} onClick={() => run('both')}>
            {loading === 'both' ? <Spinner /> : <Zap size={16} />} Run Both Algorithms
          </button>
          <button className="btn btn-secondary" disabled={busy || !results} onClick={() => { clearResults(); clearError(); }}>
            <Eraser size={16} /> Clear results
          </button>
        </div>
        {busy && (
          <p className="mt-3 flex items-center gap-2 text-sm text-slate-600" aria-live="polite">
            <Spinner /> Running {loading === 'greedy' ? 'Greedy' : loading === 'bb' ? 'Branch and Bound' : 'both algorithms'} on the backend…
          </p>
        )}
        {error && <div className="mt-4"><Alert tone="error" title="Could not optimize" onClose={clearError}>{error}</Alert></div>}
      </Card>

      {results && (
        <section className="space-y-4" aria-labelledby="results-heading">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 id="results-heading" className="text-lg font-bold text-navy">Results and route visualization</h2>
            {comparison && (
              <Link to="/comparison" className="btn btn-secondary btn-sm"><Scale size={14} /> Full comparison</Link>
            )}
          </div>

          {stale && (
            <Alert tone="warning">
              These results were computed for a different set of locations than the ones currently defined. Run the algorithms again to refresh.
            </Alert>
          )}

          {comparison && (
            <Alert tone={comparison.greedy_is_optimal ? 'success' : 'info'}>
              {comparison.greedy_is_optimal
                ? `Greedy matched the optimal distance (${formatDistance(results.bb.distance)}) on this instance.`
                : `Branch and Bound saves ${formatDistance(comparison.distance_saved)} distance units (${formatPercent(comparison.improvement_percent)} shorter than Greedy).`}
            </Alert>
          )}

          <div className="grid gap-6 xl:grid-cols-2">
            {results.greedy ? (
              <ResultCard kind="greedy" result={results.greedy} problem={results.problem} />
            ) : (
              <EmptyState icon={Info} title="Greedy not run">Click “Run Greedy” to see its route.</EmptyState>
            )}
            {results.bb ? (
              <ResultCard kind="bb" result={results.bb} problem={results.problem} />
            ) : (
              <EmptyState icon={Info} title="Branch and Bound not run">
                {tooLargeForBB ? `Too many locations (limit ${maxBB}).` : 'Click “Run Branch and Bound” to see the optimal route.'}
              </EmptyState>
            )}
          </div>
        </section>
      )}
    </div>
  );
}
