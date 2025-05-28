import streamlit as st
from supabase import create_client, Client
import os
from dotenv import load_dotenv
from datetime import date, datetime
import pandas as pd

load_dotenv()

# --- Streamlit Page Setup ---
st.markdown(""" 
<style>
    .title {
        text-align: center;
        color: #0ADD08;
        font-size: 2em;
        font-weight: bold;
        border: 4px solid;
        padding: 5px;
        animation: colorChange 10s infinite;
        border-radius: 10px;
    }
    .signature {
        position: absolute;
        right: 10px;
        bottom: -50px;
        font-family: 'Georgia', 'Times New Roman', serif;
        font-size: 1em;
        color: #FF;
        font-style: italic;
    }
    @keyframes colorChange {
        0% { color: #0ADD08; }
        25% { color: #FFD700; }
        50% { color: #FF4500; }
        75% { color: #1E90FF; }
        100% { color: #0ADD08; }
    }
</style>
<div class="title">💸 Expense Tracker</div>
<div class="signature">Made By Daanyaal</div>
""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("---")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Functions ---
def generate_custom_id(txn_date: str):
    date_part = txn_date.replace("-", "")
    timestamp_part = datetime.now().strftime("%H%M%S%f")[:-3]  # e.g., 143205123
    return f"TXN-{date_part}-{timestamp_part}"

def get_transactions():
    return supabase.table("Transactions").select("*").order("date", desc=True).execute().data

def bulk_update(transactions_to_update):
    updates = []
    for txn in transactions_to_update:
        updates.append({"id": txn["id"], **txn})
    for txn in updates:
        txn_id = txn.pop("id")
        supabase.table("Transactions").update(txn).eq("id", txn_id).execute()

def bulk_delete(ids_to_delete):
    for txn_id in ids_to_delete:
        supabase.table("Transactions").delete().eq("id", txn_id).execute()

def bulk_add(new_transactions):
    if new_transactions:
        for txn in new_transactions:
            if "id" not in txn:
                txn["id"] = generate_custom_id(txn["date"])
        supabase.table("Transactions").insert(new_transactions).execute()

with st.expander("**Transaction Form:**", expanded=True):
    # --- Add Transaction Section ---
    with st.form("add_transaction_form"):
        st.subheader("➕ Add New Transaction")
        amount = st.number_input("Amount", min_value=0.0, format="%.2f", step=0.01)
        transaction_type = st.selectbox("Transaction Type", ["Expense", "Income"])
        category = st.text_input("Category")
        payment_method = st.selectbox("Payment Method", ["Cash", "Card", "UPI", "Bank Transfer"])
        description = st.text_input("Description (optional)")
        transaction_date = st.date_input("Date", value=date.today())
        submitted = st.form_submit_button("✅ Add Transaction")
        if submitted and amount > 0 and category and payment_method:
            if "new_txns" not in st.session_state:
                st.session_state.new_txns = []
            txn_date_str = transaction_date.isoformat()
            st.session_state.new_txns.append({
                "id": generate_custom_id(txn_date_str),
                "amount": amount,
                "transaction_type": transaction_type,
                "category": category,
                "payment_method": payment_method,
                "description": description,
                "date": txn_date_str,
                "synced": False
            })
            st.success("**Transaction Queued. Click 'Save All Changes' To Persist.**")

st.markdown("---")

with st.expander("**Transaction History:**", expanded=True):
    # --- Display and Edit Table ---
    st.subheader("📋 Your Transactions")

    transactions = get_transactions() or []

    # Include unsaved transactions from session_state with temp IDs
    if "new_txns" in st.session_state:
        for i, txn in enumerate(st.session_state.new_txns):
            txn_display = txn.copy()
            txn_display["id"] = f"new_{i}"  # Assign temporary string ID for display
            transactions.append(txn_display)

    if transactions:
        df = pd.DataFrame(transactions)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df["amount"] = df["amount"].map(lambda x: float(f"{float(x):.2f}"))  # Ensure numeric with 2 decimal places

        # Create a string column for visual display in editor (Emoji-based workaround)
        def format_synced_label(val):
            if val is True:
                return "🟢 Synced"
            elif val is False:
                return "🟡 In Progress"
            return "❓ Unknown"

        df["synced_label"] = df["synced"].apply(format_synced_label)

        # Include in editable table with visual label
        edited_df = st.data_editor(
            df[["id", "amount", "transaction_type", "category", "payment_method", "description", "date", "synced_label"]],
            num_rows="fixed",
            use_container_width=True,
            column_config={
                "transaction_type": st.column_config.SelectboxColumn("Transaction Type", options=["Expense", "Income"]),
                "payment_method": st.column_config.SelectboxColumn("Payment Method", options=["Cash", "Card", "UPI", "Bank Transfer"]),
                "date": st.column_config.DateColumn("Date"),
                "amount": st.column_config.NumberColumn("Amount", format="%.2f"),
                "synced_label": st.column_config.TextColumn("Status"),
            },
            disabled=["id", "synced_label"]
        )

        deleted_rows = st.multiselect("Select Transactions To Delete", df["id"].tolist())

        if st.button("📏 Save All Changes"):
            with st.spinner("**Saving All Changes...**"):
                updated_txns = []
                new_txns_to_add = []
    
                for _, row in edited_df.iterrows():
                    txn_data = {
                        "amount": float(row["amount"]),
                        "transaction_type": row["transaction_type"],
                        "category": row["category"],
                        "payment_method": row["payment_method"],
                        "description": row["description"],
                        "date": row["date"].isoformat() if isinstance(row["date"], datetime) else str(row["date"]),
                        "synced": True
                    }
    
                    if str(row["id"]).startswith("new_"):
                        new_txns_to_add.append(txn_data)
                    else:
                        txn_data["id"] = row["id"]
                        updated_txns.append(txn_data)
    
                bulk_update(updated_txns)
                bulk_delete([txn_id for txn_id in deleted_rows if not str(txn_id).startswith("new_")])
                bulk_add(new_txns_to_add)
    
                if "new_txns" in st.session_state:
                    st.session_state.new_txns.clear()
    
                st.success("**All Changes Saved.**")
                st.rerun()
    else:
        st.info("**No Transactions Available.**")

