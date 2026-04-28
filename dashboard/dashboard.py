import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import os
from pathlib import Path
from io import BytesIO
from dotenv import load_dotenv
from supabase import create_client

# Загрузка .env (локально) или secrets (Streamlit Cloud)
load_dotenv(Path(__file__).parent / ".env")

SUPABASE_URL = os.environ.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")

KERAMIN_BRAND     = "КЕРАМИН"
STORES_WITH_STOCK = []   # Phase 2: добавить магазины с остатками
COLOR_KERAMIN     = "#E63946"
COLOR_MARKET      = "#457B9D"

KEY_COUNTRIES = [
    "БЕЛАРУСЬ", "РОССИЯ", "ТУРЦИЯ", "ИСПАНИЯ",
    "ИНДИЯ", "КИТАЙ", "ПОЛЬША", "ИТАЛИЯ", "ГЕРМАНИЯ",
    "КАЗАХСТАН", "УЗБЕКИСТАН",
]
KEY_FORMATS = [
    "120x60", "60x60", "60x30", "30x60", "40x40",
    "30x30", "20x120", "75x25", "25x75", "60x20",
]
MATERIAL_FORMATS = {
    "Керамика":     ["90x30", "60x30", "40x25", "30x10"],
    "Керамогранит": ["120x60", "60x60", "60x30", "40x40", "30x30"],
    "Клинкер":      ["40x40", "30x30", "25x5"],
}

RUSSIA_PREMIUM_BRANDS  = ["KERAMA", "ITALON", "ESTIMA", "ATLAS CONCORDE"]
EUROPE_COUNTRIES       = ["ИСПАНИЯ", "ИТАЛИЯ", "ПОЛЬША", "ГЕРМАНИЯ", "ПОРТУГАЛИЯ", "ФРАНЦИЯ"]
TURKEY_COUNTRIES       = ["ТУРЦИЯ"]
INDIA_COUNTRIES        = ["ИНДИЯ"]
CHINA_COUNTRIES        = ["КИТАЙ"]
CENTRAL_ASIA_COUNTRIES = ["КАЗАХСТАН", "УЗБЕКИСТАН", "КЫРГЫЗСТАН", "ТАДЖИКИСТАН", "ТУРКМЕНИСТАН"]

COMP_ORDER = [
    "КЕРАМИН", "Россия (премиум)", "Россия (прочие)",
    "Беларусь", "Турция", "Индия", "Китай", "Средняя Азия", "Европа", "Прочие",
]
COMP_COLORS = {
    "КЕРАМИН":          "#E63946",
    "Россия (премиум)": "#F4A261",
    "Россия (прочие)":  "#457B9D",
    "Беларусь":         "#2D6A4F",
    "Турция":           "#9B5DE5",
    "Индия":            "#E9C46A",
    "Китай":            "#2A9D8F",
    "Средняя Азия":     "#F77F00",
    "Европа":           "#06D6A0",
    "Прочие":           "#CCCCCC",
}

st.set_page_config(
    page_title="Рынок керамической плитки Беларуси",
    page_icon="🪟",
    layout="wide",
)

# ─── Загрузка данных ────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def load_data() -> pd.DataFrame:
    client = create_client(SUPABASE_URL, SUPABASE_KEY)

    def fetch_all(table: str) -> list:
        rows, page = [], 0
        while True:
            resp = (
                client.table(table)
                .select("*")
                .range(page * 1000, (page + 1) * 1000 - 1)
                .execute()
            )
            if not resp.data:
                break
            rows.extend(resp.data)
            page += 1
        return rows

    df = None

    # Попытка 1: загрузить полную историю из products + prices
    try:
        rows_prod   = fetch_all("products")
        rows_prices = fetch_all("prices")
        if rows_prod and rows_prices:
            df_prod   = pd.DataFrame(rows_prod)
            df_prices = pd.DataFrame(rows_prices)
            df = df_prices.merge(
                df_prod.drop(columns=["store"], errors="ignore"),
                on="product_id",
                how="left",
            )
    except Exception:
        df = None

    # Попытка 2: фолбэк на вью tiles_v2 (только последний период)
    if df is None or df.empty or "date" not in df.columns:
        rows_v2 = fetch_all("tiles_v2")
        df = pd.DataFrame(rows_v2) if rows_v2 else pd.DataFrame()

    # Парсинг дат и периодов
    if "date" in df.columns:
        df["date_parsed"]  = pd.to_datetime(df["date"], format="%d.%m.%Y", errors="coerce")
        df["period_label"] = df["date_parsed"].dt.strftime("%m.%Y")
    else:
        df["date_parsed"]  = pd.NaT
        df["period_label"] = "—"

    for col in ["price", "discount", "thickness", "total_stock", "total_stock_units"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Глобальный фильтр: только цены за м²
    if "price" in df.columns and "price_unit" in df.columns:
        df = df[df["price"].notna() & (df["price_unit"] == "м²")]
    return df

df = load_data()

available_periods = sorted(
    df["period_label"].dropna().unique(),
    key=lambda x: pd.to_datetime(x, format="%m.%Y"),
)

# ─── Заголовок ──────────────────────────────────────────────────────────────

st.title("Рынок керамической плитки Беларуси")
_cap_period = st.session_state.get(
    "selected_period", available_periods[-1] if available_periods else ""
)
_df_cap = df[df["period_label"] == _cap_period] if _cap_period else df
st.caption(
    f"Данные: {_df_cap['store'].nunique()} магазина  •  "
    f"{len(_df_cap):,} позиций (цена за м²)  •  "
    f"Период: {_cap_period}"
)

# ─── Session state и callbacks ───────────────────────────────────────────────

_price_min_default = int(df["price"].min()) if len(df) > 0 else 0
for _k, _v in [("pr_lo", _price_min_default), ("pr_hi", 120), ("disc_max", 30)]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

def _on_price_slider():
    lo, hi = st.session_state["_price_slider"]
    st.session_state.pr_lo = lo
    st.session_state.pr_hi = hi

def _on_disc_slider():
    st.session_state.disc_max = st.session_state["_disc_slider"]

def _assign_comp_group(brand: str, country: str) -> str:
    brand_u   = str(brand).upper()
    country_u = str(country).upper()
    if brand_u == KERAMIN_BRAND:
        return "КЕРАМИН"
    if any(brand_u.startswith(pb) for pb in RUSSIA_PREMIUM_BRANDS):
        return "Россия (премиум)"
    if country_u == "РОССИЯ":
        return "Россия (прочие)"
    if country_u == "БЕЛАРУСЬ":
        return "Беларусь"
    if country_u in TURKEY_COUNTRIES:
        return "Турция"
    if country_u in INDIA_COUNTRIES:
        return "Индия"
    if country_u in CHINA_COUNTRIES:
        return "Китай"
    if country_u in CENTRAL_ASIA_COUNTRIES:
        return "Средняя Азия"
    if country_u in EUROPE_COUNTRIES:
        return "Европа"
    return "Прочие"

def _reset_filters():
    for s in df["store"].dropna().unique():
        st.session_state[f"store_{s}"] = True
    for m in df["material"].dropna().unique():
        st.session_state[f"mat_{m}"] = True
    for m in MATERIAL_FORMATS:
        st.session_state[f"sub_fmt_{m}"] = []
    for s in df["surface_finish"].dropna().replace("", pd.NA).dropna().unique():
        st.session_state[f"sf_{s}"] = True
    st.session_state["key_formats_only"] = True
    st.session_state["fmt_pills"] = [f for f in KEY_FORMATS if f in df["format"].dropna().unique()]
    st.session_state["fmt_multi"] = []
    st.session_state["designs"] = []
    st.session_state["colors"] = []
    st.session_state["country_mode"] = "Ключевые страны"
    st.session_state["countries_pills"] = [c for c in KEY_COUNTRIES if c in df["country"].dropna().unique()]
    st.session_state["countries_multi"] = sorted(df["country"].dropna().unique())
    st.session_state.pr_lo = _price_min_default
    st.session_state.pr_hi = 120
    st.session_state["_price_slider"] = (_price_min_default, 120)
    st.session_state.disc_max = 30
    st.session_state["_disc_slider"] = 30
    st.session_state["only_with_stock"] = False

# ─── Сайдбар — фильтры ──────────────────────────────────────────────────────

with st.sidebar:
    st.header("Фильтры")

    selected_period = st.selectbox(
        "Период данных",
        options=available_periods,
        index=len(available_periods) - 1,
        key="selected_period",
    )
    st.divider()

    # Данные выбранного периода — для корректных счётчиков в фильтрах
    _df_period = df[df["period_label"] == selected_period]

    st.markdown("**Магазин**")
    store_counts = _df_period["store"].value_counts()
    stores = [
        s for s in sorted(_df_period["store"].dropna().unique())
        if st.checkbox(f"{s}  ({store_counts.get(s, 0):,})", value=True, key=f"store_{s}")
    ]

    st.divider()
    all_formats_list = sorted(_df_period["format"].dropna().unique())
    key_formats_only = st.checkbox("Только ключевые форматы", value=True, key="key_formats_only")

    st.markdown("**Материал**")
    material_counts = _df_period["material"].value_counts()
    materials = []
    sub_format_selections = {}
    for m in sorted(_df_period["material"].dropna().unique()):
        if st.checkbox(f"{m}  ({material_counts.get(m, 0):,})", value=True, key=f"mat_{m}"):
            materials.append(m)
        if key_formats_only and m in MATERIAL_FORMATS:
            mat_fmt_opts = [f for f in MATERIAL_FORMATS[m] if f in all_formats_list]
            if mat_fmt_opts:
                sel = st.pills(
                    "", options=mat_fmt_opts, selection_mode="multi", default=[],
                    label_visibility="collapsed", key=f"sub_fmt_{m}",
                )
                sub_format_selections[m] = list(sel) if sel else []

    st.markdown("**Тип поверхности**")
    sf_opts = sorted(_df_period["surface_finish"].dropna().replace("", pd.NA).dropna().unique())
    sf_counts = _df_period["surface_finish"].value_counts()
    surface_finishes = [
        s for s in sf_opts
        if st.checkbox(f"{s}  ({sf_counts.get(s, 0):,})", value=True, key=f"sf_{s}")
    ]

    st.markdown("**Формат**")
    if key_formats_only:
        fmt_opts = [f for f in KEY_FORMATS if f in all_formats_list]
        formats = st.pills(
            "", options=fmt_opts, selection_mode="multi", default=fmt_opts,
            label_visibility="collapsed", key="fmt_pills",
        )
    else:
        formats = st.multiselect("", options=all_formats_list, placeholder="Все форматы",
                                 label_visibility="collapsed", key="fmt_multi")

    designs = st.multiselect(
        "Дизайн",
        options=sorted(_df_period["primary_design"].dropna().unique()),
        placeholder="Все дизайны",
        key="designs",
    )
    colors = st.multiselect(
        "Цвет",
        options=sorted(_df_period["primary_color"].dropna().replace("", pd.NA).dropna().unique()),
        placeholder="Все цвета",
        key="colors",
    )

    st.markdown("**Страна производства**")
    country_mode = st.radio(
        "", ["Ключевые страны", "Все страны"],
        horizontal=True, key="country_mode", label_visibility="collapsed",
    )
    all_countries_list = sorted(_df_period["country"].dropna().unique())
    if country_mode == "Ключевые страны":
        country_opts = [c for c in KEY_COUNTRIES if c in all_countries_list]
        countries = st.pills(
            "Страны", options=country_opts, selection_mode="multi", default=country_opts,
            label_visibility="collapsed", key="countries_pills",
        )
    else:
        countries = st.multiselect(
            "Страна", options=all_countries_list, default=all_countries_list,
            key="countries_multi",
        )

    st.markdown("**Цена, р./м²**")
    price_max_slider = max(500, int(_df_period["price"].max()) + 10) if len(_df_period) > 0 else 500
    st.slider(
        "", 0, price_max_slider,
        (st.session_state.pr_lo, st.session_state.pr_hi),
        step=5, key="_price_slider",
        on_change=_on_price_slider,
        label_visibility="collapsed",
    )
    pc1, pc2 = st.columns(2)
    new_lo = pc1.number_input("от р.", 0, price_max_slider, st.session_state.pr_lo, step=5)
    new_hi = pc2.number_input("до р.", 0, price_max_slider, st.session_state.pr_hi, step=5)
    if int(new_lo) != st.session_state.pr_lo or int(new_hi) != st.session_state.pr_hi:
        lo_v, hi_v = int(new_lo), int(new_hi)
        if lo_v > hi_v:
            lo_v, hi_v = hi_v, lo_v
        st.session_state.pr_lo = lo_v
        st.session_state.pr_hi = hi_v
        st.session_state["_price_slider"] = (lo_v, hi_v)
        st.rerun()
    price_range = (st.session_state.pr_lo, st.session_state.pr_hi)

    st.markdown("**Макс. скидка, %**")
    st.slider(
        "", 0, 100, st.session_state.disc_max,
        step=5, key="_disc_slider",
        on_change=_on_disc_slider,
        label_visibility="collapsed",
        help="Исключить товары со скидкой выше указанного. Товары без скидки всегда включаются.",
    )
    new_disc = st.number_input("значение, %", 0, 100, st.session_state.disc_max, step=5)
    if int(new_disc) != st.session_state.disc_max:
        st.session_state.disc_max = int(new_disc)
        st.session_state["_disc_slider"] = int(new_disc)
        st.rerun()
    max_discount = st.session_state.disc_max

    only_with_stock = st.checkbox(
        "Только с остатками",
        value=False,
        key="only_with_stock",
        help="Доступно для магазинов с данными об остатках (Phase 2)",
        disabled=len(STORES_WITH_STOCK) == 0,
    )

    st.divider()
    st.button("↩ Сбросить фильтры", on_click=_reset_filters, use_container_width=True)
    st.caption("КЕРАМИН выделен красным на всех графиках")

# ─── Применение фильтров ────────────────────────────────────────────────────
# df_sidebar — все периоды, только фильтры сайдбара (используется в табе «Динамика»)
# filtered   — df_sidebar + выбранный период (используется в табах 1–5)

df_sidebar = df.copy()

if stores:
    df_sidebar = df_sidebar[df_sidebar["store"].isin(stores)]

_any_sub = any(len(v) > 0 for v in sub_format_selections.values())
if _any_sub:
    cross = pd.Series(False, index=df_sidebar.index)
    for mat, fmts in sub_format_selections.items():
        if fmts and mat in materials:
            cross |= (df_sidebar["material"] == mat) & (df_sidebar["format"].isin(fmts))
    df_sidebar = df_sidebar[cross]
else:
    if materials:
        df_sidebar = df_sidebar[df_sidebar["material"].isin(materials)]
    if formats:
        df_sidebar = df_sidebar[df_sidebar["format"].isin(formats)]

if surface_finishes:
    df_sidebar = df_sidebar[df_sidebar["surface_finish"].isin(surface_finishes)]
if designs:
    df_sidebar = df_sidebar[df_sidebar["primary_design"].isin(designs)]
if colors:
    df_sidebar = df_sidebar[df_sidebar["primary_color"].isin(colors)]
if countries:
    df_sidebar = df_sidebar[df_sidebar["country"].isin(countries)]

df_sidebar = df_sidebar[df_sidebar["price"].between(price_range[0], price_range[1])]
df_sidebar = df_sidebar[df_sidebar["discount"].isna() | (df_sidebar["discount"] <= max_discount)]

if only_with_stock and STORES_WITH_STOCK:
    df_sidebar = df_sidebar[df_sidebar["total_stock"].notna() & (df_sidebar["total_stock"] > 0)]

filtered   = df_sidebar[df_sidebar["period_label"] == selected_period].copy()
df_keramin = filtered[filtered["brand"] == KERAMIN_BRAND]
df_market  = filtered[filtered["brand"] != KERAMIN_BRAND]

# ─── ХЕЛПЕР: средневзвешенная цена ──────────────────────────────────────────

def weighted_avg_price(group: pd.DataFrame) -> float:
    g = group[group["total_stock"].notna() & (group["total_stock"] > 0)]
    if len(g) == 0 or g["total_stock"].sum() == 0:
        return group["price"].mean()
    return (g["price"] * g["total_stock"]).sum() / g["total_stock"].sum()

# ─── ХЕЛПЕР: экспорт в Excel ────────────────────────────────────────────────

def to_excel(data: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        data.to_excel(writer, index=False, sheet_name="Данные")
    return buf.getvalue()

def download_button(data: pd.DataFrame, filename: str, label: str = "Скачать Excel"):
    st.download_button(
        label=label,
        data=to_excel(data),
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

# ─── ХЕЛПЕР: bubble chart угроз ─────────────────────────────────────────────

def build_threat_bubbles(df_mkt: pd.DataFrame, df_ker: pd.DataFrame) -> pd.DataFrame:
    """Агрегирует конкурентов по format×brand_country: средн.цена, кол-во SKU, % vs КЕРАМИН."""
    keramin_median = df_ker.groupby("format")["price"].median()
    rows = []
    for (fmt, bc, grp), g in df_mkt.groupby(["format", "brand_country", "Группа"]):
        if fmt not in keramin_median.index:
            continue
        avg_price = g["price"].mean()
        sku_count = len(g)
        # Если есть остатки — используем их, иначе SKU count как прокси
        stock = g["total_stock"].sum()
        bubble_size = stock if pd.notna(stock) and stock > 0 else float(sku_count)
        k_med = keramin_median[fmt]
        pct = (avg_price - k_med) / k_med * 100
        rows.append({
            "format":         fmt,
            "brand_country":  bc,
            "Группа":         grp,
            "avg_price":      round(avg_price),
            "sku":            sku_count,
            "bubble_size":    bubble_size,
            "pct_vs_keramin": round(pct, 1),
            "k_median":       round(k_med),
        })
    return pd.DataFrame(rows)

# ─── ТАБЫ ────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Ценовой ландшафт",
    "Угрозы КЕРАМИН",
    "Позиция по форматам",
    "Поиск аналогов",
    "Данные",
    "Динамика",
])

# ════════════════════════════════════════════════════════════════════════════
# ТАБ 1 — ЦЕНОВОЙ ЛАНДШАФТ
# ════════════════════════════════════════════════════════════════════════════

with tab1:
    st.subheader("Ценовой ландшафт рынка")

    keramin_med_global = df_keramin["price"].median() if len(df_keramin) > 0 else None
    mkt_cheaper_pct = (
        (df_market["price"] < keramin_med_global).mean() * 100
        if keramin_med_global and len(df_market) > 0 else 0.0
    )

    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Позиций на рынке", f"{len(filtered):,}")
    k2.metric("Брендов", filtered["brand"].nunique())
    k3.metric("Средняя цена рынка", f"{filtered['price'].mean():.0f} р." if len(filtered) > 0 else "—")
    k4.metric("Цена КЕРАМИН (медиана)", f"{keramin_med_global:.0f} р." if keramin_med_global else "—")
    k5.metric("% рынка дешевле КЕРАМИН", f"{mkt_cheaper_pct:.1f}%")

    st.divider()

    if len(df_keramin) == 0:
        st.warning("КЕРАМИН не найден в выбранных фильтрах.")
    else:
        st.markdown("### Плотность цен по конкурентным группам")
        st.caption("Violin показывает, где реально сосредоточена масса предложений. КЕРАМИН — красные точки.")

        dp1 = filtered[filtered["price"].notna()].copy()
        dp1["Группа"] = dp1.apply(lambda r: _assign_comp_group(r["brand"], r["country"]), axis=1)

        fmt_opts1 = sorted(dp1["format"].dropna().unique())
        sel_fmt1 = st.pills(
            "Форматы", options=fmt_opts1,
            selection_mode="multi",
            default=fmt_opts1[:4] if len(fmt_opts1) >= 4 else fmt_opts1,
            key="t1_fmt_pills",
        )
        dp1_f = dp1[dp1["format"].isin(sel_fmt1)] if sel_fmt1 else dp1

        fig_vio1 = go.Figure()
        for group in COMP_ORDER:
            subset = dp1_f[dp1_f["Группа"] == group].copy()
            if len(subset) < 3:
                continue
            is_keramin = group == "КЕРАМИН"
            if is_keramin:
                cd = subset[["name", "primary_design", "primary_color"]].fillna("—").values
                hover = (
                    "<b>%{customdata[0]}</b><br>"
                    "Цена: %{y:.0f} р.<br>"
                    "Дизайн: %{customdata[1]}<br>"
                    "Цвет: %{customdata[2]}<extra></extra>"
                )
            else:
                cd = subset[["name", "brand", "primary_design", "primary_color"]].fillna("—").values
                hover = (
                    "<b>%{customdata[0]}</b><br>"
                    "Бренд: %{customdata[1]}<br>"
                    "Цена: %{y:.0f} р.<br>"
                    "Дизайн: %{customdata[2]}<br>"
                    "Цвет: %{customdata[3]}<extra></extra>"
                )
            fig_vio1.add_trace(go.Violin(
                y=subset["price"],
                name=group,
                line_color=COMP_COLORS[group],
                fillcolor=COMP_COLORS[group],
                opacity=0.8 if is_keramin else 0.35,
                points="all",
                pointpos=0,
                jitter=0.3,
                marker=dict(
                    size=7 if is_keramin else 5,
                    opacity=1.0,
                    color="#ffffff" if is_keramin else "#1a1a1a",
                    line=dict(color=COMP_COLORS[group], width=2 if is_keramin else 1),
                ),
                meanline_visible=True,
                box_visible=True,
                spanmode="soft",
                customdata=cd,
                hovertemplate=hover,
            ))
        fig_vio1.update_layout(
            yaxis_title="Цена, р./м²",
            xaxis_title="Конкурентная группа",
            violingap=0.15,
            violinmode="overlay",
            height=550,
            showlegend=False,
        )
        st.plotly_chart(fig_vio1, use_container_width=True)

        st.divider()
        st.markdown("### Распределение цен рынка")

        fig_hist1 = go.Figure()
        bin_size1 = max(5, int((dp1_f["price"].max() - dp1_f["price"].min()) / 60))
        for group in COMP_ORDER:
            subset = dp1_f[dp1_f["Группа"] == group]
            if len(subset) == 0:
                continue
            fig_hist1.add_trace(go.Histogram(
                x=subset["price"],
                name=group,
                opacity=0.7,
                marker_color=COMP_COLORS[group],
                xbins=dict(size=bin_size1),
                hovertemplate=f"<b>{group}</b><br>Цена: %{{x}}<br>Позиций: %{{y}}<extra></extra>",
            ))
        if keramin_med_global:
            fig_hist1.add_vline(
                x=keramin_med_global,
                line_dash="dash",
                line_color=COLOR_KERAMIN,
                line_width=2,
                annotation_text=f"КЕРАМИН: {keramin_med_global:.0f} р.",
                annotation_position="top right",
                annotation_font_color=COLOR_KERAMIN,
            )
        fig_hist1.update_layout(
            barmode="overlay",
            xaxis_title="Цена, р./м²",
            yaxis_title="Количество позиций",
            legend_title="Группа",
            height=420,
        )
        st.plotly_chart(fig_hist1, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# ТАБ 2 — УГРОЗЫ КЕРАМИН
# ════════════════════════════════════════════════════════════════════════════

with tab2:
    st.subheader("Угрозы КЕРАМИН")
    st.caption("Конкурентная среда вокруг цен КЕРАМИН. Дешевле с большим количеством SKU = главная угроза.")

    if len(df_keramin) == 0:
        st.warning("КЕРАМИН не найден в выбранных фильтрах.")
    else:
        dp2 = filtered[filtered["price"].notna()].copy()
        dp2["Группа"] = dp2.apply(lambda r: _assign_comp_group(r["brand"], r["country"]), axis=1)
        dp2_market  = dp2[dp2["Группа"] != "КЕРАМИН"]
        dp2_keramin = dp2[dp2["Группа"] == "КЕРАМИН"]

        threat_df = build_threat_bubbles(dp2_market, dp2_keramin)
        threat_cheaper = threat_df[threat_df["pct_vs_keramin"] < 0]

        k1, k2, k3 = st.columns(3)
        k1.metric("Конкурентов дешевле КЕРАМИН", f"{len(threat_cheaper):,}")
        k2.metric("Их позиций (SKU)",
                  f"{threat_cheaper['sku'].sum():.0f}" if len(threat_cheaper) > 0 else "0")
        k3.metric("Среднее отклонение цены",
                  f"{threat_cheaper['pct_vs_keramin'].mean():.1f}%" if len(threat_cheaper) > 0 else "—")

        st.divider()

        st.markdown("### Кто дешевле КЕРАМИН")
        st.caption(
            "Ось X: % отклонения цены от медианы КЕРАМИН (отрицательное = дешевле = угроза). "
            "Размер пузырька = кол-во SKU. Красная зона слева — зона угроз."
        )

        if len(threat_df) == 0:
            st.info("Нет данных для bubble chart.")
        else:
            size_max = threat_df["bubble_size"].max()
            sizeref2 = 2.0 * size_max / (50 ** 2) if size_max > 0 else 1.0

            fig_bubble = go.Figure()
            for group in COMP_ORDER:
                subset = threat_df[threat_df["Группа"] == group]
                if len(subset) == 0:
                    continue
                fig_bubble.add_trace(go.Scatter(
                    x=subset["pct_vs_keramin"],
                    y=subset["format"],
                    mode="markers",
                    name=group,
                    marker=dict(
                        size=subset["bubble_size"].clip(lower=1),
                        sizemode="area",
                        sizeref=sizeref2,
                        sizemin=5,
                        color=COMP_COLORS[group],
                        opacity=0.8,
                        line=dict(color="white", width=1),
                    ),
                    customdata=subset[["brand_country", "avg_price", "sku", "k_median"]].values,
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "Формат: %{y}<br>"
                        "Средняя цена: %{customdata[1]:.0f} р.<br>"
                        "Цена КЕРАМИН: %{customdata[3]:.0f} р.<br>"
                        "% vs КЕРАМИН: %{x:+.1f}%<br>"
                        "SKU: %{customdata[2]:.0f}"
                        "<extra></extra>"
                    ),
                ))
            fig_bubble.add_vline(
                x=0, line_color=COLOR_KERAMIN, line_width=2, line_dash="dash",
                annotation_text="Цена КЕРАМИН", annotation_position="top",
                annotation_font_color=COLOR_KERAMIN,
            )
            fig_bubble.add_vrect(
                x0=threat_df["pct_vs_keramin"].min() - 5, x1=0,
                fillcolor="red", opacity=0.04, line_width=0,
                annotation_text="Дешевле КЕРАМИН",
                annotation_position="top left",
            )
            fig_bubble.update_layout(
                xaxis_title="Отклонение от цены КЕРАМИН, %",
                yaxis_title="Формат",
                height=520,
                xaxis=dict(zeroline=True, zerolinecolor=COLOR_KERAMIN, zerolinewidth=2),
                legend_title="Группа",
            )
            st.plotly_chart(fig_bubble, use_container_width=True)

        st.divider()

        st.markdown("### Тепловая карта: где скапливаются конкуренты")
        st.caption(
            "Цвет = количество конкурентных позиций в ценовом диапазоне. "
            "Красные линии — цены КЕРАМИН в каждом формате."
        )

        fmt_opts2 = sorted(dp2["format"].dropna().unique())
        sel_fmt2 = st.pills(
            "Форматы для анализа", options=fmt_opts2,
            selection_mode="multi",
            default=fmt_opts2[:4] if len(fmt_opts2) >= 4 else fmt_opts2,
            key="t2_fmt_pills",
        )
        dp2_f = dp2[dp2["format"].isin(sel_fmt2)] if sel_fmt2 else dp2

        bin_step2 = st.select_slider(
            "Шаг ценового диапазона, р.", options=[5, 10, 20, 30],
            value=10, key="t2_heatmap_bin",
        )

        if sel_fmt2 and len(dp2_f) > 0:
            price_min2 = int(dp2_f["price"].min() // bin_step2 * bin_step2)
            price_max2 = int(dp2_f["price"].max() // bin_step2 * bin_step2) + bin_step2
            bins2 = range(price_min2, price_max2 + bin_step2, bin_step2)

            heat_rows2 = []
            for fmt in sel_fmt2:
                mkt_fmt = dp2_market[dp2_market["format"] == fmt]["price"]
                for b in bins2:
                    cnt = int(((mkt_fmt >= b) & (mkt_fmt < b + bin_step2)).sum())
                    heat_rows2.append({"Формат": fmt, "Цена": b, "Позиций": cnt})
            heat_df2 = pd.DataFrame(heat_rows2)
            heat_pivot2 = heat_df2.pivot(index="Цена", columns="Формат", values="Позиций").fillna(0)

            fig_heat2 = px.imshow(
                heat_pivot2,
                color_continuous_scale="Blues",
                labels={"color": "Позиций", "x": "Формат", "y": "Цена, р."},
                aspect="auto",
            )
            k_fmt_med2 = dp2_keramin[dp2_keramin["format"].isin(sel_fmt2)].groupby("format")["price"].median()
            for fmt, kprice in k_fmt_med2.items():
                x_idx = list(sel_fmt2).index(fmt) if fmt in sel_fmt2 else None
                if x_idx is not None:
                    fig_heat2.add_shape(
                        type="line", x0=x_idx - 0.5, x1=x_idx + 0.5,
                        y0=kprice, y1=kprice,
                        line=dict(color=COLOR_KERAMIN, width=3),
                    )
            fig_heat2.update_layout(height=500)
            st.plotly_chart(fig_heat2, use_container_width=True)

        st.divider()

        st.markdown("### Ценовой пояс: конкуренты в ±N% от каждой позиции КЕРАМИН")
        st.caption(
            "Для каждой позиции КЕРАМИН — сколько конкурентов находится "
            "в выбранном ценовом поясе. Показывает реальное давление."
        )

        band_pct2 = st.slider("Ширина пояса ±%", 5, 50, 20, step=5, key="t2_band_pct")

        band_rows2 = []
        for _, krow in dp2_keramin.iterrows():
            kp = krow["price"]
            lo2, hi2 = kp * (1 - band_pct2 / 100), kp * (1 + band_pct2 / 100)
            rivals2 = dp2_market[
                (dp2_market["format"] == krow["format"]) &
                (dp2_market["price"] >= lo2) &
                (dp2_market["price"] <= hi2)
            ]
            cheaper2 = rivals2[rivals2["price"] < kp]
            pricier2 = rivals2[rivals2["price"] >= kp]
            band_rows2.append({
                "Позиция":      krow.get("name", ""),
                "Формат":       krow["format"],
                "Цена КЕРАМИН": int(kp),
                f"Дешевле (±{band_pct2}%)": len(cheaper2),
                f"Дороже (±{band_pct2}%)":  len(pricier2),
                "Всего конкурентов": len(rivals2),
            })

        band_df2 = pd.DataFrame(band_rows2).sort_values("Всего конкурентов", ascending=False).reset_index(drop=True)

        fig_band2 = px.bar(
            band_df2,
            x="Позиция",
            y=[f"Дешевле (±{band_pct2}%)", f"Дороже (±{band_pct2}%)"],
            barmode="stack",
            color_discrete_map={
                f"Дешевле (±{band_pct2}%)": "#E63946",
                f"Дороже (±{band_pct2}%)":  "#457B9D",
            },
            labels={"value": "Конкурентов", "variable": ""},
            height=420,
        )
        fig_band2.update_xaxes(tickangle=45)
        st.plotly_chart(fig_band2, use_container_width=True)
        st.dataframe(
            band_df2,
            use_container_width=True,
            column_config={"Цена КЕРАМИН": st.column_config.NumberColumn(format="%d р.")},
        )


# ════════════════════════════════════════════════════════════════════════════
# ТАБ 3 — ПОЗИЦИЯ ПО ФОРМАТАМ
# ════════════════════════════════════════════════════════════════════════════

with tab3:
    st.subheader("Позиция КЕРАМИН по форматам")
    st.caption("Детальное позиционирование: средние цены конкурентов относительно КЕРАМИН.")

    if len(df_keramin) == 0:
        st.warning("КЕРАМИН не найден в выбранных фильтрах.")
    else:
        dp3 = filtered[filtered["price"].notna()].copy()
        dp3["Группа"] = dp3.apply(lambda r: _assign_comp_group(r["brand"], r["country"]), axis=1)
        dp3_market  = dp3[dp3["Группа"] != "КЕРАМИН"]
        dp3_keramin = dp3[dp3["Группа"] == "КЕРАМИН"]

        threshold3 = st.slider(
            "Порог «на уровне», %", 0, 30, 10, step=5,
            help="Бренды в диапазоне ±N% от цены КЕРАМИН считаются «на уровне»",
            key="t3_pos_threshold",
        )

        keramin_fmt_price3 = (
            dp3_keramin.groupby(["material", "format"])["price"]
            .mean()
            .reset_index(name="керамин_цена")
        )

        bc_fmt3 = (
            dp3_market.groupby(["material", "format", "Группа", "brand_country"])
            .agg(
                SKU=("price", "count"),
                Средняя_цена=("price", "mean"),
                Остаток_м2=("total_stock", "sum"),
            )
            .round({"Средняя_цена": 0, "Остаток_м2": 0})
            .reset_index()
        )
        bc_fmt3["Средняя_цена"] = bc_fmt3["Средняя_цена"].astype(int)
        bc_fmt3["Остаток_м2"]   = bc_fmt3["Остаток_м2"].fillna(0).astype(int)

        bc_fmt3 = bc_fmt3.merge(keramin_fmt_price3, on=["material", "format"], how="inner")
        bc_fmt3["vs КЕРАМИН, %"] = (
            (bc_fmt3["Средняя_цена"] - bc_fmt3["керамин_цена"]) / bc_fmt3["керамин_цена"] * 100
        ).round(1)

        def _classify3(pct: float) -> str:
            if pct < -threshold3:
                return "Дешевле"
            elif pct > threshold3:
                return "Дороже"
            return "На уровне"

        bc_fmt3["Позиция"] = bc_fmt3["vs КЕРАМИН, %"].apply(_classify3)
        bc_fmt3["керамин_цена"] = bc_fmt3["керамин_цена"].round(0).astype(int)

        grp_ord3 = {g: i for i, g in enumerate(COMP_ORDER)}
        bc_fmt3["_ord"] = bc_fmt3["Группа"].map(grp_ord3)
        bc_fmt3 = (
            bc_fmt3.sort_values(["material", "format", "_ord", "Средняя_цена"])
            .drop(columns=["_ord"])
            .reset_index(drop=True)
        )

        pos_order3 = ["Дешевле", "На уровне", "Дороже"]
        pos_counts3 = bc_fmt3["Позиция"].value_counts().reindex(pos_order3, fill_value=0)
        c1, c2, c3 = st.columns(3)
        c1.metric("Дешевле КЕРАМИН", pos_counts3["Дешевле"])
        c2.metric("На уровне",       pos_counts3["На уровне"])
        c3.metric("Дороже КЕРАМИН",  pos_counts3["Дороже"])

        sku_max3 = int(bc_fmt3["SKU"].max()) if len(bc_fmt3) > 0 else 1
        st.dataframe(
            bc_fmt3.rename(columns={
                "material": "Материал", "format": "Формат",
                "brand_country": "Бренд-страна",
                "керамин_цена": "Цена КЕРАМИН",
                "Остаток_м2": "Остаток м²",
            }),
            use_container_width=True,
            column_config={
                "Материал":      st.column_config.TextColumn("Материал"),
                "Формат":        st.column_config.TextColumn("Формат"),
                "Группа":        st.column_config.TextColumn("Группа"),
                "Бренд-страна":  st.column_config.TextColumn("Бренд-страна"),
                "SKU": st.column_config.ProgressColumn(
                    "SKU", min_value=0, max_value=sku_max3, format="%d"
                ),
                "Средняя_цена":  st.column_config.NumberColumn("Средняя цена", format="%d р."),
                "Цена КЕРАМИН":  st.column_config.NumberColumn("Цена КЕРАМИН", format="%d р."),
                "vs КЕРАМИН, %": st.column_config.NumberColumn("vs КЕРАМИН, %", format="%.1f%%"),
                "Позиция":       st.column_config.TextColumn("Позиция"),
                "Остаток м²":    st.column_config.NumberColumn("Остаток м²", format="%d"),
            },
        )
        download_button(
            bc_fmt3.rename(columns={
                "material": "Материал", "format": "Формат",
                "brand_country": "Бренд-страна",
                "керамин_цена": "Цена КЕРАМИН",
                "Остаток_м2": "Остаток м²",
            }),
            "keramin_positioning.xlsx", "Скачать Excel",
        )

        st.divider()

        st.markdown("### Плотность цен + позиции бренд-стран")
        st.caption("Форма violin = плотность. Пузырьки = бренд-страны. Размер = кол-во SKU.")

        fmt_opts3 = sorted(dp3["format"].dropna().unique())
        sel_fmt3 = st.pills(
            "Форматы", options=fmt_opts3,
            selection_mode="multi",
            default=fmt_opts3[:4] if len(fmt_opts3) >= 4 else fmt_opts3,
            key="t3_fmt_pills",
        )
        dp3_f = dp3[dp3["format"].isin(sel_fmt3)] if sel_fmt3 else dp3

        bc_agg3 = (
            dp3_f.groupby(["Группа", "brand_country"])
            .agg(avg_price=("price", "mean"), SKU=("price", "count"))
            .round({"avg_price": 0})
            .reset_index()
        )
        bc_agg3["avg_price"] = bc_agg3["avg_price"].astype(int)
        sku_max_bc = int(bc_agg3["SKU"].max()) if len(bc_agg3) > 0 else 1
        sizeref3 = 2.0 * sku_max_bc / (38 ** 2)

        fig_vio3 = go.Figure()
        for group in COMP_ORDER:
            subset3 = dp3_f[dp3_f["Группа"] == group]
            if len(subset3) < 3:
                continue
            fig_vio3.add_trace(go.Violin(
                y=subset3["price"],
                name=group,
                line_color=COMP_COLORS[group],
                fillcolor=COMP_COLORS[group],
                opacity=0.3,
                points=False,
                meanline_visible=True,
                box_visible=True,
                spanmode="soft",
                showlegend=False,
            ))
        for group in COMP_ORDER:
            subset_bc3 = bc_agg3[bc_agg3["Группа"] == group]
            if len(subset_bc3) == 0:
                continue
            fig_vio3.add_trace(go.Scatter(
                x=[group] * len(subset_bc3),
                y=subset_bc3["avg_price"],
                mode="markers",
                name=group,
                marker=dict(
                    size=subset_bc3["SKU"].tolist(),
                    sizemode="area",
                    sizeref=sizeref3,
                    sizemin=6,
                    color=COMP_COLORS[group],
                    opacity=0.85,
                    line=dict(color="white", width=1.5),
                ),
                customdata=subset_bc3[["brand_country", "avg_price", "SKU"]].values,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Средняя цена: %{customdata[1]} р.<br>"
                    "SKU: %{customdata[2]:.0f}"
                    "<extra></extra>"
                ),
                showlegend=False,
            ))
        fig_vio3.update_layout(
            yaxis_title="Цена, р./м²",
            xaxis_title="Конкурентная группа",
            violingap=0.15,
            violinmode="overlay",
            height=550,
        )
        st.plotly_chart(fig_vio3, use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# ТАБ 4 — ПОИСК АНАЛОГОВ
# ════════════════════════════════════════════════════════════════════════════

with tab4:
    st.subheader("Поиск аналогов")
    st.caption("Найдите аналоги для обоснования изменения цен — скачайте таблицу в Excel")

    c1_a, c2_a, c3_a, c4_a = st.columns(4)
    with c1_a:
        a_format = st.selectbox("Формат *", [""] + sorted(df["format"].dropna().unique()))
    with c2_a:
        a_material = st.multiselect(
            "Материал",
            sorted(df["material"].dropna().unique()),
            default=sorted(df["material"].dropna().unique()),
        )
    with c3_a:
        a_design = st.multiselect("Дизайн", sorted(df["primary_design"].dropna().unique()))
    with c4_a:
        a_color = st.multiselect("Цвет", sorted(df["primary_color"].dropna().unique()))

    c5_a, c6_a = st.columns(2)
    with c5_a:
        a_surface_finish = st.multiselect(
            "Тип поверхности (узкий)",
            sorted(df["surface_finish"].dropna().replace("", pd.NA).dropna().unique()),
            help="Полированный / Лаппатированный / Не полированный",
        )
    with c6_a:
        a_surface_type = st.multiselect(
            "Тип поверхности (широкий)",
            sorted(df["surface_type"].dropna().unique()),
            help="Более детальная классификация: Матовая, Глянцевая, Сатинированная и др.",
        )

    price_min_a = int(df["price"].min()) if len(df) > 0 else 0
    price_max_a = int(df["price"].max()) if len(df) > 0 else 500
    a_price = st.slider(
        "Диапазон цены аналогов, р./м²",
        min_value=price_min_a,
        max_value=price_max_a,
        value=(price_min_a, min(400, price_max_a)),
        step=5,
    )

    if a_format:
        analogs = df[df["format"] == a_format].copy()
        if a_material:
            analogs = analogs[analogs["material"].isin(a_material)]
        if a_surface_finish:
            analogs = analogs[analogs["surface_finish"].isin(a_surface_finish)]
        if a_surface_type:
            analogs = analogs[analogs["surface_type"].isin(a_surface_type)]
        if a_design:
            analogs = analogs[analogs["primary_design"].isin(a_design)]
        if a_color:
            analogs = analogs[analogs["primary_color"].isin(a_color)]
        analogs = analogs[analogs["price"].between(a_price[0], a_price[1])]

        st.info(f"Найдено: **{len(analogs):,}** позиций от **{analogs['brand'].nunique()}** брендов")

        if len(analogs) > 0:
            s1, s2, s3, s4 = st.columns(4)
            s1.metric("Мин. цена",  f"{analogs['price'].min():.0f} р.")
            s2.metric("Медиана",    f"{analogs['price'].median():.0f} р.")
            s3.metric("Средняя",    f"{analogs['price'].mean():.0f} р.")
            s4.metric("Макс. цена", f"{analogs['price'].max():.0f} р.")

            ACOLS = ["brand_country", "name", "format", "material", "surface_finish",
                     "surface_type", "primary_design", "primary_color", "price",
                     "discount", "availability", "store", "url"]
            acols = [c for c in ACOLS if c in analogs.columns]
            analogs_out = analogs[acols].sort_values("price").reset_index(drop=True)
            analogs_out.insert(0, "КЕРАМИН", analogs_out["brand"] == KERAMIN_BRAND if "brand" in analogs_out.columns else False)

            st.dataframe(
                analogs_out,
                use_container_width=True,
                column_config={
                    "url":      st.column_config.LinkColumn("Ссылка"),
                    "price":    st.column_config.NumberColumn("Цена", format="%.0f р."),
                    "discount": st.column_config.NumberColumn("Скидка", format="%.0f%%"),
                    "КЕРАМИН":  st.column_config.CheckboxColumn("КЕРАМИН"),
                },
            )
            download_button(
                analogs_out.drop(columns=["КЕРАМИН"], errors="ignore"),
                f"analogs_{a_format}.xlsx",
                "Скачать Excel",
            )
    else:
        st.info("Выберите формат для поиска аналогов")


# ════════════════════════════════════════════════════════════════════════════
# ТАБ 5 — ДАННЫЕ
# ════════════════════════════════════════════════════════════════════════════

with tab5:
    st.subheader("Все данные")

    DCOLS = ["name", "store", "price", "price_unit", "discount", "material", "format",
             "primary_design", "primary_color", "surface_type", "brand_country", "country",
             "availability", "url"]
    dcols = [c for c in DCOLS if c in filtered.columns]

    all_data_out = filtered[dcols].reset_index(drop=True)

    if "url" in all_data_out.columns:
        all_data_out["url"] = all_data_out["url"].fillna("").astype(str)

    col_cfg = {
        "price":    st.column_config.NumberColumn("Цена", format="%.0f р."),
        "discount": st.column_config.NumberColumn("Скидка", format="%.0f%%"),
    }
    if "url" in all_data_out.columns:
        col_cfg["url"] = st.column_config.LinkColumn("Ссылка")

    st.dataframe(all_data_out, use_container_width=True, column_config=col_cfg, height=600)
    st.caption(f"Показано {len(filtered):,} из {len(df):,} записей")
    download_button(all_data_out, "tiles_belarus.xlsx", "Скачать Excel")


# ════════════════════════════════════════════════════════════════════════════
# ТАБ 6 — ДИНАМИКА
# ════════════════════════════════════════════════════════════════════════════

with tab6:
    st.subheader("Динамика рынка")

    if len(available_periods) < 2:
        st.warning("Для анализа динамики нужно минимум два периода данных")
    else:
        # ── БЛОК 1: Сравнение двух периодов ──────────────────────────────────
        st.markdown("### Блок 1 — Сравнение двух периодов")

        col_p1, col_p2 = st.columns(2)
        with col_p1:
            period_base = st.selectbox(
                "Базовый период",
                options=available_periods,
                index=max(0, len(available_periods) - 2),
                key="dyn_period_base",
            )
        with col_p2:
            period_new = st.selectbox(
                "Новый период",
                options=available_periods,
                index=len(available_periods) - 1,
                key="dyn_period_new",
            )

        if period_base == period_new:
            st.warning("Выберите два разных периода для сравнения")
        else:
            df_base = df_sidebar[df_sidebar["period_label"] == period_base]
            df_new  = df_sidebar[df_sidebar["period_label"] == period_new]

            # ── Подблок А: Новые и исчезнувшие продукты ──────────────────────
            st.markdown("#### А — Новые и исчезнувшие товары")

            ids_base = set(df_base["product_id"].dropna())
            ids_new  = set(df_new["product_id"].dropna())
            new_ids  = ids_new - ids_base
            gone_ids = ids_base - ids_new

            mc1, mc2 = st.columns(2)
            mc1.metric("Новых товаров", len(new_ids))
            mc2.metric("Исчезнувших товаров", len(gone_ids))

            PROD_COLS = ["name", "brand", "brand_country", "format", "material", "price", "store", "url"]

            df_new_prods  = df_new[df_new["product_id"].isin(new_ids)]
            df_gone_prods = df_base[df_base["product_id"].isin(gone_ids)]

            def _show_prod_table(df_t: pd.DataFrame, title: str, fname: str):
                cols = [c for c in PROD_COLS if c in df_t.columns]
                deduped = df_t.drop_duplicates("product_id") if "product_id" in df_t.columns else df_t
                out = deduped[cols].reset_index(drop=True)
                cfg = {
                    "price": st.column_config.NumberColumn("Цена", format="%.0f р."),
                }
                if "url" in out.columns:
                    cfg["url"] = st.column_config.LinkColumn("Ссылка")
                    out["url"] = out["url"].fillna("").astype(str)
                st.markdown(f"**{title}** ({len(out):,} поз.)")
                st.dataframe(out, use_container_width=True, column_config=cfg, height=300)
                download_button(out, fname)

            t_new, t_gone = st.tabs([f"Новые ({len(new_ids):,})", f"Исчезнувшие ({len(gone_ids):,})"])
            with t_new:
                if df_new_prods.empty:
                    st.info("Нет новых товаров")
                else:
                    _show_prod_table(df_new_prods, f"Новые товары в {period_new}", f"new_products_{period_new}.xlsx")
            with t_gone:
                if df_gone_prods.empty:
                    st.info("Нет исчезнувших товаров")
                else:
                    _show_prod_table(df_gone_prods, f"Исчезнувшие товары из {period_base}", f"gone_products_{period_base}.xlsx")

            # ── Подблок Б: Изменение цен ──────────────────────────────────────
            st.markdown("#### Б — Изменение цен")

            price_b = df_base.groupby("product_id")["price"].mean().rename("price_base")
            price_n = df_new.groupby("product_id")["price"].mean().rename("price_new")
            df_chg  = price_b.to_frame().join(price_n, how="inner")
            df_chg["delta"]     = df_chg["price_new"] - df_chg["price_base"]
            df_chg["delta_pct"] = (df_chg["price_new"] / df_chg["price_base"] - 1) * 100

            _attrs = (
                df_sidebar[["product_id", "format", "material", "brand", "brand_country", "name"]]
                .drop_duplicates("product_id")
                .set_index("product_id")
            )
            df_chg = df_chg.join(_attrs)

            price_view = st.pills(
                "Разрез",
                options=["По форматам", "По типам материала", "По производителям"],
                default="По форматам",
                key="dyn_price_view",
            )

            def _price_change_charts(group_col: str, top_n: int = None):
                agg = (
                    df_chg.groupby(group_col)
                    .agg(
                        sku=("delta", "count"),
                        price_base=("price_base", "mean"),
                        price_new=("price_new", "mean"),
                        delta=("delta", "mean"),
                        delta_pct=("delta_pct", "mean"),
                    )
                    .reset_index()
                )
                if top_n:
                    agg = agg.nlargest(top_n, "sku")
                agg = agg.sort_values("delta_pct")

                # Цвет баров: зелёный — снижение, красный — рост
                def _bar_color(row):
                    if row["brand"] == KERAMIN_BRAND if "brand" in agg.columns else False:
                        return COLOR_KERAMIN
                    return "#2D6A4F" if row["delta_pct"] <= 0 else "#E63946"

                colors_bar = []
                for _, row in agg.iterrows():
                    is_keramin = (group_col == "brand_country" and KERAMIN_BRAND in str(row[group_col]))
                    if is_keramin:
                        colors_bar.append(COLOR_KERAMIN)
                    elif row["delta_pct"] <= 0:
                        colors_bar.append("#2D6A4F")
                    else:
                        colors_bar.append("#E63946")

                fig_bar = go.Figure(go.Bar(
                    x=agg[group_col],
                    y=agg["delta_pct"].round(1),
                    marker_color=colors_bar,
                    text=agg["delta_pct"].round(1).astype(str) + "%",
                    textposition="outside",
                ))
                fig_bar.update_layout(
                    xaxis_title=None, yaxis_title="Изменение цены, %",
                    height=400, margin=dict(t=20, b=20),
                    yaxis=dict(zeroline=True, zerolinewidth=2, zerolinecolor="gray"),
                )
                st.plotly_chart(fig_bar, use_container_width=True)

                tbl = agg.rename(columns={
                    group_col:    "Группа",
                    "sku":        "SKU",
                    "price_base": f"Цена {period_base} (р.)",
                    "price_new":  f"Цена {period_new} (р.)",
                    "delta":      "Δ руб.",
                    "delta_pct":  "Δ %",
                })
                tbl[f"Цена {period_base} (р.)"] = tbl[f"Цена {period_base} (р.)"].round(1)
                tbl[f"Цена {period_new} (р.)"]  = tbl[f"Цена {period_new} (р.)"].round(1)
                tbl["Δ руб."] = tbl["Δ руб."].round(1)
                tbl["Δ %"]    = tbl["Δ %"].round(1)
                st.dataframe(tbl, use_container_width=True, hide_index=True)
                download_button(
                    df_chg[[group_col, "name", "brand", "brand_country", "format",
                             "material", "price_base", "price_new", "delta", "delta_pct"]]
                    .rename(columns={"price_base": f"Цена {period_base}", "price_new": f"Цена {period_new}",
                                     "delta": "Δ руб.", "delta_pct": "Δ %"}),
                    f"price_change_{group_col}.xlsx",
                )

            if price_view == "По форматам":
                fmt_counts = df_chg.groupby("format")["delta"].count()
                valid_fmts = fmt_counts[fmt_counts >= 5].index
                df_chg_fmt = df_chg[df_chg["format"].isin(valid_fmts)]
                if df_chg_fmt.empty:
                    st.info("Недостаточно данных по форматам (нужно ≥5 продуктов)")
                else:
                    _price_change_charts.__wrapped__ = False
                    _agg = (
                        df_chg_fmt.groupby("format")
                        .agg(sku=("delta","count"), price_base=("price_base","mean"),
                             price_new=("price_new","mean"), delta=("delta","mean"), delta_pct=("delta_pct","mean"))
                        .reset_index().sort_values("delta_pct")
                    )
                    colors_bar = ["#2D6A4F" if v <= 0 else "#E63946" for v in _agg["delta_pct"]]
                    fig = go.Figure(go.Bar(x=_agg["format"], y=_agg["delta_pct"].round(1),
                        marker_color=colors_bar,
                        text=_agg["delta_pct"].round(1).astype(str)+"%", textposition="outside"))
                    fig.update_layout(xaxis_title=None, yaxis_title="Изменение цены, %", height=400,
                        margin=dict(t=20,b=20), yaxis=dict(zeroline=True,zerolinewidth=2,zerolinecolor="gray"))
                    st.plotly_chart(fig, use_container_width=True)
                    tbl = _agg.rename(columns={"format":"Формат","sku":"SKU","price_base":f"Цена {period_base} (р.)",
                        "price_new":f"Цена {period_new} (р.)","delta":"Δ руб.","delta_pct":"Δ %"})
                    for c in [f"Цена {period_base} (р.)",f"Цена {period_new} (р.)","Δ руб.","Δ %"]:
                        tbl[c] = tbl[c].round(1)
                    st.dataframe(tbl, use_container_width=True, hide_index=True)
                    download_button(df_chg_fmt[["format","name","brand","brand_country","material",
                        "price_base","price_new","delta","delta_pct"]].rename(columns={
                        "price_base":f"Цена {period_base}","price_new":f"Цена {period_new}",
                        "delta":"Δ руб.","delta_pct":"Δ %"}), "price_change_format.xlsx")

            elif price_view == "По типам материала":
                _agg = (
                    df_chg.groupby("material")
                    .agg(sku=("delta","count"), price_base=("price_base","mean"),
                         price_new=("price_new","mean"), delta=("delta","mean"), delta_pct=("delta_pct","mean"))
                    .reset_index().sort_values("delta_pct")
                )
                colors_bar = ["#2D6A4F" if v <= 0 else "#E63946" for v in _agg["delta_pct"]]
                fig = go.Figure(go.Bar(x=_agg["material"], y=_agg["delta_pct"].round(1),
                    marker_color=colors_bar,
                    text=_agg["delta_pct"].round(1).astype(str)+"%", textposition="outside"))
                fig.update_layout(xaxis_title=None, yaxis_title="Изменение цены, %", height=350,
                    margin=dict(t=20,b=20), yaxis=dict(zeroline=True,zerolinewidth=2,zerolinecolor="gray"))
                st.plotly_chart(fig, use_container_width=True)
                tbl = _agg.rename(columns={"material":"Материал","sku":"SKU","price_base":f"Цена {period_base} (р.)",
                    "price_new":f"Цена {period_new} (р.)","delta":"Δ руб.","delta_pct":"Δ %"})
                for c in [f"Цена {period_base} (р.)",f"Цена {period_new} (р.)","Δ руб.","Δ %"]:
                    tbl[c] = tbl[c].round(1)
                st.dataframe(tbl, use_container_width=True, hide_index=True)
                download_button(df_chg[["material","name","brand","brand_country","format",
                    "price_base","price_new","delta","delta_pct"]].rename(columns={
                    "price_base":f"Цена {period_base}","price_new":f"Цена {period_new}",
                    "delta":"Δ руб.","delta_pct":"Δ %"}), "price_change_material.xlsx")

            else:  # По производителям
                _agg = (
                    df_chg.groupby("brand_country")
                    .agg(sku=("delta","count"), price_base=("price_base","mean"),
                         price_new=("price_new","mean"), delta=("delta","mean"), delta_pct=("delta_pct","mean"))
                    .reset_index()
                )
                _agg = _agg.nlargest(20, "sku").sort_values("delta_pct")
                colors_bar = [COLOR_KERAMIN if KERAMIN_BRAND in str(r) else
                              ("#2D6A4F" if v <= 0 else "#E63946")
                              for r, v in zip(_agg["brand_country"], _agg["delta_pct"])]
                fig = go.Figure(go.Bar(x=_agg["brand_country"], y=_agg["delta_pct"].round(1),
                    marker_color=colors_bar,
                    text=_agg["delta_pct"].round(1).astype(str)+"%", textposition="outside"))
                fig.update_layout(xaxis_title=None, yaxis_title="Изменение цены, %", height=450,
                    margin=dict(t=20,b=20), yaxis=dict(zeroline=True,zerolinewidth=2,zerolinecolor="gray"))
                st.plotly_chart(fig, use_container_width=True)
                tbl = _agg.rename(columns={"brand_country":"Производитель","sku":"SKU",
                    "price_base":f"Цена {period_base} (р.)","price_new":f"Цена {period_new} (р.)",
                    "delta":"Δ руб.","delta_pct":"Δ %"})
                for c in [f"Цена {period_base} (р.)",f"Цена {period_new} (р.)","Δ руб.","Δ %"]:
                    tbl[c] = tbl[c].round(1)
                st.dataframe(tbl, use_container_width=True, hide_index=True)
                download_button(df_chg[["brand_country","name","brand","format","material",
                    "price_base","price_new","delta","delta_pct"]].rename(columns={
                    "price_base":f"Цена {period_base}","price_new":f"Цена {period_new}",
                    "delta":"Δ руб.","delta_pct":"Δ %"}), "price_change_brand.xlsx")

        st.divider()

        # ── БЛОК 2: Динамика за все периоды ──────────────────────────────────
        st.markdown("### Блок 2 — Динамика за все периоды")

        if len(available_periods) > 2:
            n_periods = st.slider(
                "Количество последних периодов для анализа",
                min_value=2, max_value=len(available_periods),
                value=min(len(available_periods), 6),
                key="dyn_n_periods",
                help="Периоды могут быть нерегулярными (например, квартальными)",
            )
        else:
            n_periods = 2
        selected_periods = available_periods[-n_periods:]
        df_trend = df_sidebar[df_sidebar["period_label"].isin(selected_periods)].copy()

        # ── Подблок А: Динамика числа продуктов ──────────────────────────────
        st.markdown("#### А — Динамика числа товаров и SKU")

        total_skus = (
            df_trend.groupby("period_label")["product_id"]
            .nunique()
            .reset_index()
            .rename(columns={"product_id": "total_sku"})
        )
        total_skus["period_label"] = pd.Categorical(
            total_skus["period_label"], categories=selected_periods, ordered=True
        )
        total_skus = total_skus.sort_values("period_label")

        first_seen = (
            df_sidebar.groupby("product_id")["date_parsed"]
            .min()
            .dt.strftime("%m.%Y")
            .rename("first_period")
            .reset_index()
        )
        new_by_period = (
            first_seen.groupby("first_period")["product_id"]
            .count()
            .reset_index()
            .rename(columns={"product_id": "new_products"})
        )
        new_by_period = new_by_period[new_by_period["first_period"].isin(selected_periods)]
        new_by_period["period_label"] = pd.Categorical(
            new_by_period["first_period"], categories=selected_periods, ordered=True
        )
        new_by_period = new_by_period.sort_values("period_label")
        new_by_period["cumulative_new"] = new_by_period["new_products"].cumsum()

        trend_merged = total_skus.merge(
            new_by_period[["first_period", "cumulative_new"]],
            left_on="period_label", right_on="first_period", how="left"
        )
        fig_sku = go.Figure()
        fig_sku.add_trace(go.Scatter(
            x=trend_merged["period_label"].astype(str), y=trend_merged["total_sku"],
            mode="lines+markers+text", name="Всего SKU",
            text=trend_merged["total_sku"], textposition="top center",
            line=dict(color=COLOR_MARKET, width=2),
        ))
        fig_sku.add_trace(go.Scatter(
            x=trend_merged["period_label"].astype(str), y=trend_merged["cumulative_new"],
            mode="lines+markers+text", name="Накопленно новых",
            text=trend_merged["cumulative_new"], textposition="bottom center",
            line=dict(color="#F4A261", width=2, dash="dot"),
        ))
        fig_sku.update_layout(
            xaxis_title="Период", yaxis_title="Количество товаров",
            height=350, legend=dict(orientation="h", yanchor="bottom", y=1.02),
            margin=dict(t=40, b=20),
        )
        st.plotly_chart(fig_sku, use_container_width=True)

        # ── Подблок Б: Динамика средних цен ──────────────────────────────────
        st.markdown("#### Б — Динамика средних цен")

        trend_view = st.pills(
            "Разрез",
            options=["По форматам", "По типам материала", "По производителям"],
            default="По форматам",
            key="dyn_trend_view",
        )

        def _trend_line_chart(group_col: str, groups: list, highlight: str = None):
            agg = (
                df_trend.groupby(["period_label", group_col])["price"]
                .mean()
                .reset_index()
            )
            agg = agg[agg[group_col].isin(groups)]
            agg["period_label"] = pd.Categorical(
                agg["period_label"], categories=selected_periods, ordered=True
            )
            agg = agg.sort_values("period_label")

            fig = go.Figure()
            for grp in groups:
                sub = agg[agg[group_col] == grp]
                if sub.empty:
                    continue
                is_keramin = highlight and KERAMIN_BRAND in str(grp)
                fig.add_trace(go.Scatter(
                    x=sub["period_label"].astype(str), y=sub["price"].round(1),
                    mode="lines+markers",
                    name=str(grp),
                    line=dict(
                        color=COLOR_KERAMIN if is_keramin else None,
                        width=3 if is_keramin else 1.5,
                    ),
                    hovertemplate=f"{grp}<br>Период: %{{x}}<br>Средняя цена: %{{y:.1f}} р.<extra></extra>",
                ))
            fig.update_layout(
                xaxis_title="Период", yaxis_title="Средняя цена, р.",
                height=420, legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                        font=dict(size=10)),
                margin=dict(t=50, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

        last_period = selected_periods[-1]
        if trend_view == "По форматам":
            _trend_line_chart("format", KEY_FORMATS)
        elif trend_view == "По типам материала":
            all_mats = sorted(df_trend["material"].dropna().unique())
            _trend_line_chart("material", all_mats)
        else:
            top10_bc = (
                df_trend[df_trend["period_label"] == last_period]
                .groupby("brand_country")["product_id"].nunique()
                .nlargest(10).index.tolist()
            )
            if KERAMIN_BRAND not in " ".join(top10_bc):
                keramin_bc = df_trend[df_trend["brand"] == KERAMIN_BRAND]["brand_country"].dropna().unique()
                top10_bc = list(keramin_bc) + [b for b in top10_bc if KERAMIN_BRAND not in str(b)]
            _trend_line_chart("brand_country", top10_bc, highlight=KERAMIN_BRAND)

        # ── Подблок В: Тепловая карта изменений цен ──────────────────────────
        st.markdown("#### В — Тепловая карта изменений цен, %")

        heatmap_view = st.pills(
            "Разрез",
            options=["По форматам", "По производителям"],
            default="По форматам",
            key="dyn_heatmap_view",
        )

        def _heatmap(group_col: str, groups: list):
            agg = (
                df_trend.groupby(["period_label", group_col])["price"]
                .mean()
                .reset_index()
            )
            agg = agg[agg[group_col].isin(groups)]
            pivot = agg.pivot(index=group_col, columns="period_label", values="price")
            # Хронологическая сортировка колонок
            pivot = pivot[sorted(pivot.columns, key=lambda x: pd.to_datetime(x, format="%m.%Y"))]
            # % изменения к предыдущему периоду
            pivot_pct = pivot.pct_change(axis=1) * 100
            pivot_pct_rounded = pivot_pct.round(1)

            # Заменяем NaN на None для отображения серым
            z      = pivot_pct_rounded.values.tolist()
            text_z = [
                [f"{v:.1f}%" if pd.notna(v) else "" for v in row]
                for row in pivot_pct_rounded.values
            ]

            fig = go.Figure(go.Heatmap(
                z=z,
                x=list(pivot_pct_rounded.columns),
                y=list(pivot_pct_rounded.index),
                text=text_z,
                texttemplate="%{text}",
                colorscale=[
                    [0.0, "#2D6A4F"],   # зелёный — снижение
                    [0.5, "#FFFFFF"],   # белый — без изменений
                    [1.0, "#E63946"],   # красный — рост
                ],
                zmid=0,
                colorbar=dict(title="Δ %"),
            ))
            fig.update_layout(
                xaxis_title="Период", yaxis_title=None,
                height=max(300, len(groups) * 30 + 100),
                margin=dict(t=20, b=20),
            )
            st.plotly_chart(fig, use_container_width=True)

        if heatmap_view == "По форматам":
            _heatmap("format", KEY_FORMATS)
        else:
            top20_bc = (
                df_trend[df_trend["period_label"] == last_period]
                .groupby("brand_country")["product_id"].nunique()
                .nlargest(20).index.tolist()
            )
            _heatmap("brand_country", top20_bc)
