import streamlit as st
import psycopg2
from datetime import datetime, timedelta
import math
import pandas as pd

# Set page to wide mode
st.set_page_config(layout="wide")

# --- Constants ---
TARGET_POMODOROS = 13000  # Total intended Pomodoros
PAGE_SIZE = 100           # Number of rows to display at once

# Get credentials from secrets
db_config = st.secrets["postgres"]

def get_connection():
    return psycopg2.connect(
        host=db_config.host,
        dbname=db_config.dbname,
        user=db_config.user,
        password=db_config.password
    )

def init_db():
    """Initialize the PostgreSQL database and table if it doesn't exist."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pomodoros (
            id SERIAL PRIMARY KEY,
            description TEXT,
            timestamp TIMESTAMP
        )
    """)
    conn.commit()
    cursor.close()
    conn.close()

def add_pomodoro(description: str):
    """Insert a new Pomodoro with a description and the current timestamp."""
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.now()
    cursor.execute("INSERT INTO pomodoros (description, timestamp) VALUES (%s, %s)", (description, now))
    conn.commit()
    cursor.close()
    conn.close()

def remove_pomodoro(pomo_id: int):
    """Remove a Pomodoro record by its database ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM pomodoros WHERE id = %s", (pomo_id,))
    conn.commit()
    cursor.close()
    conn.close()

def get_all_pomodoros():
    """Retrieve all completed Pomodoro records (id, description, timestamp)."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, description, timestamp FROM pomodoros ORDER BY id ASC")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return data

def get_total_pomodoros() -> int:
    """Return the count of completed Pomodoros."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pomodoros")
    count = cursor.fetchone()[0]
    cursor.close()
    conn.close()
    return count

def get_last_description() -> str:
    """Return the description from the most recent Pomodoro, if available."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT description FROM pomodoros ORDER BY id DESC LIMIT 1")
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    return row[0] if row else ""

def count_pomodoros_since(days: int) -> int:
    """Return how many pomodoros have been completed in the last `days` days."""
    cutoff = datetime.now() - timedelta(days=days)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT timestamp FROM pomodoros")
    rows = cursor.fetchall()
    cursor.close()
    conn.close()

    count = 0
    for (ts,) in rows:
        if ts >= cutoff:
            count += 1
    return count

# Initialize the database
init_db()

# --- Sidebar: Add a Pomodoro ---
st.sidebar.header("Add a Pomodoro")
default_desc = get_last_description()
with st.sidebar.form("add_pomo_form"):
    desc_input = st.text_input("What did you work on?", value=default_desc,
                               placeholder="e.g., Studied spiking neural networks")
    if st.form_submit_button("Add Pomodoro"):
        if desc_input.strip():
            add_pomodoro(desc_input)
            st.sidebar.success("Pomodoro added!")
            # Soft "rerun" via st.query_params
            qp = dict(st.query_params)  # Convert to dict
            qp["updated"] = str(datetime.now().timestamp())
            st.query_params = qp        # Assign back to st.query_params
        else:
            st.sidebar.error("Please enter a description.")

# --- Main Title & Stats ---
st.title("My work on spiking networks")

completed_count = get_total_pomodoros()
st.subheader(f"Completed Pomodoros: {completed_count} / {TARGET_POMODOROS}")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Last 7 Days", count_pomodoros_since(7))
col2.metric("Last 30 Days", count_pomodoros_since(30))
col3.metric("Last 365 Days", count_pomodoros_since(365))
col4.metric("Total (All Time)", completed_count)

# --- Retrieve all COMPLETED Pomodoros ---
pomodoros = get_all_pomodoros()  # list of (id, description, timestamp)
df = pd.DataFrame(pomodoros, columns=["ID", "Description", "Timestamp"])

# Add a "Status" column with a green checkmark
df["Status"] = "✅"

total_completed = len(df)
if total_completed == 0:
    # Nothing to show, just inform user
    st.info("No completed Pomodoros yet. Add one in the sidebar!")
    st.stop()

# --- Pagination Setup ---
PAGE_SIZE = 100
total_pages = math.ceil(total_completed / PAGE_SIZE)

qp = dict(st.query_params)  # Convert query_params to dict
if "page" not in qp:
    # default: go to last page
    current_page = total_pages
else:
    try:
        current_page = int(qp["page"][0])  # query params are lists
        if current_page < 1:
            current_page = 1
        elif current_page > total_pages:
            current_page = total_pages
    except:
        current_page = total_pages

# Slice for current page
start_index = (current_page - 1) * PAGE_SIZE
end_index = start_index + PAGE_SIZE
page_data = df.iloc[start_index:end_index]

# --- Display a Paginated Table with "Delete" Buttons ---
st.markdown("### Tasks")

# Table header
header_cols = st.columns([1, 4, 3, 1, 1])
header_cols[0].markdown("**ID**")
header_cols[1].markdown("**Description**")
header_cols[2].markdown("**Timestamp**")
header_cols[3].markdown("**Status**")
header_cols[4].markdown("**Delete**")

for idx, row in page_data.iterrows():
    row_cols = st.columns([1, 4, 3, 1, 1])
    row_id = row["ID"]
    row_cols[0].write(row_id)
    row_cols[1].write(row["Description"])
    row_cols[2].write(row["Timestamp"])
    row_cols[3].write(row["Status"])
    if row_cols[4].button("Delete", key=f"del_{row_id}"):
        remove_pomodoro(row_id)
        # Trigger re-run by modifying query params
        new_qp = dict(st.query_params)
        new_qp["updated"] = str(datetime.now().timestamp())
        st.query_params = new_qp
        st.stop()  # End execution so we don't proceed with stale data

# --- Pagination Controls (Below the Table) ---
col_left, col_mid, col_right = st.columns([1, 2, 1])

with col_left:
    if current_page > 1:
        if st.button("Previous"):
            new_qp = dict(st.query_params)
            new_qp["page"] = str(current_page - 1)
            st.query_params = new_qp

with col_mid:
    # Dropdown to jump to a specific page
    selected_page = st.selectbox(
        f"Jump to Page (1–{total_pages})",
        list(range(1, total_pages + 1)),
        index=(current_page - 1)  # 0-based index
    )
    if selected_page != current_page:
        new_qp = dict(st.query_params)
        new_qp["page"] = str(selected_page)
        st.query_params = new_qp

with col_right:
    if current_page < total_pages:
        if st.button("Next"):
            new_qp = dict(st.query_params)
            new_qp["page"] = str(current_page + 1)
            st.query_params = new_qp
