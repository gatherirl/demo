import streamlit as st
from datetime import datetime
from typing import Dict, List, Optional
import random
import time

# =============================================================================
# PRIVACY MANAGER - Manages opt-in boundaries for all data sharing
# =============================================================================

class PrivacyManager:
    """Manages opt-in boundaries for all data sharing."""
    
    def __init__(self):
        self.community_members = {}  # id -> member data
        self.shared_data = {}        # type -> [data]
    
    def add_member(self, member_id: str, name: str, interests: List[str], 
                   privacy_level: int, opt_in_level: int):
        """Add a community member with privacy settings."""
        self.community_members[member_id] = {
            "id": member_id,
            "name": name,
            "interests": interests,
            "privacy_level": privacy_level,
            "opt_in_level": opt_in_level,
            "registered_at": datetime.now().isoformat()
        }
    
    def can_contact(self, requester_id: str, target_id: str) -> bool:
        """Check if requester can contact target (based on opt-in)."""
        requester = self.community_members.get(requester_id)
        target = self.community_members.get(target_id)
        
        if not requester or not target:
            return False
        
        # The person being contacted must have opted in (level 1)
        if target["opt_in_level"] >= 1:
            return True
        return False
    
    def can_share_data(self, sharer_id: str, viewer_id: str, data_type: str) -> bool:
        """Check if data can be shared based on privacy levels."""
        sharer = self.community_members.get(sharer_id)
        viewer = self.community_members.get(viewer_id)
        
        if not sharer or not viewer:
            return False
        
        # Data type rules
        if data_type == "attendee_presence":
            # Both must opt in to being contacted
            return sharer["opt_in_level"] >= 1 and viewer["opt_in_level"] >= 1
        
        elif data_type == "personal_data":
            # Both must have level 2 (community data sharing)
            return sharer["opt_in_level"] >= 2 and viewer["opt_in_level"] >= 2
        
        elif data_type == "connection_request":
            # Sharer opts in to receiving connections
            return sharer["opt_in_level"] >= 1
        
        elif data_type == "feedback":
            # Viewer opts in to seeing feedback
            return viewer["opt_in_level"] >= 2
        
        else:
            return False
    
    def log_interaction(self, action: str, data_type: str, 
                        sharer_id: str, viewer_id: str):
        """Log an interaction and enforce privacy rules."""
        
        if not self.can_share_data(sharer_id, viewer_id, data_type):
            # Privacy violation - log it
            return {
                "violation": True,
                "action": action,
                "data_type": data_type,
                "sharer": self.community_members[sharer_id]["name"],
                "viewer": self.community_members[viewer_id]["name"],
                "reason": "Privacy boundary: " + sharer_id + " has privacy level " + str(self.community_members[sharer_id]["privacy_level"])
            }
        
        # Valid interaction
        return {"violation": False}
    
    def get_sharable_contacts(self, my_id: str, data_type: str, my_interests: List[str]) -> List[Dict]:
        """Get contacts whose data I can share based on my privacy level."""
        sharable = []
        
        for contact_id, contact in self.community_members.items():
            if contact_id == my_id:
                continue
            
            if self.can_share_data(my_id, contact_id, data_type):
                shared_interests = [i for i in contact["interests"] if i in my_interests]
                
                if shared_interests:
                    sharable.append({
                        "id": contact_id,
                        "name": contact["name"],
                        "shared_interests": shared_interests,
                        "privacy_note": contact['name'] + " - Level " + str(contact['privacy_level']) + " (Community data only)"
                    })
        
        return sharable[:5]  # Limit suggestions
    
    def get_community_stats(self) -> Dict:
        """Get anonymized community statistics."""
        total = len(self.community_members)  # PrivacyManager version
        opted_in = sum(1 for c in self.community_members.values() if c["opt_in_level"] >= 1)
        
        return {
            "total_members": total,
            "opted_in": opted_in,
            "opt_in_rate": (opted_in * 100) // total if total > 0 else 0
        }


# =============================================================================
# SIMULATED AI - For demonstration purposes (no real model needed)
# =============================================================================

class SimulatedAI:
    """
    Simulated AI for demonstration purposes.
    This simulates what a real local model would generate.
    """
    
    def __init__(self):
        self.community_members = {}
        self.events = {}
    
    def generate_response(self, prompt: str, context: str = "") -> str:
        """Simulate generating a response based on intent."""
        
        prompt_lower = prompt.lower()
        
        # Intent detection
        if "join" in prompt_lower or "invite" in prompt_lower:
            return """Hey [Name]!

We're hosting a casual evening gathering. It's a small, low-key thing for music people like you to hang out. 
There will be about 5-10 people. 
Entry: $5 or bring a $5 coffee.
No pressure to commit - just come if it feels right!

See you soon,
The Rock Club"""
        
        elif "feedback" in prompt_lower or "survey" in prompt_lower:
            return """Thanks for joining us! We'd love to hear what worked and what didn't.

Quick questions:
1. On a scale of 1-10, how connected did you feel?
2. What was the best thing about this gathering?
3. What would make it even better next time?
4. Would you like to join another session? (Yes/No)

Take about 2 minutes - we appreciate your honesty!"""
        
        elif "cancel" in prompt_lower or "not coming" in prompt_lower:
            return "Got it. We'll reschedule for when we have 10+ confirmed people. Thanks for letting us know!"
        
        elif "share" in prompt_lower and ("song" in prompt_lower or "artist" in prompt_lower):
            return f"Awesome! If you're open to sharing music or connecting with artists, we'd love that. Just 3-5 minutes, and it helps other fans connect with artists they haven't heard of before!"
        
        elif "privacy" in prompt_lower or "opt-in" in prompt_lower:
            return """Great question! Here's how our privacy system works:

Privacy Levels:
Level 1: You can be contacted by the community
Level 2: Your data can be shared within the community
Level 3: Your data can be shared publicly (rare, opt-in only)

Your choices are stored locally. We only contact you if you've opted in. 
You can change your settings anytime.

No dark patterns. No manipulation. Just you, in control."""
        
        else:
            return """Thanks for your message!

We're building tools to help communities connect in person. 
This is an early experiment with a small group. 
Could you tell us what you're interested in? We want to make sure this is actually helpful!"""
        
        return "Thanks for your message! Tell us more about what you're looking for, and we'll help."
    
    def get_model_stats(self) -> Dict:
        """Return simulated model statistics."""
        return {
            "name": "Local Demo Model",
            "parameters": "7B (simulated)",
            "running": "locally (simulated)",
            "power_consumption": "~15W (simulated, would be real with actual model)",
            "monthly_cost": "$5-10 (simulated, would be real with actual model)",
            "environmental_impact": "~1% of cloud AI (simulated)"
        }
    
    def get_community_stats(self) -> Dict:
        """Get simulated community statistics."""
        total = len(self.community_members)
        opted_in = sum(1 for c in self.community_members.values() if c["opt_in_level"] >= 1)
        
        return {
            "total_members": total,
            "opted_in": opted_in,
            "opt_in_rate": (opted_in * 100) // total if total > 0 else 0
        }
    
    def test_connection(self, requester_id: str, target_id: str) -> bool:
        """Check if connection is possible based on privacy."""
        requester = self.community_members.get(requester_id)
        target = self.community_members.get(target_id)
        
        if not requester or not target:
            return False
        
        return requester["opt_in_level"] >= 1 and target["opt_in_level"] >= 1


# =============================================================================
# STREAMLIT INTERFACE
# =============================================================================

st.set_page_config(
    page_title="Human-Scale AI Demo",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🤖 Human-Scale AI Demo")
st.markdown("""
**Gatherrhiza Labs | Gather IRL Rock Club | Mozilla Incubator Grant**

This demo demonstrates the three Human-Scale AI principles:

- **SMALL**: 7B parameter model running locally (~15W, $5/month)
- **INTENTIONAL**: Opt-in boundaries, you control your data  
- **TAILORED**: Built for music fans in a hyperlocal community
""")

# Principles Section
st.subheader("📚 The Three Human-Scale AI Principles")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
**<span style='color:#28a745'>SMALL</span>**

Efficiency over scale. Small models deliver powerful functionality.

| Metric | Traditional | Our Approach |
|--------|------------|-------------|
| Model Size | 100B+ params | **7B params** |
| Power | 2,000W | **~15W** |
| Cost | $500/month | **$5/month** |
| Privacy | Extracted | **Protected** |
    """, unsafe_allow_html=True)

with col2:
    st.markdown("""
**<span style='color:#ffc107'>INTENTIONAL</span>**

Agency over automation. Users control their data.

| Privacy Level | What You Control |
|--------------|-----------------|
| **Level 1** | Can be contacted |
| **Level 2** | Community data sharing |
| **Level 3** | Public sharing |

*No dark patterns. No manipulation.*
    """, unsafe_allow_html=True)

with col3:
    st.markdown("""
**<span style='color:#dc3545'>TAILORED</span>**

Specific over universal. Built for THIS community.

- One neighborhood
- Specific demographic (music fans)
- Local deployment
- **No one-size-fits-all**
    """, unsafe_allow_html=True)

st.divider()

# Interactive Demo Section
st.subheader("⚡ Interactive Demo")

# Phase 1: Community Setup
with st.expander("🔧 Phase 1: Community Setup"):
    st.markdown("### Add Community Members")
    st.markdown("Set privacy levels: 1=Contactable, 2=Community data, 3=Public")
    
    # Members are kept in session_state so they survive Streamlit's reruns
    if "members" not in st.session_state:
        st.session_state["members"] = [
            {"id": "ava_c1001", "name": "Ava", "interests": ["indie folk", "acoustic"], "privacy_level": 2},
            {"id": "ben_c1002", "name": "Ben", "interests": ["punk", "garage rock"], "privacy_level": 1},
            {"id": "cleo_c1003", "name": "Cleo", "interests": ["indie folk", "shoegaze"], "privacy_level": 3},
            {"id": "dev_c1004", "name": "Dev", "interests": ["acoustic", "garage rock"], "privacy_level": 2},
            {"id": "emi_c1005", "name": "Emi", "interests": ["shoegaze", "indie folk"], "privacy_level": 2},
        ]

    with st.form("add_member_form", clear_on_submit=True):
        name = st.text_input("Name")
        interests_input = st.text_area("Interests", help="Comma-separated", value="indie folk, acoustic")
        privacy = st.selectbox("Privacy Level", [1, 2, 3], help="1=Contactable, 2=Community data, 3=Public")
        submitted = st.form_submit_button("Add Member")

        if submitted:
            if not name.strip():
                st.warning("Please enter a name.")
            elif len(st.session_state["members"]) >= 10:
                st.warning("This demo is capped at 10 members. Small is better!")
            else:
                interests = [x.strip() for x in interests_input.split(",") if x.strip()]
                st.session_state["members"].append({
                    "id": f"{name.strip().replace(' ', '_').lower()}_c{random.randint(1000, 9999)}",
                    "name": name.strip(),
                    "interests": interests,
                    "privacy_level": privacy
                })
                st.success(f"✓ Added {name.strip()}")

    if st.button("Reset to sample members"):
        del st.session_state["members"]
        st.rerun()

    members_data = st.session_state["members"]

    st.markdown("**Current members:**")
    for m in members_data:
        st.markdown(f"- **{m['name']}** (Level {m['privacy_level']}): {', '.join(m['interests'])}")

    if members_data:
        st.markdown("---")
        st.markdown("### Privacy Levels Explained")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
**Level 1: Can Be Contacted**
- Community can invite you
- You can connect with others
- No external sharing
            """)
        
        with col2:
            st.markdown("""
**Level 2: Community Data**
- Full community sharing
- Attendance tracking
- Feedback data
- No vendor access
            """)
        
        with col3:
            st.markdown("""
**Level 3: Public**
- All data accessible
- Public sharing enabled
- ⚠ Only if necessary
            """)

# Phase 2: Event Creation
with st.expander("🎯 Phase 2: Event Creation"):
    st.markdown("### Create a New Event")
    st.markdown("**Note: AI handles logistics, humans run the actual event**")
    
    event_name = st.text_input("Event Name", value="Listening Lounge")
    event_date = st.text_input("Date", value="Wednesday, Nov 25")
    event_time = st.text_input("Time", value="5:00 PM")
    event_location = st.text_input("Location", value="Community Center Room B")
    entry_fee = st.slider("Entry Fee ($)", 0, 20, 5)
    
    contact_ids = []
    for member in members_data:
        selected = st.checkbox(
            f"{member['name']} {'✓' if member['id'] not in contact_ids else ''} Invite?",
            value=member['id'] not in contact_ids,
            key=f"invite_{member['id']}"
        )
        if selected:
            contact_ids.append(member['id'])
    
    if st.button("Create Event"):
        with st.spinner("Creating event and sending opt-in invitations..."):
            time.sleep(1.5)  # Simulate processing
        
        event = {
            "name": event_name,
            "date": event_date,
            "time": event_time,
            "location": event_location,
            "entry_fee": entry_fee,
            "contact_ids": contact_ids,
            "status": "invited"
        }
        
        # Show who was invited
        invited_members = [m for m in members_data if m["id"] in contact_ids]
        
        st.success(f"✓ Event '{event_name}' created!")
        st.markdown(f"**Date:** {event_date} | **Time:** {event_time}")
        st.markdown(f"**Location:** {event_location}")
        st.markdown(f"**Entry:** ${entry_fee}")
        st.markdown(f"**Invited:** {len(invited_members)} people")
        
        st.session_state["event_created"] = True
        st.session_state["event"] = event

# Phase 3: RSVPs & Connections
with st.expander("👥 Phase 3: RSVPs & Connections"):
    if not members_data:
        st.error("Please add community members first!")
    elif not st.session_state.get("event_created"):
        st.warning("Please create an event first!")
    else:
        event = st.session_state["event"]
        
        st.markdown(f"### Event: {event['name']}")
        st.markdown(f"**Status:** {event['status']}")
        
        # RSVP section
        st.markdown("### Update RSVPs")
        
        rsvps = {}
        for member in members_data:
            rsvp = st.checkbox(
                f"{member['name']} {'✓' if member['id'] in event.get('attendees', []) else ''} Going?",
                value=member['id'] in event.get('attendees', []),
                key=f"rsvp_{member['id']}"
            )
            rsvps[member["id"]] = rsvp
        
        if st.button("Confirm RSVPs"):
            confirmed_count = sum(1 for r in rsvps.values() if r)
            event["attendees"] = [mid for mid, going in rsvps.items() if going]
            if confirmed_count >= 5:
                st.success(f"✓ Event confirmed! {confirmed_count}/{len(members_data)} confirmed")
                event["status"] = "confirmed"
            else:
                st.warning(f"⚠ Too few confirmations ({confirmed_count}/5). Event will be rescheduled.")
        
        # Connection suggestions
        if event["status"] == "confirmed" and len(members_data) > 1:
            st.markdown("---")
            st.markdown("### Connection Suggestions (Opt-In Only)")
            
            # Pick a member to generate connections for
            attendee_ids = [m["id"] for m in members_data if rsvps.get(m["id"])]
            names_by_id = {m["id"]: m["name"] for m in members_data}
            selected_member_id = st.selectbox(
                "Generate connections for:",
                options=attendee_ids,
                format_func=lambda mid: names_by_id.get(mid, mid),
                key="connection_select"
            )

            suggestions = []
            if selected_member_id:
                selected_member = next(m for m in members_data if m["id"] == selected_member_id)

                with st.spinner("AI is analyzing community connections..."):
                    time.sleep(1)

                # Privacy level doubles as opt-in level in this demo
                manager = PrivacyManager()
                for member in members_data:
                    manager.add_member(member["id"], member["name"], member["interests"],
                                       member["privacy_level"], member["privacy_level"])

                # Sharing interests counts as personal data (needs Level 2+ on both sides)
                suggestions = manager.get_sharable_contacts(
                    selected_member["id"], "personal_data", selected_member["interests"]
                )

            if suggestions:
                for i, sug in enumerate(suggestions, 1):
                    with st.expander(f"Connection {i}: {sug['name']}"):
                        st.markdown(f"**Shared interests:** {', '.join(sug['shared_interests'])}")
                        st.markdown(f"**Privacy note:** {sug['privacy_note']}")
                        st.markdown(f"**Suggestion:** {sug['name']} would be a great person to connect with!")
            else:
                st.info("No connection suggestions (privacy boundaries or no shared interests)")

# Phase 4: Event Metrics
with st.expander("📊 Phase 4: Impact Metrics"):
    st.markdown("### Community Health Dashboard")
    
    stats_manager = PrivacyManager()
    for member in members_data:
        stats_manager.add_member(member["id"], member["name"], member["interests"],
                                 member["privacy_level"], member["privacy_level"])
    stats = stats_manager.get_community_stats()

    col1, col2 = st.columns(2)
    
    with col1:
        st.metric("Opt-In Rate", f"{stats.get('opt_in_rate', 100)}%")
        st.markdown("Higher opt-in rates = healthier community")
    
    with col2:
        st.metric("Community Size", stats.get("total_members", len(members_data)))
        st.markdown("Small is better for privacy and intimacy")
    
    st.markdown("---")
    st.markdown("### Principle Compliance")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown("**<span style='color:#28a745'>SMALL</span>**", unsafe_allow_html=True)
        st.markdown(f"- **Model:** 7B (simulated)")
        st.markdown(f"- **Power:** ~15W")
        st.markdown(f"- **Cost:** $5-10/mo")
        st.markdown("- **Local deployment**")
    
    with col2:
        st.markdown("**<span style='color:#ffc107'>INTENTIONAL</span>**", unsafe_allow_html=True)
        st.markdown("Privacy levels enforced:")
        for level in range(1, 4):
            count = sum(1 for m in members_data if m.get("privacy_level", 0) == level)
            st.markdown(f"- Level {level}: {count} members")
        
        st.markdown("- **Opt-in boundaries**")
        st.markdown("- **No vendor access**")
        st.markdown("- **User controls**")
    
    with col3:
        st.markdown("**<span style='color:#dc3545'>TAILORED</span>**", unsafe_allow_html=True)
        st.markdown("- **One community**")
        st.markdown("- **Specific demographic** (music fans)")
        st.markdown("- **Local deployment**")
        st.markdown("- **No vendor lock-in**")

# Architecture Section
with st.expander("🏗️ System Architecture"):
    st.markdown("""
**How it works:**

```
┌─────────────────────────────────────┐
│      LOCAL MODEL (7B params)        │
│    Runs locally on Raspberry Pi     │
└────────────────┬────────────────────┘
                 │
          ┌───────┴───────┐
          │              │
          ▼              ▼
    ┌─────────┐    ┌─────────────┐
    │ Privacy │    │   Events    │
    │ Manager │    │   (Logics)  │
    └────┬────┘    └──────┬──────┘
         │                │
         │         ┌──────┴───────┐
         │         │              │
         ▼        ┌──────────┐   ┌──────────┐
    Communs AI    │   Human   │   │   Survey │
         │         │ Facilitator│   │    AI   │
         │         └──────────┘   └──────┬───────┐
         │                               │
         └───────────────────────────────┘
                 │
                ┌───────┐
                │   Next│
                │Iteration│
                └───────┘

KEY PRINCIPLE: AI does LOGISTICS. Humans do the ACTUAL EVENTS.
```

**Agent Flow:**
1. **LocalModel Agent**: Simulates 7B parameter model for responses
2. **PrivacyManager Agent**: Enforces opt-in boundaries at runtime
3. **CommunicationAgent**: Generates personalized messages with privacy checks
4. **EventCoordinator**: Orchestrates events, handles handoff to humans

The system proves that **small local models + privacy controls = human-scale AI**.
    """)

# Technical Specs
with st.expander("⚙️ Technical Specifications"):
    st.markdown("### Model Stack")
    
    st.markdown("""```yaml
model:
  name: mistral-7b (simulated in demo)
  type: local
  parameters: 7B
  location: Raspberry Pi 5 (CPU only)
  power: ~15W average
  monthly_cost: $5-10
  deployment: offline, no cloud API
  privacy: full local storage
```
    """)
    
    st.markdown("### Privacy Architecture")
    
    st.markdown("""
**Opt-in boundaries:**

- **Contact level**: User must opt-in to be contacted (Level 1)
- **Data sharing**: Explicit consent required (Level 2)
- **External access**: Never allowed without explicit Level 3
- **No vendor data leakage**: Data stays in community database

**Key code concept:**
```python
def can_contact(requester_id, target_id):
    if requester.privacy_level < 1:
        return False  # Can't be contacted
    if target.privacy_level < 1:
        return False  # Won't accept contact
    return True
```

**No dark patterns.** Your data is yours.
    """)

# About Section
with st.expander("ℹ️ About This Project"):
    st.markdown("""
**Gather IRL Rock Club** is a project by GatherRhiza Labs building **distributable, sovereign AI infrastructure for hyperlocal community building.**

**Why Human-Scale AI?**

The current AI paradigm is broken:
- **Centralized**: Everything runs on one company's servers
- **Extraction**: Your data is mined for profit
- **Lock-in**: You can't leave, you can't inspect
- **Scale-at-all-costs**: 100B+ parameter models consume massive energy

**Our approach flips the script:**
- **Distributed**: Multiple small AI nodes
- **Community-owned**: Your infrastructure, your rules
- **Privacy-first**: Opt-in boundaries, local data
- **Small by design**: 7B models are enough for community tasks
- **Tailored**: Built for THIS community, not a global product

**What we're proving:**
- Communities CAN own their AI
- Small models CAN work for real-world tasks
- AI CAN serve humans, not extract from them

**This is not "AI for good" charity work.**
This is building the alternative to "AI for extraction."
    """)

# Quick Start Guide
with st.expander("📖 Quick Start Guide"):
    st.markdown("""
### How to Use This Demo:

1. **Read the Principles** - Understand SMALL, INTENTIONAL, TAILORED
2. **Add Community Members** - Set up 5-10 music fans with privacy levels
3. **Create Event** - Set date, time, location, entry fee
4. **Invite Members** - Select who to invite (AI respects privacy)
5. **Update RSVPs** - Mark who's going
6. **View Connections** - See who to connect with (opt-in only)
7. **Check Metrics** - Review opt-in rates, principle compliance
8. **Explore Architecture** - See how agents work together

### What You'll Discover:

- **Privacy controls work in real-time** - Test adding someone at Level 1
- **AI handles logistics only** - Humans run the actual events
- **Connections are opt-in only** - No forced connections
- **Small models work** - 7B params, not 100B+
- **Local deployment** - No cloud API, runs offline

### Questions We Have for You:

- Have you used privacy controls?
- Did the privacy boundaries work as expected?
- What do you think about small models?
- How do you feel about AI handling logistics?
- Is this approach realistic for real communities?

### Contact Us:

Project Lead: [Your Name]
Email: [your-email@example.com]
GitHub: https://github.com/your-org/humanscale-ai

Let's talk about whether this is the future of AI!
    """)

# Final CTA
st.divider()

with st.expander("🎯 Next Steps"):
    st.markdown("""
**Ready to see this live?**

This demo shows the **human-scale AI principles in action**:

✓ **SMALL** - 7B local models, not 100B cloud
✓ **INTENTIONAL** - Opt-in boundaries, user control  
✓ **TAILORED** - Built for THIS community

**To access the full live demo:**

- **Streamlit Cloud**: https://humanscale-ai.your-org.streamlit.app
- **Or deploy locally**: `streamlit run interactive_demo.py`
- **Or use the HTML**: Just open this page in your browser

**Questions?** Let's discuss whether this is how AI should work!
    """)
    
    if st.button("Contact Us"):
        st.info("Thank you for your interest! Contact: your-email@example.com")

st.divider()

# Simple Test Button
if st.session_state.get("test", False):
    st.success("✓ Demo loaded successfully!")
    st.markdown("""
The system is working with:
- **Privacy controls** - Opt-in boundaries enforced at runtime
- **AI handling logistics** - Invitations, RSVPs, connections
- **Humans running events** - Facilitation, music, experiences
- **Small local models** - 7B params, 15W power, $5/month
    """)
else:
    if st.button("Test Demo"):
        st.session_state["test"] = True
        st.rerun()