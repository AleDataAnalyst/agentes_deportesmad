"""Punto de entrada de Streamlit.

Responsabilidad futura: delegar la presentación en clientes.streamlit_app.
El grafo y sus decisiones pertenecen a agentes/, no a este archivo.
"""

import streamlit as st
from clientes.streamlit_app import render

st.set_page_config(
    page_title="Asistente Deporte Municipal Madrid",
    page_icon="🏟️",
    layout="wide",
)

render()