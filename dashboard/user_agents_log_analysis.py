import os
import pandas as pd
import sys
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

BASE_DIR = os.path.abspath(os.path.join(os.getcwd()))
sys.path.append(BASE_DIR)

print(BASE_DIR)

user_agents_log_path = BASE_DIR + "/logs/user_agents_log.csv"

df = pd.read_csv(user_agents_log_path, header=None)

df["timestamp"] = pd.to_datetime(df[0])

df["date"] = df["timestamp"].dt.date
df["time"] = df["timestamp"].dt.time

# Rename other columns
df["user_agent"] = df[1]
df["status"] = df[2]

# Convert SUCCESS / FAIL to binary
df["status_binary"] = df["status"].map({"SUCCESS": 1, "FAIL": 0})

# Store dataframe in session state for access in other pages
st.session_state["dataframe"] = df

df = df[["timestamp", "user_agent", "status", "status_binary"]]

user_agents_list = sorted(df["user_agent"].unique().tolist())

st.session_state["user_agents_list"] = user_agents_list

# Streamlit App
st.set_page_config(page_title="User Agent Performance Overview", 
                   layout="wide")

st.title("User Agent Performance Overview", text_alignment="center")

top_section = st.container()
middle_section = st.container()
bottom_section = st.container()

config = {
    "displayModeBar": "hover",
    "modeBarButtonsToRemove": [
        "zoom2d", "pan2d", "select2d", "lasso2d",
        "zoomIn2d", "zoomOut2d", "autoScale2d",
        "resetScale2d", "hoverClosestCartesian",
        "hoverCompareCartesian", "toggleSpikelines"
    ],    
    "modeBarButtonsToAdd": [
        "toImage",           
        "toggleFullscreen"   
    ],
    "displaylogo": False,
    "responsive": True
}

st.session_state["config"] = config

# TOP SECTION
with top_section:
    cols = st.columns([1, 1.5, 1.5], gap="small")  # equal width; adjust numbers to resize
    
    left_col = cols[0].container(border=False, height="stretch")
    middle_col = cols[1].container(border=False, height="stretch")
    right_col = cols[2].container(border=False, height="stretch")

    # left col (Selection)
    with left_col.container(border=True, height="content"):
        st.subheader("Selection", text_alignment="center")

        # User Agent Multiselect
        selected_ua = st.multiselect(
            "User Agents",
            options=user_agents_list,
            default=user_agents_list,
            key="ua_selector",
            width="stretch"
        )

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)  # spacer

        # Time Horizon Segmented Control
        time_horizon_options = [
            "1 hour", "1 day", "1 week", "1 month", "1 quarter", "1 year", "All time"
        ]
        selected_time_horizon = st.segmented_control(
            label="Time Horizon",
            options=time_horizon_options,
            selection_mode="single",
            default="All time",
            key="time_horizon_selector"
        )

    # Filter data based on the selections
    now = pd.Timestamp.now()
    time_map = {
        "1 hour": pd.Timedelta(hours=1),
        "1 day": pd.Timedelta(days=1),
        "1 week": pd.Timedelta(weeks=1),
        "1 month": pd.Timedelta(days=30),
        "1 quarter": pd.Timedelta(days=90),
        "1 year": pd.Timedelta(days=365),
        "All time": None
    }

    delta = time_map[selected_time_horizon]
    if delta is not None:
        time_filtered_df = df[df["timestamp"] >= now - delta]
    else:
        time_filtered_df = df.copy()

    overall_df = time_filtered_df[time_filtered_df['user_agent'].isin(selected_ua)]

    ua_success_rate_df = (
        overall_df
        .groupby("user_agent", as_index=False)
        .agg(success_rate=("status_binary", "mean"))
        .sort_values("success_rate", ascending=False)
    )
    ua_success_rate_df["success_rate"] = ua_success_rate_df["success_rate"].round(3)

    # middle col (donut graph for the best UA)
    with middle_col.container(border=True, height="content"):

        # Filter best user agents
        best_ua_success_rate = ua_success_rate_df['success_rate'].max()
        best_ua = ua_success_rate_df[ua_success_rate_df['success_rate'] == best_ua_success_rate]['user_agent'].iloc[0]
        best_ua_fail_rate = 1 - best_ua_success_rate

        best_df = pd.DataFrame({
            "Category": ["SUCCESS", "FAIL"],
            "Value": [best_ua_success_rate, best_ua_fail_rate]
        })

        # Best UA donut
        fig_best = px.pie(
            best_df,
            names="Category",
            values="Value",
            hole=0.5,
            color="Category",
            color_discrete_map={
                "SUCCESS": "#28a745",  # green
                "FAIL": "#dc3545"      # red
            }
        )

        # labels outside the donut slices
        fig_best.update_traces(
            textposition="outside",
            textinfo="label+percent",
            textfont_size=14
        )

        # Add centered title inside the donut
        fig_best.update_layout(
            annotations=[
                dict(
                    text="Best User Agent",
                    x=0.5,
                    y=0.5,
                    font_size=16,
                    showarrow=False
                )
            ],
            showlegend=False
        )

        st.plotly_chart(fig_best, width="stretch", config=config)

        st.markdown(
            f"<div style='text-align:center; word-wrap: break-word;'>{best_ua}</div>",
            unsafe_allow_html=True
        )
        
        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)  # spacer
    
    # right col (donut graph for the worst UA)
    with right_col.container(border=True, height="content"):

        # Filter worst user agents
        worst_ua_success_rate = ua_success_rate_df['success_rate'].min()

        worst_ua = ua_success_rate_df[ua_success_rate_df['success_rate'] == worst_ua_success_rate]['user_agent'].iloc[0]
        worst_ua_fail_rate = 1 - worst_ua_success_rate

        worst_df = pd.DataFrame({
            "Category": ["SUCCESS", "FAIL"],
            "Value": [worst_ua_success_rate, worst_ua_fail_rate]
        })

        # Worst UA donut
        fig_worst = px.pie(
            worst_df,
            names="Category",
            values="Value",
            hole=0.5,
            color="Category",
            color_discrete_map={
                "SUCCESS": "#28a745",  # green
                "FAIL": "#dc3545"      # red
            }
        )

        fig_worst.update_traces(
            textposition="outside", 
            textinfo="label+percent",
            textfont_size=14
        )

        # Add centered title inside the donut
        fig_worst.update_layout(
            annotations=[
                dict(
                    text="Worse User Agent", 
                    x=0.5,
                    y=0.5,
                    font_size=16,
                    showarrow=False
                )
            ],
            showlegend=False
        )

        st.plotly_chart(fig_worst, width="stretch", config=config)

        st.markdown(
            f"<div style='text-align:center; word-wrap: break-word;'>{worst_ua}</div>",
            unsafe_allow_html=True
        )

        st.markdown("<div style='height:20px;'></div>", unsafe_allow_html=True)  # spacer

# MIDDLE SECTION
with middle_section.container(border=True, height="content"):
    st.subheader("Success Rate by User Agent", text_alignment="center")

    fig = px.bar(
        ua_success_rate_df,
        x="success_rate",
        y="user_agent",
        orientation="h",
        color="success_rate",
        text=ua_success_rate_df["success_rate"].apply(lambda x: f"{x:.1%}"),
        color_continuous_scale="Greens",
        range_color=[0, 1],
        labels={
            "success_rate": "Success Rate",
            "user_agent": "User Agent"
        }
    )

    # Update font sizes
    fig.update_layout(
        xaxis_title_font_size=18,    # x-axis label font size
        yaxis_title_font_size=18,    # y-axis label font size
    )

    fig.update_traces(
        textposition="outside",
        cliponaxis=False
    )

    fig.update_layout(
        height=420 + 18 * len(ua_success_rate_df),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(tickformat=".0%", 
                   range=[0, 1], 
                   showgrid=True, 
                   automargin=True,
                   zeroline=False),

        yaxis=dict(categoryorder="total ascending", 
                   showgrid=False, 
                   automargin=True, 
                   tickfont=dict(size=14)),
            
        coloraxis_colorbar=dict(title="Success Rate", 
                                tickformat=".0%", 
                                thickness=12, 
                                len=0.75),
        hoverlabel=dict(font_size=1)
    )

    fig.update_layout(
        coloraxis_colorbar=dict(
        title="",
        tickformat=".0%",
        thickness=20,          # slimmer colorbar
        lenmode="fraction",    # relative to chart height
        len=0.8,               # 80% of chart height
        x=1.3,                 # move outside to the right
        xanchor="left",
        y=0.5,                 # center vertically
        yanchor="middle"
    ))
        
    st.plotly_chart(fig, width="stretch", config=config)

# BOTTOM SECTION
with bottom_section.container(border=True, height="content"):
    st.subheader("User Agent Attempt Distribution", 
                 text_alignment="center",
                 help="Share of total requests among the selected user agents, \
                    including both successful and failed attempts.")

    # Data Processing
    ua_counts = overall_df['user_agent'].value_counts()
    total_rows = len(overall_df)
    ua_proportions = (ua_counts / total_rows).reset_index()
    ua_proportions.columns = ['user_agent', 'proportion']
    ua_proportions = ua_proportions.sort_values(by='proportion', ascending=False)

    # Build the Chart
    fig = go.Figure()
    categories = ua_proportions['user_agent'].tolist()
    values = ua_proportions['proportion'].tolist()

    custom_palette = [
        '#e7f0b7', '#d9e8b0', '#cbd0a9', '#bdc8a2',
        '#5fa3d6', '#5597d2', '#4b8bce', '#417fca',
        '#3473c9', '#4668cd', '#585dd1', '#6a52d5',
        '#7c45d4', '#8d4ed5', '#9f57d7', '#b160d9',
        '#c36adb', '#ca75df', '#d180e3', '#d88be7',
        '#df96eb', '#e6a1ef'
    ]

    # Build stacked bar
    bar_x = 0
    bar_width = 0.1

    cumulative = 0
    for i, (cat, val) in enumerate(zip(categories, values)):
        fig.add_bar(
            x=[bar_x],
            y=[val],
            width=bar_width,
            marker_color=custom_palette[i % len(custom_palette)],
            showlegend=False,
            hovertemplate=f"<b>{cat}</b><br>Share of Attempts:: {val:.1%}<extra></extra>"
        )

        # Centered percentage label INSIDE segment
        fig.add_annotation(
            x=bar_x,                          # center horizontally on bar
            y=cumulative + val / 2,           # center vertically in segment
            text=f"{val:.1%}",
            showarrow=False,
            xanchor="center",
            yanchor="middle",
            font=dict(color="black", size=11)
        )

        # Label column placed just outside bar edge
        fig.add_annotation(
            x=bar_x + bar_width/2 + 0.02,
            y=cumulative + val / 2,
            text=cat,
            showarrow=False,
            xanchor="left",
            yanchor="middle",
            font=dict(size=13.5, color="white")
        )

        cumulative += val

    fig.update_layout(
        barmode="stack",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        xaxis=dict(
            visible=False,          # hide x-axis completely
            range=[-0.05, 0.5],      # just enough room for labels
            fixedrange=True,
        ),
        yaxis=dict(
            range=[0, 1],
            tickformat=".0%",
            title=dict(
                text="Share of Total Attempts",
                font=dict(size=18),
                standoff=70
            ),
            showgrid=False,
            zeroline=True,               # ensure 0% line shows
            zerolinecolor="rgba(255,255,255,0.4)",
            zerolinewidth=1,
            fixedrange=True,
        ),
        height=850,   # height can stay fixed; width becomes responsive
        margin=dict(l=50, r=50, t=20, b=20),
    )

    st.plotly_chart(fig, width="stretch", config=config)
