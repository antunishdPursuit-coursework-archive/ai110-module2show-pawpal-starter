import streamlit as st
from datetime import date, time
from pawpal_system import Owner, Pet, Task, Schedule, ScheduleType, Scheduler

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="wide")

st.title("🐾 PawPal+")

# --- Persist Owner across reruns ---
if "owner" not in st.session_state:
    st.session_state.owner = None

# ── Owner Setup (above columns — needed before anything else renders) ───────
st.subheader("Owner")
owner_name = st.text_input("Your name", value="Jordan")

if st.button("Set Owner"):
    if not owner_name.strip():
        st.error("Enter an owner name.")
    else:
        if st.session_state.owner is None:
            st.session_state.owner = Owner(owner_name.strip())
        else:
            st.session_state.owner.name = owner_name.strip()
        st.success(f"Owner set: {owner_name.strip()}")

if st.session_state.owner is None:
    st.info("Set an owner above to get started.")
    st.stop()

owner = st.session_state.owner

st.divider()

# ── Two-column root layout ───────────────────────────────────────────────────
col_forms, col_schedule = st.columns([1, 1.5])

# ══════════════════════════════════════════════════════════════════════════════
# LEFT — Pet & Task forms
# ══════════════════════════════════════════════════════════════════════════════
with col_forms:

    # ── Section 2: Add a Pet ─────────────────────────────────────────────────
    st.subheader("Add a Pet")

    c1, c2, c3 = st.columns(3)
    with c1:
        pet_name = st.text_input("Pet name", value="Mochi")
    with c2:
        species = st.selectbox("Species", ["dog", "cat", "other"])
    with c3:
        age = st.number_input("Age", min_value=0, max_value=30, value=2)

    if st.button("Add Pet"):
        new_pet = Pet(name=pet_name, species=species, age=age)
        try:
            if not pet_name.strip():
                raise ValueError("Enter a pet name.")
            new_pet.name = pet_name.strip()
            owner.add_pet(new_pet)
            st.success(f"Added {pet_name} the {species}!")
        except ValueError as e:
            st.error(str(e))

    if owner.pets:
        st.markdown("**Registered pets:**")
        for p in owner.pets:
            st.write(f"- [{p.pet_id}] {p.name} ({p.species}, age {p.age})")
    else:
        st.info("No pets yet. Add one above.")

    # ── Section 3: Add a Task ────────────────────────────────────────────────
    st.divider()
    st.subheader("Add a Task")

    if not owner.pets:
        st.info("Add a pet first before adding tasks.")
    else:
        pet_options = {f"{p.name} (ID {p.pet_id})": p for p in owner.pets}
        selected_label = st.selectbox("Assign to pet", list(pet_options.keys()))
        selected_pet = pet_options[selected_label]

        c1, c2 = st.columns(2)
        with c1:
            task_title = st.text_input("Task title", value="Morning walk")
            task_desc = st.text_input("Description", value="20 min walk")
            task_time = st.time_input("Time of day (optional)", value=None)
        with c2:
            schedule_type = st.selectbox("Schedule", ["DAILY", "WEEKLY", "CUSTOM"])
            interval = st.number_input("Interval (days, CUSTOM only)", min_value=1, max_value=365, value=3)

        if st.button("Add Task"):
            stype = ScheduleType[schedule_type]
            schedule = Schedule(stype, start_date=date.today(), interval=interval)
            time_of_day = time(task_time.hour, task_time.minute) if task_time else None
            new_task = Task(
                title=task_title,
                description=task_desc,
                assigned_pet_id=selected_pet.pet_id,
                schedule=schedule,
                time_of_day=time_of_day,
            )
            try:
                if not task_title.strip():
                    raise ValueError("Enter a task title.")
                new_task.title = task_title.strip()
                selected_pet.add_task(new_task)
                st.success(f"Task '{task_title}' added to {selected_pet.name}!")
            except ValueError as e:
                st.error(str(e))

# ══════════════════════════════════════════════════════════════════════════════
# RIGHT — Today's Schedule
# ══════════════════════════════════════════════════════════════════════════════
with col_schedule:
    st.subheader("Today's Schedule")

    all_due = Scheduler.get_daily_tasks(owner, include_completed=True)
    unfinished = [task for task in all_due if task.status != "done"]

    if not all_due:
        st.info("No tasks due today. Add tasks on the left to build your pet's routine.")
    else:
        # ── Conflict warnings ──
        conflicts = Scheduler.detect_conflicts(unfinished, pets=owner.pets)
        if conflicts:
            st.error(
                f"**Scheduling conflict{'s' if len(conflicts) > 1 else ''} detected — action needed!**\n\n"
                "Two or more unfinished tasks share a scheduled start time. "
                "Check the care plan before doing these tasks.",
                icon="🚨",
            )
            with st.expander(f"See {len(conflicts)} conflict detail{'s' if len(conflicts) > 1 else ''}"):
                for warning in conflicts:
                    st.markdown(f"- {warning}")

        # ── Summary metrics ──
        n_pending = sum(1 for t in all_due if t.status == "pending")
        n_overdue = sum(1 for t in all_due if t.status == "overdue")
        n_done    = sum(1 for t in all_due if t.status == "done")

        m1, m2, m3 = st.columns(3)
        m1.metric("Pending", n_pending)
        m2.metric("Overdue", n_overdue, delta=f"-{n_overdue}" if n_overdue else None,
                  delta_color="inverse")
        m3.metric("Done today", n_done)

        # ── Filters ──
        cf1, cf2 = st.columns(2)
        with cf1:
            filter_status = st.selectbox("Filter by status", ["all", "pending", "done", "overdue"])
        with cf2:
            pet_names = ["all"] + [p.name for p in owner.pets]
            filter_pet = st.selectbox("Filter by pet", pet_names)

        filtered = Scheduler.filter_tasks(
            all_due,
            status=None if filter_status == "all" else filter_status,
            pet_name=None if filter_pet == "all" else filter_pet,
            pets=owner.pets
        )

        if not filtered:
            st.info("No tasks match the selected filters.")

        # ── Task cards (sorted by time via Scheduler) ──
        pet_lookup = {p.pet_id: p for p in owner.pets}
        for task in Scheduler.sort_by_time(filtered):
            pet = pet_lookup.get(task.assigned_pet_id)
            pet_label  = pet.name if pet else "Unknown pet"
            time_label = task.time_of_day.strftime("%I:%M %p") if task.time_of_day else "Anytime"
            status     = task.status

            tc1, tc2 = st.columns([4, 1])
            with tc1:
                if status == "done":
                    st.success(
                        f"**{task.title}** — {task.description}\n\n"
                        f"{pet_label} · {time_label}",
                        icon="✅",
                    )
                elif status == "overdue":
                    st.warning(
                        f"**{task.title}** — {task.description}\n\n"
                        f"{pet_label} · {time_label} · Due {task.schedule.next_due_date}",
                        icon="⏰",
                    )
                else:
                    st.info(
                        f"**{task.title}** — {task.description}\n\n"
                        f"{pet_label} · {time_label}",
                        icon="📋",
                    )
            with tc2:
                if status != "done":
                    if st.button("Mark done", key=f"done_{task.task_id}", use_container_width=True):
                        new_task = Scheduler.complete_and_reschedule(task, pet)
                        if new_task:
                            st.toast(f"Next '{task.title}' on {new_task.schedule.next_due_date} 📅")
                        else:
                            st.toast(f"'{task.title}' complete! ✅")
                        st.rerun()
