"""Direktori broker IDX (bandarmologi).

Berisi klasifikasi edukatif untuk kode broker BEI yang umum muncul di data
arjum: kategori kepemilikan (asing/institusi global, BUMN, grup konglomerat
domestik, aplikasi retail online, sekuritas lokal/ritel) plus afiliasi grup
dan emiten terkait bila diketahui.

CATATAN PENTING:
- Ini bukan daftar resmi BEI/OJK, melainkan ringkasan edukasi dari informasi
  publik (sitasi: daftar kode broker IDX 2025) + pengetahuan umum grup usaha.
- "Smart money" di sini = broker yang biasa menjadi sarana transaksi institusi
  / asing / grup besar. "Ritel" = broker yang dominan melayani nasabah retail
  (termasuk aplikasi online). Klasifikasi bersifat indikatif, bukan fakta.
- Afiliasi grup bisa berubah (merger/akuisisi) — selalu verifikasi sebelum
  mengambil keputusan investasi.
"""
from __future__ import annotations

# Kategori kepemilikan + penjelasan singkat (ditampilkan di UI).
CATEGORY_META: dict[str, dict] = {
    "foreign": {
        "label": "Asing / Institusi Global",
        "desc": "Sekuritas milik grup keuangan global/regional (UBS, JP Morgan, CLSA, DBS, UOB, Maybank, Korea, Taiwan, dll). Sering jadi sarana transaksi institusi asing — termasuk kategori smart money.",
        "tags": ["smart_money"],
    },
    "bumn": {
        "label": "BUMN / Bank BUMN",
        "desc": "Sekuritas milik BUMN Indonesia (Bank Mandiri, BNI, BRI, Danareksa, Bahana). Likuiditas besar, sering menjadi saluran transaksi institusi domestik — smart money.",
        "tags": ["smart_money"],
    },
    "conglomerate": {
        "label": "Grup Konglomerat Domestik",
        "desc": "Sekuritas milik grup usaha besar Indonesia (Sinarmas, MNC, CT Corp, Djarum/BCA, Panin, dll). Bisa menjadi saluran transaksi afiliasi grup-nya — perhatikan saat grup memiliki emiten yang sama.",
        "tags": ["smart_money"],
    },
    "online_retail": {
        "label": "Aplikasi Retail Online",
        "desc": "Aplikasi investasi ritel (Ajaib, Stockbit, Webull, Pluang, dll). Dominan nasabah retail individu — kategori ritel.",
        "tags": ["retail"],
    },
    "local": {
        "label": "Sekuritas Lokal / Ritel",
        "desc": "Sekuritas domestik berukuran kecil-menengah yang dominan melayani nasabah ritel — kategori ritel.",
        "tags": ["retail"],
    },
}

# {kode: {name, category, group, issuers, note}}
# `issuers` = emiten yang terafiliasi dengan grup pemilik broker (bila jelas).
BROKER_DIRECTORY: dict[str, dict] = {
    # ---------------- Asing / Institusi Global ----------------
    "AK": {"name": "UBS Sekuritas Indonesia", "category": "foreign", "group": "UBS Group (Swiss)", "issuers": [], "note": "Broker asing besar — sering muncul di posisi top buyer institusi asing."},
    "BK": {"name": "JP Morgan Sekuritas Indonesia", "category": "foreign", "group": "JP Morgan Chase (AS)", "issuers": [], "note": "Institusi global; transaksi bernilai besar."},
    "KZ": {"name": "CLSA Sekuritas Indonesia", "category": "foreign", "group": "CLSA (Hong Kong)", "issuers": [], "note": "Institusi asing; sering jadi indikator aliran dana asing."},
    "RX": {"name": "Macquarie Sekuritas Indonesia", "category": "foreign", "group": "Macquarie Group (Australia)", "issuers": [], "note": "Institusi asing."},
    "DP": {"name": "DBS Vickers Sekuritas Indonesia", "category": "foreign", "group": "DBS Group (Singapura)", "issuers": [], "note": "Institusi asing Singapura."},
    "AI": {"name": "UOB Kay Hian Sekuritas", "category": "foreign", "group": "UOB Group (Singapura)", "issuers": [], "note": "Institusi asing Singapura."},
    "DR": {"name": "RHB Sekuritas Indonesia", "category": "foreign", "group": "RHB Group (Malaysia)", "issuers": [], "note": "Institusi asing Malaysia."},
    "TP": {"name": "OCBC Sekuritas Indonesia", "category": "foreign", "group": "OCBC Group (Singapura)", "issuers": [], "note": "Institusi asing Singapura."},
    "YU": {"name": "CGS International Sekuritas Indonesia", "category": "foreign", "group": "CGS International (Malaysia/Singapura)", "issuers": [], "note": "Institusi regional."},
    "XA": {"name": "NH Korindo Sekuritas Indonesia", "category": "foreign", "group": "NH Investment & Securities (Korea) + Korindo Group", "issuers": [], "note": "Jaringan Korea + lokal."},
    "AG": {"name": "Kiwoom Sekuritas Indonesia", "category": "foreign", "group": "Kiwoom Securities (Korea)", "issuers": [], "note": "Institusi Korea."},
    "AH": {"name": "Shinhan Sekuritas Indonesia", "category": "foreign", "group": "Shinhan Financial Group (Korea)", "issuers": [], "note": "Institusi Korea."},
    "CP": {"name": "KB Valbury Sekuritas", "category": "foreign", "group": "KB Financial Group (Korea)", "issuers": [], "note": "Institusi Korea."},
    "BQ": {"name": "Korea Investment and Securities Indonesia", "category": "foreign", "group": "Korea Investment & Securities (Korea)", "issuers": [], "note": "Institusi Korea."},
    "KK": {"name": "Phillip Sekuritas Indonesia", "category": "foreign", "group": "Phillip Capital (Singapura)", "issuers": [], "note": "Institusi regional."},
    "FS": {"name": "Yuanta Sekuritas Indonesia", "category": "foreign", "group": "Yuanta Financial (Taiwan)", "issuers": [], "note": "Institusi Taiwan."},
    "HD": {"name": "KGI Sekuritas Indonesia", "category": "foreign", "group": "KGI Securities (Taiwan)", "issuers": [], "note": "Institusi Taiwan."},
    "ZP": {"name": "Maybank Sekuritas Indonesia", "category": "foreign", "group": "Maybank Group (Malaysia)", "issuers": [], "note": "Institusi asing Malaysia."},
    "GI": {"name": "Webull Sekuritas Indonesia", "category": "online_retail", "group": "Webull (AS)", "issuers": [], "note": "Aplikasi trading ritel online."},
    "YO": {"name": "Amantara Securities Indonesia", "category": "online_retail", "group": "-", "issuers": [], "note": "Aplikasi ritel online."},

    # ---------------- BUMN / Bank BUMN ----------------
    "CC": {"name": "Mandiri Sekuritas", "category": "bumn", "group": "Bank Mandiri (BUMN)", "issuers": [], "note": "Sekuritas bank BUMN terbesar; likuiditas tinggi."},
    "NI": {"name": "BNI Sekuritas", "category": "bumn", "group": "Bank Negara Indonesia (BUMN)", "issuers": [], "note": "Sekuritas bank BUMN."},
    "OD": {"name": "BRI Danareksa Sekuritas", "category": "bumn", "group": "Bank Rakyat Indonesia (BUMN)", "issuers": [], "note": "Gabungan BRI + Danareksa."},
    "DX": {"name": "Bahana Sekuritas", "category": "bumn", "group": "Danareksa (BUMN)", "issuers": [], "note": "Sekuritas BUMN."},

    # ---------------- Grup Konglomerat Domestik ----------------
    "DH": {"name": "Sinarmas Sekuritas", "category": "conglomerate", "group": "Sinar Mas Group (Eka Tjipta Widjaja)", "issuers": ["BSDE", "SMAR", "TKIM", "SWAN", "TPIA"], "note": "Sekuritas grup Sinar Mas — perhatikan afiliasi dengan emiten grup (BSDE, SMAR, TKIM, dll)."},
    "EP": {"name": "MNC Sekuritas", "category": "conglomerate", "group": "MNC Group (Hary Tanoesoedibjo)", "issuers": ["MNCN", "BMTR", "MSIN", "MNCG"], "note": "Sekuritas grup MNC — emiten grup: MNCN, BMTR, dll."},
    "CD": {"name": "Mega Capital Sekuritas", "category": "conglomerate", "group": "CT Corp (Chairul Tanjung)", "issuers": ["MEGA"], "note": "Sekuritas grup CT Corp — emiten grup: MEGA."},
    "SQ": {"name": "BCA Sekuritas", "category": "conglomerate", "group": "Djarum Group (Hartono bersaudara)", "issuers": ["BBCA", "BNLI"], "note": "Sekuritas grup Djarum/BCA — emiten grup: BBCA."},
    "GR": {"name": "Panin Sekuritas Tbk", "category": "conglomerate", "group": "Panin Group (Gunawan family)", "issuers": ["PNBN", "PANI", "PANR", "ASGR"], "note": "Sekuritas grup Panin — emiten grup: PNBN, PANI, dll."},
    "MG": {"name": "Semesta Indovest Sekuritas", "category": "conglomerate", "group": "Semesta Group", "issuers": [], "note": "Sering muncul di daftar net buyer besar — perhatikan pola akumulasinya."},
    "PD": {"name": "Indo Premier Sekuritas", "category": "conglomerate", "group": "Indo Premier Group", "issuers": [], "note": "Sekuritas besar; aktif di IPO & transaksi institusi."},
    "IF": {"name": "Samuel Sekuritas Indonesia", "category": "conglomerate", "group": "Samuel Group", "issuers": [], "note": "Sekuritas besar, riset kuat."},
    "LG": {"name": "Trimegah Sekuritas Indonesia Tbk", "category": "conglomerate", "group": "Trimegah Group", "issuers": [], "note": "Sekuritas institusi."},
    "KI": {"name": "Ciptadana Sekuritas Asia", "category": "conglomerate", "group": "Ciptadana Group", "issuers": [], "note": "Sekuritas institusi."},
    "DD": {"name": "Makindo Securities", "category": "conglomerate", "group": "Makindo Group", "issuers": [], "note": "Sekuritas institusi."},
    "EL": {"name": "Evergreen Sekuritas Indonesia", "category": "conglomerate", "group": "Evergreen Group", "issuers": [], "note": "Sekuritas lokal."},
    "AZ": {"name": "Sucor Sekuritas", "category": "conglomerate", "group": "Sucor Group", "issuers": [], "note": "Sekuritas lokal."},
    "HP": {"name": "Henan Putihrai Sekuritas", "category": "conglomerate", "group": "Henan Putihrai Group", "issuers": [], "note": "Sekuritas lokal."},
    "BR": {"name": "Trust Sekuritas", "category": "conglomerate", "group": "Trust Group", "issuers": [], "note": "Sekuritas lokal."},

    # ---------------- Aplikasi Retail Online ----------------
    "XC": {"name": "Ajaib Sekuritas Indonesia", "category": "online_retail", "group": "Ajaib Group", "issuers": [], "note": "Aplikasi investasi ritel terbesar — dominan nasabah retail."},
    "XL": {"name": "Stockbit Sekuritas Digital", "category": "online_retail", "group": "Stockbit (Yosephine Group)", "issuers": [], "note": "Aplikasi ritel online (Stockbit/Bibit)."},
    "RO": {"name": "Pluang Maju Sekuritas", "category": "online_retail", "group": "Pluang (Grup Salim/Japfa)", "issuers": [], "note": "Aplikasi ritel online."},

    # ---------------- Sekuritas Lokal / Ritel ----------------
    "SS": {"name": "Supra Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sering muncul di daftar broker aktif — cek pola beli/jual harian sebelum menyimpulkan."},
    "YP": {"name": "Mirae Asset Sekuritas Indonesia", "category": "local", "group": "Mirae Asset (Korea)", "issuers": [], "note": "Broker besar, campuran ritel & institusi."},
    "AT": {"name": "Phintraco Sekuritas", "category": "local", "group": "Phintraco Group", "issuers": [], "note": "Sekuritas lokal."},
    "AP": {"name": "Pacific Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "AR": {"name": "Bina Artha Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "BB": {"name": "Verdhana Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "BS": {"name": "Equity Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "ES": {"name": "Ekopital Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "SH": {"name": "Artha Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "SF": {"name": "Surya Fajar Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "RB": {"name": "Ina Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "AD": {"name": "OSO Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "AF": {"name": "Harita Kencana Sekuritas", "category": "local", "group": "Harita Group", "issuers": ["NCKL", "ANTM"], "note": "Sekuritas grup Harita — emiten grup: NCKL (nikel), dll."},
    "AO": {"name": "Erdikha Elit Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "BF": {"name": "Inti Fikasa Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "DU": {"name": "KAF Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "FO": {"name": "Forte Global Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "FZ": {"name": "Waterfront Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "GA": {"name": "BNC Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "IC": {"name": "Integrity Capital Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "ID": {"name": "Anugerah Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "IH": {"name": "Pacific 2000 Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "II": {"name": "Danatama Makmur Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "IN": {"name": "Investindo Nusantara Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "IT": {"name": "Inti Teladan Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "IU": {"name": "Indo Capital Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "LS": {"name": "Reliance Sekuritas Indonesia Tbk", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "MI": {"name": "Victoria Sekuritas Indonesia", "category": "local", "group": "Victoria Group", "issuers": ["VICO"], "note": "Sekuritas grup Victoria."},
    "MU": {"name": "Minna Padi Investama Sekuritas Tbk", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "OK": {"name": "NET Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "PC": {"name": "FAC Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "PF": {"name": "Danasakti Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "PG": {"name": "Panca Global Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "PI": {"name": "Magenta Kapital Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "PO": {"name": "Pilarmas Investindo Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "PP": {"name": "Aldiracita Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "QA": {"name": "Tuntun Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "RF": {"name": "Buana Capital Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "RG": {"name": "Profindo Sekuritas Indonesia", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "RS": {"name": "Yulie Sekuritas Indonesia Tbk", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "SA": {"name": "Elit Sukses Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "TF": {"name": "Universal Broker Indonesia Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "TS": {"name": "Dwidana Sakti Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "YB": {"name": "Yakin Bertumbuh Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "YJ": {"name": "Lotus Andalan Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
    "ZR": {"name": "Bumiputera Sekuritas", "category": "local", "group": "-", "issuers": [], "note": "Sekuritas lokal."},
}

# Kode yang sering disebut komunitas bandarmologi sebagai "bandar/smart money"
# (indikatif — gabungan institusi asing, BUMN, dan grup besar).
SMART_MONEY_CODES: set[str] = {
    code
    for code, info in BROKER_DIRECTORY.items()
    if "smart_money" in CATEGORY_META[info["category"]]["tags"]
}

# Kode ritel (aplikasi online + sekuritas lokal kecil) — indikatif.
RETAIL_CODES: set[str] = {
    code
    for code, info in BROKER_DIRECTORY.items()
    if "retail" in CATEGORY_META[info["category"]]["tags"]
}


def broker_info(code: str) -> dict | None:
    """Return directory entry (enriched with category meta) for a broker code."""
    entry = BROKER_DIRECTORY.get(code.strip().upper())
    if entry is None:
        return None
    cat = CATEGORY_META[entry["category"]]
    return {
        "code": code.strip().upper(),
        "name": entry["name"],
        "category": entry["category"],
        "category_label": cat["label"],
        "category_desc": cat["desc"],
        "tags": cat["tags"],
        "group": entry["group"],
        "issuers": entry["issuers"],
        "note": entry["note"],
    }


def directory() -> list[dict]:
    """Full directory, sorted by category then code."""
    order = ["foreign", "bumn", "conglomerate", "online_retail", "local"]
    entries = sorted(BROKER_DIRECTORY.items(), key=lambda kv: (order.index(kv[1]["category"]), kv[0]))
    out: list[dict] = []
    for code, info in entries:
        cat = CATEGORY_META[info["category"]]
        out.append(
            {
                "code": code,
                "name": info["name"],
                "category": info["category"],
                "category_label": cat["label"],
                "tags": cat["tags"],
                "group": info["group"],
                "issuers": info["issuers"],
                "note": info["note"],
            }
        )
    return out


def explain() -> list[dict]:
    """Human-readable explanation of smart money vs retail + categories."""
    return [
        {
            "term": "Smart money",
            "def": "Uang 'pintar' — institusi, asing, BUMN, dan grup besar yang biasanya punya informasi & volume lebih besar. Di data broker, mereka tampil sebagai net buyer/nilai transaksi besar secara konsisten.",
        },
        {
            "term": "Ritel",
            "def": "Nasabah individu — volume per transaksi kecil, sering ikut-ikutan (herding). Di data broker, ritel sering tampil sebagai net seller saat harga naik (distribusi ke institusi) atau net buyer saat FOMO.",
        },
        {
            "term": "Baca datanya",
            "def": "Cek kode broker di kolom hasil: kategori 'smart money' yang net buy konsisten = sinyal akumulasi; ritel yang net sell besar saat harga turun = pola sehat (retail menjual ke institusi).",
        },
    ]