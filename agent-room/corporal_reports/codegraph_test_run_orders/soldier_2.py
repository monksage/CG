import numpy as np
from scipy.optimize import curve_fit
from scipy.spatial.distance import cosine


def compare_lane_intensities(lane_ids: list[int], marker_kb: int = 100) -> dict:
    """
    Compare background-corrected intensity profiles of multiple gel lanes.

    Uses marker regression to convert pixel positions to fragment lengths,
    then returns per-lane peak fragment lengths and a pairwise similarity matrix.

    Parameters
    ----------
    lane_ids : list[int]
        IDs of lanes to compare (must match keys in road data).
    marker_kb : int
        Marker ladder to use for regression: 100 or 1000.

    Returns
    -------
    dict with keys:
        "peak_fragment_lengths": dict[int, float | None]
            Per-lane fragment length (bp) at peak intensity.
            None if the lane has no signal in the calibrated window.
        "similarity_matrix": dict[tuple[int, int], float]
            Pairwise cosine similarity (0–1) between background-corrected,
            rescaled intensity profiles. Keys are sorted (i, j) pairs.
    """
    data = InitAllData()

    # --- load marker and calibrate regression ---
    r_mark, l_mark, mono_mark, bands = data.init_markers(with_bands=True)

    if marker_kb == 100:
        ladder = global_paths.mark100
    elif marker_kb == 1000:
        ladder = global_paths.mark1000
    else:
        raise ValueError(f"marker_kb must be 100 or 1000, got {marker_kb}")

    koef = max(ladder)
    norm_fragment_len = [i / koef for i in ladder]
    norm_bands_cords = [i / koef for i in sorted(bands)]

    def func_exp(x, a, b):
        return a / x + b

    popt, _ = curve_fit(func_exp, norm_bands_cords, norm_fragment_len, p0=(-1, 0.01))

    def pixel_to_bp(pixel_index, profile_len):
        x = pixel_index / koef
        val = func_exp(x, *popt) * koef
        return val if val < 10000 else None

    # --- build rescale array (one entry per pixel in a profile) ---
    # Profile length is determined from the marker monoline length as reference.
    # Each lane may differ; rescaling is applied per-lane using its own length.

    # --- load all road data and apply background subtraction ---
    borders, monos = data.init_roads()

    lane_profiles = {}
    for lid in lane_ids:
        key = str(lid)
        if key not in monos:
            raise KeyError(f"Lane id {lid} not found in road data.")
        mono = monos[key].copy() if isinstance(monos[key], np.ndarray) else list(monos[key])
        b_max = max(borders[key])
        b_min = min(borders[key])
        mono = data.del_close_bg(b_max, b_min, mono)
        lane_profiles[lid] = np.asarray(mono, dtype=float)

    # --- build per-lane rescale arrays and aligned intensity vectors ---
    # We align all lanes onto a common bp grid by resampling.
    BP_MIN = 50
    BP_MAX = 1000 if marker_kb == 100 else 10000

    def make_rescale(profile_len):
        rescale = []
        for idx in range(profile_len):
            bp = pixel_to_bp(idx, profile_len)
            if bp is not None and BP_MIN <= bp <= BP_MAX:
                rescale.append(bp)
            else:
                rescale.append(None)
        return rescale

    # Build aligned profiles: intensity at each pixel where rescale is valid
    aligned = {}
    peak_fragment_lengths = {}

    for lid, profile in lane_profiles.items():
        rescale = make_rescale(len(profile))
        valid_bp = []
        valid_intensity = []
        for idx, bp in enumerate(rescale):
            if bp is not None:
                valid_bp.append(bp)
                valid_intensity.append(profile[idx])

        if not valid_intensity:
            peak_fragment_lengths[lid] = None
            aligned[lid] = np.array([])
        else:
            valid_intensity = np.asarray(valid_intensity)
            peak_idx = int(np.argmax(valid_intensity))
            peak_fragment_lengths[lid] = valid_bp[peak_idx]
            aligned[lid] = valid_intensity

    # --- pairwise cosine similarity ---
    # Pad/trim vectors to the same length (shortest common length).
    ids = list(lane_ids)
    similarity_matrix = {}

    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            a = aligned[ids[i]]
            b = aligned[ids[j]]
            if len(a) == 0 or len(b) == 0:
                sim = 0.0
            else:
                min_len = min(len(a), len(b))
                a_trim = a[:min_len]
                b_trim = b[:min_len]
                norm_a = np.linalg.norm(a_trim)
                norm_b = np.linalg.norm(b_trim)
                if norm_a == 0 or norm_b == 0:
                    sim = 0.0
                else:
                    sim = float(np.dot(a_trim, b_trim) / (norm_a * norm_b))
            key = (ids[i], ids[j])
            similarity_matrix[key] = sim

    return {
        "peak_fragment_lengths": peak_fragment_lengths,
        "similarity_matrix": similarity_matrix,
    }
