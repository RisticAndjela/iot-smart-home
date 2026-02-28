from simulation.state.global_state import global_state, global_state_lock

with global_state_lock:
    global_state["people_count"] += 1