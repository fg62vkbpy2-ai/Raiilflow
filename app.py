import json
import time
from datetime import datetime
import pandas as pd
import streamlit as st

from engine import RailFlowEngine, Train, scenario_defaults, to_event_dict

st.set_page_config(page_title="RailFlow | Conflict Monitor", page_icon="🚆", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 1.3rem; padding-bottom: 2rem;}
.rf-banner {padding: 0.85rem 1rem; border-radius: 0.65rem; border: 1px solid #d97706; background: rgba(217,119,6,.09); margin-bottom: 1rem;}
.rf-small {font-size: .88rem; opacity: .8;}
.rf-track {height: 20px; background: #d1d5db; border-radius: 8px; position: relative; margin: 1rem 0 .4rem 0;}
</style>
""", unsafe_allow_html=True)

st.title("🚆 RailFlow")
st.caption("Prototipo de supervisión y detección de conflictos ferroviarios · Simulación local")

st.markdown('<div class="rf-banner"><b>⚠️ SOLO SIMULACIÓN.</b> No está conectado a trenes, Adif, Renfe ni sistemas reales. No es un sistema certificado de seguridad ferroviaria y no debe usarse para tomar decisiones operativas.</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Parámetros de simulación")
    speed_kmh = st.slider("Velocidad del tren que se aproxima (km/h)", 40, 300, 200, 5)
    gap_m = st.slider("Separación inicial entre trenes (m)", 500, 12000, 2500, 100)
    decel = st.slider("Deceleración de frenado simulada (m/s²)", 0.3, 1.2, 0.8, 0.1)
    reaction_s = st.slider("Tiempo de reacción supuesto (s)", 0.0, 8.0, 3.0, 0.5)
    margin_m = st.slider("Margen preventivo adicional (m)", 0, 2000, 500, 100)
    st.caption("Valores ilustrativos, no límites ferroviarios reales.")
    st.divider()
    apply_demo_brake = st.checkbox("Mostrar respuesta de frenado simulada", value=False)
    st.caption("Solo cambia la animación de la simulación; no representa una función de seguridad validada.")

engine = RailFlowEngine(decel, reaction_s, margin_m)
following, stopped = scenario_defaults()
following.speed_mps = speed_kmh / 3.6
stopped.position_m = following.position_m + gap_m

detection = engine.detect(following, stopped)
events = st.session_state.setdefault("events", [])
if "last_event_signature" not in st.session_state:
    st.session_state.last_event_signature = None

# Top-level metrics
m1, m2, m3, m4 = st.columns(4)
m1.metric("Tren que se aproxima", following.train_id)
m2.metric("Velocidad simulada", f"{speed_kmh} km/h")
m3.metric("Separación", f"{gap_m:,.0f} m".replace(",", "."))
m4.metric("Tiempo hasta alcanzar la posición*", "—" if detection.time_to_collision_s is None else f"{detection.time_to_collision_s:.1f} s")

if detection.severity == "RED":
    st.error(f"🔴 {detection.code} · {detection.message}")
elif detection.severity == "AMBER":
    st.warning(f"🟠 {detection.code} · {detection.message}")
else:
    st.success(f"🟢 {detection.code} · {detection.message}")

st.subheader("Vista de vía")
# Map track positions normalized to the displayed interval
track_start = min(following.position_m, stopped.position_m) - 500
track_end = max(following.position_m, stopped.position_m) + 500
span = max(1, track_end - track_start)
left_pct = (following.position_m - track_start) / span * 100
right_pct = (stopped.position_m - track_start) / span * 100
st.markdown(f"""
<div style="position:relative;height:100px;margin:10px 0 20px 0;">
  <div style="position:absolute;top:47px;left:0;right:0;height:8px;background:#9ca3af;border-radius:4px;"></div>
  <div style="position:absolute;top:0;left:{left_pct:.1f}%;transform:translateX(-50%);text-align:center;width:145px;">
    <div style="font-size:1.6rem">🚄</div><b>{following.train_id}</b><div style="font-size:.8rem">{speed_kmh} km/h</div>
  </div>
  <div style="position:absolute;top:0;left:{right_pct:.1f}%;transform:translateX(-50%);text-align:center;width:145px;">
    <div style="font-size:1.6rem">🚆</div><b>{stopped.train_id}</b><div style="font-size:.8rem">DETENIDO</div>
  </div>
</div>
""", unsafe_allow_html=True)

left, right = st.columns(2)
with left:
    st.subheader("Cálculo de distancia")
    distance_data = pd.DataFrame([
        {"Concepto": "Distancia de frenado teórica", "Metros": detection.stopping_distance_m},
        {"Concepto": "Distancia durante reacción", "Metros": detection.reaction_distance_m},
        {"Concepto": "Margen preventivo", "Metros": margin_m},
        {"Concepto": "Distancia requerida total", "Metros": detection.required_distance_m},
        {"Concepto": "Separación actual", "Metros": detection.gap_m},
    ])
    st.dataframe(distance_data.style.format({"Metros": "{:,.1f}"}), use_container_width=True, hide_index=True)
    st.caption("Modelo simplificado: d = v²/(2a) + v·tᵣ + margen. No incorpora pendiente, curvas, latencia real, condiciones del tren ni incertidumbre de localización.")
with right:
    st.subheader("Estado de los trenes")
    st.dataframe(pd.DataFrame([
        {"ID": following.train_id, "Estado": "EN MARCHA (simulado)", "Posición (km)": following.position_m/1000, "Velocidad (km/h)": speed_kmh},
        {"ID": stopped.train_id, "Estado": "DETENIDO (simulado)", "Posición (km)": stopped.position_m/1000, "Velocidad (km/h)": 0},
    ]).style.format({"Posición (km)": "{:.3f}", "Velocidad (km/h)": "{:.1f}"}), use_container_width=True, hide_index=True)

st.divider()
st.subheader("Registro de eventos")
event_col1, event_col2 = st.columns([1, 2])
with event_col1:
    if st.button("Registrar estado actual", type="primary", use_container_width=True):
        event = to_event_dict(detection, following, stopped)
        event["recorded_at_local"] = datetime.now().astimezone().isoformat(timespec="seconds")
        events.append(event)
        st.session_state.events = events
        st.success("Evento añadido al registro.")
    if st.button("Limpiar registro", use_container_width=True):
        st.session_state.events = []
        events = st.session_state.events
        st.rerun()
with event_col2:
    st.write("Los eventos se guardan durante la sesión del navegador. Puedes exportarlos a JSON o CSV.")
if events:
    st.dataframe(pd.DataFrame(events), use_container_width=True, hide_index=True)
    json_data = json.dumps(events, ensure_ascii=False, indent=2)
    csv_data = pd.DataFrame(events).to_csv(index=False).encode("utf-8")
    d1, d2 = st.columns(2)
    d1.download_button("Descargar eventos JSON", json_data, file_name="railflow_events.json", mime="application/json", use_container_width=True)
    d2.download_button("Descargar eventos CSV", csv_data, file_name="railflow_events.csv", mime="text/csv", use_container_width=True)
else:
    st.info("Todavía no hay eventos registrados. Pulsa «Registrar estado actual» para guardar una instantánea.")

st.divider()
st.subheader("Prueba rápida de evolución temporal")
st.write("Esta demostración avanza el tren que se aproxima en intervalos simulados de 1 segundo. No usa reloj en tiempo real.")
if st.button("Simular 10 segundos", use_container_width=True):
    sim_train = Train(following.train_id, following.name, following.position_m, following.speed_mps)
    rows = []
    for i in range(1, 11):
        det = engine.detect(sim_train, stopped, sim_time_s=i)
        if apply_demo_brake and det.severity == "RED":
            sim_train.speed_mps = max(0.0, sim_train.speed_mps - decel)
        sim_train.position_m += sim_train.speed_mps
        rows.append({
            "Tiempo simulado": f"T+{i}s",
            "Posición tren aproximándose (km)": sim_train.position_m / 1000,
            "Velocidad (km/h)": sim_train.speed_kmh,
            "Separación (m)": max(0, stopped.position_m - sim_train.position_m),
            "Alarma": engine.detect(sim_train, stopped, sim_time_s=i).severity,
        })
        if sim_train.position_m >= stopped.position_m:
            rows[-1]["Alarma"] = "COLISIÓN SIMULADA"
            break
    st.dataframe(pd.DataFrame(rows).style.format({
        "Posición tren aproximándose (km)": "{:.3f}",
        "Velocidad (km/h)": "{:.1f}",
        "Separación (m)": "{:.1f}",
    }), use_container_width=True, hide_index=True)

st.caption("*Tiempo hasta alcanzar la posición del tren detenido si la velocidad se mantuviera constante. No es una predicción validada de colisión.")
