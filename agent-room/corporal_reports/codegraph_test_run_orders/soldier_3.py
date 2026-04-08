import numpy as np
from scipy.optimize import curve_fit
from scipy.stats import pearsonr


def compare_lane_intensities(lane_ids: list[int], marker_kb: int = 100) -> dict:
    """
    Compare background-corrected intensity profiles of multiple gel lanes.

    Loads road lanes, applies background subtraction (del_close_bg), then uses
    the marker regression (exponential fit of pixel position vs known fragment
    length) to convert each pixel to bp. Returns per-lane peak fragment lengths
    and a pairwise Pearson r similarity matrix computed on the shared bp axis.

    Parameters
    ----------
    lane_ids : list[int]
        IDs of the lanes to compare (correspond to road keys).
    marker_kb : int
        Marker ladder to use for regression calibration: 100 or 1000.

    Returns
    -------
    dict with keys:
        "peak_fragment_lengths" : dict[int, float | None]
            Fragment length in bp at the intensity peak for each lane.
            None if the lane is missing or has no valid calibrated region.
        "similarity_matrix" : dict[tuple[int, int], float | None]
            Pearson r between every pair of lanes (including self-pairs = 1.0).
            Keys are sorted (min_id, max_id) tuples. None if a lane is invalid.
    """
    data = InitAllData()

    # ------------------------------------------------------------------
    # 1. Load marker and build pixel-to-bp regression
    # ------------------------------------------------------------------
    r_mark, l_mark, mono_mark, bands = data.init_markers(with_bands=True)

    # Select the correct ladder fragment-length array.
    if marker_kb == 100:
        ladder = list(global_paths.mark100)
    elif marker_kb == 1000:
        ladder = list(global_paths.mark1000)
    else:
        raise ValueError(f"marker_kb must be 100 or 1000, got {marker_kb}")

    # bands and ladder are co-indexed (band pixel positions vs known bp values).
    # Sort both together by ascending pixel position so the fit is monotone.
    paired = sorted(zip(bands, ladder), key=lambda t: t[0])
    sorted_pixels = np.array([t[0] for t in paired], dtype=float)
    sorted_bp     = np.array([t[1] for t in paired], dtype=float)

    # Normalise by their respective maxima to keep curve_fit well-conditioned.
    px_max = float(sorted_pixels.max())
    bp_max = float(sorted_bp.max())
    norm_px = sorted_pixels / px_max
    norm_bp = sorted_bp     / bp_max

    def _exp_model(x, a, b):
        return a / x + b

    popt, _ = curve_fit(_exp_model, norm_px, norm_bp, p0=(-1.0, 0.01))

    def pixel_to_bp(px: float) -> float | None:
        """Convert a pixel index to fragment length in bp; None if out of range."""
        if px <= 0:
            return None
        bp = _exp_model(px / px_max, *popt) * bp_max
        return float(bp) if 50 <= bp <= bp_max else None

    # ------------------------------------------------------------------
    # 2. Load road data and apply background subtraction per lane
    # ------------------------------------------------------------------
    borders, monos = data.init_roads()

    lane_profiles: dict[int, np.ndarray | None] = {}
    for lid in lane_ids:
        key = str(lid)
        if key not in monos or key not in borders or len(borders[key]) < 2:
            lane_profiles[lid] = None
            continue
        raw = list(monos[key]) if not isinstance(monos[key], list) else monos[key][:]
        b_min = min(borders[key])
        b_max = max(borders[key])
        corrected = data.del_close_bg(b_max, b_min, raw)
        lane_profiles[lid] = np.asarray(corrected, dtype=float)

    # ------------------------------------------------------------------
    # 3. Convert each lane to a common bp axis via interpolation
    # ------------------------------------------------------------------
    # Determine the shared bp grid: evenly spaced from 50 bp to bp_max.
    N_GRID = 500
    bp_grid = np.linspace(50.0, bp_max, N_GRID)

    def resample_to_grid(profile: np.ndarray) -> np.ndarray | None:
        """
        Build a (pixel_index -> bp) map for this profile, then interpolate
        the intensity values onto the shared bp_grid.
        """
        n = len(profile)
        if n == 0:
            return None

        # Pixel indices run 0..n-1; pixel_to_bp uses the marker-calibrated scale.
        px_bp   = []
        px_int  = []
        for idx in range(n):
            bp = pixel_to_bp(float(idx))
            if bp is not None:
                px_bp.append(bp)
                px_int.append(profile[idx])

        if len(px_bp) < 2:
            return None

        px_bp_arr  = np.array(px_bp)
        px_int_arr = np.array(px_int)

        # Sort by bp (ascending) to prepare for interpolation.
        order = np.argsort(px_bp_arr)
        px_bp_arr  = px_bp_arr[order]
        px_int_arr = px_int_arr[order]

        return np.interp(bp_grid, px_bp_arr, px_int_arr,
                         left=0.0, right=0.0)

    resampled: dict[int, np.ndarray | None] = {}
    for lid, profile in lane_profiles.items():
        if profile is None:
            resampled[lid] = None
        else:
            resampled[lid] = resample_to_grid(profile)

    # ------------------------------------------------------------------
    # 4. Peak fragment lengths
    # ------------------------------------------------------------------
    peak_fragment_lengths: dict[int, float | None] = {}
    for lid, grid_profile in resampled.items():
        if grid_profile is None or grid_profile.max() == 0:
            peak_fragment_lengths[lid] = None
        else:
            peak_fragment_lengths[lid] = float(bp_grid[int(np.argmax(grid_profile))])

    # ------------------------------------------------------------------
    # 5. Pairwise Pearson r similarity matrix
    # ------------------------------------------------------------------
    similarity_matrix: dict[tuple[int, int], float | None] = {}

    for i in range(len(lane_ids)):
        for j in range(i, len(lane_ids)):
            a_id = lane_ids[i]
            b_id = lane_ids[j]
            key = (min(a_id, b_id), max(a_id, b_id))

            if a_id == b_id:
                similarity_matrix[key] = 1.0
                continue

            va = resampled.get(a_id)
            vb = resampled.get(b_id)

            if va is None or vb is None:
                similarity_matrix[key] = None
                continue

            if np.std(va) == 0 or np.std(vb) == 0:
                # Flat profile — correlation undefined; treat as 0.
                similarity_matrix[key] = 0.0
                continue

            r_val, _ = pearsonr(va, vb)
            similarity_matrix[key] = float(r_val)

    return {
        "peak_fragment_lengths": peak_fragment_lengths,
        "similarity_matrix": similarity_matrix,
    }
