def compare_lane_intensities(lane_ids: list[int], marker_kb: int = 100) -> dict:
    """
    Compare background-corrected intensity profiles of multiple gel lanes.

    Returns a dict with:
      - 'peak_fragment_lengths': {lane_id: float or None} — fragment length (bp) at
        the intensity peak for each lane, derived via marker regression.
      - 'similarity_matrix': {(lane_id_a, lane_id_b): float} — pairwise Pearson
        correlation coefficients between the intensity profiles of every pair of
        lanes, computed on the shared fragment-length scale produced by the marker
        regression.  Keys are sorted tuples so (a, b) == (b, a).
    """
    import numpy as np
    from scipy.stats import pearsonr

    # ------------------------------------------------------------------
    # 1. Load marker data and build regression-based fragment-length scale
    # ------------------------------------------------------------------
    data = InitAllData()
    r_mark, l_mark, mono_mark, bands = data.init_markers(with_bands=True)
    bands = sorted(bands)

    reg = MarkerRegression()
    reg.normalize_ladder(bands, kb=marker_kb)
    reg.get_band_reg()
    reg.get_rescaled(mono_mark)          # populates reg.rescale (pixel -> bp)
    rescale = reg.rescale                # list, len == len(mono_mark), values bp or None

    # ------------------------------------------------------------------
    # 2. Load and background-correct every requested lane
    # ------------------------------------------------------------------
    borders, monos = data.init_roads()

    lane_profiles: dict[int, list] = {}
    for lane_id in lane_ids:
        key = str(lane_id)
        if key not in borders or len(borders[key]) != 2:
            lane_profiles[lane_id] = None
            continue
        l = min(borders[key])
        r = max(borders[key])
        mono = list(monos[key])
        mono = data.del_close_bg(r, l, mono)
        lane_profiles[lane_id] = mono

    # ------------------------------------------------------------------
    # 3. Build a common fragment-length axis and interpolate each profile
    # ------------------------------------------------------------------
    # Collect only positions where the scale gives a valid bp value and
    # all requested lanes have a profile of sufficient length.
    valid_min_len = min(
        (len(p) for p in lane_profiles.values() if p is not None),
        default=0
    )
    if valid_min_len == 0:
        return {
            'peak_fragment_lengths': {lid: None for lid in lane_ids},
            'similarity_matrix': {},
        }

    scale_len = min(len(rescale), valid_min_len)

    # Build arrays aligned to the shared pixel axis [0, scale_len)
    bp_axis = np.array([rescale[i] for i in range(scale_len)], dtype=float)   # may contain NaN via None
    bp_axis = np.where([v is None for v in [rescale[i] for i in range(scale_len)]], np.nan, bp_axis)

    aligned: dict[int, np.ndarray] = {}
    for lane_id, profile in lane_profiles.items():
        if profile is None:
            aligned[lane_id] = None
        else:
            aligned[lane_id] = np.array(profile[:scale_len], dtype=float)

    # ------------------------------------------------------------------
    # 4. Peak fragment lengths
    # ------------------------------------------------------------------
    peak_fragment_lengths: dict[int, float | None] = {}
    for lane_id, arr in aligned.items():
        if arr is None:
            peak_fragment_lengths[lane_id] = None
            continue
        # Only consider positions where we have a valid bp value
        valid_mask = ~np.isnan(bp_axis)
        if not valid_mask.any():
            peak_fragment_lengths[lane_id] = None
            continue
        peak_idx = int(np.argmax(arr[valid_mask]))
        peak_bp = bp_axis[valid_mask][peak_idx]
        peak_fragment_lengths[lane_id] = float(peak_bp)

    # ------------------------------------------------------------------
    # 5. Pairwise similarity (Pearson r on valid-scale positions)
    # ------------------------------------------------------------------
    valid_mask = ~np.isnan(bp_axis)
    similarity_matrix: dict[tuple[int, int], float] = {}

    lane_list = lane_ids
    for i in range(len(lane_list)):
        for j in range(i, len(lane_list)):
            a, b = lane_list[i], lane_list[j]
            arr_a = aligned.get(a)
            arr_b = aligned.get(b)
            if arr_a is None or arr_b is None:
                similarity_matrix[(a, b)] = None
                continue
            va = arr_a[valid_mask]
            vb = arr_b[valid_mask]
            if len(va) < 2 or np.std(va) == 0 or np.std(vb) == 0:
                similarity_matrix[(a, b)] = None
                continue
            r_val, _ = pearsonr(va, vb)
            similarity_matrix[(a, b)] = float(r_val)

    return {
        'peak_fragment_lengths': peak_fragment_lengths,
        'similarity_matrix': similarity_matrix,
    }
