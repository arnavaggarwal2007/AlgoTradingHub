/* assets/dashAgGridFunctions.js
   Custom cell-style and value-getter functions for dash-ag-grid.
   All functions must live on window.dashAgGridFunctions.
---------------------------------------------------------------------- */
var dagfuncs = window.dashAgGridFunctions = window.dashAgGridFunctions || {};

/* ── Market State cell colour ───────────────────────────────────────── */
dagfuncs.stateStyle = function (params) {
    var map = {
        'Strong Uptrend':   { color: '#00e676', fontWeight: '700' },
        'Uptrend':          { color: '#00d4ff', fontWeight: '600' },
        'Pullback Setup':   { color: '#64b5f6', fontWeight: '600', backgroundColor: 'rgba(100,181,246,0.08)' },
        'Sideways':         { color: '#8896ac' },
        'Choppy':           { color: '#ff9800' },
        'Downtrend':        { color: '#ef5350' },
        'Strong Downtrend': { color: '#b71c1c', fontWeight: '700' },
    };
    // The value contains the icon + label e.g. "🚀 Strong Uptrend"
    for (var k in map) {
        if (params.value && params.value.indexOf(k) !== -1) return map[k];
    }
    return {};
};

/* ── Change % colour ────────────────────────────────────────────────── */
dagfuncs.changeStyle = function (params) {
    var v = parseFloat(params.value);
    return { color: v >= 0 ? '#00e676' : '#ef5350', fontWeight: '600' };
};

/* ── Score colour gradient ──────────────────────────────────────────── */
dagfuncs.scoreStyle = function (params) {
    var v = parseFloat(params.value);
    if (v >= 5) return { color: '#00e676', fontWeight: '700' };
    if (v >= 4) return { color: '#00d4ff', fontWeight: '700' };
    if (v >= 3) return { color: '#64b5f6', fontWeight: '600' };
    if (v >= 2) return { color: '#8896ac' };
    return { color: '#ef5350' };
};

/* ── Grade badge colours ────────────────────────────────────────────── */
dagfuncs.gradeStyle = function (params) {
    var map = {
        'A+': { color: '#00e676', fontWeight: '700' },
        'A':  { color: '#00d4ff', fontWeight: '700' },
        'B':  { color: '#64b5f6' },
        'C':  { color: '#8896ac' },
        'D':  { color: '#ef5350' },
    };
    return map[params.value] || {};
};

/* ── Action badge ───────────────────────────────────────────────────── */
dagfuncs.actionStyle = function (params) {
    var map = {
        'Buy Setup': { color: '#00e676', fontWeight: '700', backgroundColor: 'rgba(0,230,118,0.12)', borderRadius: '4px', padding: '1px 6px' },
        'Watch':     { color: '#00d4ff', backgroundColor: 'rgba(0,212,255,0.08)',   borderRadius: '4px', padding: '1px 6px' },
        'Wait':      { color: '#ff9800', backgroundColor: 'rgba(255,152,0,0.08)',   borderRadius: '4px', padding: '1px 6px' },
        'Avoid':     { color: '#ef5350', backgroundColor: 'rgba(239,83,80,0.08)',   borderRadius: '4px', padding: '1px 6px' },
    };
    return map[params.value] || {};
};

/* ── Earnings risk ──────────────────────────────────────────────────── */
dagfuncs.earningsStyle = function (params) {
    return params.value && params.value.indexOf('YES') !== -1
        ? { color: '#ff9800', fontWeight: '700' }
        : { color: '#4caf50' };
};

/* ── RSI colour ─────────────────────────────────────────────────────── */
dagfuncs.rsiStyle = function (params) {
    var v = parseFloat(params.value);
    if (v >= 70) return { color: '#ff9800', fontWeight: '600' };
    if (v >= 55) return { color: '#00e676' };
    if (v >= 40) return { color: '#e8ecf4' };
    return { color: '#ef5350' };
};

/* ── Volume ratio ───────────────────────────────────────────────────── */
dagfuncs.volStyle = function (params) {
    var v = parseFloat(params.value);
    if (v >= 2.0) return { color: '#00e676', fontWeight: '700' };
    if (v >= 1.3) return { color: '#64b5f6' };
    return { color: '#8896ac' };
};

/* ── 52W position % ─────────────────────────────────────────────────── */
dagfuncs.pos52wStyle = function (params) {
    var v = parseFloat(params.value);
    if (v >= -5)  return { color: '#00e676' };   // near highs
    if (v >= -15) return { color: '#64b5f6' };
    if (v >= -30) return { color: '#8896ac' };
    return { color: '#ef5350' };
};

/* ── MACD histogram ─────────────────────────────────────────────────── */
dagfuncs.macdStyle = function (params) {
    var v = parseFloat(params.value);
    return { color: v >= 0 ? '#00e676' : '#ef5350' };
};

/* ── Symbol — clickable look ────────────────────────────────────────── */
dagfuncs.symbolStyle = function (params) {
    return { color: '#00d4ff', fontWeight: '700', cursor: 'pointer', textDecoration: 'underline dotted' };
};

/* ── Row-level style: dim error rows, highlight Buy Setup ───────────── */
dagfuncs.rowStyle = function (params) {
    if (params.data && params.data.error) {
        return { opacity: '0.45' };
    }
    if (params.data && params.data.action === 'Buy Setup') {
        return { borderLeft: '3px solid #00e676' };
    }
    return {};
};

/* ── Breakout text colour ───────────────────────────────────────────── */
dagfuncs.breakoutStyle = function (params) {
    return params.value ? { color: '#ffd54f', fontWeight: '600' } : { color: '#8896ac' };
};

/* ── MTF ok/x colour ────────────────────────────────────────────────── */
dagfuncs.mtfStyle = function (params) {
    return params.value === '✓'
        ? { color: '#00e676', fontWeight: '700' }
        : { color: '#8896ac' };
};
