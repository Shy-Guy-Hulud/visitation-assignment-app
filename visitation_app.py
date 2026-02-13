import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import requests

# --- 1. SESSION STATE FOR LOGIN ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

# --- 2. PASSWORD CHECK ---
if not st.session_state["authenticated"]:
    st.title("🔐 Secure Access")
    pwd_input = st.text_input("Enter Password", type="password")
    if st.button("Login"):
        if pwd_input == st.secrets["APP_PASSWORD"]:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()  # Stop execution here if not logged in

# --- 3. CONFIG & DATA (Only runs if logged in) ---
st.set_page_config(page_title="Officer Assignments", page_icon="📋")


@st.cache_data
def get_sheet_data():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    # Using secrets for credentials dictionary
    creds = Credentials.from_service_account_info(st.secrets["google_credentials"], scopes=scopes)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk").sheet1
    return sheet.get_all_values()


all_rows = get_sheet_data()
names = sorted(list(set(
    row[6].strip()
    for row in all_rows[4:]
    if len(row) > 6 and row[6].strip() != ""
)))

# --- 4. THE MAIN UI ---
st.title("📋 Visitation Assignments")
st.write(f"Welcome back! Found **{len(names)}** officers in the sheet.")

# Select All Option
send_all = st.checkbox("Select all officers")

if send_all:
    selected_officers = names
    st.info(f"Ready to send to all {len(names)} officers.")
else:
    selected_officers = st.multiselect("Select specific officers:", options=names)


def escape_html(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- 5. SENDING LOGIC ---
if st.button("🚀 Send Assignments", type="primary"):
    if not selected_officers:
        st.warning("Please select at least one officer or check 'Select all'.")
    else:
        progress_bar = st.progress(0)

        for i, officer in enumerate(selected_officers):
            matches = []
            target_name = officer.strip().lower()
            recipient_id = st.secrets["USER_MAP"].get(officer, st.secrets["DEFAULT_CHAT_ID"])

            for row in all_rows[4:]:
                if len(row) > 6 and row[6].strip().lower() == target_name:
                    col_a = escape_html(row[0])
                    col_b = escape_html(row[1])
                    col_f = escape_html(row[5])
                    matches.append(f"📍 {col_a}, {col_b}\n-----☎️ {col_f}")

            if matches:
                body = "\n".join(matches)
                sheet_url = "https://docs.google.com/spreadsheets/d/1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk/edit?usp=sharing"
                final_text = (
                    f"📋 <b>Assignments for {officer}:</b>\n\n"
                    f"{body}\n\n"
                    f'🔗 <a href="{sheet_url}">View Spreadsheet</a>'
                )

                payload = {
                    "chat_id": recipient_id,
                    "text": final_text,
                    "parse_mode": "HTML",
                    "link_preview_options": {"is_disabled": True}
                }

                requests.post(f"https://api.telegram.org/bot{st.secrets['TELEGRAM_TOKEN']}/sendMessage", json=payload)

            progress_bar.progress((i + 1) / len(selected_officers))

        st.success("Finished processing all assignments!")
        st.balloons()

if st.button("Logout"):
    st.session_state["authenticated"] = False
    st.rerun()