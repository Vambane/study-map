"""
Re-classify existing entries that are missing AI classification.

Usage:
    python reclassify.py           # re-classify all unclassified entries
    python reclassify.py 1 3       # re-classify specific entry IDs
"""

import sys
import json
import database as db
import ai_service


def reclassify_entry(entry_id: int) -> bool:
    """Re-classify a single entry and update the database."""
    entry = db.get_entry_by_id(entry_id)
    if not entry:
        print(f"  Entry #{entry_id} not found.")
        return False

    print(f"  Processing #{entry_id}: {entry['topic_title']}")

    # Get topic and skills
    topic = entry["topic_title"]
    skills = [s.strip() for s in entry.get("skills", "").split(", ") if s.strip()]
    summary = entry["summary"]

    # Get all entries for context (excluding this one)
    all_entries = [e for e in db.get_all_entries() if e["id"] != entry_id]

    # Call AI
    try:
        result = ai_service.classify_entry(topic, skills, summary, all_entries)
    except Exception as exc:
        print(f"  AI classification failed: {exc}")
        return False

    if not result:
        print(f"  No result from AI.")
        return False

    # Update classification in database
    classification = result.get("classification")
    if classification:
        conn = db.get_connection()
        conn.execute(
            "UPDATE entries SET ai_classification = ? WHERE id = ?",
            (json.dumps(classification), entry_id),
        )
        conn.commit()
        conn.close()
        print(f"  Updated classification: {classification.get('domain')} / {classification.get('complexity')}")

    # Add connections
    for c in result.get("connections", []):
        try:
            db.add_connection(
                source_id=entry_id,
                target_id=int(c["entry_id"]),
                relationship=c["relationship"],
                strength=float(c.get("strength", 0.5)),
                explanation=c.get("explanation"),
            )
            print(f"  Added connection to #{c['entry_id']}: {c['relationship']}")
        except Exception as e:
            print(f"  Connection skipped: {e}")

    # Add blindspots
    for bs in result.get("blindspots", []):
        try:
            db.add_blindspot(
                entry_id=entry_id,
                suggestion=bs["suggestion"],
                category=bs.get("category"),
                why_important=bs.get("why_important"),
                how_it_helps=bs.get("how_it_helps"),
            )
            print(f"  Added blindspot: {bs['suggestion'][:50]}...")
        except Exception as e:
            print(f"  Blindspot skipped: {e}")

    # Save enhanced summary
    enhanced = result.get("enhanced_summary")
    if enhanced:
        db.update_enhanced_summary(entry_id, enhanced)
        print(f"  Updated enhanced summary ({len(enhanced)} chars)")

    return True


def main():
    db.init_db()

    # Determine which entries to process
    if len(sys.argv) > 1:
        entry_ids = [int(x) for x in sys.argv[1:]]
    else:
        # Find all unclassified entries
        entries = db.get_all_entries()
        entry_ids = [e["id"] for e in entries if not e.get("ai_classification")]

    if not entry_ids:
        print("No entries to re-classify.")
        return

    print(f"Re-classifying {len(entry_ids)} entry(s): {entry_ids}\n")

    success = 0
    for eid in entry_ids:
        if reclassify_entry(eid):
            success += 1
        print()

    print(f"Done. {success}/{len(entry_ids)} entries re-classified.")


if __name__ == "__main__":
    main()
