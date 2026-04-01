import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import datetime
import requests

# --- CONSTANTS ---
SPREADSHEET_ID = "1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk"

def send_telegram_message(message, chat_id):
    """Sends a notification via your existing Telegram bot."""
    token = st.secrets["TELEGRAM_TOKEN"] # Updated key
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload)
    except Exception as e:
        st.error(f"Failed to send Telegram notification: {e}")

# 1. Page Config (Best to have this at the very top)
st.set_page_config(page_title="Visitation App", page_icon="👤")

# --- 1. SESSION STATE & LOGIN ---
if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔐 Visitation App")
    with st.form("login_form"):
        pwd_input = st.text_input("Enter Access Code", type="password")
        if st.form_submit_button("Login"):
            if pwd_input == st.secrets["APP_PASSWORD"]:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Invalid Code")
    st.stop()


# --- 2. DATA FETCHING ---
@st.cache_resource
def get_sheet_client():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]

    # Load the dictionary from secrets
    creds_info = dict(st.secrets["google_credentials"])

    # Ensure the private key handles newlines correctly regardless of TOML format
    if "private_key" in creds_info:
        creds_info["private_key"] = creds_info["private_key"].replace("\\n", "\n")

    creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
    return gspread.authorize(creds)

@st.cache_resource
def get_tab_names():
    client = get_sheet_client()
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    return [sh.title for sh in spreadsheet.worksheets()]

@st.cache_data(ttl=600)
def get_sheet_data(tab_name):
    # Use the helper function to get an authorized client
    client = get_sheet_client()

    # Open the specific spreadsheet and worksheet
    spreadsheet = client.open_by_key(SPREADSHEET_ID)
    sheet = spreadsheet.worksheet(tab_name)

    return sheet.get_all_values()

# NEW: Function to build the Area-Group Lookup Dictionary
@st.cache_data(ttl=3600)
def get_area_group_map():
    """Returns a dictionary mapping 'First Last' names to their 'AREA-GROUP' from the Roster."""
    roster_rows = get_sheet_data("Roster")
    # Assuming Column A is Last Name, Column B is First Name, Column L is Area-Group (index 11)
    mapping = {}
    for row in roster_rows[1:]: # Skip header
        if len(row) >= 12:
            full_name = f"{row[1]} {row[0]}".strip().lower()
            area_group = row[11] # Column L
            mapping[full_name] = area_group
    return mapping

# --- INITIAL LOAD ---
available_tabs = get_tab_names()
hidden_tabs = ["Monthly Template", "Roster"]
# Filter out hidden tabs AND any tab that starts with "Archive"
month_list = [t for t in available_tabs if t not in hidden_tabs and not t.startswith("Archive")]

# Determine the safe starting tab
now = datetime.datetime.now()
current_month = now.strftime("%B")            # e.g., "February"
next_month = (now.replace(day=28) + datetime.timedelta(days=4)).strftime("%B") # e.g., "March"

if current_month in month_list:
    initial_tab = current_month
elif next_month in month_list:
    initial_tab = next_month
else:
    # Fallback to the first non-hidden, non-archived tab
    initial_tab = month_list[0] if month_list else None

if not initial_tab:
    st.error("No active month tabs found! Please ensure your month tab (e.g., 'March') is not named 'Archive'.")
    st.stop()

all_rows = get_sheet_data(initial_tab)

# (Names list logic follows...)

names = [
    "Ana",
    "Bobbie",
    "Carlos",
    "Jasmynne",
    "Jestoni",
    "Johnny",
    "Julie",
    "Kim"
]

# --- 3. MAIN UI ---
st.title("📋 Visitation App")

user_name = st.selectbox("Who is viewing?", options=["-- Select Name --"] + names)

if user_name != "-- Select Name --":
    # --- ADMIN NOTIFICATION (RESTORED) ---
    # Only notify if the user is NOT you and hasn't been notified this session
    if user_name != "Carlos" and f"notified_{user_name}" not in st.session_state:
        admin_id = st.secrets["DEFAULT_CHAT_ID"]
        send_telegram_message(f"🚀 **App Activity:** {user_name} has logged into the Visitation Portal.", admin_id)
        st.session_state[f"notified_{user_name}"] = True

    # 1. Dynamic Month Selector
    # Use initial_tab to set the default index
    try:
        default_idx = month_list.index(initial_tab)
    except ValueError:
        default_idx = 0

    target_tab = st.selectbox("Select Month to View", options=month_list, index=default_idx)

    # 2. Re-fetch data ONLY if the user changes the dropdown
    if target_tab != initial_tab:
        all_rows = get_sheet_data(target_tab)

    st.divider()

    # Step 2: Present THREE Menu Options
    menu_choice = st.radio(
        f"Hi {user_name}, what would you like to do?",
        ["View My Assignments", "View Scheduled Visitations", "Assign officers (leadership)"],
        horizontal=True
    )

    st.divider()

    # --- OPTION 1: PERSONAL ASSIGNMENTS (WITH AREA-GROUP UPDATE) ---
    if menu_choice == "View My Assignments":
        st.subheader(f"Assignments for {user_name}")

        # Ensure the area map is loaded here so the variable is always defined
        area_map = get_area_group_map()

        my_assignments = [
            row for row in all_rows[4:]
            if len(row) > 6 and row[6].strip().lower() == user_name.lower()
        ]

        if my_assignments:
            for row in my_assignments:
                row_number = all_rows.index(row) + 1

                first_name = row[1] if len(row) > 1 else ""
                last_name = row[0] if len(row) > 0 else ""
                full_name = f"{first_name} {last_name}".strip()

                # LOOKUP AREA GROUP
                member_lookup_key = full_name.lower()
                area_group_val = area_map.get(member_lookup_key, "N/A")

                dob = row[2] if len(row) > 2 and row[2].strip() != "" else "N/A"
                anniversary = row[3] if len(row) > 3 and row[3].strip() != "" else "N/A"
                last_visited = row[20] if len(row) > 20 and row[20].strip() != "" else None
                address_for_map = row[4] if len(row) > 4 else ""
                phone = row[5] if len(row) > 5 else "N/A"

                try_1 = len(row) > 7 and row[7].upper() == 'TRUE'
                try_2 = len(row) > 8 and row[8].upper() == 'TRUE'

                with st.container(border=True):
                    # Display Name and Area Group (Highlighted)
                    st.markdown(f"### 👤 {full_name}")
                    st.markdown(f"📍 **Area-Group:** `{area_group_val}`")  # Added this line
                    st.markdown(f"🎂 **DOB:** {dob}    💍 **Married:** {anniversary}")

                    if last_visited:
                        st.info(f"🕒 **Last Visited:** {last_visited}")

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"📞 [{phone}](tel:{phone.replace('-', '').replace(' ', '')})")
                    with col2:
                        if address_for_map:
                            map_search_url = f"https://www.google.com/maps/search/?api=1&query={address_for_map.replace(' ', '+')}"
                            st.link_button("🗺️ Open Maps", map_search_url, use_container_width=True)
                        else:
                            st.button("No Address Found", disabled=True, use_container_width=True)

                    st.write("---")
                    if try_1 and try_2:
                        st.success("✅ **Goal Reached:** 2 of 2 attempts completed.")
                    elif try_1:
                        st.info("🟡 **Progress:** 1 of 2 attempts completed.")
                    else:
                        st.warning("⚪ **Not Started:** 0 attempts completed.")

                    with st.expander("📝 Log a Visitation Attempt"):
                        attempt_choice = st.selectbox("Which attempt?", ["-- Select --", "Try #1", "Try #2"],
                                                      key=f"status_{row_number}")
                        if st.button(f"Confirm attempt", key=f"btn_{row_number}"):
                            if attempt_choice != "-- Select --":
                                client = get_sheet_client()
                                sheet = client.open_by_key(SPREADSHEET_ID).worksheet(target_tab)
                                col_to_update = "H" if attempt_choice == "Try #1" else "I"
                                sheet.update_acell(f"{col_to_update}{row_number}", "TRUE")
                                st.cache_data.clear()
                                st.rerun()

                    with st.expander("📅 Schedule a Future Visitation"):
                        col_d, col_t = st.columns(2)
                        with col_d:
                            v_date = st.date_input("Select Date", key=f"date_in_{row_number}", format="MM/DD/YYYY")
                        with col_t:
                            time_options = [f"{str(h).zfill(2)}:{m} {p}" for p in ["AM", "PM"] for h in
                                            [12] + list(range(1, 12)) for m in ["00", "30"]]
                            selected_time_str = st.selectbox("Select Time", options=time_options, index=26,
                                                             key=f"time_select_{row_number}")

                        if st.button("Save Schedule", key=f"sched_btn_{row_number}"):
                            client = get_sheet_client()
                            sheet = client.open_by_key(SPREADSHEET_ID).worksheet(target_tab)
                            date_str = v_date.strftime("%m/%d/%Y")
                            sheet.update_acell(f"J{row_number}", date_str)
                            sheet.update_acell(f"K{row_number}", selected_time_str)

                            officer_map = st.secrets["USER_MAP"]
                            notification_msg = f"📅 **New Visitation!**\n\n**{full_name}** ({area_group_val}) on {date_str} at {selected_time_str}."
                            for off_name, chat_id in officer_map.items():
                                send_telegram_message(notification_msg, chat_id)
                            st.cache_data.clear()
                            st.rerun()
        else:
            st.info("No active assignments found.")

    # Option 2: Scheduled Visitations
    elif menu_choice == "View Scheduled Visitations":
        st.subheader("🗓️ Upcoming Scheduled Visitations")

        # 1. Get today's date for comparison
        today = datetime.date.today()

        # 2. Filter rows where Column J (index 9) is not empty AND is NOT in the past
        scheduled = []
        for row in all_rows[4:]:
            if len(row) > 9 and row[9].strip() != "":
                date_str = row[9].strip()
                try:
                    # Convert spreadsheet string "MM/DD/YYYY" to a date object
                    visit_date_obj = datetime.datetime.strptime(date_str, "%m/%d/%Y").date()

                    # ONLY include if the date is today or in the future
                    if visit_date_obj >= today:
                        scheduled.append(row)
                except ValueError:
                    # This skips rows with invalid date formats so the app doesn't crash
                    continue

        if not scheduled:
            st.info("No upcoming visitations scheduled. (Past visits are hidden)")
        else:
            header_row = all_rows[3]
            officer_names = [header_row[i] for i in range(11, 19)]
            col_letters = ["L", "M", "N", "O", "P", "Q", "R", "S"]
            officer_cols = dict(zip(officer_names, col_letters))

            for row in scheduled:
                row_number = all_rows.index(row) + 1

                # --- DEFINE VARIABLES FIRST ---
                first_name = row[1] if len(row) > 1 else ""
                last_name = row[0] if len(row) > 0 else ""
                full_name = f"{first_name} {last_name}".strip()

                address = row[4] if len(row) > 4 else "No Address"
                visit_date = row[9]  # Column J
                visit_time = row[10] if len(row) > 10 else "TBD"  # Column K

                with st.container(border=True):
                    st.markdown(f"### 👤 {full_name}")

                    # Display Date and Time as plain text
                    st.write(f"📅 **Date:** {visit_date}    ⏰ **Time:** {visit_time}")

                    # Create the clickable Google Maps URL
                    # We use address.replace(' ', '+') to make the URL web-safe
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')}"

                    # Display the address as a blue hyperlink
                    st.markdown(f"📍 **Location:** [{address}]({maps_url})")

                    # Attendance Check
                    attending = [all_rows[3][i] for i in range(11, 19) if len(row) > i and row[i].upper() == 'TRUE']
                    if attending:
                        st.success(f"👥 **Attending:** {', '.join(attending)}")
                    else:
                        st.caption("No officers have responded yet.")

                    # RSVP Section
                    st.divider()
                    if user_name in officer_names:
                        col_letter = officer_cols.get(user_name)
                        if user_name not in attending:

                            st.caption(f"💡 Click the button below if you can make the visitation for **{full_name}**")

                            if st.button(f"🙋‍♂️ I can attend ({full_name})", key=f"rsvp_{row_number}"):
                                client = get_sheet_client()
                                sheet = client.open_by_key(SPREADSHEET_ID).worksheet(target_tab)
                                sheet.update_acell(f"{col_letter}{row_number}", "TRUE")
                                st.success("RSVP Saved!")
                                st.cache_data.clear()
                                st.rerun()
                        else:
                            st.button(f"✅ You are attending ({full_name})", disabled=True, key=f"done_{row_number}")
                    else:
                        st.warning("You are not listed in the attendance columns (L-S).")

    # --- OPTION 3: ASSIGN OFFICERS ---
    else:
        st.subheader("🛠️ Assign Officers (Leadership)")

        area_map = get_area_group_map()

        all_members = [
            row for row in all_rows[4:]
            if len(row) > 19 and str(row[19]).strip().upper() == "YES"
        ]

        if not all_members:
            st.warning("⚠️ No members found. Ensure Column T is 'YES' in the spreadsheet.")
        else:
            # --- 1. BATCH NOTIFICATION SECTION ---
            st.info("Assign everyone first, then use the button below to notify all officers.")

            with st.container(border=True):
                col_notif, col_switch = st.columns([2, 1])
                with col_switch:
                    confirm_all = st.toggle("Unlock Batch Notify", key="unlock_top")
                with col_notif:
                    if st.button("📢 Send New Assignments via Telegram", disabled=not confirm_all,
                                 type="primary", use_container_width=True):

                        officer_map = st.secrets["USER_MAP"]
                        notified_count = 0
                        summary = {}

                        # Loop 1: Just gather data for the messages
                        for row in all_members:
                            off = row[6].strip().title() if len(row) > 6 else ""
                            member_name = f"{row[1]} {row[0]}".strip()

                            if off in officer_map:
                                if off not in summary: summary[off] = []
                                summary[off].append(member_name)

                        # Loop 2: Send the grouped messages
                        for off, assigned_members in summary.items():
                            # The URL of your web app
                            app_url = "https://visitation-assignment-app.streamlit.app/"

                            # Constructing the clean Markdown message
                            msg = (
                                f"📋 **{target_tab} Visitation Assignments Have Been Made**\n\n"
                                f"To see your assignments, [click here]({app_url})"
                            )

                            send_telegram_message(msg, officer_map[off])
                            notified_count += 1

                        # SUCCESS MESSAGE: Now safely inside the button logic
                        st.success(f"Sent summaries to {notified_count} officers!")

            st.divider()

            # --- 2. INDIVIDUAL MEMBER CARDS SECTION ---
            # Loop 3: Create the UI cards
            for row in all_members:
                row_idx = all_rows.index(row)
                row_number = row_idx + 1
                unique_key = f"{target_tab}_{row_number}"

                first_name = row[1] if len(row) > 1 else ""
                last_name = row[0] if len(row) > 0 else ""
                full_name = f"{first_name} {last_name}".strip()

                # LOOKUP AREA GROUP
                member_lookup_key = full_name.lower()
                area_group_val = area_map.get(member_lookup_key, "N/A")

                current_officer = row[6].strip() if len(row) > 6 else ""
                last_visited = row[20] if len(row) > 20 and row[20].strip() != "" else None

                with st.container(border=True):
                    col_info, col_action = st.columns([1.5, 1])
                    with col_info:
                        st.markdown(f"### {full_name}")
                        # ADDED: Display the Area-Group here
                        st.markdown(f"📍 **Area-Group:** `{area_group_val}`")

                        if last_visited:
                            st.write(f"🕒 **Last Visited:** {last_visited}")
                        st.caption(f"👤 Currently: **{current_officer if current_officer else 'Unassigned'}**")

                    with col_action:
                        try:
                            default_index = names.index(current_officer) + 1 if current_officer in names else 0
                        except ValueError:
                            default_index = 0

                        new_assignment = st.selectbox(
                            "Assign:",
                            options=["-- Select --"] + names,
                            index=default_index,
                            key=f"reassign_{unique_key}"
                        )

                        if new_assignment != current_officer and new_assignment != "-- Select --":
                            if st.button("Update Sheet", key=f"upd_btn_{unique_key}"):
                                client = get_sheet_client()
                                sheet = client.open_by_key(SPREADSHEET_ID).worksheet(
                                    target_tab)
                                with st.spinner(f"Updating {full_name}..."):
                                    sheet.update_acell(f"G{row_number}", new_assignment)
                                    st.success("Updated!")
                                    st.cache_data.clear()
                                    st.rerun()

# --- 4. EXTERNAL LINK SECTION ---
st.divider()
st.info("💡 **Tip:** If you need to view or update the spreadsheet manually, [click here](https://docs.google.com/spreadsheets/d/1i3Q9ff1yA3mTLJJS8-u8vcW3cz-B7envmThxijfyWTk/edit?usp=sharing).")

# Logout option in the bottom
if st.button("Logout"):
    st.session_state["authenticated"] = False
    st.rerun()