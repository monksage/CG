def compare_lane_intensities(lane_ids: list[int], marker_kb: int = 100) -> dict:
    """
    Compare background-corrected intensity profiles of multiple gel lanes.

    Uses the marker ladder regression to convert pixel positions to fragment
    lengths, then returns per-lane peak fragment lengths and a pairwise
    Pearson-correlation similarity matrix computed on the shared fragment-length
    scale.

    Parameters
    ----------
    lane_ids : list[int]
        Lane identifiers to compare.  Each must be present in the road data.
    marker_kb : int
        Marker ladder size in kb used for regression normalisation (default 100).

    Returns
    -------
    dict with two keys:
        "peak_fragment_lengths" : dict[int, float | None]
            Fragment length (bp) at the intensity peak for each lane, derived
            from the marker regression.  None when the lane has no valid
            calibrated pixels or could not be loaded.
        "similarity_matrix" : dict[tuple[int, int], float | None]
            Pairwise Pearson r between background-corrected intensity profiles
            on the shared calibrated pixel range.  Keys are sorted (i, j) tuples
            so (a, b) == (b, a).  None when at least one lane in the pair is
            unavailable or the profiles are constant.
    """
    import numpy as np
    from scipy.stats import pearsonr

    # ------------------------------------------------------------------
    # 1. Load marker data and build the regression-based fragment-length
    #    scale (pixel index -> bp).
    # ------------------------------------------------------------------
    marker = load_marker_data(with_bands=True)
    r_mark = marker["r"]
    l_mark = marker["l"]
    mono_mark = marker["mono"]        # np.ndarray — marker monoline
    bands = marker["bands"]           # np.ndarray of band pixel positions

    # Normalise the ladder: populates norm_fragment_len and norm_bands_cords
    # on this call's implicit self (the module-level regression object).
    band_cords = sorted(int(b) for b in bands)
    normalize_marker_ladder(band_cords=band_cords, kb=marker_kb)

    # ------------------------------------------------------------------
    # 2. Load lane road data.
    # ------------------------------------------------------------------
    road = load_road_data()
    borders = road["borders"]   # dict[str, border info with l/r pixel coords]
    monos = road["monos"]       # dict[str, np.ndarray] raw monoline per lane

    # ------------------------------------------------------------------
    # 3. Background-correct each requested lane.
    # ------------------------------------------------------------------
    corrected: dict[int, list[float] | None] = {}
    for lane_id in lane_ids:
        key = str(lane_id)
        if key not in monos or key not in borders:
            corrected[lane_id] = None
            continue
        border = borders[key]
        r_lane = int(max(border["l"], border["r"]) if isinstance(border, dict)
                     else max(border))
        l_lane = int(min(border["l"], border["r"]) if isinstance(border, dict)
                     else min(border))
        raw_mono = list(monos[key])
        result = subtract_nearby_background(r=r_lane, l=l_lane, monoline=raw_mono)
        corrected[lane_id] = result["monoline"]

    # ------------------------------------------------------------------
    # 4. Build a common pixel range valid for calibration.
    #
    #    norm_fragment_len  — normalised bp values (len == len(band_cords))
    #    norm_bands_cords   — normalised pixel positions for the bands
    #
    #    We derive a pixel-to-bp mapping by fitting the same exponential used
    #    by normalize_marker_ladder and rescaling by marker_kb so that output
    #    values are in base-pairs.
    #
    #    The marker monoline defines the reference pixel axis length.
    # ------------------------------------------------------------------
    from scipy.optimize import curve_fit

    norm_cords = [c / marker_kb for c in band_cords]
    norm_frags = [f / marker_kb for f in band_cords]  # placeholder until
    # normalize_marker_ladder exposes its outputs; reconstruct from raw ladder.

    # Reconstruct normalised ladder values from the known marker_kb sizes.
    # Standard gel ladders: 100 bp ladder uses multiples of 100; here we use
    # the band pixel positions as the x-axis and fit bp = f(pixel).
    # norm_bands_cords = [c / max(band_cords) for c in band_cords]
    # norm_fragment_len = [bp_val / max_bp for bp_val in known_bp_values]
    # Because the known bp values are not passed directly, we use the contract:
    # normalize_marker_ladder accepts band_cords (pixel positions) and kb (scalar
    # fragment length represented by those cords), so it maps each position to a
    # fragment-length proportional to kb.  We approximate the pixel->bp curve by
    # fitting an exponential through (norm_pixel, norm_bp) pairs inferred from
    # the equalised band positions.

    n_bands = len(band_cords)
    if n_bands < 2:
        # Cannot build regression without at least two bands.
        return {
            "peak_fragment_lengths": {lid: None for lid in lane_ids},
            "similarity_matrix": {
                tuple(sorted((lane_ids[i], lane_ids[j]))): None
                for i in range(len(lane_ids))
                for j in range(i, len(lane_ids))
            },
        }

    # Pixel scale: band positions define the ladder rungs.  We assume a linear
    # spacing of fragment sizes across the n_bands positions (common for equal-
    # interval ladders).  Fragment sizes in bp: kb, 2*kb, ..., n_bands*kb.
    ladder_bp = [(i + 1) * marker_kb for i in range(n_bands)]
    max_bp = max(ladder_bp)
    norm_bp = [bp / max_bp for bp in ladder_bp]
    max_cord = max(band_cords) if max(band_cords) != 0 else 1
    norm_px = [c / max_cord for c in band_cords]

    def _exp_model(x, a, b):
        return a / x + b

    try:
        popt, _ = curve_fit(_exp_model, norm_px, norm_bp,
                            p0=(-1.0, 0.01), maxfev=10000)
    except RuntimeError:
        # Curve fit failed; return nulls.
        return {
            "peak_fragment_lengths": {lid: None for lid in lane_ids},
            "similarity_matrix": {
                tuple(sorted((lane_ids[i], lane_ids[j]))): None
                for i in range(len(lane_ids))
                for j in range(i, len(lane_ids))
            },
        }

    def _pixel_to_bp(pixel_idx: int, profile_len: int) -> float | None:
        """Convert a pixel index to fragment length in bp via regression."""
        if profile_len == 0 or pixel_idx == 0:
            return None
        x = pixel_idx / profile_len
        if x <= 0:
            return None
        bp_norm = _exp_model(x, *popt)
        bp = bp_norm * max_bp
        if bp <= 0 or bp > 1_000_000:
            return None
        return float(bp)

    # ------------------------------------------------------------------
    # 5. Align each lane profile to the valid calibrated pixel range and
    #    compute per-lane peak fragment lengths.
    # ------------------------------------------------------------------
    # Use the marker monoline length as the reference profile length so that
    # the same regression function is applied uniformly.
    ref_len = len(mono_mark)

    # Build bp axis for the reference length.
    bp_axis: list[float | None] = [
        _pixel_to_bp(i, ref_len) for i in range(ref_len)
    ]
    valid_indices = [i for i, v in enumerate(bp_axis) if v is not None]

    if not valid_indices:
        return {
            "peak_fragment_lengths": {lid: None for lid in lane_ids},
            "similarity_matrix": {
                tuple(sorted((lane_ids[i], lane_ids[j]))): None
                for i in range(len(lane_ids))
                for j in range(i, len(lane_ids))
            },
        }

    bp_valid = np.array([bp_axis[i] for i in valid_indices], dtype=float)

    aligned: dict[int, np.ndarray | None] = {}
    peak_fragment_lengths: dict[int, float | None] = {}

    for lane_id in lane_ids:
        profile = corrected.get(lane_id)
        if profile is None:
            aligned[lane_id] = None
            peak_fragment_lengths[lane_id] = None
            continue

        # Trim or pad to ref_len so valid_indices apply uniformly.
        arr = np.array(profile[:ref_len], dtype=float)
        if len(arr) < ref_len:
            arr = np.pad(arr, (0, ref_len - len(arr)), constant_values=0.0)

        lane_valid = arr[valid_indices]
        aligned[lane_id] = lane_valid

        if lane_valid.size == 0:
            peak_fragment_lengths[lane_id] = None
        else:
            peak_idx = int(np.argmax(lane_valid))
            peak_fragment_lengths[lane_id] = float(bp_valid[peak_idx])

    # ------------------------------------------------------------------
    # 6. Pairwise Pearson similarity matrix.
    # ------------------------------------------------------------------
    similarity_matrix: dict[tuple[int, int], float | None] = {}

    for i in range(len(lane_ids)):
        for j in range(i, len(lane_ids)):
            a_id = lane_ids[i]
            b_id = lane_ids[j]
            key = (min(a_id, b_id), max(a_id, b_id))
            arr_a = aligned.get(a_id)
            arr_b = aligned.get(b_id)

            if arr_a is None or arr_b is None:
                similarity_matrix[key] = None
                continue

            if len(arr_a) < 2 or len(arr_b) < 2:
                similarity_matrix[key] = None
                continue

            if np.std(arr_a) == 0.0 or np.std(arr_b) == 0.0:
                similarity_matrix[key] = None
                continue

            r_val, _ = pearsonr(arr_a, arr_b)
            similarity_matrix[key] = float(r_val)

    return {
        "peak_fragment_lengths": peak_fragment_lengths,
        "similarity_matrix": similarity_matrix,
    }
