/**
 * The contract between frontend and backend.
 * Field names match the FastAPI/Pydantic models exactly — see Backend /docs.
 * Reconciled against the actual backend response shape; no adapter layer needed.
 */
 
// ---------- Components ----------
 
export type ComponentType =
  | 'title'
  | 'body'
  | 'text_box'
  | 'picture'
  | 'table'
  | 'chart'
  | 'group'
  | 'other'
 
/** Normalised 0..1 fractions of slide width/height — never pixels. Backend field names: left/top/width/height. */
export interface BBox {
  left: number
  top: number
  width: number
  height: number
}
 
export interface Component {
  id: string
  type: ComponentType
  bbox: BBox
  text: string
  /** Pre-computed at upload time — the default hover explanation. No extra call needed. */
  context: string | null
  sources: string[]
}
 
export interface Slide {
  index: number
  notes: string
  components: Component[]
  imageUrl: string | null
  /** Not returned by the backend — derived client-side from the first TITLE component, if any. */
  title?: string
}
 
export interface Deck {
  id: string
  slides: Slide[]
  slides_filename?: string
  doc_filenames?: string[]
  source?: 'local' | 'google_drive'
  selected_docs?: string[]
  /**
   * Not currently returned by the backend (needs prs.slide_width / prs.slide_height
   * added server-side). Falls back to a standard 16:9 default until then.
   */
  aspectRatio?: number
}
 
// ---------- Audience (replaces the old fixed persona system) ----------
 
export type AudiencePreset =
  | 'general'
  | 'swe'
  | 'marketing'
  | 'executive'
  | 'sales'
  | 'student'
  | 'designer'
  | 'finance'
 
export const AUDIENCE_PRESETS: AudiencePreset[] = [
  'general',
  'swe',
  'marketing',
  'executive',
  'sales',
  'student',
  'designer',
  'finance',
]
 
/** A preset, or any free-text role string (e.g. "junior PM at a B2B SaaS startup"). */
export type Audience = AudiencePreset | (string & {})
 
// ---------- Single-shot query ----------
 
export type QueryMode = 'ask' | 'summarize' | 'explain'
 
export interface QueryRequest {
  mode: QueryMode
  /** Required when mode === 'ask'. */
  question?: string
  component_id?: string
  slide_index?: number
  audience?: Audience
}
 
export interface QueryResponse {
  answer: string
  sources: string[]
}
 
// ---------- Sessions (multi-turn chat per component) ----------
 
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  sources?: string[]
  created_at: string
}
 
export interface Session {
  id: string
  deck_id: string
  component_id: string
  audience: Audience
  messages: ChatMessage[]
}
 
export interface CreateSessionRequest {
  component_id: string
  audience?: Audience
  force_new?: boolean
}
 
export interface SendMessageRequest {
  mode: QueryMode
  /** Required for mode === 'ask'; may be empty for summarize/explain. */
  content: string
}
 
// ---------- Google Drive storage ----------
 
export interface DriveConnection {
  id: string
  created_at: string
}
 
export interface DriveFile {
  id: string
  name: string
  mime_type: string
}
 
export interface DriveFileList {
  slides: DriveFile[]
  docs: DriveFile[]
}
 
export interface DriveImportRequest {
  connection_id?: string
  access_token?: string
  slides_file_id: string
  auto_select_docs: boolean
  max_docs?: number
  folder_id?: string | null
  doc_file_ids?: string[]
}
 
// ---------- Local error shape ----------
 
export interface ApiError {
  detail: string
}