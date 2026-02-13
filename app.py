"""
Study Map – Flask application for personal learning tracking with
AI classification and knowledge graph visualisation.

Run:  python app.py
"""

import json
from flask import Flask, render_template, request, redirect, url_for, jsonify

import database as db
import ai_service

app = Flask(__name__)
app.config["SECRET_KEY"] = "study-map-local-secret"

# ── Initialise DB ────────────────────────────────────────
db.init_db()


# ── Helpers ──────────────────────────────────────────────
def _sidebar_stats():
    """Common sidebar stats passed to every template."""
    return {
        "entries": len(db.get_all_entries()),
        "skills": len(db.get_all_skills()),
        "blindspots": len(db.get_all_blindspots()),
    }


# ══════════════════════════════════════════════════════════
# PAGE ROUTES
# ══════════════════════════════════════════════════════════

@app.route("/")
def index():
    return redirect(url_for("log_entry"))


@app.route("/log-entry", methods=["GET", "POST"])
def log_entry():
    error = None
    result = None
    success_id = None

    if request.method == "POST":
        topic = request.form.get("topic", "").strip()
        skills_raw = request.form.get("skills", "").strip()
        summary = request.form.get("summary", "").strip()

        if not topic or not skills_raw or not summary:
            error = "Please fill in all three fields."
        else:
            skills = [s.strip() for s in skills_raw.split(",") if s.strip()]
            existing = db.get_all_entries()

            # AI classification
            ai_result = None
            try:
                ai_result = ai_service.classify_entry(topic, skills, summary, existing)
            except Exception as exc:
                error = f"AI classification failed: {exc}"

            # Save entry
            topic_id = db.get_or_create_topic(topic)
            skill_ids = [db.get_or_create_skill(s) for s in skills]
            entry_id = db.create_entry(
                topic_id,
                summary,
                skill_ids,
                ai_classification=ai_result.get("classification") if ai_result else None,
            )

            # Save connections & blindspots
            if ai_result:
                for conn in ai_result.get("connections", []):
                    try:
                        db.add_connection(
                            source_id=entry_id,
                            target_id=int(conn["entry_id"]),
                            relationship=conn["relationship"],
                            strength=float(conn.get("strength", 0.5)),
                            explanation=conn.get("explanation"),
                        )
                    except Exception:
                        pass

                for bs in ai_result.get("blindspots", []):
                    db.add_blindspot(
                        entry_id=entry_id,
                        suggestion=bs["suggestion"],
                        category=bs.get("category"),
                        why_important=bs.get("why_important"),
                        how_it_helps=bs.get("how_it_helps"),
                    )

                enhanced = ai_result.get("enhanced_summary")
                if enhanced:
                    db.update_enhanced_summary(entry_id, enhanced)

            success_id = entry_id

            # Build result dict for template
            if ai_result:
                all_conns = db.get_all_connections()
                all_bs = db.get_all_blindspots()
                result = {
                    "classification": ai_result.get("classification"),
                    "connections": [c for c in all_conns if c["source_entry_id"] == entry_id],
                    "blindspots": [b for b in all_bs if b["entry_id"] == entry_id],
                    "enhanced_summary": ai_result.get("enhanced_summary"),
                }

    # Handle GET with success redirect
    if request.method == "GET" and request.args.get("success"):
        success_id = request.args.get("success")

    return render_template(
        "log_entry.html",
        active="log",
        sidebar=_sidebar_stats(),
        error=error,
        success_id=success_id,
        result=result,
    )


@app.route("/graph")
def graph():
    entries = db.get_all_entries()
    return render_template(
        "graph.html",
        active="graph",
        sidebar=_sidebar_stats(),
        has_data=len(entries) > 0,
    )


@app.route("/entries")
def entries():
    all_entries = db.get_all_entries()

    unique_skills = set()
    domains = set()
    for e in all_entries:
        if e.get("skills"):
            for s in e["skills"].split(", "):
                unique_skills.add(s.strip())
        cls = e.get("ai_classification") or {}
        if cls.get("domain"):
            domains.add(cls["domain"])

    stats = {
        "total": len(all_entries),
        "skills": len(unique_skills),
        "domains": len(domains),
    }

    return render_template(
        "entries.html",
        active="entries",
        sidebar=_sidebar_stats(),
        entries=all_entries,
        stats=stats,
    )


@app.route("/blindspots")
def blindspots():
    all_bs = db.get_all_blindspots()

    categories = {}
    for bs in all_bs:
        cat = bs.get("category") or "General"
        categories.setdefault(cat, []).append(bs)

    return render_template(
        "blindspots.html",
        active="blindspots",
        sidebar=_sidebar_stats(),
        total=len(all_bs),
        categories=categories,
    )


@app.route("/analytics")
def analytics():
    all_entries = db.get_all_entries()
    all_skills = []
    domains = set()
    for e in all_entries:
        if e.get("skills"):
            all_skills.extend([s.strip() for s in e["skills"].split(",")])
        cls = e.get("ai_classification") or {}
        if cls.get("domain"):
            domains.add(cls["domain"])

    connections = db.get_all_connections()

    stats = {
        "total": len(all_entries),
        "skills": len(set(all_skills)),
        "domains": len(domains),
        "connections": len(connections),
    }

    return render_template(
        "analytics.html",
        active="analytics",
        sidebar=_sidebar_stats(),
        stats=stats,
        has_data=len(all_entries) > 0,
    )


# ══════════════════════════════════════════════════════════
# API ROUTES (JSON)
# ══════════════════════════════════════════════════════════

@app.route("/api/entry/<int:entry_id>")
def api_entry(entry_id):
    entry = db.get_entry_by_id(entry_id)
    if not entry:
        return jsonify({"error": "Not found"}), 404
    return jsonify(dict(entry))


@app.route("/api/entry/<int:entry_id>/enhance", methods=["POST"])
def api_enhance_entry(entry_id):
    entry = db.get_entry_by_id(entry_id)
    if not entry:
        return jsonify({"error": "Not found"}), 404

    topic = entry["topic_title"]
    skills = [s.strip() for s in (entry.get("skills") or "").split(", ") if s.strip()]
    summary = entry["summary"]

    try:
        enhanced = ai_service.enhance_notes(topic, skills, summary)
    except Exception as exc:
        return jsonify({"error": f"Enhancement failed: {exc}"}), 500

    db.update_enhanced_summary(entry_id, enhanced)
    return jsonify({"enhanced_summary": enhanced})


@app.route("/api/graph-data")
def api_graph_data():
    entries = db.get_all_entries()
    connections = db.get_all_connections()

    nodes = []
    edges = []
    seen_skills = set()

    for e in entries:
        nodes.append({
            "id": f"entry_{e['id']}",
            "label": f"#{e['id']}: {e['topic_title']}",
            "shape": "dot",
            "size": 28,
            "color": "#8b5cf6",
            "font": {"color": "#0f0f0f", "size": 12},
            "title": f"{e['summary'][:120]}...\nSkills: {e.get('skills', 'N/A')}\nDate: {e['created_at']}",
        })

        if e.get("skills"):
            for sk in e["skills"].split(", "):
                sk_key = sk.strip().lower()
                if sk_key and sk_key not in seen_skills:
                    nodes.append({
                        "id": f"skill_{sk_key}",
                        "label": sk.strip(),
                        "shape": "diamond",
                        "size": 20,
                        "color": "#ef6c4e",
                        "font": {"color": "#6b6b76", "size": 11},
                    })
                    seen_skills.add(sk_key)

                if sk_key:
                    edges.append({
                        "from": f"entry_{e['id']}",
                        "to": f"skill_{sk_key}",
                        "color": {"color": "rgba(0,0,0,0.08)"},
                        "width": 1,
                    })

    for c in connections:
        edges.append({
            "from": f"entry_{c['source_entry_id']}",
            "to": f"entry_{c['target_entry_id']}",
            "label": c["relationship"],
            "title": c.get("explanation") or c["relationship"],
            "color": {"color": "#f43f5e"},
            "width": max(1.5, c["strength"] * 5),
            "arrows": "to",
        })

    return jsonify({"nodes": nodes, "edges": edges})


@app.route("/api/analytics-data")
def api_analytics_data():
    entries = db.get_all_entries()

    # Activity by date
    activity = {}
    for e in entries:
        d = e["created_at"][:10]
        activity[d] = activity.get(d, 0) + 1

    # Top skills
    skill_counts = {}
    for e in entries:
        if e.get("skills"):
            for s in e["skills"].split(", "):
                s = s.strip()
                skill_counts[s] = skill_counts.get(s, 0) + 1
    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    # Complexity
    complexity = {}
    for e in entries:
        cls = e.get("ai_classification") or {}
        c = cls.get("complexity", "").lower()
        if c:
            complexity[c] = complexity.get(c, 0) + 1

    # Domains
    domain_counts = {}
    for e in entries:
        cls = e.get("ai_classification") or {}
        d = cls.get("domain")
        if d:
            domain_counts[d] = domain_counts.get(d, 0) + 1

    return jsonify({
        "activity": {
            "labels": sorted(activity.keys()),
            "data": [activity[k] for k in sorted(activity.keys())],
        },
        "skills": {
            "labels": [s[0] for s in top_skills],
            "data": [s[1] for s in top_skills],
        },
        "complexity": {
            "labels": list(complexity.keys()),
            "data": list(complexity.values()),
        },
        "domains": {
            "labels": list(domain_counts.keys()),
            "data": list(domain_counts.values()),
        },
    })


# ── Run ──────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)
