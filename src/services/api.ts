const BACKEND_URL = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";


export interface HealthResponse {
  status: string;
  service: string;
  database: string;
}

export interface ConnectionStatus {
  backendConnected: boolean;
  databaseConnected: boolean;
}

// Candidate Profile TypeScript Structures
export interface PersonalInfo {
  name: string;
  email: string | null;
  phone: string | null;
  location: string | null;
}

export interface Education {
  institution: string;
  degree: string | null;
  field_of_study: string | null;
  graduation_year: number | null;
}

export interface Experience {
  company: string;
  role: string;
  location: string | null;
  start_date: string | null;
  end_date: string | null;
  description: string | null;
  technologies: string[];
}

export interface Project {
  name: string;
  description: string | null;
  technologies: string[];
  url: string | null;
}

export interface Skills {
  programming_languages: string[];
  frameworks: string[];
  libraries: string[];
  databases: string[];
  cloud: string[];
  tools: string[];
  other_skills: string[];
}

export interface AdditionalInfo {
  achievements: string[];
  languages: string[];
  links: string[];
}

export interface UserPreferences {
  preferred_roles: string[];
  preferred_locations: string[];
  remote_preference: string | null;
  experience_level: string | null;
}

export interface CandidateProfile {
  version: string;
  personal_info: PersonalInfo;
  education: Education[];
  skills: Skills;
  experience: Experience[];
  projects: Project[];
  certifications: string[];
  additional_info: AdditionalInfo;
  preferences: UserPreferences;
  profile_source: string;
  preferences_source: string;
}

/**
 * Checks the health of the FastAPI backend and local SQLite database dynamically.
 * Catches any network errors when backend is offline.
 */
export async function checkBackendHealth(): Promise<ConnectionStatus> {
  try {
    const response = await fetch(`${BACKEND_URL}/api/health`, {
      method: "GET",
      headers: {
        "Accept": "application/json",
      },
      signal: AbortSignal.timeout(2000),
    });

    if (!response.ok) {
      return { backendConnected: false, databaseConnected: false };
    }

    const data: HealthResponse = await response.json();
    return {
      backendConnected: data.status === "ok",
      databaseConnected: data.database === "connected",
    };
  } catch (error) {
    return { backendConnected: false, databaseConnected: false };
  }
}

/**
 * Uploads a PDF/DOCX resume file to the backend parsing API.
 * Returns the structured CandidateProfile schema for review.
 */
export async function uploadResume(file: File): Promise<CandidateProfile> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${BACKEND_URL}/api/profile/resume`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to upload and parse resume.");
  }

  return response.json();
}

/**
 * Fetches the currently saved candidate profile from SQLite.
 * Returns null if no profile exists.
 */
export async function getCandidateProfile(): Promise<CandidateProfile | null> {
  const response = await fetch(`${BACKEND_URL}/api/profile`, {
    method: "GET",
    headers: {
      "Accept": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error("Failed to retrieve candidate profile.");
  }

  return response.json();
}

/**
 * Saves/updates the reviewed candidate profile into SQLite.
 */
export async function saveCandidateProfile(profile: CandidateProfile): Promise<CandidateProfile> {
  const response = await fetch(`${BACKEND_URL}/api/profile`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify(profile),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to save candidate profile.");
  }

  return response.json();
}

// Job Ingestion and Aggregation TypeScript Structures
export interface Job {
  job_id: string;
  source: string;
  source_job_id: string;
  title: string;
  normalized_title: string;
  company: string;
  normalized_company: string;
  location: string;
  normalized_location: string;
  remote_status: string;
  description: string;
  requirements: string[];
  preferred_qualifications: string[];
  skills: string[];
  experience_required: number | null;
  employment_type: string;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  posted_date: string | null;
  application_url: string;
  first_seen_at: string;
  last_seen_at: string;
  collected_at: string;
}

export interface JobSearchRequest {
  query: string;
  location?: string | null;
  remote?: string | null;
  page?: number;
  limit?: number;
  max_pages?: number;
}

export interface DuplicateRecordInfo {
  title: string;
  company: string;
  sources: string[];
  canonical_url: string;
  detected_at: string;
}

export interface JobSearchResponse {
  jobs_found: number;
  new_jobs: number;
  duplicates_removed: number;
  errors: Record<string, string>;
  jobs: Job[];
  duplicate_records?: DuplicateRecordInfo[];
}


export interface JobQueryParams {
  page?: number;
  limit?: number;
  source?: string;
  company?: string;
  location?: string;
  remote?: string;
  title?: string;
  min_exp?: number;
  max_exp?: number;
}


/**
 * Searches for jobs across multiple sources and ingests them into the backend database.
 */
export async function searchJobs(params: JobSearchRequest): Promise<JobSearchResponse> {
  const response = await fetch(`${BACKEND_URL}/api/jobs/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to query job aggregation pipeline.");
  }

  return response.json();
}

/**
 * Fetches stored jobs from the database with pagination and filters.
 */
export async function getJobs(filters: JobQueryParams = {}): Promise<Job[]> {
  const urlParams = new URLSearchParams();
  Object.entries(filters).forEach(([key, val]) => {
    if (val !== undefined && val !== null && val !== "") {
      urlParams.append(key, val.toString());
    }
  });

  const response = await fetch(`${BACKEND_URL}/api/jobs?${urlParams.toString()}`, {
    method: "GET",
    headers: {
      "Accept": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error("Failed to load jobs list.");
  }

  return response.json();
}

/**
 * Retrieves the full details of a specific job by ID.
 */
export async function getJob(jobId: string): Promise<Job> {
  const response = await fetch(`${BACKEND_URL}/api/jobs/${jobId}`, {
    method: "GET",
    headers: {
      "Accept": "application/json",
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to load job details.");
  }

  return response.json();
}

// Matching and Suitability Engine TypeScript Structures
export type RecommendationEnum = "STRONG_MATCH" | "MATCH" | "POSSIBLE" | "WEAK_MATCH" | "REJECT";

export interface MatchResult {
  match_id: string;
  job_id: string;
  candidate_profile_id: string;
  overall_score: number;
  recommendation: RecommendationEnum;
  skill_score: number;
  experience_score: number;
  education_score: number;
  role_score: number;
  location_score: number;
  required_qualification_score: number;
  preferred_qualification_score: number;
  matching_skills: string[];
  missing_required_skills: string[];
  missing_preferred_skills: string[];
  experience_gap: number;
  concerns: string[];
  explanation: string;
  confidence: number;
  engine_version: string;
  created_at: string;
  updated_at: string;
}

export interface BatchMatchRequest {
  minimum_score?: number;
  limit?: number;
  include_llm_analysis?: boolean;
}

export interface MatchSearchResponse {
  jobs_processed: number;
  matches_created: number;
  matches_updated: number;
  matches: MatchResult[];
}

/**
 * Computes suitability score and rating for a single job opening.
 */
export async function matchJob(jobId: string, includeLlm: boolean = true): Promise<MatchResult> {
  const response = await fetch(`${BACKEND_URL}/api/matches/job/${jobId}?include_llm=${includeLlm}`, {
    method: "POST",
    headers: {
      "Accept": "application/json",
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to analyze job suitability.");
  }

  return response.json();
}

/**
 * Triggers batch matches for all stored jobs in SQLite.
 */
export async function batchMatch(params: BatchMatchRequest = {}): Promise<MatchSearchResponse> {
  const response = await fetch(`${BACKEND_URL}/api/matches/search`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify(params),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to run batch job matching.");
  }

  return response.json();
}

/**
 * Retrieves ranked match results list from SQLite.
 */
export async function getMatches(minScore?: number, limit: number = 50): Promise<MatchResult[]> {
  const urlParams = new URLSearchParams();
  urlParams.append("limit", limit.toString());
  if (minScore !== undefined && minScore !== null) {
    urlParams.append("min_score", minScore.toString());
  }

  const response = await fetch(`${BACKEND_URL}/api/matches?${urlParams.toString()}`, {
    method: "GET",
    headers: {
      "Accept": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error("Failed to load match results list.");
  }

  return response.json();
}

/**
 * Loads details of a specific candidate-job match score.
 */
export async function getMatchDetails(matchId: string): Promise<MatchResult> {
  const response = await fetch(`${BACKEND_URL}/api/matches/${matchId}`, {
    method: "GET",
    headers: {
      "Accept": "application/json",
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to load match details.");
  }

  return response.json();
}

// ==========================================
// Phase 4: Application Intelligence Interfaces & APIs
// ==========================================

export interface ApplicationFormField {
  id: string;
  application_id: string;
  field_name: string;
  label: string;
  field_type: string;
  required: boolean;
  options: string[];
  current_value: string | null;
  suggested_value: string | null;
  source: "candidate_profile" | "llm_generated" | "user_override" | "unknown" | string;
  confidence: number;
  requires_review: boolean;
}

export interface ApplicationResponse {
  id: string;
  job_id: string;
  candidate_profile_id: string;
  application_url: string;
  platform: string;
  status: "DISCOVERED" | "ANALYZING" | "READY_FOR_REVIEW" | "APPROVED" | "FAILED" | string;
  created_at: string;
  updated_at: string;
  fields: ApplicationFormField[];
}

export interface ApplicationFieldUpdate {
  field_id: string;
  current_value?: string | null;
  requires_review?: boolean | null;
}

/**
 * Analyzes application form fields for a target job.
 */
export async function analyzeApplication(jobId: string, applicationUrl?: string): Promise<ApplicationResponse> {
  const response = await fetch(`${BACKEND_URL}/api/applications/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify({ job_id: jobId, application_url: applicationUrl }),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to analyze application form.");
  }

  return response.json();
}

/**
 * Retrieves full detail of an analyzed application.
 */
export async function getApplicationDetails(applicationId: string): Promise<ApplicationResponse> {
  const response = await fetch(`${BACKEND_URL}/api/applications/${applicationId}`, {
    method: "GET",
    headers: {
      "Accept": "application/json",
    },
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to load application details.");
  }

  return response.json();
}

/**
 * Approves an application package after human review.
 */
export async function approveApplication(
  applicationId: string,
  fieldUpdates?: ApplicationFieldUpdate[]
): Promise<ApplicationResponse> {
  const response = await fetch(`${BACKEND_URL}/api/applications/${applicationId}/approve`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept": "application/json",
    },
    body: JSON.stringify({ field_updates: fieldUpdates }),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({}));
    throw new Error(errData.detail || "Failed to approve application package.");
  }

  return response.json();
}



