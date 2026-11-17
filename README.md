# PATH PIONEERS – Delivery Route and Cost Optimizer

> *Smarter Routes. Shorter Distances. Better Deliveries.*

A full-stack web application for the **Design and Analysis of Algorithms (DAA)** course.
It solves the **Travelling Salesman Problem (TSP)** for a delivery vehicle with two algorithms,
**Greedy Nearest Neighbour** and **Branch and Bound**, and compares them on distance, optimality and measured running time.

---

## 1. Introduction

A delivery company has one vehicle and one warehouse. The vehicle must deliver to several locations and come back.
Visiting them in a careless order wastes distance (and fuel and time). Path Pioneers lets you enter the
locations and the distances between them, runs both algorithms on a Python/Flask backend, and shows the routes,
distances and timings in a React dashboard.

## 2. Problem statement

Given a warehouse and *n − 1* delivery locations with a symmetric, non-negative distance matrix `d`,
find the shortest tour that starts at the warehouse, visits every delivery location **exactly once**, and returns to the warehouse.

Assumptions: one vehicle · start = end = warehouse (index 0) · `d[i][j] = d[j][i] ≥ 0` · `d[i][i] = 0` ·
distances are **manually entered** (they are not real map distances).

## 3. Objectives

1. Implement TSP heuristics and exact search **from scratch** (no TSP libraries).
2. Show that a fast heuristic (Greedy) can be suboptimal while Branch and Bound is provably optimal.
3. Measure real running times and relate them to the theoretical complexity (O(n²) vs O(n!)).
4. Present everything in a professional, usable logistics dashboard.

## 4. Features

- **Manage locations**: add/rename/delete a warehouse and deliveries, unique names, validation.
- **Dynamic symmetric distance matrix**: editing A→B updates B→A, diagonal fixed at 0, non-negative only, reset, two sample datasets.
- **Route optimizer**: run Greedy, Branch and Bound, or both; loading states; configurable Branch and Bound size limit explained in the UI.
- **Results & visualization**: route sequence, distance, execution time, locations visited, SVG route graph with arrows (Greedy = orange dashed, Branch and Bound = blue solid).
- **Algorithm comparison**: improvement %, optimality, complexity, bar charts.
- **Performance analysis**: repeated runs for chosen sizes, **median** times, line charts, table, complexity explanation.
- **Backend validation** with proper HTTP status codes and JSON errors; **40 automated tests**.

## 5. Technology stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, Tailwind CSS 3, React Router, Lucide icons, Chart.js (react-chartjs-2) |
| Backend | Python 3.10+, Flask, Flask-CORS |
| Algorithms | Pure Python (`backend/algorithms/`) |
| Storage | None. Inputs/results are kept in React state for the session |

## 6. The Travelling Salesman Problem

TSP asks for the cheapest round trip through a set of cities. With *n* locations there are *(n − 1)!* possible tours
from a fixed start (the warehouse). For 10 locations that is 362,880 tours; for 20 it is about 1.2 × 10¹⁷.
TSP is **NP-hard**: no polynomial-time algorithm is known that solves every instance exactly. So we have two options:
a fast but approximate heuristic (Greedy), or an exact algorithm that is exponential in the worst case (Branch and Bound).

## 7. Greedy Nearest Neighbour

"Always drive to the closest place you have not visited yet."

1. Start at the warehouse; mark it visited.
2. Move to the nearest unvisited location (ties: lowest index).
3. Repeat until all are visited.
4. Return to the warehouse.

It is quick, but short-sighted: a cheap early move can force a very long move later. Example in the tests (4 locations):
Greedy gives **37**, the optimum is **35**.

## 8. Branch and Bound

**Branching.** Each search node is a *partial route* from the warehouse. Its children extend the route by one unvisited location.

**Bounding.** For a partial route ending at city `c` with cost `g` so far and unvisited set `U`, every completion looks like
`c → u1 → … → uk → warehouse`. Each city that starts one of those edges (`c` and every `u` in `U`) contributes exactly one edge, so

```
LB = g
   + min over j in U of d[c][j]                          (edge leaving c)
   + sum over u in U of  min over v in (U − {u}) ∪ {0} of d[u][v]   (edge leaving each unvisited u)
```

Each term is a lower bound on a *different* edge of any completion, therefore **LB ≤ cost of the best completion**
(the bound is *admissible*). It needs no triangle inequality.

**Pruning.** If `LB ≥ best` (the best complete tour found so far) the branch cannot produce a strictly better tour and is discarded.
Because LB never overestimates, pruning never throws away a better tour, so the result is **guaranteed optimal**.

**Engineering choices** (they change speed, not correctness): the search starts with the Greedy tour as the initial upper bound,
and tries the cheapest edge first so good tours are found early.

## 9. Pseudocode

```
GREEDY(d, n):
    visited[0..n-1] = false;  visited[0] = true
    route = [0];  cur = 0
    repeat n-1 times:
        nxt = unvisited j with smallest d[cur][j]   (ties -> lowest j)
        visited[nxt] = true;  route.append(nxt);  cur = nxt
    route.append(0)
    return route, length(route)
```

```
BRANCH_AND_BOUND(d, n):
    best = GREEDY(d, n)                 # valid tour => valid upper bound
    EXPLORE(cur = 0, cost = 0, U = {1..n-1}, path = [0])

EXPLORE(cur, cost, U, path):
    if U is empty:
        total = cost + d[cur][0]
        if total < best.cost: best = (path + [0], total)
        return
    for nxt in U sorted by d[cur][nxt]:
        newCost = cost + d[cur][nxt]
        if LOWER_BOUND(nxt, newCost, U - {nxt}) >= best.cost:
            continue                    # prune
        EXPLORE(nxt, newCost, U - {nxt}, path + [nxt])
```

## 10. Time and space complexity

| | Time | Space | Optimal? |
|---|---|---|---|
| Greedy | **O(n²)** (n−1 steps × scan of n) | **O(n)** | No |
| Branch and Bound | **O(n!)** worst case (each node also costs O(n²) to bound) | **O(n²)**: recursion depth ≤ n, each level holds an O(n) unvisited list; the tree is never stored | Yes |

In practice pruning removes most of the tree (see section 14), but there is no polynomial guarantee, hence the size limit
(default **12 locations including the warehouse**, set with the `MAX_BB_LOCATIONS` environment variable on the backend).

## 11. System architecture

```
┌──────────────────────────┐   JSON / REST    ┌────────────────────────────────────┐
│ React + Tailwind (Vite)  │ ───────────────▶ │ Flask  (backend/app.py)            │
│  pages · components      │                  │   routes/optimizer.py  (validation, │
│  state: AppContext       │ ◀─────────────── │   timing with perf_counter)         │
│  charts · SVG graph      │                  │        │                            │
└──────────────────────────┘                  │        ▼                            │
        :5173                                 │ algorithms/greedy.py                │
                                              │ algorithms/branch_bound.py          │
                                              │ algorithms/common.py (validation)   │
                                              └────────────────────────────────────┘
                                                              :5000
```

```
Path-Pioneers/
├── backend/
│   ├── algorithms/  greedy.py · branch_bound.py · common.py
│   ├── routes/      optimizer.py
│   ├── tests/       test_algorithms.py · test_api.py
│   ├── app.py · requirements.txt
├── frontend/
│   ├── src/ components · pages · layouts · services · hooks · context · utils
│   ├── package.json · vite.config.js · tailwind.config.js
└── README.md
```

## 12. API documentation

Base URL: `http://127.0.0.1:5000`. All bodies are JSON. Errors look like `{"error": "message"}`.

**Problem input** (used by the three optimize endpoints):

```json
{
  "locations": ["Warehouse", "A", "B", "C"],
  "distance_matrix": [[0,10,15,20],[10,0,35,25],[15,35,0,30],[20,25,30,0]]
}
```

`locations[0]` is the warehouse. Names must be unique, non-empty strings. The matrix must be square, numeric, finite,
non-negative, symmetric, with a zero diagonal, and the same size as `locations`.

| Method & path | Purpose |
|---|---|
| `GET /api/health` | `{"status":"ok","max_branch_bound_locations":12,"max_locations":500}` |
| `POST /api/optimize/greedy` | Returns `{"greedy": {...}}` |
| `POST /api/optimize/branch-bound` | Returns `{"branch_and_bound": {...}}` |
| `POST /api/optimize/compare` | Returns both results plus a `comparison` object |
| `POST /api/performance/test` | Body `{"sizes":[4,6,8], "repeats":5, "seed":42}` (sizes = delivery locations) |

A result object:

```json
{
  "route": ["Warehouse","A","C","B","Warehouse"],
  "route_indices": [0,1,3,2,0],
  "distance": 80,
  "execution_time": 0.000018,
  "execution_time_ms": 0.018,
  "locations_visited": 4,
  "nodes_explored": 9,
  "branches_pruned": 13
}
```

(`nodes_explored` / `branches_pruned` appear for Branch and Bound only.) `comparison` contains
`distance_saved`, `improvement_percent` = ((Greedy − Optimal) / Greedy) × 100 (0 when Greedy is 0), `greedy_is_optimal`, `same_route`.

| Status | Meaning |
|---|---|
| 200 | Success |
| 400 | Malformed JSON, matrix or parameters |
| 404 / 405 | Unknown endpoint / wrong method (JSON body) |
| 413 | Request body larger than 1 MB |
| 422 | Valid input but too large (Branch and Bound limit, or > 500 locations) |
| 500 | Unexpected server error |

CORS is enabled for `http://localhost:5173` and `http://127.0.0.1:5173` (override with `CORS_ORIGINS`, comma-separated).

## 13. Installation, running and testing

### Prerequisites
Python 3.10+, Node.js 18+ and npm.

### Backend (terminal 1)

```bash
cd backend
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                     # http://127.0.0.1:5000
```

Optional: `MAX_BB_LOCATIONS=11 python app.py` changes the Branch and Bound limit (hard ceiling: 14).

### Frontend (terminal 2)

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

If the backend is not on port 5000, copy `.env.example` to `.env` and set `VITE_API_URL`.

### How and where to test

**A. Automated tests (run in `backend/`, no server needed)**

```bash
cd backend
python -m unittest discover -s tests -t . -v      # 40 tests
```

- `tests/test_algorithms.py` tests both algorithms directly. Branch and Bound is checked against a brute-force oracle on hundreds of random instances.
- `tests/test_api.py` tests every endpoint with Flask's test client (status codes, validation, size limits).

Run one file: `python -m unittest tests.test_algorithms -v`.

**B. Test the API by hand** (backend running):

```bash
curl http://127.0.0.1:5000/api/health

curl -X POST http://127.0.0.1:5000/api/optimize/compare \
  -H "Content-Type: application/json" \
  -d '{"locations":["Warehouse","A","B","C","D"],
       "distance_matrix":[[0,16,14,2,3],[16,0,18,19,11],[14,18,0,11,12],[2,19,11,0,20],[3,11,12,20,0]]}'
# -> greedy 52, branch_and_bound 45, improvement 13.46 %
```

**C. Test the whole app in the browser** (both servers running, open http://localhost:5173)

1. Dashboard → **Load demo data** (5 locations where Greedy fails) → you land on *Route Optimizer*.
2. Click **Run Both Algorithms** → Greedy 52, Branch and Bound 45, two route graphs.
3. *Algorithm Comparison* → improvement 13.46 %, charts, complexity table.
4. *Distance Matrix* → change a value (the mirrored cell updates), clear one (optimizing now shows a validation error), type a negative number (cell turns red).
5. *Manage Locations* → try a duplicate name and an empty name (both rejected); rename and delete a location.
6. Add 12 delivery locations → Branch and Bound buttons disable and the limit is explained; Greedy still runs.
7. *Performance Analysis* → run the default sizes, then the preset that goes past the limit (Branch and Bound rows show "Skipped").
8. Stop the backend and click Run → a clear "cannot reach the backend" message appears.

## 14. Testing results

Automated tests: **40 passed** (24 algorithm tests + 16 API tests).

| Requirement | Result |
|---|---|
| 4, 5 and 6 locations | Correct, equal to brute force |
| Greedy non-optimal | 4 locations: Greedy 37 vs optimal 35; 5 locations: 52 vs 45 |
| Both algorithms equal | Brief matrix: both 80 |
| Equal distances / all zeros | Correct (n × d, and 0) |
| Routes valid | Start and end at the warehouse, every location exactly once, distance recomputed from the route |
| Branch and Bound ≤ Greedy | Holds on every instance tested |
| Optimality | Matches brute force on 300 random instances (n = 1–8, with ties) and 100 non-metric instances |
| Lower bound admissible | Never exceeds the true best completion over 150 random partial routes |
| Real pruning | At n = 10 it explores under 10 % of the nodes of the full tree |
| Invalid input | 13 malformed matrix kinds rejected by both algorithms; API returns 400 / 422 |

Example measured scaling (random matrices, one machine, median of 3 runs, seed 42 via `/api/performance/test`;
your numbers will differ):

| Deliveries | Greedy distance | Greedy time | B&B distance | B&B time |
|---|---|---|---|---|
| 4 | 98 | 0.008 ms | 98 | 0.03 ms |
| 8 | 270 | 0.017 ms | 145 | 0.48 ms |
| 11 | 256 | 0.027 ms | 211 | 22 ms |

Note how Greedy's time barely moves while Branch and Bound's grows steeply, and how Greedy can be far from optimal (270 vs 145).

## 15. Limitations and future scope

- Branch and Bound is capped (default 12 locations) because of its O(n!) worst case.
- Distances are entered by hand; the route graph is schematic, not a map.
- One vehicle, symmetric distances; no time windows, capacities or traffic.
- Timings depend on hardware, Python, and the instance (pruning is data-dependent).
- Future work: real map distances, stronger bounds (reduced cost matrix / 1-trees / Held-Karp), a dynamic-programming (Held-Karp) comparison,
  2-opt improvement for Greedy, multiple vehicles, saving projects, CSV import/export.
