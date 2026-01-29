import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta, date

df = st.session_state['dataframe']

# Keep only required columns
df = df[["timestamp", "date", "time", "user_agent", "status", "status_binary"]]

user_agents_list = st.session_state['user_agents_list']

# Streamlit App
st.set_page_config(
    page_title="User Agent Performance Details",
    layout="wide"
)

st.title("User Agent Performance Details", text_alignment="center")

config = st.session_state['config']

cols = st.columns([1, 2.2], gap="small")
left_section = cols[0].container(border=True, height="content")
right_section = cols[1].container(border=True, height="content")

# LEFT SECTION
with left_section:
    st.subheader("Selection", text_alignment="center")

    # User Agent Selectbox (single selection)
    selected_ua = st.selectbox(
        "User Agent",
        options=user_agents_list,
        index=0,
        key="ua_selector",
        help="Please select one user agent"
    )

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)  # spacer

    # Two Date Pickers
    today = datetime.today().date()
    default_start = today - timedelta(days=8)
    default_end = today - timedelta(days=1)


    if "reset_dates_trigger" not in st.session_state:
        st.session_state["reset_dates_trigger"] = False

    if st.session_state.get("reset_dates_trigger") == True:
        st.session_state["start_date_picker"] = default_start
        st.session_state["end_date_picker"] = default_end
        st.session_state["reset_dates_trigger"] = False

    prev_start_date = st.session_state.get("start_date", default_start)
    prev_end_date = st.session_state.get("end_date", default_end)

    start_date = st.date_input(
        "Start Date",
        value=prev_start_date,
        min_value=date(2025, 1, 1),  
        max_value=today,
        key="start_date_picker",
        width="stretch",
        help="Select the start date (inclusive)."
    )

    end_date = st.date_input(
        "End Date",
        value=max(prev_end_date, start_date),
        min_value=start_date,
        max_value=today,
        key="end_date_picker",
        width="stretch",
        help="Select the end date (inclusive)."
    )
    
    st.session_state["start_date"] = start_date
    st.session_state["end_date"] = end_date

    # Reset Dates button
    # Sets a trigger to reset the date pickers.
    # This workaround handles current Streamlit widget state bugs that are difficult to fix otherwise.
    if st.button("Reset Dates"):
        st.session_state["reset_dates_trigger"] = True
        st.rerun()
        
    # Filter dataframe based on selection of user agent
    user_agent_df = df[df['user_agent'] == selected_ua]

    # Filter dataframe based on date range
    if start_date == end_date:
        filtered_df = user_agent_df[user_agent_df["date"] == start_date]
    # start_date < end_date
    else: 
        filtered_df = user_agent_df[
            (user_agent_df["date"] >= start_date) &
            (user_agent_df["date"] <= end_date)
        ]

    now = datetime.now()
    end_interval = pd.to_datetime(end_date)

    if end_interval.date() == now.date():
        end_interval = end_interval.replace(hour=now.hour, minute=0, second=0, microsecond=0)
    else: 
        # Include the entire end date if it's in the past
        end_interval += pd.Timedelta(days=1)

    start_interval = pd.to_datetime(start_date)

    # Total hours
    total_hours = (end_interval - start_interval).total_seconds() / 3600

    # Interval hours
    if total_hours < 12:
        interval_hours = 1 
    elif total_hours <= 24:
        interval_hours = 2
    else:
        interval_hours = total_hours / 8

    # Generate interval boundaries
    intervals = pd.date_range(start=start_interval, end=end_interval, freq=f'{int(interval_hours)}h')

    # Assign each row to an interval
    filtered_df['interval_start'] = pd.cut(
        filtered_df['timestamp'],
        bins=intervals,
        right=False, # interval includes left, excludes right
        labels=intervals[:-1]  # label each interval by its start time
    )

    # Aggregate: mean success rate and count of all rows
    interval_success_rate = (
        filtered_df
        .groupby('interval_start')
        .agg(
            success_rate=('status_binary', 'mean'),
            count=('status_binary', 'count')  # count all attempts, success or fail
        )
        .reset_index()
    )

    interval_success_rate['success_rate'] = interval_success_rate['success_rate'].fillna(0)

    # --- Convert interval start back to datetime ---
    interval_success_rate['interval_start'] = pd.to_datetime(interval_success_rate['interval_start'])

    # --- Compute midpoint of each interval for plotting ---
    interval_success_rate['interval_label'] = interval_success_rate['interval_start'] + pd.to_timedelta(interval_hours/2, unit='h')

    interval_success_rate['interval_end'] = interval_success_rate['interval_label'] + pd.to_timedelta(interval_hours/2, unit='h')

    # Format label: show date + time, minutes only if needed
    def format_label(dt):
        date_str = dt.strftime('%m/%d/%y')
        if dt.minute == 0:
            time_str = dt.strftime('%-I%p').lower()
        else:
            time_str = dt.strftime('%-I:%M%p').lower()
        return f"{date_str} {time_str}"

    interval_success_rate['interval_label'] = interval_success_rate['interval_label'].apply(format_label)

    interval_success_rate['interval_label_multiline'] = interval_success_rate['interval_label'].apply(
        lambda x: x.split(' ')[0] + '<br>' + x.split(' ')[1]
    )

    # Convert interval_start and interval_end to string format: MM/DD/YY H[am/pm]
    interval_success_rate['interval_start'] = interval_success_rate['interval_start'].apply(format_label)
    interval_success_rate['interval_end'] = interval_success_rate['interval_end'].apply(format_label)

# RIGHT SECTION
with right_section:
    st.markdown(
        f"<h3 style='font-size:24px; font-weight:bold; text-align:center;'>{selected_ua}</h3>",
        unsafe_allow_html=True
    )

    st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)

    # Line chart
    fig = px.line(
        interval_success_rate,
        x='interval_label_multiline',
        y='success_rate',
        markers=True,
        labels={'interval_label_multiline': '', 'success_rate': 'Success Rate'},
        title=''
    )

    fig.update_traces(
        customdata=interval_success_rate[['interval_start', 'interval_end']],
        hovertemplate=
            "<b>%{customdata[0]} - %{customdata[1]}</b><br>" +
            "Success Rate: %{y:.2%}" +
            "<extra></extra>"
    )

    fig.update_layout(
        yaxis=dict(
            range=[-0.02, 1.02],
            tickformat=".0%",
            dtick=0.2,
            title=dict(
                text="Success Rate",
                font=dict(size=16)   
            )
        ),
        xaxis=dict(
            tickmode='array',
            tickvals=interval_success_rate['interval_label_multiline'],
            ticktext=interval_success_rate['interval_label_multiline'],
            tickangle=0,
            tickfont=dict(size=12)
        ),
        margin=dict(l=50, r=50, t=50, b=100)
    )

    st.plotly_chart(fig, width="stretch", config=config)

    # Area chart
    fig = px.area(
        interval_success_rate,
        x='interval_label_multiline',
        y='count',
        labels={'interval_label_multiline': '', 'count': 'Attempt Count'},
    )

    # Add markers + text labels on top
    fig.update_traces(
        mode='lines+markers+text',  
        text=interval_success_rate['count'],  # show count values
        textposition='top center',              # position above each marker
        textfont=dict(size=14),
        cliponaxis=False,
        customdata=interval_success_rate[['interval_start', 'interval_end']],
        hovertemplate=
            "<b>%{customdata[0]} - %{customdata[1]}</b><br>" +
            "Attempt Count: %{y:.0f}" +
            "<extra></extra>"
    )

    # construct X-axis padding
    x_positions = np.arange(len(interval_success_rate))
    padding = 0.06 * len(interval_success_rate)
    x_range = [-padding, len(interval_success_rate)-1 + padding]

    fig.update_xaxes(
        range=x_range,
        tickmode='array',
        tickvals=x_positions,
        ticktext=interval_success_rate['interval_label_multiline'],
        tickangle=0,
        tickfont=dict(size=12)
    )

    # Y-axis integer ticks
    y_max = interval_success_rate['count'].max()

    view_max = max(y_max, 5) 

    approx_step = max(1, int(np.ceil(view_max / 5)))
    y_buffer = approx_step * 0.2 

    fig.update_yaxes(
        title=dict(text="Attempt Count", font=dict(size=16)),
        range=[-y_buffer, view_max + y_buffer], 
        tickmode='linear',
        dtick=approx_step,
        tick0=0,
        zeroline=True,
        zerolinewidth=1,
        zerolinecolor='rgba(255, 255, 255, 0.2)' # Keeps the zero line visible
    )

    fig.update_layout(
        margin=dict(l=50, r=50, t=50, b=100)
    )

    st.plotly_chart(fig, width="stretch", config=config)
