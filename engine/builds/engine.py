"""AIde Kernel — engine.py
Single-file kernel: primitives, validator, reducer, renderer.
Pure functions. No IO. No AI. Deterministic.

Usage:
    import json, engine
    snap = engine.empty_state()
    for evt in events:
        result = engine.reduce(snap, evt)
        snap = result["snapshot"]
    html = engine.render(snap, blueprint, events)
"""
from __future__ import annotations
import copy, json, re
from datetime import datetime, timezone
from html import escape as _esc

# ── Field Types ──────────────────────────────────────────────────────────────

SCALAR_TYPES = {"string","int","float","bool","date","datetime"}
NULLABLE_TYPES = {f"{t}?" for t in SCALAR_TYPES}
ALL_SIMPLE_TYPES = SCALAR_TYPES | NULLABLE_TYPES

def is_nullable(schema_type):
    if isinstance(schema_type, str): return schema_type.endswith("?")
    if isinstance(schema_type, dict):
        if "enum" in schema_type: return False  # enums required by default
        if "list" in schema_type: return False
    return False

def base_type(schema_type):
    if isinstance(schema_type, str): return schema_type.rstrip("?")
    if isinstance(schema_type, dict):
        if "enum" in schema_type: return "enum"
        if "list" in schema_type: return "list"
    return "unknown"

def is_valid_type(schema_type):
    if isinstance(schema_type, str): return schema_type in ALL_SIMPLE_TYPES
    if isinstance(schema_type, dict):
        if "enum" in schema_type: return isinstance(schema_type["enum"], list) and len(schema_type["enum"]) > 0
        if "list" in schema_type: return schema_type["list"] in SCALAR_TYPES
    return False

def validate_value(value, schema_type):
    if value is None: return is_nullable(schema_type)
    bt = base_type(schema_type)
    if bt == "string": return isinstance(value, str)
    if bt == "int": return isinstance(value, int) and not isinstance(value, bool)
    if bt == "float": return isinstance(value, (int, float)) and not isinstance(value, bool)
    if bt == "bool": return isinstance(value, bool)
    if bt == "date": return isinstance(value, str) and _is_date(value)
    if bt == "datetime": return isinstance(value, str) and _is_datetime(value)
    if bt == "enum":
        opts = schema_type["enum"] if isinstance(schema_type, dict) else []
        return value in opts
    if bt == "list":
        if not isinstance(value, list): return False
        inner = schema_type["list"] if isinstance(schema_type, dict) else "string"
        return all(validate_value(v, inner) for v in value)
    return False

def _is_date(s):
    try: datetime.strptime(s, "%Y-%m-%d"); return True
    except ValueError: return False

def _is_datetime(s):
    try:
        s = s.replace("Z", "+00:00")
        datetime.fromisoformat(s); return True
    except ValueError: return False

# ── Empty State ──────────────────────────────────────────────────────────────

def empty_state():
    return {"version":1,"meta":{},"collections":{},"relationships":[],"relationship_types":{},"constraints":[],"blocks":{"block_root":{"type":"root","children":[]}},"views":{},"styles":{},"annotations":[]}

# ── Reducer ──────────────────────────────────────────────────────────────────

def reduce(snapshot, event):
    s = copy.deepcopy(snapshot)
    t, p, seq = event["type"], event["payload"], event.get("sequence", 0)
    fn = _REDUCERS.get(t)
    if not fn: return _reject(s, "UNKNOWN_PRIMITIVE", f"Unknown type: {t}")
    return fn(s, p, seq, event)

def replay(events):
    s = empty_state()
    for e in events:
        r = reduce(s, e)
        s = r["snapshot"]
    return s

class ReduceResult(dict):
    """Dict that also supports attribute access."""
    def __getattr__(self, k):
        try: return self[k]
        except KeyError: raise AttributeError(k)

class Warning(dict):
    def __getattr__(self, k):
        try: return self[k]
        except KeyError: raise AttributeError(k)

def _ok(s, warnings=None): return ReduceResult(snapshot=s,applied=True,warnings=warnings or [],error=None)
def _reject(s, code, msg): return ReduceResult(snapshot=s,applied=False,warnings=[],error=f"{code}: {msg}")
def _warn(code, msg): return Warning(code=code,message=msg)

def _get_coll(s, cid):
    c = s["collections"].get(cid)
    if not c: return None, "COLLECTION_NOT_FOUND"
    if c.get("_removed"): return None, "COLLECTION_NOT_FOUND"
    return c, None

# ── Constraint Checking ──────────────────────────────────────────────────────

def _check_constraints(s, event_type, collection_id=None, entity_id=None):
    warnings = []
    for con in s.get("constraints", []):
        rule = con.get("rule")
        strict = con.get("strict", False)
        if rule == "collection_max_entities" and event_type == "entity.create":
            cid = con.get("collection")
            if cid != collection_id: continue
            c = s["collections"].get(cid)
            if not c: continue
            count = sum(1 for e in c["entities"].values() if not e.get("_removed"))
            if count > con.get("value", float("inf")):
                code = "STRICT_CONSTRAINT_VIOLATED" if strict else "CONSTRAINT_VIOLATED"
                warnings.append(_warn(code, con.get("message", f"Max {con.get('value')} entities exceeded")))
        elif rule == "unique_field" and event_type in ("entity.create", "entity.update"):
            cid = con.get("collection")
            if cid != collection_id: continue
            field = con.get("field")
            c = s["collections"].get(cid)
            if not c or not field: continue
            vals = [e.get(field) for e in c["entities"].values() if not e.get("_removed") and e.get(field) is not None]
            if len(vals) != len(set(str(v) for v in vals)):
                code = "STRICT_CONSTRAINT_VIOLATED" if strict else "CONSTRAINT_VIOLATED"
                warnings.append(_warn(code, con.get("message", f"Duplicate values in {field}")))
    return warnings

# ── Entity Primitives ────────────────────────────────────────────────────────

def _entity_create(s, p, seq, evt):
    cid = p.get("collection")
    c, err = _get_coll(s, cid)
    if err: return _reject(s, err, cid)
    eid = p.get("id") or f"{cid}_{len(c['entities'])+1}"
    existing = c["entities"].get(eid)
    if existing and not existing.get("_removed"):
        return _reject(s, "ENTITY_ALREADY_EXISTS", eid)
    fields, schema, warnings = p.get("fields", {}), c["schema"], []
    entity = {}
    for fname, ftype in schema.items():
        if fname in fields:
            if not validate_value(fields[fname], ftype):
                return _reject(s, "TYPE_MISMATCH", f"{fname}: expected {ftype}")
            entity[fname] = fields[fname]
        elif is_nullable(ftype):
            entity[fname] = None
        else:
            return _reject(s, "REQUIRED_FIELD_MISSING", fname)
    for k in fields:
        if k not in schema: warnings.append(_warn("UNKNOWN_FIELD_IGNORED", k))
    entity["_removed"] = False
    entity["_created_seq"] = seq
    c["entities"][eid] = entity
    # Check constraints
    warnings.extend(_check_constraints(s, "entity.create", cid, eid))
    # If strict constraint violated, reject
    for w in warnings:
        if w.get("code") == "STRICT_CONSTRAINT_VIOLATED":
            c["entities"].pop(eid)
            return _reject(s, "STRICT_CONSTRAINT_VIOLATED", w.get("message",""))
    return _ok(s, warnings)

def _entity_update(s, p, seq, evt):
    if "filter" in p: return _entity_update_filter(s, p, seq)
    ref = p.get("ref", "")
    parts = ref.split("/", 1)
    if len(parts) != 2: return _reject(s, "ENTITY_NOT_FOUND", ref)
    cid, eid = parts
    c, err = _get_coll(s, cid)
    if err: return _reject(s, err, cid)
    e = c["entities"].get(eid)
    if not e: return _reject(s, "ENTITY_NOT_FOUND", eid)
    if e.get("_removed"): return _reject(s, "ENTITY_NOT_FOUND", f"{eid} (removed)")
    for fname, val in p.get("fields", {}).items():
        ftype = c["schema"].get(fname)
        if ftype and not validate_value(val, ftype):
            return _reject(s, "TYPE_MISMATCH", f"{fname}: expected {ftype}")
        e[fname] = val
    e["_updated_seq"] = seq
    return _ok(s)

def _entity_update_filter(s, p, seq):
    f = p["filter"]
    cid = f.get("collection")
    c, err = _get_coll(s, cid)
    if err: return _reject(s, err, cid)
    where = f.get("where", {})
    fields = p.get("fields", {})
    count = 0
    for e in c["entities"].values():
        if e.get("_removed"): continue
        if all(e.get(k) == v for k, v in where.items()):
            for fname, val in fields.items():
                ftype = c["schema"].get(fname)
                if ftype and not validate_value(val, ftype):
                    return _reject(s, "TYPE_MISMATCH", f"{fname}: expected {ftype}")
                e[fname] = val
            e["_updated_seq"] = seq
            count += 1
    return _ok(s, [_warn("ENTITIES_AFFECTED", f"{count} entities updated")])

def _entity_remove(s, p, seq, evt):
    ref = p.get("ref", "")
    parts = ref.split("/", 1)
    if len(parts) != 2: return _reject(s, "ENTITY_NOT_FOUND", ref)
    cid, eid = parts
    c, err = _get_coll(s, cid)
    if err: return _reject(s, err, cid)
    e = c["entities"].get(eid)
    if not e: return _reject(s, "ENTITY_NOT_FOUND", eid)
    if e.get("_removed"): return _ok(s, [_warn("ALREADY_REMOVED", eid)])
    e["_removed"] = True
    e["_removed_seq"] = seq
    s["relationships"] = [r for r in s["relationships"] if r.get("from") != ref and r.get("to") != ref]
    return _ok(s)

# ── Collection Primitives ────────────────────────────────────────────────────

def _collection_create(s, p, seq, evt):
    cid = p.get("id")
    existing = s["collections"].get(cid)
    if existing and not existing.get("_removed"):
        return _reject(s, "COLLECTION_ALREADY_EXISTS", cid)
    schema = p.get("schema", {})
    for fname, ftype in schema.items():
        if not is_valid_type(ftype):
            return _reject(s, "TYPE_MISMATCH", f"Unknown type: {ftype}")
    s["collections"][cid] = {"id":cid,"name":p.get("name",cid),"schema":schema,"settings":p.get("settings",{}),"entities":{},"_removed":False,"_created_seq":seq}
    return _ok(s)

def _collection_update(s, p, seq, evt):
    cid = p.get("id")
    c, err = _get_coll(s, cid)
    if err: return _reject(s, err, cid)
    if "name" in p: c["name"] = p["name"]
    if "settings" in p:
        for k, v in p["settings"].items():
            if v is None: c["settings"].pop(k, None)
            else: c["settings"][k] = v
    return _ok(s)

def _collection_remove(s, p, seq, evt):
    cid = p.get("id")
    c = s["collections"].get(cid)
    if not c: return _reject(s, "COLLECTION_NOT_FOUND", cid)
    if c.get("_removed"): return _ok(s, [_warn("ALREADY_REMOVED", cid)])
    c["_removed"] = True
    for e in c["entities"].values(): e["_removed"] = True
    s["views"] = {k:v for k,v in s["views"].items() if v.get("source") != cid}
    return _ok(s)

# ── Field Primitives ─────────────────────────────────────────────────────────

def _field_add(s, p, seq, evt):
    cid = p.get("collection")
    c, err = _get_coll(s, cid)
    if err: return _reject(s, err, cid)
    name, ftype = p.get("name"), p.get("type")
    if name in c["schema"]: return _reject(s, "FIELD_ALREADY_EXISTS", name)
    if not is_valid_type(ftype): return _reject(s, "TYPE_MISMATCH", f"Unknown type: {ftype}")
    default = p.get("default")
    has_entities = any(not e.get("_removed") for e in c["entities"].values())
    if not is_nullable(ftype) and default is None and has_entities:
        return _reject(s, "REQUIRED_FIELD_NO_DEFAULT", name)
    c["schema"][name] = ftype
    for e in c["entities"].values():
        e[name] = default
    return _ok(s)

def _field_update(s, p, seq, evt):
    cid = p.get("collection")
    c, err = _get_coll(s, cid)
    if err: return _reject(s, err, cid)
    name = p.get("name")
    if name not in c["schema"]: return _reject(s, "FIELD_NOT_FOUND", name)
    warnings = []
    if "type" in p:
        old_type, new_type = c["schema"][name], p["type"]
        old_base, new_base = base_type(old_type), base_type(new_type)
        # Type compatibility matrix
        _COMPAT = {
            ("string","int"),("string","float"),("string","bool"),("string","enum"),("string","date"),
            ("int","string"),("int","float"),("int","bool"),("int","enum"),
            ("float","string"),("float","int"),("float","enum"),
            ("bool","string"),("bool","int"),("bool","enum"),
            ("enum","string"),("enum","enum"),
            ("date","string"),("date","date"),
        }
        if old_base != new_base:
            if old_base == "list" or new_base == "list":
                return _reject(s, "INCOMPATIBLE_TYPE_CHANGE", f"{old_type} → {new_type}")
            if (old_base, new_base) not in _COMPAT:
                return _reject(s, "INCOMPATIBLE_TYPE_CHANGE", f"{old_type} → {new_type}")
            if old_base == "float" and new_base == "int":
                warnings.append(_warn("LOSSY_TYPE_CONVERSION", "float → int"))
            # Check* conversions: scan existing values
            _CHECK_CONVERT = {("string","int"),("string","float"),("string","bool"),("string","date"),("string","enum")}
            if (old_base, new_base) in _CHECK_CONVERT:
                for e in c["entities"].values():
                    if e.get("_removed"): continue
                    v = e.get(name)
                    if v is None: continue
                    if new_base == "int":
                        try: int(v)
                        except (ValueError, TypeError):
                            return _reject(s, "INCOMPATIBLE_TYPE_CHANGE", f"value '{v}' can't convert to int")
                    elif new_base == "float":
                        try: float(v)
                        except (ValueError, TypeError):
                            return _reject(s, "INCOMPATIBLE_TYPE_CHANGE", f"value '{v}' can't convert to float")
                    elif new_base == "bool":
                        if v not in ("true","false","0","1","True","False"):
                            return _reject(s, "INCOMPATIBLE_TYPE_CHANGE", f"value '{v}' can't convert to bool")
                    elif new_base == "date":
                        if not _is_date(str(v)):
                            return _reject(s, "INCOMPATIBLE_TYPE_CHANGE", f"value '{v}' can't convert to date")
            # Check existing values for enum conversion
            if new_base == "enum" and isinstance(new_type, dict):
                allowed = new_type.get("enum", [])
                for e in c["entities"].values():
                    if e.get("_removed"): continue
                    v = e.get(name)
                    if v is not None and v not in allowed:
                        return _reject(s, "INCOMPATIBLE_TYPE_CHANGE", f"value '{v}' not in {allowed}")
        c["schema"][name] = new_type
    if "rename" in p:
        new_name = p["rename"]
        if new_name in c["schema"]: return _reject(s, "FIELD_ALREADY_EXISTS", new_name)
        c["schema"][new_name] = c["schema"].pop(name)
        for e in c["entities"].values():
            if name in e: e[new_name] = e.pop(name)
    return _ok(s, warnings)

def _field_remove(s, p, seq, evt):
    cid = p.get("collection")
    c, err = _get_coll(s, cid)
    if err: return _reject(s, err, cid)
    name = p.get("name")
    if name not in c["schema"]: return _reject(s, "FIELD_NOT_FOUND", name)
    del c["schema"][name]
    for e in c["entities"].values(): e.pop(name, None)
    warnings = []
    for v in s["views"].values():
        cfg = v.get("config", {})
        for key in ("show_fields","hide_fields"):
            if name in cfg.get(key, []):
                cfg[key] = [f for f in cfg[key] if f != name]
                warnings.append(_warn("VIEW_FIELD_MISSING", f"{v['id']}.{key}"))
        if cfg.get("sort_by") == name: cfg.pop("sort_by", None)
        if cfg.get("group_by") == name: cfg.pop("group_by", None)
    return _ok(s, warnings)

# ── Relationship Primitives ──────────────────────────────────────────────────

def _relationship_set(s, p, seq, evt):
    fr, to, rtype = p.get("from"), p.get("to"), p.get("type")
    # Validate both entity refs exist
    for ref in (fr, to):
        if ref:
            parts = ref.split("/", 1)
            if len(parts) == 2:
                cid, eid = parts
                c = s["collections"].get(cid)
                if not c or c.get("_removed"):
                    return _reject(s, "COLLECTION_NOT_FOUND", cid)
                e = c["entities"].get(eid)
                if not e or e.get("_removed"):
                    return _reject(s, "ENTITY_NOT_FOUND", ref)
    card = p.get("cardinality", "many_to_one")
    if rtype not in s["relationship_types"]:
        s["relationship_types"][rtype] = {"cardinality": card}
    else:
        card = s["relationship_types"][rtype]["cardinality"]
    if card == "many_to_one":
        s["relationships"] = [r for r in s["relationships"] if not (r["from"]==fr and r["type"]==rtype)]
    elif card == "one_to_one":
        s["relationships"] = [r for r in s["relationships"] if not ((r["from"]==fr and r["type"]==rtype) or (r["to"]==to and r["type"]==rtype))]
    s["relationships"].append({"from":fr,"to":to,"type":rtype,"data":p.get("data",{}),"_seq":seq})
    return _ok(s)

def _relationship_constrain(s, p, seq, evt):
    s["constraints"].append({"id":p.get("id"),"rule":p.get("rule"),"entities":p.get("entities",[]),"relationship_type":p.get("relationship_type"),"value":p.get("value"),"message":p.get("message",""),"strict":p.get("strict",False)})
    return _ok(s)

# ── Block Primitives ─────────────────────────────────────────────────────────

def _block_set(s, p, seq, evt):
    bid = p.get("id")
    blocks = s["blocks"]
    if bid in blocks:  # UPDATE
        b = blocks[bid]
        if "props" in p:
            b.setdefault("props", {}).update(p["props"])
        if "parent" in p:  # reparent
            for blk in blocks.values():
                if bid in blk.get("children", []):
                    blk["children"].remove(bid)
            parent = blocks.get(p["parent"])
            if parent:
                pos = p.get("position")
                if pos is not None: parent["children"].insert(pos, bid)
                else: parent["children"].append(bid)
    else:  # CREATE
        if "type" not in p: return _reject(s, "BLOCK_TYPE_MISSING", bid)
        parent_id = p.get("parent", "block_root")
        parent = blocks.get(parent_id)
        if not parent: return _reject(s, "BLOCK_NOT_FOUND", parent_id)
        blocks[bid] = {"type":p["type"],"children":[],"props":p.get("props",{})}
        pos = p.get("position")
        if pos is not None: parent["children"].insert(pos, bid)
        else: parent["children"].append(bid)
    return _ok(s)

def _block_remove(s, p, seq, evt):
    bid = p.get("id")
    if bid == "block_root": return _reject(s, "CANT_REMOVE_ROOT", "")
    blocks = s["blocks"]
    if bid not in blocks: return _reject(s, "BLOCK_NOT_FOUND", bid)
    def collect(b):
        ids = [b]
        for c in blocks.get(b, {}).get("children", []): ids.extend(collect(c))
        return ids
    to_remove = collect(bid)
    for blk in blocks.values():
        if bid in blk.get("children", []): blk["children"].remove(bid)
    for rid in to_remove: blocks.pop(rid, None)
    return _ok(s)

def _block_reorder(s, p, seq, evt):
    pid = p.get("parent")
    parent = s["blocks"].get(pid)
    if not parent: return _reject(s, "BLOCK_NOT_FOUND", pid)
    new_order = p.get("children", [])
    current = parent["children"]
    remaining = [c for c in current if c not in new_order]
    parent["children"] = [c for c in new_order if c in current] + remaining
    return _ok(s)

# ── View Primitives ──────────────────────────────────────────────────────────

def _view_create(s, p, seq, evt):
    vid = p.get("id")
    if vid in s["views"]: return _reject(s, "VIEW_ALREADY_EXISTS", vid)
    src = p.get("source")
    c, err = _get_coll(s, src)
    if err: return _reject(s, err, src)
    s["views"][vid] = {"id":vid,"type":p.get("type","table"),"source":src,"config":p.get("config",{})}
    return _ok(s)

def _view_update(s, p, seq, evt):
    vid = p.get("id")
    v = s["views"].get(vid)
    if not v: return _reject(s, "VIEW_NOT_FOUND", vid)
    if "type" in p: v["type"] = p["type"]
    if "config" in p: v["config"].update(p["config"])
    return _ok(s)

def _view_remove(s, p, seq, evt):
    vid = p.get("id")
    if vid not in s["views"]: return _reject(s, "VIEW_NOT_FOUND", vid)
    del s["views"][vid]
    return _ok(s)

# ── Style Primitives ─────────────────────────────────────────────────────────

def _style_set(s, p, seq, evt):
    for k, v in p.items():
        if v is None: s["styles"].pop(k, None)
        else: s["styles"][k] = v
    return _ok(s)

def _style_set_entity(s, p, seq, evt):
    ref = p.get("ref", "")
    parts = ref.split("/", 1)
    if len(parts) != 2: return _reject(s, "ENTITY_NOT_FOUND", ref)
    cid, eid = parts
    c, err = _get_coll(s, cid)
    if err: return _reject(s, err, cid)
    e = c["entities"].get(eid)
    if not e or e.get("_removed"): return _reject(s, "ENTITY_NOT_FOUND", ref)
    e.setdefault("_styles", {}).update(p.get("styles", {}))
    return _ok(s)

# ── Meta Primitives ──────────────────────────────────────────────────────────

def _meta_update(s, p, seq, evt):
    for k, v in p.items(): s["meta"][k] = v
    return _ok(s)

def _meta_annotate(s, p, seq, evt):
    s["annotations"].append({"note":p.get("note",""),"pinned":p.get("pinned",False),"seq":seq,"timestamp":evt.get("timestamp","")})
    return _ok(s)

def _meta_constrain(s, p, seq, evt):
    cid = p.get("id")
    for i, c in enumerate(s["constraints"]):
        if c.get("id") == cid: s["constraints"][i] = p; return _ok(s)
    s["constraints"].append(p)
    return _ok(s)

_REDUCERS = {
    "entity.create":_entity_create,"entity.update":_entity_update,"entity.remove":_entity_remove,
    "collection.create":_collection_create,"collection.update":_collection_update,"collection.remove":_collection_remove,
    "field.add":_field_add,"field.update":_field_update,"field.remove":_field_remove,
    "relationship.set":_relationship_set,"relationship.constrain":_relationship_constrain,
    "block.set":_block_set,"block.remove":_block_remove,"block.reorder":_block_reorder,
    "view.create":_view_create,"view.update":_view_update,"view.remove":_view_remove,
    "style.set":_style_set,"style.set_entity":_style_set_entity,
    "meta.update":_meta_update,"meta.annotate":_meta_annotate,"meta.constrain":_meta_constrain,
}

# ── Renderer ─────────────────────────────────────────────────────────────────

def render(snapshot, blueprint, events=None, footer="Made with AIde"):
    title = _esc(snapshot.get("meta",{}).get("title","AIde"))
    desc = _esc(_derive_desc(snapshot))
    bp_json = json.dumps(blueprint, indent=2, sort_keys=True, ensure_ascii=False)
    st_json = json.dumps(snapshot, indent=2, sort_keys=True, ensure_ascii=False)
    ev_json = json.dumps(events or [], indent=2, sort_keys=True, ensure_ascii=False)
    body = _render_block("block_root", snapshot)
    annots = _render_annotations(snapshot)
    foot = _render_footer(footer) if footer else ""
    now = datetime.now(timezone.utc).strftime("%b %-d, %Y")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta property="og:title" content="{title}">
  <meta property="og:type" content="website">
  <meta property="og:description" content="{desc}">
  <meta name="description" content="{desc}">
  <script type="application/aide-blueprint+json" id="aide-blueprint">
{bp_json}
  </script>
  <script type="application/aide+json" id="aide-state">
{st_json}
  </script>
  <script type="application/aide-events+json" id="aide-events">
{ev_json}
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,400&family=IBM+Plex+Sans:wght@300;400;500&display=swap" rel="stylesheet">
  <style>{CSS}</style>
</head>
<body>
  <main class="aide-page">
{body}{annots}
    <footer class="aide-footer">
      <a href="https://toaide.com" class="aide-footer__link">{foot}</a>
      <span class="aide-footer__sep">&middot;</span>
      <span>Updated {now}</span>
    </footer>
  </main>
</body>
</html>"""

def _derive_desc(s):
    root = s["blocks"].get("block_root",{})
    for bid in root.get("children",[]):
        b = s["blocks"].get(bid,{})
        if b.get("type") == "text": return b.get("props",{}).get("content","")[:160]
    for c in s["collections"].values():
        if c.get("_removed"): continue
        n = sum(1 for e in c["entities"].values() if not e.get("_removed"))
        return f"{c.get('name',c['id'])}: {n} items"
    return s.get("meta",{}).get("title","A living page")

def _render_footer(text): return text or "Made with AIde"

# ── Block Rendering ──────────────────────────────────────────────────────────

def _render_block(bid, s):
    b = s["blocks"].get(bid)
    if not b: return ""
    t = b.get("type","")
    p = b.get("props",{})
    html = ""
    if t == "root": pass
    elif t == "heading":
        lvl = p.get("level",1)
        html = f'    <h{lvl} class="aide-heading aide-heading--{lvl}">{_inline(p.get("content",""))}</h{lvl}>\n'
    elif t == "text":
        html = f'    <p class="aide-text">{_inline(p.get("content",""))}</p>\n'
    elif t == "metric":
        html = f'    <div class="aide-metric"><span class="aide-metric__label">{_esc(p.get("label",""))}</span><span class="aide-metric__value">{_esc(p.get("value",""))}</span></div>\n'
    elif t == "divider":
        html = '    <hr class="aide-divider">\n'
    elif t == "callout":
        html = f'    <div class="aide-callout">{_inline(p.get("content",""))}</div>\n'
    elif t == "image":
        cap = f'<figcaption class="aide-image__caption">{_esc(p.get("caption",""))}</figcaption>' if p.get("caption") else ""
        html = f'    <figure class="aide-image"><img src="{_esc(p.get("src",""))}" alt="{_esc(p.get("alt",""))}" loading="lazy">{cap}</figure>\n'
    elif t == "collection_view":
        html = _render_collection_view(p, s)
    elif t == "column_list":
        html = '    <div class="aide-columns">\n'
    elif t == "column":
        w = p.get("width")
        style = f' style="flex:0 0 {w}"' if w else ""
        html = f'    <div class="aide-column"{style}>\n'
    children = "".join(_render_block(c, s) for c in b.get("children",[]))
    if t == "column_list": children += "    </div>\n"
    if t == "column": children += "    </div>\n"
    return html + children

def _render_collection_view(props, s):
    vid = props.get("view_id") or props.get("view")
    view = s["views"].get(vid)
    if not view: return ""
    src = view.get("source") or props.get("source")
    coll = s["collections"].get(src)
    if not coll or coll.get("_removed"): return ""
    entities = [e for e in coll["entities"].values() if not e.get("_removed")]
    cfg = view.get("config",{})
    entities = _apply_sort(entities, cfg)
    entities = _apply_filter(entities, cfg)
    vtype = view.get("type","table")
    schema = coll.get("schema",{})
    show = cfg.get("show_fields") or [f for f in schema if not f.startswith("_")]
    if vtype == "table": return _render_table(entities, schema, show)
    if vtype == "list": return _render_list(entities, schema, show)
    return _render_table(entities, schema, show)  # fallback

def _apply_sort(entities, cfg):
    sb = cfg.get("sort_by")
    if not sb: return entities
    rev = cfg.get("sort_order","asc") == "desc"
    return sorted(entities, key=lambda e: (0 if e.get(sb) is not None else 1, e.get(sb,"")), reverse=rev)

def _apply_filter(entities, cfg):
    f = cfg.get("filter")
    if not f: return entities
    return [e for e in entities if all(e.get(k)==v for k,v in f.items())]

def _render_table(entities, schema, fields):
    if not entities and not fields: return '    <p class="aide-collection-empty">No items yet.</p>\n'
    h = "".join(f'<th>{_esc(_display_name(f))}</th>' for f in fields)
    rows = ""
    for e in entities:
        cells = "".join(f'<td class="aide-table__td--{base_type(schema.get(f,"string"))}">{_fmt(e.get(f), schema.get(f,"string"))}</td>' for f in fields)
        rows += f"<tr>{cells}</tr>"
    return f'    <div class="aide-table-wrap"><table class="aide-table"><thead><tr>{h}</tr></thead><tbody>{rows}</tbody></table></div>\n'

def _render_list(entities, schema, fields):
    if not entities: return '    <p class="aide-collection-empty">No items yet.</p>\n'
    items = ""
    for e in entities:
        spans = "".join(f'<span class="aide-list__field">{_fmt(e.get(f), schema.get(f,"string"))}</span>' for f in fields)
        items += f'<li class="aide-list__item">{spans}</li>'
    return f'    <ul class="aide-list">{items}</ul>\n'

def _render_annotations(s):
    annots = s.get("annotations",[])
    if not annots: return ""
    pinned = [a for a in annots if a.get("pinned")]
    unpinned = [a for a in annots if not a.get("pinned")]
    ordered = pinned + list(reversed(unpinned))
    items = ""
    for a in ordered:
        ts = a.get("timestamp","")
        short = ts[:10] if ts else ""
        pin = " aide-annotation--pinned" if a.get("pinned") else ""
        items += f'<div class="aide-annotation{pin}"><span class="aide-annotation__text">{_esc(a.get("note",""))}</span><span class="aide-annotation__meta">{short}</span></div>'
    return f'    <section class="aide-annotations"><h3 class="aide-heading aide-heading--3">Notes</h3>{items}</section>\n'

# ── Value Formatting ─────────────────────────────────────────────────────────

def _fmt(val, schema_type):
    if val is None: return '<span class="aide-null">&mdash;</span>'
    bt = base_type(schema_type)
    if bt == "bool": return "&#10003;" if val else "&#9675;"
    if bt == "date" and isinstance(val, str):
        try:
            d = datetime.strptime(val, "%Y-%m-%d")
            return _esc(d.strftime("%b %-d"))
        except ValueError: pass
    if bt == "datetime" and isinstance(val, str):
        try:
            d = datetime.fromisoformat(val.replace("Z","+00:00"))
            return _esc(d.strftime("%b %-d, %-I:%M %p"))
        except ValueError: pass
    if bt == "enum": return _esc(str(val).replace("_"," ").title())
    if bt == "list" and isinstance(val, list): return _esc(", ".join(str(v) for v in val))
    if bt in ("int","float") and isinstance(val, (int,float)): return _esc(f"{val:,}" if isinstance(val,int) else f"{val:,.2f}")
    return _esc(str(val))

def _display_name(field_name):
    return field_name.replace("_"," ").title()

def _inline(text):
    t = _esc(text)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'\*(.+?)\*', r'<em>\1</em>', t)
    t = re.sub(r'\[(.+?)\]\((https?://[^\)]+)\)', r'<a href="\2">\1</a>', t)
    return t

# ── CSS ──────────────────────────────────────────────────────────────────────

CSS = """*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--font-serif:'Cormorant Garamond',Georgia,serif;--font-sans:'IBM Plex Sans',-apple-system,sans-serif;--text-primary:#2d3748;--text-secondary:#4a5568;--text-tertiary:#a0aec0;--text-slate:#4a5568;--bg-primary:#fafaf9;--bg-cream:#faf5ef;--border:#e2e8f0;--border-light:#edf2f7;--accent-steel:#4a6fa5;--accent-navy:#2c5282;--accent-forest:#48bb78;--radius-sm:4px;--space-1:4px;--space-2:8px;--space-3:12px;--space-4:16px;--space-5:20px;--space-6:24px;--space-8:32px;--space-10:40px;--space-12:48px;--space-16:64px}
body{font-family:var(--font-sans);font-size:16px;font-weight:300;line-height:1.65;color:var(--text-primary);background:var(--bg-primary);-webkit-font-smoothing:antialiased}
.aide-page{max-width:720px;margin:0 auto;padding:var(--space-12) var(--space-8)}
@media(max-width:640px){.aide-page{padding:var(--space-8) var(--space-5)}}
.aide-heading{margin-bottom:var(--space-4)}
.aide-heading--1{font-family:var(--font-serif);font-size:clamp(32px,4.5vw,42px);font-weight:400;line-height:1.2}
.aide-heading--2{font-family:var(--font-serif);font-size:clamp(24px,3.5vw,32px);font-weight:400;line-height:1.25;margin-top:var(--space-8)}
.aide-heading--3{font-family:var(--font-sans);font-size:18px;font-weight:500;line-height:1.4}
.aide-text{font-size:16px;font-weight:300;line-height:1.65;color:var(--text-secondary);margin-bottom:var(--space-4)}
.aide-text strong{font-weight:500;color:var(--text-primary)}
.aide-text a{color:var(--accent-steel);text-decoration:underline;text-decoration-color:var(--border);text-underline-offset:2px}
.aide-text a:hover{text-decoration-color:var(--accent-steel)}
.aide-metric{display:flex;align-items:baseline;gap:var(--space-2);padding:var(--space-3) 0}
.aide-metric__label{font-size:15px;font-weight:400;color:var(--text-secondary)}
.aide-metric__label::after{content:':'}
.aide-metric__value{font-size:15px;font-weight:500;color:var(--text-primary)}
.aide-divider{border:none;border-top:1px solid var(--border-light);margin:var(--space-6) 0}
.aide-callout{background:var(--bg-cream);border-left:3px solid var(--border);padding:var(--space-4) var(--space-5);margin:var(--space-4) 0;border-radius:0 var(--radius-sm) var(--radius-sm) 0;font-size:15px;line-height:1.55;color:var(--text-slate)}
.aide-image{margin:var(--space-6) 0}
.aide-image img{max-width:100%;height:auto;border-radius:var(--radius-sm)}
.aide-image__caption{font-size:13px;color:var(--text-tertiary);margin-top:var(--space-2)}
.aide-columns{display:flex;gap:var(--space-6)}
@media(max-width:640px){.aide-columns{flex-direction:column}}
.aide-column{flex:1}
.aide-table-wrap{overflow-x:auto;margin:var(--space-4) 0}
.aide-table{width:100%;border-collapse:collapse;font-size:15px}
.aide-table th{font-size:11px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;color:var(--text-tertiary);text-align:left;padding:var(--space-2) var(--space-3);border-bottom:2px solid var(--border)}
.aide-table td{padding:var(--space-3);border-bottom:1px solid var(--border-light);color:var(--text-slate);vertical-align:top}
.aide-table tr:last-child td{border-bottom:none}
.aide-table__td--int,.aide-table__td--float{text-align:right;font-variant-numeric:tabular-nums}
.aide-table__td--bool{text-align:center}
.aide-list{list-style:none;padding:0}
.aide-list__item{display:flex;align-items:baseline;gap:var(--space-3);padding:var(--space-3) 0;border-bottom:1px solid var(--border-light);font-size:15px;line-height:1.5}
.aide-list__item:last-child{border-bottom:none}
.aide-list__field{color:var(--text-secondary)}
.aide-null{color:var(--text-tertiary);font-style:italic}
.aide-collection-empty{color:var(--text-tertiary);font-size:15px;padding:var(--space-8) 0;text-align:center}
.aide-annotations{margin-top:var(--space-10)}
.aide-annotation{padding:var(--space-3) 0;border-bottom:1px solid var(--border-light)}
.aide-annotation:last-child{border-bottom:none}
.aide-annotation__text{font-size:15px;color:var(--text-slate);line-height:1.5}
.aide-annotation__meta{font-size:12px;color:var(--text-tertiary);margin-left:var(--space-3)}
.aide-annotation--pinned{border-left:3px solid var(--accent-navy);padding-left:var(--space-4)}
.aide-highlight{background-color:rgba(31,42,68,.04)}
.aide-group{margin-bottom:var(--space-6)}
.aide-group__header{font-size:11px;font-weight:500;letter-spacing:.1em;text-transform:uppercase;color:var(--text-tertiary);margin-bottom:var(--space-3);padding-bottom:var(--space-2);border-bottom:1px solid var(--border-light)}
.aide-footer{margin-top:var(--space-16);padding-top:var(--space-6);border-top:1px solid var(--border-light);font-size:12px;color:var(--text-tertiary);text-align:center}
.aide-footer a{color:var(--text-tertiary);text-decoration:none}
.aide-footer a:hover{color:var(--text-secondary)}
.aide-footer .aide-footer__sep{margin:0 var(--space-2)}"""

# ── CLI ──────────────────────────────────────────────────────────────────────

def parse_aide_html(html):
    """Extract blueprint, snapshot, events from an aide HTML file."""
    def _extract(tag_type):
        pat = rf'<script type="{re.escape(tag_type)}"[^>]*>(.*?)</script>'
        m = re.search(pat, html, re.DOTALL)
        return json.loads(m.group(1)) if m else None
    return {
        "blueprint": _extract("application/aide-blueprint+json") or {},
        "snapshot": _extract("application/aide+json") or empty_state(),
        "events": _extract("application/aide-events+json") or [],
    }

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: engine.py <command> [args]")
        print("  replay <events.json>              → snapshot.json")
        print("  render <snapshot.json> <bp.json>   → aide.html")
        print("  reduce <snapshot.json> <event.json> → result.json")
        print("  parse  <aide.html>                 → {blueprint,snapshot,events}.json")
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "replay":
        events = json.load(open(sys.argv[2]))
        print(json.dumps(replay(events), indent=2, sort_keys=True))
    elif cmd == "render":
        snap = json.load(open(sys.argv[2]))
        bp = json.load(open(sys.argv[3]))
        evts = json.load(open(sys.argv[4])) if len(sys.argv) > 4 else []
        print(render(snap, bp, evts))
    elif cmd == "reduce":
        snap = json.load(open(sys.argv[2]))
        evt = json.load(open(sys.argv[3]))
        print(json.dumps(reduce(snap, evt), indent=2, sort_keys=True))
    elif cmd == "parse":
        html = open(sys.argv[2]).read()
        parsed = parse_aide_html(html)
        for k, v in parsed.items():
            json.dump(v, open(f"{k}.json","w"), indent=2, sort_keys=True)
            print(f"Wrote {k}.json")
