"""CMYGO Dashboard — Streamlit UI for shinagaki collection tracking.

Launch: uv run --group dashboard streamlit run dashboard.py
"""

import sqlite3
from pathlib import Path

import streamlit as st
import yaml

# ---------------------------------------------------------------------------
# Config & DB helpers
# ---------------------------------------------------------------------------

def load_config(config_path: str = "config.yaml") -> dict:
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_db_path(config: dict) -> Path:
    raw = config
    for k in "paths.database".split("."):
        raw = raw.get(k)
        if raw is None:
            return Path("data/database.db")
    p = Path(raw)
    if not p.is_absolute():
        p = Path.cwd() / p
    return p


@st.cache_resource
def get_connection(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def query(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> list[dict]:
    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="CMYGO Dashboard",
    page_icon="📦",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    /* Metric cards */
    [data-testid="stMetric"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem 1.25rem;
        border-radius: 12px;
        color: white;
    }
    [data-testid="stMetric"] label {
        color: rgba(255,255,255,0.85) !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: white !important;
        font-weight: 700;
    }
    [data-testid="stMetric"] [data-testid="stMetricDelta"] {
        color: rgba(255,255,255,0.9) !important;
    }

    /* Progress bar */
    .progress-container {
        background: #e9ecef;
        border-radius: 8px;
        overflow: hidden;
        height: 28px;
        margin: 0.5rem 0 1rem;
    }
    .progress-bar {
        height: 100%;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-weight: 600;
        font-size: 13px;
        color: white;
        transition: width 0.4s ease;
    }

    /* Table tweaks */
    .dataframe th {
        background-color: #f8f9fa !important;
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

config = load_config()
db_path = get_db_path(config)

if not db_path.exists():
    st.error(f"数据库不存在: `{db_path}`")
    st.info("请先运行 `uv run python main.py migrate` 初始化数据库。")
    st.stop()

conn = get_connection(str(db_path))

# Get available events
events = query(conn, """
    SELECT DISTINCT event_name FROM comike_info ORDER BY event_name DESC
""")
event_names = [e["event_name"] for e in events]

if not event_names:
    st.warning("数据库中没有活动数据。请先运行 `uv run python main.py sync`。")
    st.stop()

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("📦 CMYGO")
    st.caption("品書收集管理工具")
    st.divider()

    selected_event = st.selectbox("🎌 选择活动", event_names, index=0)

    st.divider()

    # Stats summary
    total_circles = query(conn, "SELECT COUNT(*) as c FROM circles")[0]["c"]
    total_comike = query(
        conn,
        "SELECT COUNT(*) as c FROM comike_info WHERE event_name = ?",
        (selected_event,),
    )[0]["c"]
    cached_visions = query(conn, "SELECT COUNT(*) as c FROM vision_cache")[0]["c"]
    total_captures = query(conn, "SELECT COUNT(*) as c FROM captures")[0]["c"]

    st.metric("数据库社团数", total_circles)
    st.metric(f"{selected_event} 收藏数", total_comike)
    if total_captures > 0:
        st.metric("捕获入库", total_captures)
    if cached_visions > 0:
        st.metric("Vision 缓存", cached_visions)

    st.divider()
    st.caption("启动方式: `uv run --group dashboard streamlit run dashboard.py`")

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab_progress, tab_search, tab_pending, tab_captures, tab_vision = st.tabs(
    ["📊 收集进度", "🔍 社团搜索", "📋 待收集列表", "📸 捕获记录", "🤖 Vision 缓存"]
)

# ---------------------------------------------------------------------------
# Tab 1: Collection Progress
# ---------------------------------------------------------------------------

with tab_progress:
    st.header(f"📊 {selected_event} 收集进度")

    # Get all comike_info for this event
    all_comike = query(
        conn,
        "SELECT * FROM comike_info WHERE event_name = ? ORDER BY booth",
        (selected_event,),
    )

    # Get existing booth numbers from shinagaki directory
    shinagaki_dir = Path(config.get("paths", {}).get("shinagaki_dir", "data/shinagaki"))
    if not shinagaki_dir.is_absolute():
        shinagaki_dir = Path.cwd() / shinagaki_dir
    processed_dir = shinagaki_dir / config.get("paths", {}).get(
        "processed_subdir_name", "已处理"
    )

    existing_booths: set[str] = set()
    for scan_dir in [shinagaki_dir, processed_dir]:
        if scan_dir.exists():
            for fn in scan_dir.iterdir():
                if fn.is_file() and fn.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                    base = fn.stem.strip()
                    if base:
                        booth = base.split()[0]
                        existing_booths.add(booth)

    total = len(all_comike)
    collected = sum(
        1 for r in all_comike
        if r.get("booth") and r["booth"].strip() in existing_booths
    )
    remaining = total - collected
    pct = (collected / total * 100) if total > 0 else 0

    # Metrics row
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总收藏数", total)
    col2.metric("已收集", collected, delta=f"{pct:.0f}%")
    col3.metric("待收集", remaining)
    col4.metric("匹配率", f"{pct:.1f}%")

    # Custom progress bar
    bar_color = "#28a745" if pct >= 80 else "#ffc107" if pct >= 50 else "#dc3545"
    st.markdown(f"""
    <div class="progress-container">
        <div class="progress-bar" style="width: {max(pct, 2)}%; background: {bar_color};">
            {collected}/{total}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Per-color breakdown
    st.subheader("按颜色分组")
    color_stats: dict[str, dict] = {}
    for row in all_comike:
        color = (row.get("color") or "").strip() or "无颜色"
        if color not in color_stats:
            color_stats[color] = {"total": 0, "collected": 0}
        color_stats[color]["total"] += 1
        if row.get("booth") and row["booth"].strip() in existing_booths:
            color_stats[color]["collected"] += 1

    if color_stats:
        cols = st.columns(min(len(color_stats), 4))
        for i, (color, stats) in enumerate(sorted(color_stats.items())):
            c_pct = (stats["collected"] / stats["total"] * 100) if stats["total"] > 0 else 0
            with cols[i % len(cols)]:
                st.metric(
                    color,
                    f"{stats['collected']}/{stats['total']}",
                    delta=f"{c_pct:.0f}%",
                )

# ---------------------------------------------------------------------------
# Tab 2: Circle Search
# ---------------------------------------------------------------------------

with tab_search:
    st.header("🔍 社团搜索")

    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        search_query = st.text_input(
            "搜索",
            placeholder="输入社团名、Twitter ID 或作者名...",
            label_visibility="collapsed",
        )
    with search_col2:
        search_scope = st.selectbox(
            "搜索范围",
            ["circles 数据库", f"{selected_event} 收藏"],
            label_visibility="collapsed",
        )

    if search_query:
        q = f"%{search_query}%"
        if search_scope == "circles 数据库":
            results = query(conn, """
                SELECT name, name_alt, twitter_id, twitter_id_alt,
                       twitter_url, pixiv_url, identifier, author
                FROM circles
                WHERE name LIKE ? OR name_alt LIKE ?
                   OR twitter_id LIKE ? OR twitter_id_alt LIKE ?
                   OR author LIKE ? OR identifier LIKE ?
                ORDER BY name
                LIMIT 100
            """, (q, q, q, q, q, q))
        else:
            results = query(conn, """
                SELECT booth, circle_name, author, notes, color, detail_url
                FROM comike_info
                WHERE event_name = ?
                  AND (circle_name LIKE ? OR author LIKE ?
                       OR booth LIKE ? OR notes LIKE ?)
                ORDER BY booth
                LIMIT 100
            """, (selected_event, q, q, q, q))

        if results:
            st.success(f"找到 {len(results)} 条结果")
            st.dataframe(results, use_container_width=True, hide_index=True)
        else:
            st.info("未找到匹配结果")
    else:
        st.caption("输入关键词开始搜索。支持社团名、Twitter ID、作者名、摊位号。")

# ---------------------------------------------------------------------------
# Tab 3: Pending Collection List
# ---------------------------------------------------------------------------

with tab_pending:
    st.header(f"📋 {selected_event} 待收集列表")

    # Filter by color
    available_colors = sorted(set(
        (r.get("color") or "").strip() or "无颜色"
        for r in all_comike
    ))
    selected_colors = st.multiselect(
        "按颜色筛选",
        available_colors,
        default=available_colors,
    )

    pending_rows = []
    for row in all_comike:
        booth = (row.get("booth") or "").strip()
        if not booth or booth in existing_booths:
            continue
        color = (row.get("color") or "").strip() or "无颜色"
        if color not in selected_colors:
            continue
        pending_rows.append({
            "摊位": booth,
            "社团": row.get("circle_name", ""),
            "作者": row.get("author", ""),
            "颜色": color,
            "备注": row.get("notes", ""),
            "详情": row.get("detail_url", ""),
        })

    st.info(f"待收集: {len(pending_rows)} 个社团")

    if pending_rows:
        st.dataframe(
            pending_rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "详情": st.column_config.LinkColumn("详情", display_text="查看"),
            },
        )

        # Download as CSV
        import csv
        import io

        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, fieldnames=pending_rows[0].keys())
        writer.writeheader()
        writer.writerows(pending_rows)
        st.download_button(
            "📥 下载 CSV",
            csv_buffer.getvalue(),
            file_name=f"{selected_event}_pending.csv",
            mime="text/csv",
        )

# ---------------------------------------------------------------------------
# Tab 4: Captures
# ---------------------------------------------------------------------------

with tab_captures:
    st.header("📸 捕获记录")

    captures_data = query(conn, """
        SELECT twitter_id, tweet_url, tweet_text,
               image_filename, captured_at, ingested_at
        FROM captures
        ORDER BY ingested_at DESC
        LIMIT 200
    """)

    if not captures_data:
        st.info(
            "暂无捕获记录。安装 Chrome 插件 CMYGO Capture 后，"
            "在 X/Twitter 上点击 📦 按钮捕获品书，然后运行 "
            "`python main.py ingest` 入库。"
        )
    else:
        st.success(f"共 {len(captures_data)} 条捕获记录")

        display_rows = []
        for row in captures_data:
            text_preview = (row.get("tweet_text") or "")[:80]
            if len(row.get("tweet_text") or "") > 80:
                text_preview += "..."
            display_rows.append({
                "Twitter ID": row.get("twitter_id", "-"),
                "图片": row.get("image_filename", "-"),
                "推文内容": text_preview,
                "捕获时间": row.get("captured_at", "-"),
                "推文链接": row.get("tweet_url", ""),
            })

        st.dataframe(
            display_rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "推文链接": st.column_config.LinkColumn("推文链接", display_text="打开"),
            },
        )

# ---------------------------------------------------------------------------
# Tab 5: Vision Cache
# ---------------------------------------------------------------------------

with tab_vision:
    st.header("🤖 Vision 识别缓存")

    vision_data = query(conn, """
        SELECT image_hash, result_json, confidence, created_at
        FROM vision_cache
        ORDER BY created_at DESC
        LIMIT 100
    """)

    if not vision_data:
        st.info("暂无 Vision 识别记录。启用 Vision LLM 后运行 rename 即可。")
    else:
        st.success(f"共 {len(vision_data)} 条识别记录")

        import json

        display_rows = []
        for row in vision_data:
            try:
                result = json.loads(row["result_json"])
            except (json.JSONDecodeError, TypeError):
                result = {}

            display_rows.append({
                "hash": row["image_hash"][:12] + "...",
                "摊位": result.get("booth") or "-",
                "社团": result.get("circle_name") or "-",
                "作者": result.get("author") or "-",
                "Twitter": result.get("twitter_id") or "-",
                "置信度": f"{row.get('confidence', 0):.2f}",
                "时间": row.get("created_at", "-"),
            })

        st.dataframe(display_rows, use_container_width=True, hide_index=True)

        # Stats
        confidences = [
            row.get("confidence", 0) for row in vision_data if row.get("confidence")
        ]
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            high_conf = sum(1 for c in confidences if c >= 0.8)
            st.caption(
                f"平均置信度: {avg_conf:.2f} | "
                f"高置信度 (≥0.8): {high_conf}/{len(confidences)}"
            )
