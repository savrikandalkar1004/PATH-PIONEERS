"""
REST endpoints for Path Pioneers.

    GET  /api/health
    POST /api/optimize/greedy
    POST /api/optimize/branch-bound
    POST /api/optimize/compare
    POST /api/performance/test

Every number returned here is computed by the algorithms at request time.
Execution times are measured with time.perf_counter().

HTTP status codes used
    200 success
    400 malformed JSON / malformed matrix / bad field
    413 request body too large
    422 well-formed input that is too big for the algorithm
"""

import random
import statistics
import time

from flask import Blueprint, current_app, jsonify, request

from algorithms.branch_bound import DEFAULT_MAX_LOCATIONS, branch_and_bound
from algorithms.common import InputTooLargeError, InvalidInputError, validate_distance_matrix
from algorithms.greedy import greedy_nearest_neighbour

optimizer_bp = Blueprint("optimizer", __name__, url_prefix="/api")

MAX_GREEDY_LOCATIONS = 500          # Greedy is O(n^2); this keeps requests fast
MAX_PERFORMANCE_SIZES = 15          # how many input sizes one performance test may contain
MAX_REPEATS = 10
HARD_MAX_BB = 14                    # absolute ceiling, even if configured higher


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def error(message, status=400):
    return jsonify({"error": message}), status


def bb_limit():
    """Configured Branch-and-Bound size limit (warehouse included)."""
    return min(current_app.config.get("MAX_BB_LOCATIONS", DEFAULT_MAX_LOCATIONS), HARD_MAX_BB)


def parse_problem():
    """
    Read and validate {"locations": [...], "distance_matrix": [[...]]}.
    Returns (names, matrix). Raises InvalidInputError / InputTooLargeError.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        raise InvalidInputError("Request body must be a JSON object.")

    names = body.get("locations")
    matrix = body.get("distance_matrix")
    if not isinstance(names, list) or not names:
        raise InvalidInputError("'locations' must be a non-empty list (warehouse first).")
    if matrix is None:
        raise InvalidInputError("'distance_matrix' is required.")

    cleaned = []
    for i, name in enumerate(names):
        if not isinstance(name, str) or not name.strip():
            raise InvalidInputError(f"Location {i + 1} has an empty or invalid name.")
        cleaned.append(name.strip())
    if len({n.lower() for n in cleaned}) != len(cleaned):
        raise InvalidInputError("Location names must be unique.")

    n = validate_distance_matrix(matrix)
    if n != len(cleaned):
        raise InvalidInputError(
            f"'locations' has {len(cleaned)} entries but the matrix is {n}x{n}."
        )
    if n > MAX_GREEDY_LOCATIONS:
        raise InputTooLargeError(f"At most {MAX_GREEDY_LOCATIONS} locations are supported.")
    return cleaned, matrix


def timed(fn, *args, **kwargs):
    """Run fn and return (result, elapsed_seconds) using perf_counter."""
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    return result, time.perf_counter() - start


def format_result(names, result, seconds):
    out = {
        "route": [names[i] for i in result["route"]],
        "route_indices": result["route"],
        "distance": result["distance"],
        "execution_time": seconds,                 # seconds
        "execution_time_ms": seconds * 1000.0,
        "locations_visited": len(result["route"]) - 1,
    }
    for key in ("nodes_explored", "branches_pruned"):
        if key in result:
            out[key] = result[key]
    return out


def improvement_percent(greedy_distance, optimal_distance):
    """((Greedy - Optimal) / Greedy) * 100, safe when Greedy == 0."""
    if greedy_distance == 0:
        return 0.0
    return (greedy_distance - optimal_distance) / greedy_distance * 100.0


def run_greedy(names, matrix):
    result, secs = timed(greedy_nearest_neighbour, matrix)
    return format_result(names, result, secs)


def run_bb(names, matrix):
    result, secs = timed(branch_and_bound, matrix, max_locations=bb_limit())
    return format_result(names, result, secs)


# --------------------------------------------------------------------------
# Endpoints
# --------------------------------------------------------------------------
@optimizer_bp.get("/health")
def health():
    return jsonify(
        {
            "status": "ok",
            "max_branch_bound_locations": bb_limit(),
            "max_locations": MAX_GREEDY_LOCATIONS,
        }
    )


@optimizer_bp.post("/optimize/greedy")
def optimize_greedy():
    names, matrix = parse_problem()
    return jsonify({"greedy": run_greedy(names, matrix)})


@optimizer_bp.post("/optimize/branch-bound")
def optimize_branch_bound():
    names, matrix = parse_problem()
    return jsonify({"branch_and_bound": run_bb(names, matrix)})


@optimizer_bp.post("/optimize/compare")
def optimize_compare():
    names, matrix = parse_problem()
    greedy = run_greedy(names, matrix)
    bb = run_bb(names, matrix)   # raises InputTooLargeError -> 422 if too big
    saved = greedy["distance"] - bb["distance"]
    return jsonify(
        {
            "greedy": greedy,
            "branch_and_bound": bb,
            "comparison": {
                "distance_saved": saved,
                "improvement_percent": improvement_percent(greedy["distance"], bb["distance"]),
                "greedy_is_optimal": saved <= 1e-9,
                "same_route": greedy["route_indices"] == bb["route_indices"],
            },
        }
    )


@optimizer_bp.post("/performance/test")
def performance_test():
    """
    Body: {"sizes": [4,5,6,...],   # numbers of DELIVERY locations
           "repeats": 5,            # runs per size; the MEDIAN time is reported
           "seed": 42}              # optional; makes the random test matrices reproducible

    For each size a random symmetric matrix (integer distances 1-100) is
    generated as TEST INPUT; the algorithms then run on it and the reported
    distances and times are real measurements, never invented.
    Branch and Bound is skipped (and reported as skipped) when the instance
    exceeds the configured limit.
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return error("Request body must be a JSON object.")

    sizes = body.get("sizes")
    repeats = body.get("repeats", 5)
    seed = body.get("seed")

    if not isinstance(sizes, list) or not sizes or len(sizes) > MAX_PERFORMANCE_SIZES:
        return error(f"'sizes' must be a list of 1-{MAX_PERFORMANCE_SIZES} integers.")
    if not all(isinstance(s, int) and not isinstance(s, bool) and 1 <= s < MAX_GREEDY_LOCATIONS for s in sizes):
        return error(f"Each size (delivery locations) must be an integer from 1 to {MAX_GREEDY_LOCATIONS - 1}.")
    if not isinstance(repeats, int) or isinstance(repeats, bool) or not 1 <= repeats <= MAX_REPEATS:
        return error(f"'repeats' must be an integer from 1 to {MAX_REPEATS}.")
    if seed is not None and (not isinstance(seed, int) or isinstance(seed, bool)):
        return error("'seed' must be an integer.")

    rng = random.Random(seed)
    results = []
    for deliveries in sorted(set(sizes)):
        n = deliveries + 1                      # + warehouse
        matrix = [[0] * n for _ in range(n)]
        for i in range(n):
            for j in range(i + 1, n):
                matrix[i][j] = matrix[j][i] = rng.randint(1, 100)

        greedy_times, greedy_result = [], None
        for _ in range(repeats):
            greedy_result, secs = timed(greedy_nearest_neighbour, matrix)
            greedy_times.append(secs)

        row = {
            "delivery_locations": deliveries,
            "total_locations": n,
            "greedy": {
                "distance": greedy_result["distance"],
                "median_time_ms": statistics.median(greedy_times) * 1000.0,
                "runs": repeats,
            },
            "branch_and_bound": None,
            "branch_and_bound_skipped": False,
        }

        if n <= bb_limit():
            bb_times, bb_result = [], None
            for _ in range(repeats):
                bb_result, secs = timed(branch_and_bound, matrix, max_locations=bb_limit())
                bb_times.append(secs)
            row["branch_and_bound"] = {
                "distance": bb_result["distance"],
                "median_time_ms": statistics.median(bb_times) * 1000.0,
                "runs": repeats,
                "nodes_explored": bb_result["nodes_explored"],
                "branches_pruned": bb_result["branches_pruned"],
            }
            row["improvement_percent"] = improvement_percent(
                greedy_result["distance"], bb_result["distance"]
            )
        else:
            row["branch_and_bound_skipped"] = True
        results.append(row)

    return jsonify(
        {
            "results": results,
            "repeats": repeats,
            "seed": seed,
            "max_branch_bound_locations": bb_limit(),
            "note": "Times are the median of the repeated runs on this machine; "
                    "they depend on hardware and the Python implementation.",
        }
    )
