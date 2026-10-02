export type SlotStatus = "planned" | "passed" | "replaced";
export type SlotKind = "fixed" | "major_elective" | "free_elective";

export interface Slot {
  slot_id: string;
  codes: string[];
  title: string;
  units: number;
  slot_kind: SlotKind;
  swappable: boolean;
  pool_section_id: number | null;
  counts_toward_major: boolean;
  status: SlotStatus;
}

export interface Term {
  position: number;
  label: string;
  slots: Slot[];
}

export interface Pathway {
  program_id: number;
  program_title: string;
  program_level: string | null;
  roadmap_id: number;
  roadmap_name: string;
  total_units_required: number | null;
  major_units_required: number | null;
  terms: Term[];
  unplaced_passed: string[];
}

export interface AppliedEdit {
  slot_id: string;
  new_course_code: string;
  title: string;
  reason: string;
}

export interface Violation {
  rule: string;
  slot_id: string | null;
  message: string;
}

export interface DroppedEdit {
  edit: { slot_id: string; new_course_code: string; reason: string };
  violations: Violation[];
}

export interface Intent {
  specialization: boolean;
  topics: string[];
  keywords: string[];
  summary: string;
}

export interface PathwayResult {
  pathway: Pathway;
  applied: AppliedEdit[];
  dropped: DroppedEdit[];
  warnings: string[];
  intent: Intent | null;
  note: string | null;
  cached: boolean;
}

export interface SavedPathway extends PathwayResult {
  id: number;
  interest: string | null;
}

export interface PathwayListItem {
  id: number;
  program_id: number;
  program_title: string;
  roadmap_name: string;
  interest: string | null;
  swaps: number;
  created_at: string;
}

export interface ProgramBrief {
  id: number;
  title: string;
  slug: string;
  college: string | null;
  department: string | null;
  degree_type: string | null;
  level: string | null;
  concentration: string | null;
}

export interface RoadmapBrief {
  id: number;
  name: string;
  is_default: boolean;
  total_units_required: number | null;
  major_units: number | null;
}

export interface CourseDetail {
  code: string;
  title: string;
  units_min: number;
  units_max: number;
  description: string | null;
  prereq_text: string | null;
  prereq_groups: string[][];
  attributes: string[];
}

export interface Candidate {
  code: string;
  title: string;
  units: number;
  similarity: number;
  summary: string;
  warnings: string[];
}

export interface OptionsResponse {
  slot_id: string;
  query: string;
  candidates: Candidate[];
}

export interface TranscriptCourse {
  code: string;
  title?: string | null;
  grade: string | null;
  term: string | null;
  flagged: boolean;
}

export interface TranscriptSummary {
  count: number;
  courses: TranscriptCourse[];
  flagged: string[];
}

export interface User {
  id: number;
  email: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
  token_type: string;
}

export interface GeCourse {
  code: string;
  title: string;
  units_min: number;
  units_max: number;
  description: string;
  attributes: string[];
}
