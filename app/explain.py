"""Plain-language verdict explanations.

Turns the raw numbers (EMA/RSI/band/anchor/net-value) into sentences anyone can
read: why did this stock get MAXIMUM_CONVICTION_BUY / STRONG_BUY / NEUTRAL_HOLD /
WATCHLIST / REJECTED — and what each number actually means.
"""
from __future__ import annotations

from typing import Optional

from .models import ScanParams, StockVerdict


def _fmt(n: Optional[float]) -> str:
    if n is None or n != n:  # NaN
        return "—"
    if abs(n) >= 1e9:
        return f"Rp {n / 1e9:.2f} M"
    if abs(n) >= 1e6:
        return f"Rp {n / 1e6:.1f} jt"
    return f"Rp {n:,.0f}"  # harga saham tampil penuh, e.g. Rp 3.390


def explain_verdict(result: StockVerdict, params: ScanParams) -> dict:
    t = result.technicals or {}
    checks = t.get("checks") or {}
    bf = result.broker_flow or {}
    b_details = (bf.get("layer_b") or {}).get("details") or {}
    c_details = (bf.get("layer_c") or {}).get("details") or {}
    close = t.get("close")
    points: list[dict] = []
    ok = "pass"
    fail = "fail"

    # ---- Layer A: teknikal ----
    uptrend = checks.get("uptrend")
    if uptrend:
        points.append({"kind": ok, "text": f"Harga {_fmt(close)} > EMA20 {_fmt(t.get('ema20'))} > SMA50 {_fmt(t.get('sma50'))} — tren jangka panjang masih NAIK, bukan turun."})
    else:
        points.append({"kind": fail, "text": f"Tren belum naik: harga {_fmt(close)} tidak berada di atas EMA20 {_fmt(t.get('ema20'))} dan/atau EMA20 tidak di atas SMA50 {_fmt(t.get('sma50'))} — syarat uptrend gagal."})

    dz = checks.get("discount_zone")
    if dz:
        points.append({"kind": ok, "text": f"Low hari ini menyentuh/mendekati Lower Bollinger Band {_fmt(t.get('lower_band'))} — harga sedang di ZONA DISKON (area relatif murah 20 hari terakhir)."})
    else:
        points.append({"kind": fail, "text": f"Harga {_fmt(close)} belum menyentuh Lower Bollinger Band {_fmt(t.get('lower_band'))} — belum masuk zona diskon (masih 'mahal' relatif 20 hari)."})

    liq = checks.get("liquidity")
    if liq:
        points.append({"kind": ok, "text": f"Nilai transaksi 20 hari rata-rata {_fmt(t.get('avg_20d_value_idr'))} > syarat {_fmt(params.min_liquidity_idr)} — saham cukup LIKUID, mudah masuk & keluar."})
    else:
        points.append({"kind": fail, "text": f"Nilai transaksi 20 hari {_fmt(t.get('avg_20d_value_idr'))} ≤ syarat {_fmt(params.min_liquidity_idr)} — kurang ramai, risiko susah jual."})

    if checks.get("min_price") is False:
        points.append({"kind": fail, "text": f"Harga {_fmt(close)} di bawah batas minimum {_fmt(params.min_price)} — terlalu murah/spekulatif."})

    rsi = t.get("rsi14")
    if checks.get("rsi_ok"):
        points.append({"kind": ok, "text": f"RSI {rsi} (< {params.rsi_max:g}) — belum overbought (jenuh beli), masih ada ruang naik."})
    elif rsi is not None:
        points.append({"kind": fail, "text": f"RSI {rsi} ≥ {params.rsi_max:g} — sudah overbought/panas, risiko koreksi lebih tinggi."})

    pull = t.get("pullback_from_20d_high_pct")
    if checks.get("pullback"):
        points.append({"kind": ok, "text": f"Sudah terkoreksi {pull}% dari high 20 hari (≥ syarat {params.pullback_pct:g}%) — ini PULLBACK wajar, bukan mengejar harga yang sudah melonjak."})
    elif pull is not None:
        points.append({"kind": fail, "text": f"Baru terkoreksi {pull}% dari high 20 hari (< syarat {params.pullback_pct:g}%) — harga masih terlalu dekat puncak."})

    # ---- Layer B: bandarmologi ----
    b_status = (bf.get("layer_b") or {}).get("status") or (result.layers.get("b") or {}).get("status")
    matched = b_details.get("matched_brokers") or []
    if b_status == "pass" and matched:
        names = ", ".join(m["broker_code"] for m in matched)
        nets = ", ".join(f"{m['broker_code']} net beli {_fmt(m['nval'])}" for m in matched[:2])
        points.append({"kind": ok, "text": f"Broker {names} masuk Top {params.top_n_brokers} NET BUYER ({nets}) — institusi/bandar sedang AKUMULASI (mengumpulkan saham)."})
        anchor_ok = b_details.get("price_anchor_ok")
        if anchor_ok:
            points.append({"kind": ok, "text": f"Harga {_fmt(close)} ≤ anchor {_fmt(b_details.get('buy_avg_anchor'))} × (1 + {params.price_anchor_pct:g}%) — harga masih DEKAT zona beli rata-rata, belum 'kabur' naik."})
        else:
            points.append({"kind": fail, "text": f"Harga {_fmt(close)} sudah di atas batas anchor {_fmt(b_details.get('price_anchor_max'))} — sudah naik terlalu jauh dari zona akumulasi (risiko kejar-kejaran)."})
    elif b_status == "fail":
        if params.brokers:
            points.append({"kind": fail, "text": f"Filter broker {', '.join(params.brokers)}: broker yang diminta TIDAK ada di Top {params.top_n_brokers} net buyer — akumulasi broker lain tidak dihitung."})
        else:
            points.append({"kind": fail, "text": "Tidak ada broker institusi di Top " + str(params.top_n_brokers) + " net buyer, atau harga sudah lewat batas anchor — akumulasi bandar belum terkonfirmasi."})
    elif b_status in ("unavailable", "skipped"):
        reason = b_details.get("reason") or "data broker tidak tersedia"
        points.append({"kind": "info", "text": f"Layer B tidak dapat dicek otomatis: {reason}. Verifikasi bandarmologi secara manual."})

    # ---- Layer C: retail ----
    c_status = (bf.get("layer_c") or {}).get("status") or (result.layers.get("c") or {}).get("status")
    share = c_details.get("retail_share_of_net_sell")
    retail_sellers = c_details.get("retail_sellers") or []
    if c_status == "pass" and retail_sellers:
        codes = ", ".join(r["broker_code"] for r in retail_sellers)
        points.append({"kind": ok, "text": f"Broker retail ({codes}) mendominasi jualan bersih (porsi {(share or 0) * 100:.0f}%) — RETAIL MENJUAL ke institusi, pola sehat untuk swing buy."})
    elif c_status == "fail":
        points.append({"kind": fail, "text": "Jualan bersih belum didominasi broker retail — distribusi retail (Layer C) belum terkonfirmasi."})
    elif c_status in ("unavailable", "skipped"):
        points.append({"kind": "info", "text": "Layer C tidak dicek otomatis (data broker tidak tersedia)."})

    # ---- Ringkasan verdict ----
    summaries = {
        "MAXIMUM_CONVICTION_BUY": "Semua lapisan lolos: teknikal bagus + institusi mengakumulasi + retail mendistribusikan → kandidat BELI paling kuat.",
        "STRONG_BUY": "Teknikal + akumulasi institusi bagus, tapi distribusi retail belum terkonfirmasi → layak beli dengan porsi lebih kecil / tunggu konfirmasi.",
        "NEUTRAL_HOLD": "Teknikal lolos, tapi akumulasi broker belum terkonfirmasi atau harga sudah melewati zona anchor → TAHAN dulu, pantau.",
        "WATCHLIST": "Teknikal lolos, tapi data broker tidak bisa dicek otomatis → amati manual, konfirmasi bandarmologi sebelum masuk.",
        "REJECTED": "Gagal filter teknikal → tidak direkomendasikan masuk sekarang.",
    }
    summary = summaries.get(result.verdict, "")

    return {
        "verdict": result.verdict,
        "summary": summary,
        "points": points,
        "cara_baca": GLOSSARY,
    }


GLOSSARY = [
    {"term": "EMA20 / SMA50", "def": "Rata-rata harga 20 & 50 hari terakhir. Harga > EMA20 > SMA50 artinya tren sedang naik."},
    {"term": "Bollinger Band (20, 2σ)", "def": "Pita di sekitar rata-rata. Lower band = area 'murah' relatif 20 hari; menyentuhnya = zona diskon."},
    {"term": "RSI(14)", "def": "Skala 0–100. >70 = overbought (mahal, rawan koreksi), <30 = oversold (murah)."},
    {"term": "ATR(14)", "def": "Rata-rata pergerakan harga harian. Dipakai untuk stop loss (2×ATR dari harga masuk)."},
    {"term": "Nilai transaksi 20 hari", "def": "Rata-rata Rp saham × volume 20 hari = likuiditas. Makin besar, makin mudah jual-beli."},
    {"term": "Anchor / VWAP", "def": "Rata-rata harga tertimbang volume selama lookback — proxy harga beli rata-rata broker. Harga ≤ anchor × 1,03 = masih dekat zona akumulasi."},
    {"term": "nval (net value)", "def": "Nilai beli − nilai jual sebuah broker dalam Rp. Positif = net buy (akumulasi), negatif = net sell (distribusi)."},
    {"term": "TP1 / TP2 / SL", "def": "Target profit 1 (+10%, jual 50% lot), target profit 2 (+20%, jual semua), stop loss (batas rugi)."},
    {"term": "Lot", "def": "Satuan transaksi IDX: 1 lot = 100 lembar saham."},
    {"term": "Pullback", "def": "Koreksi wajar dari harga tertinggi. Strategi ini membeli saat pullback ke zona diskon, bukan mengejar harga yang sudah naik."},
]