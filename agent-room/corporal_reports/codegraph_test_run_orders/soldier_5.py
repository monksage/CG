def compare_lane_intensities(lane_ids: list[int], marker_kb: int = 100) -> dict:
    """
    Compare the background-corrected intensity profiles of multiple gel lanes.

    Returns per-lane peak fragment lengths and a pairwise similarity matrix,
    using the marker regression to convert pixel positions to fragment lengths.

    Parameters
    ----------
    lane_ids : list[int]
        IDs of the gel lanes to compare.
    marker_kb : int
        Marker ladder size in kb used for regression calibration (100 or 1000).

    Returns
    -------
    dict with keys:
        "peak_fragment_lengths" : dict[int, float | None]
            Fragment length (bp) at the intensity peak for each lane.
            None if the lane has no valid calibrated signal.
        "similarity_matrix" : dict[tuple[int, int], float | None]
            Pairwise Pearson correlation between background-corrected
            intensity profiles on the shared fragment-length scale.
            Keys are sorted (i, j) tuples so (a, b) == (b, a).
            None if either lane lacks a valid profile.
    """
    import numpy as np
    from scipy.stats import pearsonr
    from scipy.interpolate import interp1d

    data = InitAllData()

    # ------------------------------------------------------------------
    # 1. Load marker data and fit pixel-to-fragment-length regression
    # ------------------------------------------------------------------
    r_mark, l_mark, mono_mark, bands = data.init_markers(with_bands=True)
    bands_sorted = sorted(bands)

    reg = MarkerRegression()
    reg.normalize_ladder(bands_sorted, kb=marker_kb)
    reg.get_band_reg()
    reg.get_rescaled(mono_mark)
    rescale = reg.rescale  # list of bp values (or None) per pixel index

    # Build numeric bp axis, treating None as NaN
    bp_axis = np.array(
        [v if v is not None else np.nan for v in rescale],
        dtype=float,
    )

    # ------------------------------------------------------------------
    # 2. Load lanes and apply background correction
    # ------------------------------------------------------------------
    borders, monos = data.init_roads()

    lane_profiles: dict[int, np.ndarray | None] = {}
    for lid in lane_ids:
        key = str(lid)
        if key not in monos or key not in borders or len(borders[key]) != 2:
            lane_profiles[lid] = None
            continue
        b_min = min(borders[key])
        b_max = max(borders[key])
        mono = list(monos[key])
        mono = data.del_close_bg(b_max, b_min, mono)
        lane_profiles[lid] = np.asarray(mono, dtype=float)

    # ------------------------------------------------------------------
    # 3. Align all lanes to the shared fragment-length scale
    # ------------------------------------------------------------------
    # The bp_axis may be shorter or longer than individual lane profiles.
    # We truncate to the minimum valid overlap, then interpolate each lane
    # onto a dense common bp grid so profiles of different pixel lengths
    # can be compared fairly.

    valid_profiles = {
        lid: arr for lid, arr in lane_profiles.items() if arr is not None
    }

    if not valid_profiles:
        return {
            "peak_fragment_lengths": {lid: None for lid in lane_ids},
            "similarity_matrix": {},
        }

    # Determine the common pixel range: limited by bp_axis and shortest lane.
    min_px_len = min(len(arr) for arr in valid_profiles.values())
    shared_len = min(len(bp_axis), min_px_len)
    bp_shared = bp_axis[:shared_len]
    valid_mask = ~np.isnan(bp_shared)

    if not valid_mask.any():
        return {
            "peak_fragment_lengths": {lid: None for lid in lane_ids},
            "similarity_matrix": {},
        }

    bp_valid = bp_shared[valid_mask]
    # Common dense grid for interpolation: 512 evenly-spaced bp values.
    bp_grid = np.linspace(bp_valid.min(), bp_valid.max(), 512)

    aligned: dict[int, np.ndarray | None] = {}
    for lid in lane_ids:
        arr = lane_profiles.get(lid)
        if arr is None:
            aligned[lid] = None
            continue
        pixel_intensities = arr[:shared_len]
        intensities_valid = pixel_intensities[valid_mask]
        if len(intensities_valid) < 2:
            aligned[lid] = None
            continue
        # Interpolate onto the common bp grid
        try:
            interp_fn = interp1d(
                bp_valid,
                intensities_valid,
                kind="linear",
                bounds_error=False,
                fill_value=0.0,
            )
            aligned[lid] = interp_fn(bp_grid)
        except ValueError:
            aligned[lid] = None

    # ------------------------------------------------------------------
    # 4. Peak fragment lengths
    # ------------------------------------------------------------------
    peak_fragment_lengths: dict[int, float | None] = {}
    for lid in lane_ids:
        arr = aligned.get(lid)
        if arr is None or len(arr) == 0:
            peak_fragment_lengths[lid] = None
        else:
            peak_bp = float(bp_grid[int(np.argmax(arr))])
            peak_fragment_lengths[lid] = peak_bp

    # ------------------------------------------------------------------
    # 5. Pairwise similarity (Pearson r on common bp grid)
    # ------------------------------------------------------------------
    similarity_matrix: dict[tuple[int, int], float | None] = {}
    ids = list(lane_ids)

    for i in range(len(ids)):
        for j in range(i, len(ids)):
            a, b = ids[i], ids[j]
            arr_a = aligned.get(a)
            arr_b = aligned.get(b)
            key = (a, b)
            if arr_a is None or arr_b is None or len(arr_a) < 2 or len(arr_b) < 2:
                similarity_matrix[key] = None
                continue
            std_a = float(np.std(arr_a))
            std_b = float(np.std(arr_b))
            if std_a == 0.0 or std_b == 0.0:
                similarity_matrix[key] = None
                continue
            r_val, _ = pearsonr(arr_a, arr_b)
            similarity_matrix[key] = float(r_val)

    return {
        "peak_fragment_lengths": peak_fragment_lengths,
        "similarity_matrix": similarity_matrix,
    }
