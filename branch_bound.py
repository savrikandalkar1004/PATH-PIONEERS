"""
Branch and Bound for the Travelling Salesman Problem (exact / optimal).

Search tree
-----------
Each node of the tree is a PARTIAL ROUTE that starts at the warehouse (0).
Branching = extend the partial route by one not-yet-visited location.
A leaf is a complete route; we add the return edge to the warehouse.

Lower bound (the "bound" part)
------------------------------
For a partial route ending at city `c` with cost `g` so far, and U = the set
of unvisited cities, ANY completion of this route has the form

        c -> u1 -> u2 -> ... -> uk -> 0        (u1..uk is a permutation of U)

and its remaining cost is the sum of k+1 edges. Look at the TAIL (starting
city) of each of those edges. The tails are exactly c, u1, ..., uk - all
different, one edge each. So:

  * the edge leaving c goes to some city in U
        -> it costs at least  min_{j in U} d[c][j]
  * the edge leaving u in U goes to some other city in U, or back to 0
        -> it costs at least  min_{v in (U - {u}) + {0}} d[u][v]

Adding these minima gives

    LB = g + min_{j in U} d[c][j] + sum_{u in U} min_{v in (U - {u}) + {0}} d[u][v]

Because every term is a lower bound on a distinct edge of any completion,
    LB <= cost of the best completion.
So LB is ADMISSIBLE: it never overestimates, and the argument does not need
the triangle inequality. If U is empty the only completion is the edge c->0,
so LB = g + d[c][0] is exact.

Pruning rule
------------
Keep the best complete tour found so far (`best_cost`). A branch is cut ONLY
when LB >= best_cost, because then no completion of it can be strictly
better. (A tiny tolerance EPSILON absorbs floating-point rounding.)
Because LB is admissible, pruning never discards a strictly better tour, so
the returned tour is optimal.

Upper bound seed
----------------
By default best_cost starts as the Nearest-Neighbour tour (a real, valid
tour). A good initial upper bound makes pruning effective from the first
node. Set seed_with_greedy=False to start from infinity instead; the answer
(distance) is the same either way.

Branch ordering
---------------
Children are tried cheapest-edge-first (ties: lowest index). This finds good
tours early, which tightens best_cost sooner. Ordering never affects
correctness, only speed.

Complexity
----------
* Worst-case time : O(n!) - if the bound prunes nothing, every permutation of
  the n-1 delivery cities is generated. Each node also costs O(n^2) to bound.
  In practice pruning removes most of the tree, but there is no polynomial
  guarantee.
* Space           : O(n) for the recursion stack (depth <= n) and the
  current path, plus O(n) per stack frame for the unvisited list, so O(n^2)
  worst case in total. The search never stores the whole tree.
"""

from .common import (
    EPSILON,
    InputTooLargeError,
    InvalidInputError,
    route_distance,
    validate_distance_matrix,
)
from .greedy import greedy_nearest_neighbour

# Configurable safety limit: total locations INCLUDING the warehouse.
DEFAULT_MAX_LOCATIONS = 12


def lower_bound(matrix, current, cost_so_far, unvisited):
    """
    Admissible lower bound on the cost of the best tour that extends a
    partial route ending at `current` (cost `cost_so_far`), where `unvisited`
    is the collection of cities not yet on the route. See module docstring.
    """
    if not unvisited:
        return cost_so_far + matrix[current][0]

    bound = cost_so_far
    # Edge leaving the current city must go to an unvisited city.
    bound += min(matrix[current][j] for j in unvisited)
    # Each unvisited city leaves via one edge to another unvisited city or home.
    for u in unvisited:
        cheapest = matrix[u][0]
        for v in unvisited:
            if v != u and matrix[u][v] < cheapest:
                cheapest = matrix[u][v]
        bound += cheapest
    return bound


def branch_and_bound(matrix, max_locations=DEFAULT_MAX_LOCATIONS, seed_with_greedy=True):
    """
    Solve TSP exactly.

    Returns a dict:
        route          : optimal tour as indices, starts and ends with 0
        distance       : its length (the minimum possible)
        nodes_explored : search-tree nodes expanded
        branches_pruned: child branches cut by the lower bound
    Raises InvalidInputError (bad matrix) or InputTooLargeError
    (len(matrix) > max_locations).
    """
    if not isinstance(max_locations, int) or isinstance(max_locations, bool) or max_locations < 1:
        raise InvalidInputError("max_locations must be a positive integer.")
    n = validate_distance_matrix(matrix)
    if n > max_locations:
        raise InputTooLargeError(
            f"Branch and Bound is limited to {max_locations} locations "
            f"(warehouse included); got {n}. Its worst case is O(n!)."
        )

    if seed_with_greedy:
        seed = greedy_nearest_neighbour(matrix)
        best_route, best_cost = seed["route"], seed["distance"]
    else:
        best_route, best_cost = None, float("inf")

    stats = {"explored": 0, "pruned": 0}
    path = [0]

    def explore(current, cost, unvisited):
        nonlocal best_route, best_cost
        stats["explored"] += 1

        if not unvisited:  # complete tour: close it at the warehouse
            total = cost + matrix[current][0]
            if best_route is None or total < best_cost - EPSILON:
                best_cost = total
                best_route = path + [0]
            return

        # cheapest edge first; ties -> lowest index
        for nxt in sorted(unvisited, key=lambda j: (matrix[current][j], j)):
            new_cost = cost + matrix[current][nxt]
            remaining = tuple(u for u in unvisited if u != nxt)
            if lower_bound(matrix, nxt, new_cost, remaining) >= best_cost - EPSILON:
                stats["pruned"] += 1  # cannot beat the best tour: cut
                continue
            path.append(nxt)
            explore(nxt, new_cost, remaining)
            path.pop()

    explore(0, 0, tuple(range(1, n)))

    return {
        "route": best_route,
        # recompute from the route so the reported distance is always consistent
        "distance": route_distance(matrix, best_route),
        "nodes_explored": stats["explored"],
        "branches_pruned": stats["pruned"],
    }
