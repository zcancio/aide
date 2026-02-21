"use strict";
/**
 * AIde Kernel — engine.ts
 * Single-file kernel: primitives, validator, reducer.
 * Pure functions. No IO. No AI. Deterministic.
 *
 * Usage:
 *   import { emptyState, reduce, replay, baseType, resolveViewEntities } from "./engine"
 *   let snap = emptyState()
 *   for (const evt of events) { snap = reduce(snap, evt).snapshot }
 *   // React renders from snapshot directly
 */
Object.defineProperty(exports, "__esModule", { value: true });
exports.emptyState = emptyState;
exports.reduce = reduce;
exports.replay = replay;
exports.isNullable = isNullable;
exports.baseType = baseType;
exports.applySort = applySort;
exports.applyFilter = applyFilter;
exports.resolveViewEntities = resolveViewEntities;
exports.resolveViewFields = resolveViewFields;
// ── Field Types ─────────────────────────────────────────────────────────────
const SCALAR_TYPES = new Set(["string", "int", "float", "bool", "date", "datetime"]);
function isNullable(t) {
    return typeof t === "string" && t.endsWith("?");
}
function baseType(t) {
    if (typeof t === "string")
        return t.replace(/\?$/, "");
    if (typeof t === "object" && "enum" in t)
        return "enum";
    if (typeof t === "object" && "list" in t)
        return "list";
    return "unknown";
}
function isValidType(t) {
    if (typeof t === "string")
        return SCALAR_TYPES.has(t.replace(/\?$/, ""));
    if (typeof t === "object" && "enum" in t)
        return Array.isArray(t.enum) && t.enum.length > 0;
    if (typeof t === "object" && "list" in t)
        return SCALAR_TYPES.has(t.list);
    return false;
}
function validateValue(val, t) {
    if (val === null || val === undefined)
        return isNullable(t);
    const bt = baseType(t);
    switch (bt) {
        case "string": return typeof val === "string";
        case "int": return typeof val === "number" && Number.isInteger(val);
        case "float": return typeof val === "number";
        case "bool": return typeof val === "boolean";
        case "date": return typeof val === "string" && /^\d{4}-\d{2}-\d{2}$/.test(val);
        case "datetime": return typeof val === "string" && !isNaN(Date.parse(val));
        case "enum": return typeof t === "object" && "enum" in t && t.enum.includes(val);
        case "list":
            if (!Array.isArray(val))
                return false;
            const inner = typeof t === "object" && "list" in t ? t.list : "string";
            return val.every(v => validateValue(v, inner));
        default: return false;
    }
}
// ── Empty State ─────────────────────────────────────────────────────────────
function emptyState() {
    return {
        version: 1, meta: {}, collections: {}, relationships: [],
        relationship_types: {}, constraints: [],
        blocks: { block_root: { type: "root", children: [], props: {} } },
        views: {}, styles: {}, annotations: [],
    };
}
// ── Reducer ─────────────────────────────────────────────────────────────────
function ok(s, warnings = []) {
    return { snapshot: s, applied: true, warnings, error: null };
}
function reject(s, code, msg) {
    return { snapshot: s, applied: false, warnings: [], error: `${code}: ${msg}` };
}
function warn(code, message) { return { code, message }; }
function getColl(s, cid) {
    const c = s.collections[cid];
    if (!c || c._removed)
        return [null, "COLLECTION_NOT_FOUND"];
    return [c, null];
}
function deepClone(obj) { return JSON.parse(JSON.stringify(obj)); }
function reduce(snapshot, event) {
    const s = deepClone(snapshot);
    const { type, payload, sequence: seq } = event;
    const fn = REDUCERS[type];
    if (!fn)
        return reject(s, "UNKNOWN_PRIMITIVE", `Unknown type: ${type}`);
    return fn(s, payload, seq ?? 0, event);
}
function replay(events) {
    let s = emptyState();
    for (const e of events) {
        const r = reduce(s, e);
        s = r.snapshot;
    }
    return s;
}
// ── Constraint Checking ─────────────────────────────────────────────────────
function checkConstraints(s, eventType, collectionId) {
    const warnings = [];
    for (const con of s.constraints) {
        if (con.rule === "collection_max_entities" && eventType === "entity.create") {
            if (con.collection !== collectionId)
                continue;
            const c = s.collections[con.collection];
            if (!c)
                continue;
            const count = Object.values(c.entities).filter(e => !e._removed).length;
            if (count > (con.value ?? Infinity)) {
                const code = con.strict ? "STRICT_CONSTRAINT_VIOLATED" : "CONSTRAINT_VIOLATED";
                warnings.push(warn(code, con.message || `Max ${con.value} entities exceeded`));
            }
        }
        else if (con.rule === "unique_field" && (eventType === "entity.create" || eventType === "entity.update")) {
            if (con.collection !== collectionId)
                continue;
            const c = s.collections[con.collection];
            if (!c || !con.field)
                continue;
            const vals = Object.values(c.entities).filter(e => !e._removed && e[con.field] != null).map(e => String(e[con.field]));
            if (vals.length !== new Set(vals).size) {
                const code = con.strict ? "STRICT_CONSTRAINT_VIOLATED" : "CONSTRAINT_VIOLATED";
                warnings.push(warn(code, con.message || `Duplicate values in ${con.field}`));
            }
        }
    }
    return warnings;
}
// ── Entity Primitives ───────────────────────────────────────────────────────
const entityCreate = (s, p, seq) => {
    const [c, err] = getColl(s, p.collection);
    if (err)
        return reject(s, err, p.collection);
    const eid = p.id || `${p.collection}_${Object.keys(c.entities).length + 1}`;
    const existing = c.entities[eid];
    if (existing && !existing._removed)
        return reject(s, "ENTITY_ALREADY_EXISTS", eid);
    const fields = p.fields || {};
    const schema = c.schema;
    const warnings = [];
    const entity = {};
    for (const [fname, ftype] of Object.entries(schema)) {
        if (fname in fields) {
            if (!validateValue(fields[fname], ftype))
                return reject(s, "TYPE_MISMATCH", `${fname}: expected ${JSON.stringify(ftype)}`);
            entity[fname] = fields[fname];
        }
        else if (isNullable(ftype)) {
            entity[fname] = null;
        }
        else {
            return reject(s, "REQUIRED_FIELD_MISSING", fname);
        }
    }
    for (const k of Object.keys(fields)) {
        if (!(k in schema))
            warnings.push(warn("UNKNOWN_FIELD_IGNORED", k));
    }
    entity._removed = false;
    entity._created_seq = seq;
    c.entities[eid] = entity;
    // Check constraints
    const cWarnings = checkConstraints(s, "entity.create", p.collection);
    warnings.push(...cWarnings);
    const strict = cWarnings.find(w => w.code === "STRICT_CONSTRAINT_VIOLATED");
    if (strict) {
        delete c.entities[eid];
        return reject(s, "STRICT_CONSTRAINT_VIOLATED", strict.message);
    }
    return ok(s, warnings);
};
const entityUpdate = (s, p, seq) => {
    if (p.filter)
        return entityUpdateFilter(s, p, seq);
    const parts = (p.ref || "").split("/", 2);
    if (parts.length !== 2)
        return reject(s, "ENTITY_NOT_FOUND", p.ref);
    const [cid, eid] = parts;
    const [c, err] = getColl(s, cid);
    if (err)
        return reject(s, err, cid);
    const e = c.entities[eid];
    if (!e)
        return reject(s, "ENTITY_NOT_FOUND", eid);
    if (e._removed)
        return reject(s, "ENTITY_NOT_FOUND", `${eid} (removed)`);
    for (const [fname, val] of Object.entries(p.fields || {})) {
        const ftype = c.schema[fname];
        if (ftype && !validateValue(val, ftype))
            return reject(s, "TYPE_MISMATCH", `${fname}: expected ${JSON.stringify(ftype)}`);
        e[fname] = val;
    }
    e._updated_seq = seq;
    return ok(s);
};
const entityUpdateFilter = (s, p, seq) => {
    const f = p.filter;
    const [c, err] = getColl(s, f.collection);
    if (err)
        return reject(s, err, f.collection);
    const where = f.where || {};
    const fields = p.fields || {};
    let count = 0;
    for (const e of Object.values(c.entities)) {
        if (e._removed)
            continue;
        if (!Object.entries(where).every(([k, v]) => e[k] === v))
            continue;
        for (const [fname, val] of Object.entries(fields)) {
            const ftype = c.schema[fname];
            if (ftype && !validateValue(val, ftype))
                return reject(s, "TYPE_MISMATCH", `${fname}: expected ${JSON.stringify(ftype)}`);
            e[fname] = val;
        }
        e._updated_seq = seq;
        count++;
    }
    return ok(s, [warn("ENTITIES_AFFECTED", `${count} entities updated`)]);
};
const entityRemove = (s, p, seq) => {
    const parts = (p.ref || "").split("/", 2);
    if (parts.length !== 2)
        return reject(s, "ENTITY_NOT_FOUND", p.ref);
    const [cid, eid] = parts;
    const [c, err] = getColl(s, cid);
    if (err)
        return reject(s, err, cid);
    const e = c.entities[eid];
    if (!e)
        return reject(s, "ENTITY_NOT_FOUND", eid);
    if (e._removed)
        return ok(s, [warn("ALREADY_REMOVED", eid)]);
    e._removed = true;
    e._removed_seq = seq;
    s.relationships = s.relationships.filter(r => r.from !== p.ref && r.to !== p.ref);
    return ok(s);
};
// ── Collection Primitives ───────────────────────────────────────────────────
const collectionCreate = (s, p, seq) => {
    const existing = s.collections[p.id];
    if (existing && !existing._removed)
        return reject(s, "COLLECTION_ALREADY_EXISTS", p.id);
    const schema = p.schema || {};
    for (const [fname, ftype] of Object.entries(schema)) {
        if (!isValidType(ftype))
            return reject(s, "TYPE_MISMATCH", `Unknown type: ${JSON.stringify(ftype)}`);
    }
    s.collections[p.id] = {
        id: p.id, name: p.name || p.id, schema, settings: p.settings || {},
        entities: {}, _removed: false, _created_seq: seq,
    };
    return ok(s);
};
const collectionUpdate = (s, p, seq) => {
    const [c, err] = getColl(s, p.id);
    if (err)
        return reject(s, err, p.id);
    if (p.name !== undefined)
        c.name = p.name;
    if (p.settings) {
        for (const [k, v] of Object.entries(p.settings)) {
            if (v === null)
                delete c.settings[k];
            else
                c.settings[k] = v;
        }
    }
    return ok(s);
};
const collectionRemove = (s, p, seq) => {
    const c = s.collections[p.id];
    if (!c)
        return reject(s, "COLLECTION_NOT_FOUND", p.id);
    if (c._removed)
        return ok(s, [warn("ALREADY_REMOVED", p.id)]);
    c._removed = true;
    for (const e of Object.values(c.entities))
        e._removed = true;
    for (const [vid, v] of Object.entries(s.views)) {
        if (v.source === p.id)
            delete s.views[vid];
    }
    return ok(s);
};
// ── Field Primitives ────────────────────────────────────────────────────────
const COMPAT_PAIRS = new Set([
    "string→int", "string→float", "string→bool", "string→enum", "string→date",
    "int→string", "int→float", "int→bool", "int→enum",
    "float→string", "float→int", "float→enum",
    "bool→string", "bool→int", "bool→enum",
    "enum→string", "enum→enum", "date→string", "date→date",
]);
const CHECK_CONVERT = new Set(["string→int", "string→float", "string→bool", "string→date", "string→enum"]);
const fieldAdd = (s, p, seq) => {
    const [c, err] = getColl(s, p.collection);
    if (err)
        return reject(s, err, p.collection);
    if (p.name in c.schema)
        return reject(s, "FIELD_ALREADY_EXISTS", p.name);
    if (!isValidType(p.type))
        return reject(s, "TYPE_MISMATCH", `Unknown type: ${JSON.stringify(p.type)}`);
    const def = p.default ?? null;
    const hasEntities = Object.values(c.entities).some(e => !e._removed);
    if (!isNullable(p.type) && def === null && hasEntities)
        return reject(s, "REQUIRED_FIELD_NO_DEFAULT", p.name);
    c.schema[p.name] = p.type;
    for (const e of Object.values(c.entities))
        e[p.name] = def;
    return ok(s);
};
const fieldUpdate = (s, p, seq) => {
    const [c, err] = getColl(s, p.collection);
    if (err)
        return reject(s, err, p.collection);
    if (!(p.name in c.schema))
        return reject(s, "FIELD_NOT_FOUND", p.name);
    const warnings = [];
    if (p.type !== undefined) {
        const oldBase = baseType(c.schema[p.name]);
        const newBase = baseType(p.type);
        if (oldBase !== newBase) {
            if (oldBase === "list" || newBase === "list")
                return reject(s, "INCOMPATIBLE_TYPE_CHANGE", `${oldBase} → ${newBase}`);
            if (!COMPAT_PAIRS.has(`${oldBase}→${newBase}`))
                return reject(s, "INCOMPATIBLE_TYPE_CHANGE", `${oldBase} → ${newBase}`);
            if (oldBase === "float" && newBase === "int")
                warnings.push(warn("LOSSY_TYPE_CONVERSION", "float → int"));
            // Check* conversions: scan existing values
            if (CHECK_CONVERT.has(`${oldBase}→${newBase}`)) {
                for (const e of Object.values(c.entities)) {
                    if (e._removed)
                        continue;
                    const v = e[p.name];
                    if (v == null)
                        continue;
                    if (newBase === "int" && (typeof v !== "string" || isNaN(parseInt(v))))
                        return reject(s, "INCOMPATIBLE_TYPE_CHANGE", `value '${v}' can't convert to int`);
                    if (newBase === "float" && (typeof v !== "string" || isNaN(parseFloat(v))))
                        return reject(s, "INCOMPATIBLE_TYPE_CHANGE", `value '${v}' can't convert to float`);
                    if (newBase === "bool" && !["true", "false", "0", "1", "True", "False"].includes(String(v)))
                        return reject(s, "INCOMPATIBLE_TYPE_CHANGE", `value '${v}' can't convert to bool`);
                    if (newBase === "date" && !/^\d{4}-\d{2}-\d{2}$/.test(String(v)))
                        return reject(s, "INCOMPATIBLE_TYPE_CHANGE", `value '${v}' can't convert to date`);
                }
            }
            // Check enum conversion
            if (newBase === "enum" && typeof p.type === "object" && "enum" in p.type) {
                const allowed = p.type.enum;
                for (const e of Object.values(c.entities)) {
                    if (e._removed)
                        continue;
                    const v = e[p.name];
                    if (v != null && !allowed.includes(v))
                        return reject(s, "INCOMPATIBLE_TYPE_CHANGE", `value '${v}' not in [${allowed}]`);
                }
            }
        }
        c.schema[p.name] = p.type;
    }
    if (p.rename !== undefined) {
        if (p.rename in c.schema)
            return reject(s, "FIELD_ALREADY_EXISTS", p.rename);
        c.schema[p.rename] = c.schema[p.name];
        delete c.schema[p.name];
        for (const e of Object.values(c.entities)) {
            if (p.name in e) {
                e[p.rename] = e[p.name];
                delete e[p.name];
            }
        }
    }
    return ok(s, warnings);
};
const fieldRemove = (s, p, seq) => {
    const [c, err] = getColl(s, p.collection);
    if (err)
        return reject(s, err, p.collection);
    if (!(p.name in c.schema))
        return reject(s, "FIELD_NOT_FOUND", p.name);
    delete c.schema[p.name];
    for (const e of Object.values(c.entities))
        delete e[p.name];
    const warnings = [];
    for (const v of Object.values(s.views)) {
        const cfg = v.config;
        for (const key of ["show_fields", "hide_fields"]) {
            if (Array.isArray(cfg[key]) && cfg[key].includes(p.name)) {
                cfg[key] = cfg[key].filter((f) => f !== p.name);
                warnings.push(warn("VIEW_FIELD_MISSING", `${v.id}.${key}`));
            }
        }
        if (cfg.sort_by === p.name)
            delete cfg.sort_by;
        if (cfg.group_by === p.name)
            delete cfg.group_by;
    }
    return ok(s, warnings);
};
// ── Relationship Primitives ─────────────────────────────────────────────────
const relationshipSet = (s, p, seq) => {
    const { from: fr, to, type: rtype } = p;
    // Validate entity refs
    for (const ref of [fr, to]) {
        if (!ref)
            continue;
        const parts = ref.split("/", 2);
        if (parts.length === 2) {
            const [cid, eid] = parts;
            const c = s.collections[cid];
            if (!c || c._removed)
                return reject(s, "COLLECTION_NOT_FOUND", cid);
            const e = c.entities[eid];
            if (!e || e._removed)
                return reject(s, "ENTITY_NOT_FOUND", ref);
        }
    }
    let card = p.cardinality || "many_to_one";
    if (!s.relationship_types[rtype]) {
        s.relationship_types[rtype] = { cardinality: card };
    }
    else {
        card = s.relationship_types[rtype].cardinality;
    }
    if (card === "many_to_one") {
        s.relationships = s.relationships.filter(r => !(r.from === fr && r.type === rtype));
    }
    else if (card === "one_to_one") {
        s.relationships = s.relationships.filter(r => !((r.from === fr && r.type === rtype) || (r.to === to && r.type === rtype)));
    }
    s.relationships.push({ from: fr, to, type: rtype, data: p.data || {}, _seq: seq });
    return ok(s);
};
const relationshipConstrain = (s, p, seq) => {
    s.constraints.push({
        id: p.id, rule: p.rule, entities: p.entities || [],
        relationship_type: p.relationship_type, value: p.value,
        message: p.message || "", strict: p.strict ?? false,
    });
    return ok(s);
};
// ── Block Primitives ────────────────────────────────────────────────────────
const blockSet = (s, p, seq) => {
    const bid = p.id;
    if (bid in s.blocks) {
        // UPDATE
        const b = s.blocks[bid];
        if (p.props)
            Object.assign(b.props, p.props);
        if (p.parent !== undefined) {
            for (const blk of Object.values(s.blocks)) {
                const idx = blk.children.indexOf(bid);
                if (idx !== -1)
                    blk.children.splice(idx, 1);
            }
            const parent = s.blocks[p.parent];
            if (parent) {
                if (p.position != null)
                    parent.children.splice(p.position, 0, bid);
                else
                    parent.children.push(bid);
            }
        }
    }
    else {
        // CREATE
        if (!p.type)
            return reject(s, "BLOCK_TYPE_MISSING", bid);
        const parentId = p.parent || "block_root";
        const parent = s.blocks[parentId];
        if (!parent)
            return reject(s, "BLOCK_NOT_FOUND", parentId);
        s.blocks[bid] = { type: p.type, children: [], props: p.props || {} };
        if (p.position != null)
            parent.children.splice(p.position, 0, bid);
        else
            parent.children.push(bid);
    }
    return ok(s);
};
const blockRemove = (s, p, seq) => {
    const bid = p.id;
    if (bid === "block_root")
        return reject(s, "CANT_REMOVE_ROOT", "");
    if (!(bid in s.blocks))
        return reject(s, "BLOCK_NOT_FOUND", bid);
    const collect = (b) => [b, ...(s.blocks[b]?.children || []).flatMap(collect)];
    const toRemove = collect(bid);
    for (const blk of Object.values(s.blocks)) {
        const idx = blk.children.indexOf(bid);
        if (idx !== -1)
            blk.children.splice(idx, 1);
    }
    for (const rid of toRemove)
        delete s.blocks[rid];
    return ok(s);
};
const blockReorder = (s, p, seq) => {
    const parent = s.blocks[p.parent];
    if (!parent)
        return reject(s, "BLOCK_NOT_FOUND", p.parent);
    const newOrder = p.children || [];
    const current = parent.children;
    const remaining = current.filter(c => !newOrder.includes(c));
    parent.children = [...newOrder.filter(c => current.includes(c)), ...remaining];
    return ok(s);
};
// ── View Primitives ─────────────────────────────────────────────────────────
const viewCreate = (s, p, seq) => {
    if (p.id in s.views)
        return reject(s, "VIEW_ALREADY_EXISTS", p.id);
    const [, err] = getColl(s, p.source);
    if (err)
        return reject(s, err, p.source);
    s.views[p.id] = { id: p.id, type: p.type || "table", source: p.source, config: p.config || {} };
    return ok(s);
};
const viewUpdate = (s, p, seq) => {
    const v = s.views[p.id];
    if (!v)
        return reject(s, "VIEW_NOT_FOUND", p.id);
    if (p.type !== undefined)
        v.type = p.type;
    if (p.config)
        Object.assign(v.config, p.config);
    return ok(s);
};
const viewRemove = (s, p, seq) => {
    if (!(p.id in s.views))
        return reject(s, "VIEW_NOT_FOUND", p.id);
    delete s.views[p.id];
    return ok(s);
};
// ── Style Primitives ────────────────────────────────────────────────────────
const styleSet = (s, p, seq) => {
    for (const [k, v] of Object.entries(p)) {
        if (v === null)
            delete s.styles[k];
        else
            s.styles[k] = v;
    }
    return ok(s);
};
const styleSetEntity = (s, p, seq) => {
    const parts = (p.ref || "").split("/", 2);
    if (parts.length !== 2)
        return reject(s, "ENTITY_NOT_FOUND", p.ref);
    const [cid, eid] = parts;
    const [c, err] = getColl(s, cid);
    if (err)
        return reject(s, err, cid);
    const e = c.entities[eid];
    if (!e || e._removed)
        return reject(s, "ENTITY_NOT_FOUND", p.ref);
    e._styles = { ...(e._styles || {}), ...(p.styles || {}) };
    return ok(s);
};
// ── Meta Primitives ─────────────────────────────────────────────────────────
const metaUpdate = (s, p, seq) => {
    Object.assign(s.meta, p);
    return ok(s);
};
const metaAnnotate = (s, p, seq, evt) => {
    s.annotations.push({ note: p.note || "", pinned: p.pinned ?? false, seq, timestamp: evt.timestamp || "" });
    return ok(s);
};
const metaConstrain = (s, p, seq) => {
    const idx = s.constraints.findIndex(c => c.id === p.id);
    if (idx >= 0)
        s.constraints[idx] = p;
    else
        s.constraints.push(p);
    return ok(s);
};
// ── Reducer Map ─────────────────────────────────────────────────────────────
const REDUCERS = {
    "entity.create": entityCreate, "entity.update": entityUpdate, "entity.remove": entityRemove,
    "collection.create": collectionCreate, "collection.update": collectionUpdate, "collection.remove": collectionRemove,
    "field.add": fieldAdd, "field.update": fieldUpdate, "field.remove": fieldRemove,
    "relationship.set": relationshipSet, "relationship.constrain": relationshipConstrain,
    "block.set": blockSet, "block.remove": blockRemove, "block.reorder": blockReorder,
    "view.create": viewCreate, "view.update": viewUpdate, "view.remove": viewRemove,
    "style.set": styleSet, "style.set_entity": styleSetEntity,
    "meta.update": metaUpdate, "meta.annotate": metaAnnotate, "meta.constrain": metaConstrain,
};
// ── Query Helpers ───────────────────────────────────────────────────────────
function applySort(entities, cfg) {
    const sb = cfg.sort_by;
    if (!sb)
        return entities;
    const rev = cfg.sort_order === "desc";
    return [...entities].sort((a, b) => {
        const av = a[sb], bv = b[sb];
        const an = av == null ? 1 : 0, bn = bv == null ? 1 : 0;
        if (an !== bn)
            return an - bn;
        if (av < bv)
            return rev ? 1 : -1;
        if (av > bv)
            return rev ? -1 : 1;
        return 0;
    });
}
function applyFilter(entities, cfg) {
    const f = cfg.filter;
    if (!f)
        return entities;
    return entities.filter(e => Object.entries(f).every(([k, v]) => e[k] === v));
}
function resolveViewEntities(snapshot, viewId) {
    const view = snapshot.views[viewId];
    if (!view)
        return [];
    const coll = snapshot.collections[view.source];
    if (!coll || coll._removed)
        return [];
    let entities = Object.values(coll.entities).filter(e => !e._removed);
    const cfg = view.config || {};
    entities = applySort(entities, cfg);
    entities = applyFilter(entities, cfg);
    return entities;
}
function resolveViewFields(snapshot, viewId) {
    const view = snapshot.views[viewId];
    if (!view)
        return [];
    const coll = snapshot.collections[view.source];
    if (!coll || coll._removed)
        return [];
    const cfg = view.config || {};
    return cfg.show_fields || Object.keys(coll.schema).filter(f => !f.startsWith("_"));
}
