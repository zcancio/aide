/**
 * AIde Kernel — engine.ts
 * Single-file kernel: primitives, validator, reducer, renderer.
 * Pure functions. No IO. No AI. Deterministic.
 *
 * Usage:
 *   import { emptyState, reduce, replay, render, parseAideHtml } from "./engine"
 *   let snap = emptyState()
 *   for (const evt of events) { snap = reduce(snap, evt).snapshot }
 *   const html = render(snap, blueprint, events)
 */

// ── Types ───────────────────────────────────────────────────────────────────

export interface AideState {
  version: number
  meta: Record<string, any>
  collections: Record<string, Collection>
  relationships: Relationship[]
  relationship_types: Record<string, { cardinality: Cardinality }>
  constraints: Constraint[]
  blocks: Record<string, Block>
  views: Record<string, View>
  styles: Record<string, any>
  annotations: Annotation[]
}

export interface Collection {
  id: string
  name: string
  schema: Record<string, SchemaType>
  settings: Record<string, any>
  entities: Record<string, Entity>
  _removed: boolean
  _created_seq: number
}

export type Entity = Record<string, any> & {
  _removed: boolean
  _created_seq: number
  _updated_seq?: number
  _removed_seq?: number
  _styles?: Record<string, any>
}

export interface Block {
  type: string
  children: string[]
  props: Record<string, any>
}

export interface View {
  id: string
  type: string
  source: string
  config: Record<string, any>
}

export interface Relationship {
  from: string
  to: string
  type: string
  data: Record<string, any>
  _seq: number
}

export interface Constraint {
  id: string
  rule: string
  entities?: string[]
  relationship_type?: string
  collection?: string
  field?: string
  value?: any
  message: string
  strict: boolean
}

export interface Annotation {
  note: string
  pinned: boolean
  seq: number
  timestamp: string
}

export interface Event {
  id: string
  sequence: number
  timestamp: string
  actor: string
  source: string
  type: string
  payload: Record<string, any>
  intent?: string
  message?: string
  message_id?: string
}

export interface Warning { code: string; message: string }

export interface ReduceResult {
  snapshot: AideState
  applied: boolean
  warnings: Warning[]
  error: string | null
}

export interface Blueprint {
  identity: string
  voice: string
  prompt: string
}

export interface RenderOptions {
  footer?: string | null
}

export type SchemaType = string | { enum: string[] } | { list: string }
type Cardinality = "many_to_one" | "one_to_one" | "many_to_many"

// ── Field Types ─────────────────────────────────────────────────────────────

const SCALAR_TYPES = new Set(["string", "int", "float", "bool", "date", "datetime"])

function isNullable(t: SchemaType): boolean {
  return typeof t === "string" && t.endsWith("?")
}

function baseType(t: SchemaType): string {
  if (typeof t === "string") return t.replace(/\?$/, "")
  if (typeof t === "object" && "enum" in t) return "enum"
  if (typeof t === "object" && "list" in t) return "list"
  return "unknown"
}

function isValidType(t: SchemaType): boolean {
  if (typeof t === "string") return SCALAR_TYPES.has(t.replace(/\?$/, ""))
  if (typeof t === "object" && "enum" in t) return Array.isArray(t.enum) && t.enum.length > 0
  if (typeof t === "object" && "list" in t) return SCALAR_TYPES.has(t.list)
  return false
}

function validateValue(val: any, t: SchemaType): boolean {
  if (val === null || val === undefined) return isNullable(t)
  const bt = baseType(t)
  switch (bt) {
    case "string": return typeof val === "string"
    case "int": return typeof val === "number" && Number.isInteger(val)
    case "float": return typeof val === "number"
    case "bool": return typeof val === "boolean"
    case "date": return typeof val === "string" && /^\d{4}-\d{2}-\d{2}$/.test(val)
    case "datetime": return typeof val === "string" && !isNaN(Date.parse(val))
    case "enum": return typeof t === "object" && "enum" in t && t.enum.includes(val)
    case "list":
      if (!Array.isArray(val)) return false
      const inner = typeof t === "object" && "list" in t ? t.list : "string"
      return val.every(v => validateValue(v, inner))
    default: return false
  }
}

// ── Empty State ─────────────────────────────────────────────────────────────

export function emptyState(): AideState {
  return {
    version: 1, meta: {}, collections: {}, relationships: [],
    relationship_types: {}, constraints: [],
    blocks: { block_root: { type: "root", children: [], props: {} } },
    views: {}, styles: {}, annotations: [],
  }
}

// ── Reducer ─────────────────────────────────────────────────────────────────

function ok(s: AideState, warnings: Warning[] = []): ReduceResult {
  return { snapshot: s, applied: true, warnings, error: null }
}

function reject(s: AideState, code: string, msg: string): ReduceResult {
  return { snapshot: s, applied: false, warnings: [], error: `${code}: ${msg}` }
}

function warn(code: string, message: string): Warning { return { code, message } }

function getColl(s: AideState, cid: string): [Collection | null, string | null] {
  const c = s.collections[cid]
  if (!c || c._removed) return [null, "COLLECTION_NOT_FOUND"]
  return [c, null]
}

function deepClone<T>(obj: T): T { return JSON.parse(JSON.stringify(obj)) }

export function reduce(snapshot: AideState, event: Event): ReduceResult {
  const s = deepClone(snapshot)
  const { type, payload, sequence: seq } = event
  const fn = REDUCERS[type]
  if (!fn) return reject(s, "UNKNOWN_PRIMITIVE", `Unknown type: ${type}`)
  return fn(s, payload, seq ?? 0, event)
}

export function replay(events: Event[]): AideState {
  let s = emptyState()
  for (const e of events) {
    const r = reduce(s, e)
    s = r.snapshot
  }
  return s
}

type ReducerFn = (s: AideState, p: Record<string, any>, seq: number, evt: Event) => ReduceResult

// ── Constraint Checking ─────────────────────────────────────────────────────

function checkConstraints(s: AideState, eventType: string, collectionId?: string): Warning[] {
  const warnings: Warning[] = []
  for (const con of s.constraints) {
    if (con.rule === "collection_max_entities" && eventType === "entity.create") {
      if (con.collection !== collectionId) continue
      const c = s.collections[con.collection!]
      if (!c) continue
      const count = Object.values(c.entities).filter(e => !e._removed).length
      if (count > (con.value ?? Infinity)) {
        const code = con.strict ? "STRICT_CONSTRAINT_VIOLATED" : "CONSTRAINT_VIOLATED"
        warnings.push(warn(code, con.message || `Max ${con.value} entities exceeded`))
      }
    } else if (con.rule === "unique_field" && (eventType === "entity.create" || eventType === "entity.update")) {
      if (con.collection !== collectionId) continue
      const c = s.collections[con.collection!]
      if (!c || !con.field) continue
      const vals = Object.values(c.entities).filter(e => !e._removed && e[con.field!] != null).map(e => String(e[con.field!]))
      if (vals.length !== new Set(vals).size) {
        const code = con.strict ? "STRICT_CONSTRAINT_VIOLATED" : "CONSTRAINT_VIOLATED"
        warnings.push(warn(code, con.message || `Duplicate values in ${con.field}`))
      }
    }
  }
  return warnings
}

// ── Entity Primitives ───────────────────────────────────────────────────────

const entityCreate: ReducerFn = (s, p, seq) => {
  const [c, err] = getColl(s, p.collection)
  if (err) return reject(s, err, p.collection)
  const eid = p.id || `${p.collection}_${Object.keys(c!.entities).length + 1}`
  const existing = c!.entities[eid]
  if (existing && !existing._removed) return reject(s, "ENTITY_ALREADY_EXISTS", eid)
  const fields = p.fields || {}
  const schema = c!.schema
  const warnings: Warning[] = []
  const entity: Record<string, any> = {}
  for (const [fname, ftype] of Object.entries(schema)) {
    if (fname in fields) {
      if (!validateValue(fields[fname], ftype)) return reject(s, "TYPE_MISMATCH", `${fname}: expected ${JSON.stringify(ftype)}`)
      entity[fname] = fields[fname]
    } else if (isNullable(ftype)) {
      entity[fname] = null
    } else {
      return reject(s, "REQUIRED_FIELD_MISSING", fname)
    }
  }
  for (const k of Object.keys(fields)) {
    if (!(k in schema)) warnings.push(warn("UNKNOWN_FIELD_IGNORED", k))
  }
  entity._removed = false
  entity._created_seq = seq
  c!.entities[eid] = entity as Entity
  // Check constraints
  const cWarnings = checkConstraints(s, "entity.create", p.collection)
  warnings.push(...cWarnings)
  const strict = cWarnings.find(w => w.code === "STRICT_CONSTRAINT_VIOLATED")
  if (strict) { delete c!.entities[eid]; return reject(s, "STRICT_CONSTRAINT_VIOLATED", strict.message) }
  return ok(s, warnings)
}

const entityUpdate: ReducerFn = (s, p, seq) => {
  if (p.filter) return entityUpdateFilter(s, p, seq)
  const parts = (p.ref || "").split("/", 2)
  if (parts.length !== 2) return reject(s, "ENTITY_NOT_FOUND", p.ref)
  const [cid, eid] = parts
  const [c, err] = getColl(s, cid)
  if (err) return reject(s, err, cid)
  const e = c!.entities[eid]
  if (!e) return reject(s, "ENTITY_NOT_FOUND", eid)
  if (e._removed) return reject(s, "ENTITY_NOT_FOUND", `${eid} (removed)`)
  for (const [fname, val] of Object.entries(p.fields || {})) {
    const ftype = c!.schema[fname]
    if (ftype && !validateValue(val, ftype)) return reject(s, "TYPE_MISMATCH", `${fname}: expected ${JSON.stringify(ftype)}`)
    e[fname] = val
  }
  e._updated_seq = seq
  return ok(s)
}

const entityUpdateFilter = (s: AideState, p: Record<string, any>, seq: number): ReduceResult => {
  const f = p.filter
  const [c, err] = getColl(s, f.collection)
  if (err) return reject(s, err, f.collection)
  const where = f.where || {}
  const fields = p.fields || {}
  let count = 0
  for (const e of Object.values(c!.entities)) {
    if (e._removed) continue
    if (!Object.entries(where).every(([k, v]) => e[k] === v)) continue
    for (const [fname, val] of Object.entries(fields)) {
      const ftype = c!.schema[fname]
      if (ftype && !validateValue(val, ftype)) return reject(s, "TYPE_MISMATCH", `${fname}: expected ${JSON.stringify(ftype)}`)
      e[fname] = val
    }
    e._updated_seq = seq
    count++
  }
  return ok(s, [warn("ENTITIES_AFFECTED", `${count} entities updated`)])
}

const entityRemove: ReducerFn = (s, p, seq) => {
  const parts = (p.ref || "").split("/", 2)
  if (parts.length !== 2) return reject(s, "ENTITY_NOT_FOUND", p.ref)
  const [cid, eid] = parts
  const [c, err] = getColl(s, cid)
  if (err) return reject(s, err, cid)
  const e = c!.entities[eid]
  if (!e) return reject(s, "ENTITY_NOT_FOUND", eid)
  if (e._removed) return ok(s, [warn("ALREADY_REMOVED", eid)])
  e._removed = true
  e._removed_seq = seq
  s.relationships = s.relationships.filter(r => r.from !== p.ref && r.to !== p.ref)
  return ok(s)
}

// ── Collection Primitives ───────────────────────────────────────────────────

const collectionCreate: ReducerFn = (s, p, seq) => {
  const existing = s.collections[p.id]
  if (existing && !existing._removed) return reject(s, "COLLECTION_ALREADY_EXISTS", p.id)
  const schema = p.schema || {}
  for (const [fname, ftype] of Object.entries(schema)) {
    if (!isValidType(ftype as SchemaType)) return reject(s, "TYPE_MISMATCH", `Unknown type: ${JSON.stringify(ftype)}`)
  }
  s.collections[p.id] = {
    id: p.id, name: p.name || p.id, schema, settings: p.settings || {},
    entities: {}, _removed: false, _created_seq: seq,
  }
  return ok(s)
}

const collectionUpdate: ReducerFn = (s, p, seq) => {
  const [c, err] = getColl(s, p.id)
  if (err) return reject(s, err, p.id)
  if (p.name !== undefined) c!.name = p.name
  if (p.settings) {
    for (const [k, v] of Object.entries(p.settings)) {
      if (v === null) delete c!.settings[k]; else c!.settings[k] = v
    }
  }
  return ok(s)
}

const collectionRemove: ReducerFn = (s, p, seq) => {
  const c = s.collections[p.id]
  if (!c) return reject(s, "COLLECTION_NOT_FOUND", p.id)
  if (c._removed) return ok(s, [warn("ALREADY_REMOVED", p.id)])
  c._removed = true
  for (const e of Object.values(c.entities)) e._removed = true
  for (const [vid, v] of Object.entries(s.views)) {
    if (v.source === p.id) delete s.views[vid]
  }
  return ok(s)
}

// ── Field Primitives ────────────────────────────────────────────────────────

const COMPAT_PAIRS = new Set([
  "string→int", "string→float", "string→bool", "string→enum", "string→date",
  "int→string", "int→float", "int→bool", "int→enum",
  "float→string", "float→int", "float→enum",
  "bool→string", "bool→int", "bool→enum",
  "enum→string", "enum→enum", "date→string", "date→date",
])
const CHECK_CONVERT = new Set(["string→int", "string→float", "string→bool", "string→date", "string→enum"])

const fieldAdd: ReducerFn = (s, p, seq) => {
  const [c, err] = getColl(s, p.collection)
  if (err) return reject(s, err, p.collection)
  if (p.name in c!.schema) return reject(s, "FIELD_ALREADY_EXISTS", p.name)
  if (!isValidType(p.type)) return reject(s, "TYPE_MISMATCH", `Unknown type: ${JSON.stringify(p.type)}`)
  const def = p.default ?? null
  const hasEntities = Object.values(c!.entities).some(e => !e._removed)
  if (!isNullable(p.type) && def === null && hasEntities) return reject(s, "REQUIRED_FIELD_NO_DEFAULT", p.name)
  c!.schema[p.name] = p.type
  for (const e of Object.values(c!.entities)) e[p.name] = def
  return ok(s)
}

const fieldUpdate: ReducerFn = (s, p, seq) => {
  const [c, err] = getColl(s, p.collection)
  if (err) return reject(s, err, p.collection)
  if (!(p.name in c!.schema)) return reject(s, "FIELD_NOT_FOUND", p.name)
  const warnings: Warning[] = []
  if (p.type !== undefined) {
    const oldBase = baseType(c!.schema[p.name])
    const newBase = baseType(p.type)
    if (oldBase !== newBase) {
      if (oldBase === "list" || newBase === "list") return reject(s, "INCOMPATIBLE_TYPE_CHANGE", `${oldBase} → ${newBase}`)
      if (!COMPAT_PAIRS.has(`${oldBase}→${newBase}`)) return reject(s, "INCOMPATIBLE_TYPE_CHANGE", `${oldBase} → ${newBase}`)
      if (oldBase === "float" && newBase === "int") warnings.push(warn("LOSSY_TYPE_CONVERSION", "float → int"))
      // Check* conversions: scan existing values
      if (CHECK_CONVERT.has(`${oldBase}→${newBase}`)) {
        for (const e of Object.values(c!.entities)) {
          if (e._removed) continue
          const v = e[p.name]
          if (v == null) continue
          if (newBase === "int" && (typeof v !== "string" || isNaN(parseInt(v)))) return reject(s, "INCOMPATIBLE_TYPE_CHANGE", `value '${v}' can't convert to int`)
          if (newBase === "float" && (typeof v !== "string" || isNaN(parseFloat(v)))) return reject(s, "INCOMPATIBLE_TYPE_CHANGE", `value '${v}' can't convert to float`)
          if (newBase === "bool" && !["true", "false", "0", "1", "True", "False"].includes(String(v))) return reject(s, "INCOMPATIBLE_TYPE_CHANGE", `value '${v}' can't convert to bool`)
          if (newBase === "date" && !/^\d{4}-\d{2}-\d{2}$/.test(String(v))) return reject(s, "INCOMPATIBLE_TYPE_CHANGE", `value '${v}' can't convert to date`)
        }
      }
      // Check enum conversion
      if (newBase === "enum" && typeof p.type === "object" && "enum" in p.type) {
        const allowed = p.type.enum
        for (const e of Object.values(c!.entities)) {
          if (e._removed) continue
          const v = e[p.name]
          if (v != null && !allowed.includes(v)) return reject(s, "INCOMPATIBLE_TYPE_CHANGE", `value '${v}' not in [${allowed}]`)
        }
      }
    }
    c!.schema[p.name] = p.type
  }
  if (p.rename !== undefined) {
    if (p.rename in c!.schema) return reject(s, "FIELD_ALREADY_EXISTS", p.rename)
    c!.schema[p.rename] = c!.schema[p.name]
    delete c!.schema[p.name]
    for (const e of Object.values(c!.entities)) {
      if (p.name in e) { e[p.rename] = e[p.name]; delete e[p.name] }
    }
  }
  return ok(s, warnings)
}

const fieldRemove: ReducerFn = (s, p, seq) => {
  const [c, err] = getColl(s, p.collection)
  if (err) return reject(s, err, p.collection)
  if (!(p.name in c!.schema)) return reject(s, "FIELD_NOT_FOUND", p.name)
  delete c!.schema[p.name]
  for (const e of Object.values(c!.entities)) delete e[p.name]
  const warnings: Warning[] = []
  for (const v of Object.values(s.views)) {
    const cfg = v.config
    for (const key of ["show_fields", "hide_fields"] as const) {
      if (Array.isArray(cfg[key]) && cfg[key].includes(p.name)) {
        cfg[key] = cfg[key].filter((f: string) => f !== p.name)
        warnings.push(warn("VIEW_FIELD_MISSING", `${v.id}.${key}`))
      }
    }
    if (cfg.sort_by === p.name) delete cfg.sort_by
    if (cfg.group_by === p.name) delete cfg.group_by
  }
  return ok(s, warnings)
}

// ── Relationship Primitives ─────────────────────────────────────────────────

const relationshipSet: ReducerFn = (s, p, seq) => {
  const { from: fr, to, type: rtype } = p
  // Validate entity refs
  for (const ref of [fr, to]) {
    if (!ref) continue
    const parts = ref.split("/", 2)
    if (parts.length === 2) {
      const [cid, eid] = parts
      const c = s.collections[cid]
      if (!c || c._removed) return reject(s, "COLLECTION_NOT_FOUND", cid)
      const e = c.entities[eid]
      if (!e || e._removed) return reject(s, "ENTITY_NOT_FOUND", ref)
    }
  }
  let card: Cardinality = p.cardinality || "many_to_one"
  if (!s.relationship_types[rtype]) {
    s.relationship_types[rtype] = { cardinality: card }
  } else {
    card = s.relationship_types[rtype].cardinality
  }
  if (card === "many_to_one") {
    s.relationships = s.relationships.filter(r => !(r.from === fr && r.type === rtype))
  } else if (card === "one_to_one") {
    s.relationships = s.relationships.filter(r => !((r.from === fr && r.type === rtype) || (r.to === to && r.type === rtype)))
  }
  s.relationships.push({ from: fr, to, type: rtype, data: p.data || {}, _seq: seq })
  return ok(s)
}

const relationshipConstrain: ReducerFn = (s, p, seq) => {
  s.constraints.push({
    id: p.id, rule: p.rule, entities: p.entities || [],
    relationship_type: p.relationship_type, value: p.value,
    message: p.message || "", strict: p.strict ?? false,
  })
  return ok(s)
}

// ── Block Primitives ────────────────────────────────────────────────────────

const blockSet: ReducerFn = (s, p, seq) => {
  const bid = p.id
  if (bid in s.blocks) {
    // UPDATE
    const b = s.blocks[bid]
    if (p.props) Object.assign(b.props, p.props)
    if (p.parent !== undefined) {
      for (const blk of Object.values(s.blocks)) {
        const idx = blk.children.indexOf(bid)
        if (idx !== -1) blk.children.splice(idx, 1)
      }
      const parent = s.blocks[p.parent]
      if (parent) {
        if (p.position != null) parent.children.splice(p.position, 0, bid)
        else parent.children.push(bid)
      }
    }
  } else {
    // CREATE
    if (!p.type) return reject(s, "BLOCK_TYPE_MISSING", bid)
    const parentId = p.parent || "block_root"
    const parent = s.blocks[parentId]
    if (!parent) return reject(s, "BLOCK_NOT_FOUND", parentId)
    s.blocks[bid] = { type: p.type, children: [], props: p.props || {} }
    if (p.position != null) parent.children.splice(p.position, 0, bid)
    else parent.children.push(bid)
  }
  return ok(s)
}

const blockRemove: ReducerFn = (s, p, seq) => {
  const bid = p.id
  if (bid === "block_root") return reject(s, "CANT_REMOVE_ROOT", "")
  if (!(bid in s.blocks)) return reject(s, "BLOCK_NOT_FOUND", bid)
  const collect = (b: string): string[] => [b, ...(s.blocks[b]?.children || []).flatMap(collect)]
  const toRemove = collect(bid)
  for (const blk of Object.values(s.blocks)) {
    const idx = blk.children.indexOf(bid)
    if (idx !== -1) blk.children.splice(idx, 1)
  }
  for (const rid of toRemove) delete s.blocks[rid]
  return ok(s)
}

const blockReorder: ReducerFn = (s, p, seq) => {
  const parent = s.blocks[p.parent]
  if (!parent) return reject(s, "BLOCK_NOT_FOUND", p.parent)
  const newOrder: string[] = p.children || []
  const current = parent.children
  const remaining = current.filter(c => !newOrder.includes(c))
  parent.children = [...newOrder.filter(c => current.includes(c)), ...remaining]
  return ok(s)
}

// ── View Primitives ─────────────────────────────────────────────────────────

const viewCreate: ReducerFn = (s, p, seq) => {
  if (p.id in s.views) return reject(s, "VIEW_ALREADY_EXISTS", p.id)
  const [, err] = getColl(s, p.source)
  if (err) return reject(s, err, p.source)
  s.views[p.id] = { id: p.id, type: p.type || "table", source: p.source, config: p.config || {} }
  return ok(s)
}

const viewUpdate: ReducerFn = (s, p, seq) => {
  const v = s.views[p.id]
  if (!v) return reject(s, "VIEW_NOT_FOUND", p.id)
  if (p.type !== undefined) v.type = p.type
  if (p.config) Object.assign(v.config, p.config)
  return ok(s)
}

const viewRemove: ReducerFn = (s, p, seq) => {
  if (!(p.id in s.views)) return reject(s, "VIEW_NOT_FOUND", p.id)
  delete s.views[p.id]
  return ok(s)
}

// ── Style Primitives ────────────────────────────────────────────────────────

const styleSet: ReducerFn = (s, p, seq) => {
  for (const [k, v] of Object.entries(p)) {
    if (v === null) delete s.styles[k]; else s.styles[k] = v
  }
  return ok(s)
}

const styleSetEntity: ReducerFn = (s, p, seq) => {
  const parts = (p.ref || "").split("/", 2)
  if (parts.length !== 2) return reject(s, "ENTITY_NOT_FOUND", p.ref)
  const [cid, eid] = parts
  const [c, err] = getColl(s, cid)
  if (err) return reject(s, err, cid)
  const e = c!.entities[eid]
  if (!e || e._removed) return reject(s, "ENTITY_NOT_FOUND", p.ref)
  e._styles = { ...(e._styles || {}), ...(p.styles || {}) }
  return ok(s)
}

// ── Meta Primitives ─────────────────────────────────────────────────────────

const metaUpdate: ReducerFn = (s, p, seq) => {
  Object.assign(s.meta, p)
  return ok(s)
}

const metaAnnotate: ReducerFn = (s, p, seq, evt) => {
  s.annotations.push({ note: p.note || "", pinned: p.pinned ?? false, seq, timestamp: evt.timestamp || "" })
  return ok(s)
}

const metaConstrain: ReducerFn = (s, p, seq) => {
  const idx = s.constraints.findIndex(c => c.id === p.id)
  if (idx >= 0) s.constraints[idx] = p as Constraint
  else s.constraints.push(p as Constraint)
  return ok(s)
}

// ── Reducer Map ─────────────────────────────────────────────────────────────

const REDUCERS: Record<string, ReducerFn> = {
  "entity.create": entityCreate, "entity.update": entityUpdate, "entity.remove": entityRemove,
  "collection.create": collectionCreate, "collection.update": collectionUpdate, "collection.remove": collectionRemove,
  "field.add": fieldAdd, "field.update": fieldUpdate, "field.remove": fieldRemove,
  "relationship.set": relationshipSet, "relationship.constrain": relationshipConstrain,
  "block.set": blockSet, "block.remove": blockRemove, "block.reorder": blockReorder,
  "view.create": viewCreate, "view.update": viewUpdate, "view.remove": viewRemove,
  "style.set": styleSet, "style.set_entity": styleSetEntity,
  "meta.update": metaUpdate, "meta.annotate": metaAnnotate, "meta.constrain": metaConstrain,
}

// ── Renderer ────────────────────────────────────────────────────────────────

function esc(s: string): string {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&#x27;")
}

function inline(text: string): string {
  let t = esc(text)
  t = t.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
  t = t.replace(/\*(.+?)\*/g, "<em>$1</em>")
  t = t.replace(/\[(.+?)\]\((https?:\/\/[^\)]+)\)/g, '<a href="$2">$1</a>')
  return t
}

function displayName(field: string): string {
  return field.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase())
}

function fmtValue(val: any, schemaType: SchemaType): string {
  if (val == null) return '<span class="aide-null">&mdash;</span>'
  const bt = baseType(schemaType)
  if (bt === "bool") return val ? "&#10003;" : "&#9675;"
  if (bt === "date" && typeof val === "string") {
    const d = new Date(val + "T00:00:00Z")
    if (!isNaN(d.getTime())) return esc(d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" }))
  }
  if (bt === "datetime" && typeof val === "string") {
    const d = new Date(val)
    if (!isNaN(d.getTime())) return esc(d.toLocaleDateString("en-US", { month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone: "UTC" }))
  }
  if (bt === "enum") return esc(String(val).replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase()))
  if (bt === "list" && Array.isArray(val)) return esc(val.join(", "))
  if (bt === "int" && typeof val === "number") return esc(val.toLocaleString("en-US"))
  if (bt === "float" && typeof val === "number") return esc(val.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 }))
  return esc(String(val))
}

function deriveDesc(s: AideState): string {
  const root = s.blocks.block_root
  for (const bid of root?.children || []) {
    const b = s.blocks[bid]
    if (b?.type === "text") return (b.props.content || "").slice(0, 160)
  }
  for (const c of Object.values(s.collections)) {
    if (c._removed) continue
    const n = Object.values(c.entities).filter(e => !e._removed).length
    return `${c.name || c.id}: ${n} items`
  }
  return s.meta.title || "A living page"
}

function applySort(entities: Entity[], cfg: Record<string, any>): Entity[] {
  const sb = cfg.sort_by
  if (!sb) return entities
  const rev = cfg.sort_order === "desc"
  return [...entities].sort((a, b) => {
    const av = a[sb], bv = b[sb]
    const an = av == null ? 1 : 0, bn = bv == null ? 1 : 0
    if (an !== bn) return an - bn
    if (av < bv) return rev ? 1 : -1
    if (av > bv) return rev ? -1 : 1
    return 0
  })
}

function applyFilter(entities: Entity[], cfg: Record<string, any>): Entity[] {
  const f = cfg.filter
  if (!f) return entities
  return entities.filter(e => Object.entries(f).every(([k, v]) => e[k] === v))
}

// ── Block Rendering ─────────────────────────────────────────────────────────

function renderBlock(bid: string, s: AideState): string {
  const b = s.blocks[bid]
  if (!b) return ""
  const { type, props: p } = b
  let html = ""
  switch (type) {
    case "root": break
    case "heading": {
      const lvl = p.level || 1
      html = `    <h${lvl} class="aide-heading aide-heading--${lvl}">${inline(p.content || "")}</h${lvl}>\n`
      break
    }
    case "text":
      html = `    <p class="aide-text">${inline(p.content || "")}</p>\n`; break
    case "metric":
      html = `    <div class="aide-metric"><span class="aide-metric__label">${esc(p.label || "")}</span><span class="aide-metric__value">${esc(p.value || "")}</span></div>\n`; break
    case "divider":
      html = `    <hr class="aide-divider">\n`; break
    case "callout":
      html = `    <div class="aide-callout">${inline(p.content || "")}</div>\n`; break
    case "image": {
      const cap = p.caption ? `<figcaption class="aide-image__caption">${esc(p.caption)}</figcaption>` : ""
      html = `    <figure class="aide-image"><img src="${esc(p.src || "")}" alt="${esc(p.alt || "")}" loading="lazy">${cap}</figure>\n`
      break
    }
    case "collection_view":
      html = renderCollectionView(p, s); break
    case "column_list":
      html = `    <div class="aide-columns">\n`; break
    case "column": {
      const w = p.width
      const style = w ? ` style="flex:0 0 ${w}"` : ""
      html = `    <div class="aide-column"${style}>\n`; break
    }
  }
  const children = b.children.map(c => renderBlock(c, s)).join("")
  if (type === "column_list") return html + children + "    </div>\n"
  if (type === "column") return html + children + "    </div>\n"
  return html + children
}

function renderCollectionView(props: Record<string, any>, s: AideState): string {
  const vid = props.view_id || props.view
  const view = s.views[vid]
  if (!view) return ""
  const src = view.source || props.source
  const coll = s.collections[src]
  if (!coll || coll._removed) return ""
  let entities = Object.values(coll.entities).filter(e => !e._removed)
  const cfg = view.config || {}
  entities = applySort(entities, cfg)
  entities = applyFilter(entities, cfg)
  const show = cfg.show_fields || Object.keys(coll.schema).filter(f => !f.startsWith("_"))
  return view.type === "list" ? renderList(entities, coll.schema, show) : renderTable(entities, coll.schema, show)
}

function renderTable(entities: Entity[], schema: Record<string, SchemaType>, fields: string[]): string {
  if (!entities.length && !fields.length) return `    <p class="aide-collection-empty">No items yet.</p>\n`
  const h = fields.map(f => `<th>${esc(displayName(f))}</th>`).join("")
  const rows = entities.map(e =>
    `<tr>${fields.map(f => `<td class="aide-table__td--${baseType(schema[f] || "string")}">${fmtValue(e[f], schema[f] || "string")}</td>`).join("")}</tr>`
  ).join("")
  return `    <div class="aide-table-wrap"><table class="aide-table"><thead><tr>${h}</tr></thead><tbody>${rows}</tbody></table></div>\n`
}

function renderList(entities: Entity[], schema: Record<string, SchemaType>, fields: string[]): string {
  if (!entities.length) return `    <p class="aide-collection-empty">No items yet.</p>\n`
  const items = entities.map(e =>
    `<li class="aide-list__item">${fields.map(f => `<span class="aide-list__field">${fmtValue(e[f], schema[f] || "string")}</span>`).join("")}</li>`
  ).join("")
  return `    <ul class="aide-list">${items}</ul>\n`
}

function renderAnnotations(s: AideState): string {
  if (!s.annotations.length) return ""
  const pinned = s.annotations.filter(a => a.pinned)
  const unpinned = s.annotations.filter(a => !a.pinned).reverse()
  const ordered = [...pinned, ...unpinned]
  const items = ordered.map(a => {
    const ts = (a.timestamp || "").slice(0, 10)
    const pin = a.pinned ? " aide-annotation--pinned" : ""
    return `<div class="aide-annotation${pin}"><span class="aide-annotation__text">${esc(a.note)}</span><span class="aide-annotation__meta">${ts}</span></div>`
  }).join("")
  return `    <section class="aide-annotations"><h3 class="aide-heading aide-heading--3">Notes</h3>${items}</section>\n`
}

// ── Main Render ─────────────────────────────────────────────────────────────

export function render(
  snapshot: AideState,
  blueprint: Blueprint,
  events: Event[] = [],
  options: RenderOptions = {},
): string {
  const title = esc(snapshot.meta.title || "AIde")
  const desc = esc(deriveDesc(snapshot))
  const footer = options.footer !== undefined ? options.footer : "Made with AIde"
  const bpJson = JSON.stringify(blueprint, null, 2)
  const stJson = JSON.stringify(snapshot, null, 2)
  const evJson = JSON.stringify(events, null, 2)
  const body = renderBlock("block_root", snapshot)
  const annots = renderAnnotations(snapshot)
  const now = new Date().toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })
  const footerHtml = footer
    ? `    <footer class="aide-footer">
      <a href="https://toaide.com" class="aide-footer__link">${esc(footer)}</a>
      <span class="aide-footer__sep">&middot;</span>
      <span>Updated ${now}</span>
    </footer>`
    : ""

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${title}</title>
  <meta property="og:title" content="${title}">
  <meta property="og:type" content="website">
  <meta property="og:description" content="${desc}">
  <meta name="description" content="${desc}">
  <script type="application/aide-blueprint+json" id="aide-blueprint">
${bpJson}
  </script>
  <script type="application/aide+json" id="aide-state">
${stJson}
  </script>
  <script type="application/aide-events+json" id="aide-events">
${evJson}
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500;600;700&family=Instrument+Sans:wght@400;500;600;700&family=DM+Sans:opsz,wght@9..40,300;9..40,400;9..40,500;9..40,600&display=swap" rel="stylesheet">
  <style>${CSS}</style>
</head>
<body>
  <main class="aide-page">
${body}${annots}${footerHtml}
  </main>
</body>
</html>`
}

// ── HTML Parser ─────────────────────────────────────────────────────────────

export function parseAideHtml(html: string): { blueprint: Blueprint; snapshot: AideState; events: Event[] } {
  const extract = (tagType: string) => {
    const re = new RegExp(`<script type="${tagType.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}"[^>]*>([\\s\\S]*?)</script>`)
    const m = html.match(re)
    return m ? JSON.parse(m[1]) : null
  }
  return {
    blueprint: extract("application/aide-blueprint+json") || {} as Blueprint,
    snapshot: extract("application/aide+json") || emptyState(),
    events: extract("application/aide-events+json") || [],
  }
}

// ── CSS ─────────────────────────────────────────────────────────────────────

const CSS = `*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
:root{--font-serif:'Playfair Display',Georgia,serif;--font-sans:'DM Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;--font-heading:'Instrument Sans',-apple-system,BlinkMacSystemFont,sans-serif;--text-primary:#2D2D2A;--text-secondary:#6B6963;--text-tertiary:#A8A5A0;--text-inverse:#F7F5F2;--bg-primary:#F7F5F2;--bg-secondary:#EFECEA;--bg-tertiary:#E6E3DF;--bg-elevated:#FFFFFF;--sage-50:#F0F3ED;--sage-100:#DDE4D7;--sage-200:#C2CCB8;--sage-300:#A3B394;--sage-400:#8B9E7C;--sage-500:#7C8C6E;--sage-600:#667358;--sage-700:#515C46;--sage-800:#3C4534;--sage-900:#282E23;--accent:var(--sage-500);--accent-hover:var(--sage-600);--accent-subtle:var(--sage-50);--accent-muted:var(--sage-100);--border-subtle:#E0DDD8;--border-default:#D4D1CC;--border-strong:#A8A5A0;--border:var(--border-default);--border-light:var(--border-subtle);--radius-sm:6px;--radius-md:10px;--radius-lg:16px;--radius-full:999px;--space-1:4px;--space-2:8px;--space-3:12px;--space-4:16px;--space-5:20px;--space-6:24px;--space-8:32px;--space-10:40px;--space-12:48px;--space-16:64px}
body{font-family:var(--font-sans);font-size:16px;font-weight:400;line-height:1.65;color:var(--text-primary);background:var(--bg-primary);-webkit-font-smoothing:antialiased}
.aide-page{max-width:720px;margin:0 auto;padding:var(--space-12) var(--space-8)}
@media(max-width:640px){.aide-page{padding:var(--space-8) var(--space-5)}}
.aide-heading{margin-bottom:var(--space-4)}
.aide-heading--1{font-family:var(--font-serif);font-size:clamp(36px,4.5vw,42px);font-weight:700;line-height:1.2}
.aide-heading--2{font-family:var(--font-serif);font-size:clamp(28px,3.5vw,32px);font-weight:700;line-height:1.25;margin-top:var(--space-8)}
.aide-heading--3{font-family:var(--font-heading);font-size:18px;font-weight:600;line-height:1.4}
.aide-text{font-size:16px;font-weight:400;line-height:1.65;color:var(--text-secondary);margin-bottom:var(--space-4)}
.aide-text strong{font-weight:500;color:var(--text-primary)}
.aide-text a{color:var(--accent);text-decoration:underline;text-decoration-color:var(--border);text-underline-offset:2px}
.aide-text a:hover{text-decoration-color:var(--accent)}
.aide-metric{display:flex;align-items:baseline;gap:var(--space-2);padding:var(--space-3) 0}
.aide-metric__label{font-size:15px;font-weight:400;color:var(--text-secondary)}
.aide-metric__label::after{content:':'}
.aide-metric__value{font-size:15px;font-weight:500;color:var(--text-primary)}
.aide-divider{border:none;border-top:1px solid var(--border-light);margin:var(--space-6) 0}
.aide-callout{background:var(--bg-secondary);border-left:3px solid var(--border);padding:var(--space-4) var(--space-5);margin:var(--space-4) 0;border-radius:0 var(--radius-sm) var(--radius-sm) 0;font-size:15px;line-height:1.55;color:var(--text-secondary)}
.aide-image{margin:var(--space-6) 0}
.aide-image img{max-width:100%;height:auto;border-radius:var(--radius-sm)}
.aide-image__caption{font-size:13px;color:var(--text-tertiary);margin-top:var(--space-2)}
.aide-columns{display:flex;gap:var(--space-6)}
@media(max-width:640px){.aide-columns{flex-direction:column}}
.aide-column{flex:1}
.aide-table-wrap{overflow-x:auto;margin:var(--space-4) 0}
.aide-table{width:100%;border-collapse:collapse;font-size:15px}
.aide-table th{font-size:11px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;color:var(--text-tertiary);text-align:left;padding:var(--space-2) var(--space-3);border-bottom:2px solid var(--border)}
.aide-table td{padding:var(--space-3);border-bottom:1px solid var(--border-light);color:var(--text-secondary);vertical-align:top}
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
.aide-annotation__text{font-size:15px;color:var(--text-secondary);line-height:1.5}
.aide-annotation__meta{font-size:12px;color:var(--text-tertiary);margin-left:var(--space-3)}
.aide-annotation--pinned{border-left:3px solid var(--accent);padding-left:var(--space-4)}
.aide-highlight{background-color:var(--accent-subtle)}
.aide-group{margin-bottom:var(--space-6)}
.aide-group__header{font-size:11px;font-weight:500;letter-spacing:.1em;text-transform:uppercase;color:var(--text-tertiary);margin-bottom:var(--space-3);padding-bottom:var(--space-2);border-bottom:1px solid var(--border-light)}
.aide-footer{margin-top:var(--space-16);padding-top:var(--space-6);border-top:1px solid var(--border-light);font-size:12px;color:var(--text-tertiary);text-align:center}
.aide-footer a{color:var(--text-tertiary);text-decoration:none}
.aide-footer a:hover{color:var(--text-secondary)}
.aide-footer .aide-footer__sep{margin:0 var(--space-2)}`
