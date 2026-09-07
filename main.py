#!/usr/bin/env python3
"""Routing Dashboard Suite - Landing Page"""
import streamlit as st

st.set_page_config(
    page_title="Routing Dashboard Suite",
    page_icon="🚚",
    layout="wide"
)

st.title("🚚 Vehicle Routing Dashboard Suite")
st.markdown("---")

# Two main flows
col1, col2 = st.columns(2, gap="large")

with col1:
    st.header("⚡ Quick Routing")
    st.write("""
    **Direct route optimization from a single warehouse**

    Perfect when:
    - Single distribution center
    - All stores from one location
    - Quick simulation needed

    Upload your store CSV and go!
    """)

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Start Quick Routing →", use_container_width=True, type="primary"):
        st.switch_page("pages/1_⚡_Quick_Routing.py")

with col2:
    st.header("🎯 Full Simulation")
    st.write("""
    **Multi-warehouse store mapping + routing**

    Perfect when:
    - Multiple distribution centers
    - Need to assign stores to warehouses
    - Complex network optimization

    Map stores, then optimize routes per warehouse!
    """)

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Start Full Simulation →", use_container_width=True, type="secondary"):
        st.switch_page("pages/2_📍_Warehouse_Mapping.py")

st.markdown("---")

# Quick info section
with st.expander("ℹ️ What's the difference?"):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **Quick Routing**
        - Single warehouse/plant location
        - Directly upload stores and configure
        - Clarke-Wright optimization
        - Cost minimization
        - Fast results
        """)

    with col2:
        st.markdown("""
        **Full Simulation**
        - Multiple warehouses/distribution centers
        - Visual store-to-warehouse assignment
        - Radius-based mapping with manual overrides
        - Run routing for selected warehouses
        - Comprehensive multi-location optimization
        """)

st.caption("Built with Clarke-Wright algorithm | Cost-optimized routing | Forward-Reverse delivery models")
