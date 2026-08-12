import React, { useState, useEffect, useRef } from "react";
import { 
  Server, 
  Database, 
  Sparkles, 
  UploadCloud, 
  FileText, 
  Plus, 
  Trash2, 
  Save, 
  Edit3, 
  CheckCircle2, 
  Globe, 
  Briefcase, 
  GraduationCap, 
  Award, 
  Sliders,
  AlertCircle,
  FileCheck,
  RefreshCw,
  Search,
  MapPin,
  ExternalLink,
  Info,
  Calendar,
  DollarSign,
  ChevronRight,
  Gauge,
  TrendingUp,
  AlertTriangle,
  X,
  SlidersHorizontal
} from "lucide-react";
import { 
  checkBackendHealth, 
  ConnectionStatus, 
  uploadResume, 
  getCandidateProfile, 
  saveCandidateProfile, 
  searchJobs,
  getJobs,
  getJob,
  matchJob,
  batchMatch,
  getMatches,
  CandidateProfile, 
  Education, 
  Experience, 
  Project,
  Job,
  MatchResult,
  RecommendationEnum
} from "./services/api";

export default function App() {
  // Status states
  const [status, setStatus] = useState<ConnectionStatus>({
    backendConnected: false,
    databaseConnected: false,
  });
  
  // Navigation
  const [activeTab, setActiveTab] = useState<"profile" | "jobs">("profile");
  
  // Candidate Profile logic states
  const [profile, setProfile] = useState<CandidateProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [uploadState, setUploadState] = useState<"idle" | "uploading" | "parsing" | "saving" | "done">("idle");
  const [profileError, setProfileError] = useState<string | null>(null);
  const [isEditingProfile, setIsEditingProfile] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  
  // Job Board logic states
  const [jobs, setJobs] = useState<Job[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchLocation, setSearchLocation] = useState("");
  const [searchRemote, setSearchRemote] = useState("any");
  const [isSearchingJobs, setIsSearchingJobs] = useState(false);
  const [jobSearchStats, setJobSearchStats] = useState<{ jobs_found: number; new_jobs: number; duplicates_removed: number; errors: Record<string, string> } | null>(null);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [isDetailDrawerOpen, setIsDetailDrawerOpen] = useState(false);
  const [jobFilterSource, setJobFilterSource] = useState("");
  const [jobsPage, setJobsPage] = useState(1);
  const [hasMoreJobs, setHasMoreJobs] = useState(true);

  // Match Engine logic states
  const [matches, setMatches] = useState<Record<string, MatchResult>>({});
  const [isAnalyzingId, setIsAnalyzingId] = useState<string | null>(null);
  const [isBatchAnalyzing, setIsBatchAnalyzing] = useState(false);
  const [matchFilterScore, setMatchFilterScore] = useState<number>(0);
  const [matchFilterRec, setMatchFilterRec] = useState<string>("");
  const [jobsSortOrder, setJobsSortOrder] = useState<"score" | "newest">("score");

  // File input ref
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Poll backend health status endpoint and load active profile + saved jobs + matches
  const checkHealthAndLoadData = async (initialLoad = false) => {
    const currentStatus = await checkBackendHealth();
    setStatus(currentStatus);
    
    if (currentStatus.backendConnected) {
      if (initialLoad) {
        try {
          // Fetch candidate profile from SQLite
          const savedProfile = await getCandidateProfile();
          if (savedProfile) {
            setProfile(savedProfile);
            setUploadState("done");
          }
          
          // Fetch existing jobs from SQLite
          const savedJobs = await getJobs({ page: 1, limit: 30 });
          setJobs(savedJobs);
          if (savedJobs.length < 30) {
            setHasMoreJobs(false);
          }

          // Fetch match results
          await loadMatches();
        } catch (err: any) {
          console.error("Failed to load initial data from backend:", err);
        } finally {
          setIsLoading(false);
        }
      }
    } else if (initialLoad) {
      setIsLoading(false);
    }
  };

  const loadMatches = async () => {
    try {
      const matchResults = await getMatches(undefined, 200);
      const matchMap: Record<string, MatchResult> = {};
      matchResults.forEach((m) => {
        matchMap[m.job_id] = m;
      });
      setMatches(matchMap);
    } catch (err) {
      console.error("Failed to load match results from database:", err);
    }
  };

  useEffect(() => {
    checkHealthAndLoadData(true);
    const interval = setInterval(() => checkHealthAndLoadData(false), 3000);
    return () => clearInterval(interval);
  }, []);

  const triggerToast = (msg: string) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 3000);
  };

  // ==========================================
  // RESUME UPLOAD HANDLERS
  // ==========================================
  const [dragActive, setDragActive] = useState(false);
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      await handleFileProcessing(e.dataTransfer.files[0]);
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      await handleFileProcessing(e.target.files[0]);
    }
  };

  const handleFileProcessing = async (file: File) => {
    setProfileError(null);
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (ext !== "pdf" && ext !== "docx") {
      setProfileError("Unsupported file format. Please upload a PDF or DOCX file.");
      return;
    }
    
    if (file.size > 5 * 1024 * 1024) {
      setProfileError("File exceeds 5MB size limit.");
      return;
    }

    try {
      setUploadState("uploading");
      setTimeout(() => setUploadState("parsing"), 800);
      
      const parsedProfile = await uploadResume(file);
      setProfile(parsedProfile);
      setIsEditingProfile(true); // Open edit panel immediately for review
      setUploadState("done");
      triggerToast("Resume analyzed successfully!");
    } catch (err: any) {
      setProfileError(err.message || "Failed to process resume.");
      setUploadState("idle");
    }
  };

  // ==========================================
  // PROFILE EDIT HANDLERS
  // ==========================================
  const updatePersonalInfo = (field: string, val: string) => {
    if (!profile) return;
    setProfile({
      ...profile,
      personal_info: { ...profile.personal_info, [field]: val }
    });
  };

  const updatePreferences = (field: string, val: any) => {
    if (!profile) return;
    setProfile({
      ...profile,
      preferences: { ...profile.preferences, [field]: val }
    });
  };

  const handleSaveProfile = async () => {
    if (!profile) return;
    setProfileError(null);
    setUploadState("saving");
    try {
      const saved = await saveCandidateProfile(profile);
      setProfile(saved);
      setIsEditingProfile(false);
      setUploadState("done");
      triggerToast("Candidate profile saved to SQLite!");
      
      // Auto re-run matches if we have jobs stored
      if (jobs.length > 0) {
        triggerToast("Profile updated. Recalculating scores...");
        handleBatchMatch();
      }
    } catch (err: any) {
      setProfileError(err.message || "Failed to save profile.");
      setUploadState("done");
    }
  };

  // Relational list helpers
  const handleUpdateEducation = (index: number, field: keyof Education, val: any) => {
    if (!profile) return;
    const list = [...profile.education];
    list[index] = { ...list[index], [field]: val };
    setProfile({ ...profile, education: list });
  };
  const handleUpdateExperience = (index: number, field: keyof Experience, val: any) => {
    if (!profile) return;
    const list = [...profile.experience];
    list[index] = { ...list[index], [field]: val };
    setProfile({ ...profile, experience: list });
  };
  const handleUpdateProject = (index: number, field: keyof Project, val: any) => {
    if (!profile) return;
    const list = [...profile.projects];
    list[index] = { ...list[index], [field]: val };
    setProfile({ ...profile, projects: list });
  };

  // ==========================================
  // JOB BOARD & DISCOVERY HANDLERS
  // ==========================================
  const handleJobSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setJobsError("Please enter search keywords or role title.");
      return;
    }
    
    setJobsError(null);
    setIsSearchingJobs(true);
    setJobSearchStats(null);
    setJobsPage(1);

    try {
      // Ingest new jobs from remote boards
      const stats = await searchJobs({
        query: searchQuery,
        location: searchLocation || null,
        remote: searchRemote === "any" ? null : searchRemote,
        page: 1,
        limit: 15,
        max_pages: 1
      });
      
      setJobSearchStats(stats);
      
      // Load latest database jobs
      const dbJobs = await getJobs({ 
        page: 1, 
        limit: 30,
        remote: searchRemote === "any" ? undefined : searchRemote,
        title: searchQuery
      });
      setJobs(dbJobs);
      setHasMoreJobs(dbJobs.length === 30);
      
      // Automatically score new jobs deterministically
      if (profile && dbJobs.length > 0) {
        await handleBatchMatch(false); // fast deterministic matching
      }
      triggerToast("Job board updated!");
    } catch (err: any) {
      setJobsError(err.message || "Failed to discover new jobs.");
    } finally {
      setIsSearchingJobs(false);
    }
  };

  const loadMoreJobs = async () => {
    const nextPage = jobsPage + 1;
    try {
      const moreJobs = await getJobs({
        page: nextPage,
        limit: 30,
        source: jobFilterSource || undefined,
        remote: searchRemote === "any" ? undefined : searchRemote,
        title: searchQuery || undefined
      });
      
      if (moreJobs.length > 0) {
        setJobs([...jobs, ...moreJobs]);
        setJobsPage(nextPage);
        setHasMoreJobs(moreJobs.length === 30);
      } else {
        setHasMoreJobs(false);
      }
    } catch (err: any) {
      console.error("Failed to load more jobs:", err);
    }
  };

  const handleViewJobDetails = async (jobId: string) => {
    try {
      const details = await getJob(jobId);
      setSelectedJob(details);
      setIsDetailDrawerOpen(true);
    } catch (err: any) {
      triggerToast("Failed to load job details.");
    }
  };

  const formatJobDate = (dateStr: string | null) => {
    if (!dateStr) return "Just now";
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
    } catch {
      return "Recent";
    }
  };

  // ==========================================
  // MATCH ENGINE HANDLERS
  // ==========================================
  const handleSingleMatch = async (jobId: string, e: React.MouseEvent) => {
    e.stopPropagation(); // prevent card drawer trigger
    if (!profile) {
      triggerToast("Please upload a Candidate Profile first.");
      return;
    }
    
    setIsAnalyzingId(jobId);
    try {
      const result = await matchJob(jobId, true); // Runs semantic integration
      setMatches(prev => ({ ...prev, [jobId]: result }));
      triggerToast(`Job score calculated: ${result.overall_score}%`);
    } catch (err: any) {
      triggerToast(err.message || "Analysis failed.");
    } finally {
      setIsAnalyzingId(null);
    }
  };

  const handleBatchMatch = async (includeLlm = true) => {
    if (!profile) {
      triggerToast("Please upload a Candidate Profile first.");
      return;
    }
    setIsBatchAnalyzing(true);
    try {
      const response = await batchMatch({
        minimum_score: 0,
        limit: 100,
        include_llm_analysis: includeLlm
      });
      await loadMatches();
      triggerToast(`Analyzed ${response.jobs_processed} jobs successfully.`);
    } catch (err: any) {
      triggerToast(err.message || "Batch matching failed.");
    } finally {
      setIsBatchAnalyzing(false);
    }
  };

  // Score Badge helpers
  const getRecommendationBadgeColor = (rec: RecommendationEnum) => {
    switch (rec) {
      case "STRONG_MATCH":
        return "bg-emerald-500/10 border-emerald-500/30 text-emerald-400";
      case "MATCH":
        return "bg-teal-500/10 border-teal-500/30 text-teal-400";
      case "POSSIBLE":
        return "bg-amber-500/10 border-amber-500/30 text-amber-400";
      case "WEAK_MATCH":
        return "bg-orange-500/10 border-orange-500/30 text-orange-400";
      case "REJECT":
        return "bg-rose-500/10 border-rose-500/30 text-rose-400";
      default:
        return "bg-neutral-800 border-neutral-700 text-neutral-400";
    }
  };

  const getScoreColorClass = (score: number) => {
    if (score >= 80) return "text-emerald-400 border-emerald-500/20";
    if (score >= 60) return "text-teal-400 border-teal-500/20";
    if (score >= 45) return "text-amber-400 border-amber-500/20";
    return "text-rose-400 border-rose-500/20";
  };

  // Sort and Filter Jobs Feed
  const getFilteredJobs = () => {
    let list = [...jobs];
    
    // Source filter
    if (jobFilterSource) {
      list = list.filter(j => j.source === jobFilterSource);
    }

    // Match filtering checks
    list = list.filter(j => {
      const match = matches[j.job_id];
      
      // Score filter
      if (matchFilterScore > 0) {
        if (!match || match.overall_score < matchFilterScore) {
          return false;
        }
      }
      
      // Recommendation filter
      if (matchFilterRec) {
        if (!match || match.recommendation !== matchFilterRec) {
          return false;
        }
      }
      
      return true;
    });

    // Sorting
    if (jobsSortOrder === "score") {
      list.sort((a, b) => {
        const scoreA = matches[a.job_id]?.overall_score || 0;
        const scoreB = matches[b.job_id]?.overall_score || 0;
        return scoreB - scoreA;
      });
    } else {
      list.sort((a, b) => {
        const dateA = a.posted_date ? new Date(a.posted_date).getTime() : 0;
        const dateB = b.posted_date ? new Date(b.posted_date).getTime() : 0;
        return dateB - dateA;
      });
    }

    return list;
  };

  const filteredJobs = getFilteredJobs();
  const currentMatch = selectedJob ? matches[selectedJob.job_id] : null;

  if (isLoading) {
    return (
      <div className="min-h-screen bg-neutral-950 text-neutral-100 flex items-center justify-center font-sans">
        <div className="flex flex-col items-center gap-3">
          <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
          <p className="text-sm text-neutral-400 font-medium">Loading JobHunter AI Dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-neutral-950 text-neutral-100 flex flex-col font-sans selection:bg-indigo-600 selection:text-white antialiased relative">
      {/* Toast Notification */}
      {successMessage && (
        <div className="fixed bottom-6 right-6 px-5 py-3.5 bg-emerald-950/90 border border-emerald-500/40 rounded-xl shadow-2xl flex items-center gap-3 text-emerald-300 text-sm font-semibold z-50 animate-bounce">
          <CheckCircle2 className="w-5 h-5 text-emerald-400" />
          {successMessage}
        </div>
      )}

      {/* Header */}
      <header className="border-b border-neutral-900 bg-neutral-950/80 backdrop-blur-md sticky top-0 z-50 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2.5">
            <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400 border border-indigo-500/20">
              <Sparkles className="w-5 h-5 animate-pulse" />
            </div>
            <span className="text-xl font-bold tracking-tight bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
              JobHunter AI
            </span>
          </div>
          
          {/* Navigation tabs */}
          <nav className="hidden md:flex items-center bg-neutral-900 border border-neutral-850 rounded-xl p-1">
            <button
              onClick={() => { setActiveTab("profile"); setJobsError(null); }}
              className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                activeTab === "profile" 
                  ? "bg-neutral-800 text-white shadow-sm" 
                  : "text-neutral-400 hover:text-neutral-200"
              }`}
            >
              Resume Profile
            </button>
            <button
              onClick={() => { setActiveTab("jobs"); setProfileError(null); }}
              className={`px-4 py-1.5 text-xs font-semibold rounded-lg transition-all cursor-pointer ${
                activeTab === "jobs" 
                  ? "bg-neutral-800 text-white shadow-sm" 
                  : "text-neutral-400 hover:text-neutral-200"
              }`}
            >
              Job Board
            </button>
          </nav>
        </div>
        
        {/* Connection status checkers */}
        <div className="flex items-center gap-4 text-xs font-semibold">
          <span className={`px-2.5 py-1 bg-neutral-900 border rounded-full flex items-center gap-1.5 ${
            status.backendConnected ? "border-emerald-500/20 text-emerald-400" : "border-rose-500/20 text-rose-400"
          }`}>
            <Server className="w-3.5 h-3.5" />
            Backend: {status.backendConnected ? "Connected" : "Disconnected"}
          </span>
          <span className={`px-2.5 py-1 bg-neutral-900 border rounded-full flex items-center gap-1.5 ${
            status.databaseConnected ? "border-emerald-500/20 text-emerald-400" : "border-rose-500/20 text-rose-400"
          }`}>
            <Database className="w-3.5 h-3.5" />
            Database: {status.databaseConnected ? "Connected" : "Disconnected"}
          </span>
        </div>
      </header>

      {/* Main Container */}
      <main className="flex-1 max-w-6xl mx-auto w-full px-6 py-8 flex flex-col justify-start">
        
        {/* Mobile Tab Switcher */}
        <div className="md:hidden flex bg-neutral-900 border border-neutral-850 rounded-xl p-1 mb-6">
          <button
            onClick={() => setActiveTab("profile")}
            className={`flex-1 text-center py-2 text-xs font-semibold rounded-lg transition-all ${
              activeTab === "profile" ? "bg-neutral-800 text-white" : "text-neutral-400"
            }`}
          >
            Resume Profile
          </button>
          <button
            onClick={() => setActiveTab("jobs")}
            className={`flex-1 text-center py-2 text-xs font-semibold rounded-lg transition-all ${
              activeTab === "jobs" ? "bg-neutral-800 text-white" : "text-neutral-400"
            }`}
          >
            Job Board
          </button>
        </div>

        {/* TAB 1: RESUME PROFILE */}
        {activeTab === "profile" && (
          <div>
            {profileError && (
              <div className="mb-6 p-4 bg-rose-950/20 border border-rose-500/30 text-rose-300 rounded-xl flex items-start gap-3 text-sm animate-pulse">
                <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">Error:</span> {profileError}
                </div>
              </div>
            )}

            {/* Ingestion zone */}
            {uploadState !== "done" && uploadState !== "saving" && !profile && (
              <div className="max-w-2xl mx-auto w-full py-12">
                <div className="text-center mb-10">
                  <h1 className="text-4xl font-extrabold tracking-tight mb-3 bg-gradient-to-br from-white to-neutral-400 bg-clip-text text-transparent">
                    Upload Your Resume
                  </h1>
                  <p className="text-neutral-400">
                    Let AI build your candidate profile locally. PDF and DOCX formats supported.
                  </p>
                </div>

                {uploadState === "idle" ? (
                  <div
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                    onClick={() => fileInputRef.current?.click()}
                    className={`border-2 border-dashed rounded-3xl p-12 text-center cursor-pointer transition-all duration-300 flex flex-col items-center justify-center ${
                      dragActive 
                        ? "border-indigo-500 bg-indigo-950/10 scale-[1.01]" 
                        : "border-neutral-800 bg-neutral-900/20 hover:border-neutral-700 hover:bg-neutral-900/30"
                    }`}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      onChange={handleFileChange}
                      accept=".pdf,.docx"
                      className="hidden"
                    />
                    <div className="p-4 bg-indigo-500/10 rounded-2xl text-indigo-400 border border-indigo-500/20 mb-4">
                      <UploadCloud className="w-8 h-8" />
                    </div>
                    <h3 className="text-lg font-bold text-neutral-200 mb-1">Drag and drop file here</h3>
                    <p className="text-sm text-neutral-500 max-w-xs mb-4">or click to browse local folders (5MB limit)</p>
                    <span className="px-3.5 py-1.5 bg-neutral-950 border border-neutral-800 rounded-lg text-xs font-semibold text-neutral-400 hover:text-neutral-200">
                      Select PDF / DOCX
                    </span>
                  </div>
                ) : (
                  <div className="bg-neutral-900/40 border border-neutral-800 rounded-3xl p-12 flex flex-col items-center justify-center text-center">
                    <RefreshCw className="w-10 h-10 text-indigo-400 animate-spin mb-4" />
                    <h3 className="text-lg font-bold text-neutral-200 mb-1">
                      {uploadState === "uploading" ? "Uploading Resume File..." : "Analyzing Resume via Gemini AI..."}
                    </h3>
                    <p className="text-sm text-neutral-500 max-w-xs">
                      {uploadState === "uploading" 
                        ? "Reading raw document bytes locally." 
                        : "Extracting facts, mapping skills, and building schema."}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Profile Review Dashboard */}
            {profile && (
              <div className="w-full flex flex-col gap-6">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-neutral-900 pb-6">
                  <div>
                    <div className="flex items-center gap-3">
                      <h1 className="text-3xl font-extrabold tracking-tight">Candidate Profile</h1>
                      <span className={`px-2.5 py-1 text-xs font-semibold rounded-md flex items-center gap-1.5 ${
                        profile.profile_source === "user_provided"
                          ? "bg-emerald-500/10 border border-emerald-500/20 text-emerald-400"
                          : "bg-amber-500/10 border border-amber-500/20 text-amber-400"
                      }`}>
                        <FileCheck className="w-3.5 h-3.5" />
                        {profile.profile_source === "user_provided" ? "Authoritative (Saved)" : "Factual Extraction (Unsaved)"}
                      </span>
                    </div>
                    <p className="text-sm text-neutral-400 mt-1">
                      Verify or edit the candidate schema below. The checked profile will be saved locally to SQLite.
                    </p>
                  </div>
                  <div className="flex items-center gap-3">
                    {isEditingProfile ? (
                      <>
                        <button
                          onClick={handleSaveProfile}
                          disabled={uploadState === "saving"}
                          className="px-4 py-2.5 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:bg-neutral-800 disabled:text-neutral-500 font-semibold rounded-xl text-sm flex items-center gap-2 cursor-pointer transition-all border border-indigo-500/30"
                        >
                          {uploadState === "saving" ? (
                            <RefreshCw className="w-4 h-4 animate-spin" />
                          ) : (
                            <Save className="w-4 h-4" />
                          )}
                          Save Profile
                        </button>
                        <button
                          onClick={() => {
                            setIsEditingProfile(false);
                            checkHealthAndLoadData(true);
                          }}
                          className="px-4 py-2.5 bg-neutral-900 hover:bg-neutral-850 border border-neutral-850 font-semibold rounded-xl text-sm transition-all"
                        >
                          Cancel
                        </button>
                      </>
                    ) : (
                      <button
                        onClick={() => setIsEditingProfile(true)}
                        className="px-4 py-2.5 bg-neutral-900 hover:bg-neutral-800 border border-neutral-800 font-semibold rounded-xl text-sm flex items-center gap-2 cursor-pointer transition-all"
                      >
                        <Edit3 className="w-4 h-4 text-indigo-400" />
                        Edit Profile
                      </button>
                    )}
                    <button
                      onClick={() => {
                        if (window.confirm("Are you sure you want to parse another resume? Unsaved changes will be lost.")) {
                          setProfile(null);
                          setUploadState("idle");
                          setProfileError(null);
                        }
                      }}
                      className="px-4 py-2.5 bg-neutral-950 hover:bg-neutral-900 border border-neutral-900 hover:border-neutral-800 font-semibold rounded-xl text-sm flex items-center gap-2 transition-all text-neutral-400"
                    >
                      Parse New Resume
                    </button>
                  </div>
                </div>

                {/* Bento Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                  
                  {/* Left: Personal details & Job Preferences */}
                  <div className="lg:col-span-1 flex flex-col gap-6">
                    {/* Personal details */}
                    <div className="bg-neutral-900/40 border border-neutral-900 rounded-2xl p-6 flex flex-col gap-4">
                      <div className="flex items-center gap-2 text-indigo-400 font-bold border-b border-neutral-900 pb-3">
                        <Globe className="w-4 h-4" />
                        Personal Details
                      </div>
                      <div className="flex flex-col gap-3">
                        <div>
                          <label className="text-xs font-semibold text-neutral-500 block mb-1">Full Name</label>
                          <input
                            type="text"
                            disabled={!isEditingProfile}
                            value={profile.personal_info.name || ""}
                            onChange={(e) => updatePersonalInfo("name", e.target.value)}
                            className="w-full bg-neutral-950/60 border border-neutral-850 rounded-xl px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500 disabled:opacity-75"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-semibold text-neutral-500 block mb-1">Email Address</label>
                          <input
                            type="email"
                            disabled={!isEditingProfile}
                            value={profile.personal_info.email || ""}
                            onChange={(e) => updatePersonalInfo("email", e.target.value)}
                            className="w-full bg-neutral-950/60 border border-neutral-850 rounded-xl px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500 disabled:opacity-75"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-semibold text-neutral-500 block mb-1">Phone Number</label>
                          <input
                            type="text"
                            disabled={!isEditingProfile}
                            value={profile.personal_info.phone || ""}
                            onChange={(e) => updatePersonalInfo("phone", e.target.value)}
                            className="w-full bg-neutral-950/60 border border-neutral-850 rounded-xl px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500 disabled:opacity-75"
                          />
                        </div>
                        <div>
                          <label className="text-xs font-semibold text-neutral-500 block mb-1">Location</label>
                          <input
                            type="text"
                            disabled={!isEditingProfile}
                            value={profile.personal_info.location || ""}
                            onChange={(e) => updatePersonalInfo("location", e.target.value)}
                            className="w-full bg-neutral-950/60 border border-neutral-850 rounded-xl px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500 disabled:opacity-75"
                          />
                        </div>
                      </div>
                    </div>

                    {/* Job Preferences (Explicit user input) */}
                    <div className="bg-neutral-900/40 border border-neutral-900 rounded-2xl p-6 flex flex-col gap-4 relative overflow-hidden">
                      <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500/5 rounded-full blur-2xl"></div>
                      
                      <div className="flex items-center justify-between border-b border-neutral-900 pb-3">
                        <div className="flex items-center gap-2 text-indigo-400 font-bold">
                          <Sliders className="w-4 h-4" />
                          Job Preferences
                        </div>
                        <span className="px-2 py-0.5 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-md text-[10px] font-bold tracking-wider uppercase">
                          Manual Input Only
                        </span>
                      </div>

                      <p className="text-xs text-neutral-500 leading-relaxed bg-neutral-950/40 p-2.5 rounded-lg border border-neutral-850/50">
                        💡 These preferences are **never** inferred from your resume. Please enter them manually for accurate matching.
                      </p>

                      <div className="flex flex-col gap-3">
                        <div>
                          <label className="text-xs font-semibold text-neutral-500 block mb-1">Preferred Roles (Comma-separated)</label>
                          <input
                            type="text"
                            disabled={!isEditingProfile}
                            placeholder="e.g. Frontend Engineer, Fullstack Developer"
                            value={profile.preferences.preferred_roles?.join(", ") || ""}
                            onChange={(e) => updatePreferences("preferred_roles", e.target.value.split(",").map(s => s.trim()).filter(Boolean))}
                            className="w-full bg-neutral-950/60 border border-neutral-850 rounded-xl px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500 disabled:opacity-75"
                          />
                        </div>
                        
                        <div>
                          <label className="text-xs font-semibold text-neutral-500 block mb-1">Preferred Locations (Comma-separated)</label>
                          <input
                            type="text"
                            disabled={!isEditingProfile}
                            placeholder="e.g. New York, Remote"
                            value={profile.preferences.preferred_locations?.join(", ") || ""}
                            onChange={(e) => updatePreferences("preferred_locations", e.target.value.split(",").map(s => s.trim()).filter(Boolean))}
                            className="w-full bg-neutral-950/60 border border-neutral-850 rounded-xl px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500 disabled:opacity-75"
                          />
                        </div>

                        <div className="grid grid-cols-2 gap-3">
                          <div>
                            <label className="text-xs font-semibold text-neutral-500 block mb-1">Remote preference</label>
                            <select
                              disabled={!isEditingProfile}
                              value={profile.preferences.remote_preference || ""}
                              onChange={(e) => updatePreferences("remote_preference", e.target.value || null)}
                              className="w-full bg-neutral-950/60 border border-neutral-850 rounded-xl px-3 py-2 text-sm text-neutral-200 focus:outline-none disabled:opacity-75"
                            >
                              <option value="">Unspecified</option>
                              <option value="remote">Remote</option>
                              <option value="hybrid">Hybrid</option>
                              <option value="onsite">Onsite</option>
                              <option value="any">Any</option>
                            </select>
                          </div>

                          <div>
                            <label className="text-xs font-semibold text-neutral-500 block mb-1">Experience Level</label>
                            <select
                              disabled={!isEditingProfile}
                              value={profile.preferences.experience_level || ""}
                              onChange={(e) => updatePreferences("experience_level", e.target.value || null)}
                              className="w-full bg-neutral-950/60 border border-neutral-850 rounded-xl px-3 py-2 text-sm text-neutral-200 focus:outline-none disabled:opacity-75"
                            >
                              <option value="">Unspecified</option>
                              <option value="intern">Internship</option>
                              <option value="entry">Entry-Level</option>
                              <option value="mid">Mid-Level</option>
                              <option value="senior">Senior-Level</option>
                              <option value="lead">Lead / Staff</option>
                            </select>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Right Column: Skills & Projects */}
                  <div className="lg:col-span-2 flex flex-col gap-6">
                    {/* Skills */}
                    <div className="bg-neutral-900/40 border border-neutral-900 rounded-2xl p-6 flex flex-col gap-4">
                      <div className="flex items-center gap-2 text-indigo-400 font-bold border-b border-neutral-900 pb-3">
                        <Award className="w-4 h-4" />
                        Skills Inventory
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {Object.entries({
                          programming_languages: "Programming Languages",
                          frameworks: "Frameworks",
                          libraries: "Libraries",
                          databases: "Databases",
                          cloud: "Cloud Infrastructure",
                          tools: "Development Tools",
                          other_skills: "Other Skills"
                        }).map(([key, label]) => (
                          <div key={key}>
                            <label className="text-xs font-semibold text-neutral-500 block mb-1">{label}</label>
                            <input
                              type="text"
                              disabled={!isEditingProfile}
                              value={(profile.skills as any)[key]?.join(", ") || ""}
                              placeholder={`e.g. Skill A, Skill B`}
                              onChange={(e) => {
                                const list = e.target.value.split(",").map(s => s.trim()).filter(Boolean);
                                setProfile({
                                  ...profile,
                                  skills: { ...profile.skills, [key]: list }
                                });
                              }}
                              className="w-full bg-neutral-950/60 border border-neutral-850 rounded-xl px-3 py-2 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500 disabled:opacity-75"
                            />
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Projects */}
                    <div className="bg-neutral-900/40 border border-neutral-900 rounded-2xl p-6 flex flex-col gap-4">
                      <div className="flex items-center justify-between border-b border-neutral-900 pb-3">
                        <div className="flex items-center gap-2 text-indigo-400 font-bold">
                          <FileText className="w-4 h-4" />
                          Projects
                        </div>
                        {isEditingProfile && (
                          <button
                            onClick={() => {
                              const newProj: Project = { name: "Project Name", description: "", technologies: [], url: "" };
                              setProfile({ ...profile, projects: [...profile.projects, newProj] });
                            }}
                            className="px-2.5 py-1 bg-neutral-950 border border-neutral-800 hover:border-neutral-700 text-neutral-300 rounded-lg text-xs flex items-center gap-1 cursor-pointer"
                          >
                            <Plus className="w-3.5 h-3.5" /> Add Project
                          </button>
                        )}
                      </div>

                      <div className="flex flex-col gap-4">
                        {profile.projects.length === 0 && (
                          <p className="text-sm text-neutral-600 text-center py-4">No projects listed.</p>
                        )}
                        {profile.projects.map((proj, idx) => (
                          <div key={idx} className="p-4 bg-neutral-950/40 border border-neutral-855 rounded-xl flex flex-col gap-3 relative">
                            {isEditingProfile && (
                              <button
                                onClick={() => {
                                  const list = [...profile.projects];
                                  list.splice(idx, 1);
                                  setProfile({ ...profile, projects: list });
                                }}
                                className="absolute top-4 right-4 text-neutral-600 hover:text-rose-400 p-1 rounded cursor-pointer"
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            )}
                            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pr-8">
                              <div>
                                <label className="text-[10px] font-bold text-neutral-500 uppercase block mb-1">Project Name</label>
                                <input
                                  type="text"
                                  disabled={!isEditingProfile}
                                  value={proj.name || ""}
                                  onChange={(e) => handleUpdateProject(idx, "name", e.target.value)}
                                  className="w-full bg-neutral-950 border border-neutral-850 rounded-lg px-2.5 py-1.5 text-xs text-neutral-200"
                                />
                              </div>
                              <div>
                                <label className="text-[10px] font-bold text-neutral-500 uppercase block mb-1">Project URL</label>
                                <input
                                  type="text"
                                  disabled={!isEditingProfile}
                                  value={proj.url || ""}
                                  placeholder="https://..."
                                  onChange={(e) => handleUpdateProject(idx, "url", e.target.value)}
                                  className="w-full bg-neutral-950 border border-neutral-850 rounded-lg px-2.5 py-1.5 text-xs text-neutral-200"
                                />
                              </div>
                            </div>
                            <div>
                              <label className="text-[10px] font-bold text-neutral-500 uppercase block mb-1">Technologies (Comma-separated)</label>
                              <input
                                type="text"
                                disabled={!isEditingProfile}
                                value={proj.technologies?.join(", ") || ""}
                                onChange={(e) => handleUpdateProject(idx, "technologies", e.target.value.split(",").map(s => s.trim()).filter(Boolean))}
                                className="w-full bg-neutral-950 border border-neutral-850 rounded-lg px-2.5 py-1.5 text-xs text-neutral-200"
                              />
                            </div>
                            <div>
                              <label className="text-[10px] font-bold text-neutral-500 uppercase block mb-1">Description</label>
                              <textarea
                                disabled={!isEditingProfile}
                                rows={2}
                                value={proj.description || ""}
                                onChange={(e) => handleUpdateProject(idx, "description", e.target.value)}
                                className="w-full bg-neutral-950 border border-neutral-855 rounded-lg px-2.5 py-1.5 text-xs text-neutral-200 resize-none"
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: JOB DISCOVERY BOARD */}
        {activeTab === "jobs" && (
          <div className="flex flex-col gap-6">
            
            {/* Search inputs */}
            <div className="bg-neutral-900/40 border border-neutral-900 rounded-2xl p-6 flex flex-col gap-4">
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <h2 className="text-xl font-bold bg-gradient-to-r from-white to-neutral-400 bg-clip-text text-transparent flex items-center gap-2">
                  <Search className="w-5 h-5 text-indigo-400" />
                  Aggregated Job Board
                </h2>
                
                {profile && (
                  <button
                    onClick={() => handleBatchMatch(true)}
                    disabled={isBatchAnalyzing || jobs.length === 0}
                    className="px-4 py-2 bg-neutral-900 hover:bg-neutral-850 disabled:bg-neutral-950 border border-neutral-850 hover:border-neutral-800 disabled:opacity-50 text-neutral-300 font-semibold rounded-xl text-xs flex items-center gap-2 transition-all cursor-pointer"
                  >
                    {isBatchAnalyzing ? (
                      <>
                        <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        Scoring Jobs...
                      </>
                    ) : (
                      <>
                        <Gauge className="w-3.5 h-3.5 text-indigo-400" />
                        Batch Match Stored Jobs
                      </>
                    )}
                  </button>
                )}
              </div>
              
              <form onSubmit={handleJobSearch} className="flex flex-col md:flex-row md:items-end gap-4 border-t border-neutral-950/40 pt-4">
                <div className="flex-1">
                  <label className="text-xs font-semibold text-neutral-500 block mb-1">Role keywords / Title</label>
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="e.g. React Developer, Python, Software Engineer"
                    className="w-full bg-neutral-950 border border-neutral-850 rounded-xl px-4 py-3 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>
                
                <div className="w-full md:w-60">
                  <label className="text-xs font-semibold text-neutral-500 block mb-1">Location bounds</label>
                  <input
                    type="text"
                    value={searchLocation}
                    onChange={(e) => setSearchLocation(e.target.value)}
                    placeholder="e.g. Boston, London (optional)"
                    className="w-full bg-neutral-950 border border-neutral-850 rounded-xl px-4 py-3 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500"
                  />
                </div>

                <div className="w-full md:w-44">
                  <label className="text-xs font-semibold text-neutral-500 block mb-1">Remote filter</label>
                  <select
                    value={searchRemote}
                    onChange={(e) => setSearchRemote(e.target.value)}
                    className="w-full bg-neutral-950 border border-neutral-850 rounded-xl px-4 py-3 text-sm text-neutral-200 focus:outline-none focus:border-indigo-500"
                  >
                    <option value="any">Any Status</option>
                    <option value="remote">Remote Only</option>
                    <option value="hybrid">Hybrid</option>
                    <option value="onsite">Onsite Only</option>
                  </select>
                </div>

                <button
                  type="submit"
                  disabled={isSearchingJobs}
                  className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 disabled:bg-neutral-800 disabled:text-neutral-500 font-semibold rounded-xl text-sm flex items-center justify-center gap-2 cursor-pointer transition-all border border-indigo-500/30 shadow-lg shadow-indigo-500/10 flex-shrink-0"
                >
                  {isSearchingJobs ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      Searching...
                    </>
                  ) : (
                    <>
                      <Search className="w-4 h-4" />
                      Search Jobs
                    </>
                  )}
                </button>
              </form>
            </div>

            {/* jobs error warning */}
            {jobsError && (
              <div className="p-4 bg-rose-950/20 border border-rose-500/30 text-rose-300 rounded-xl flex items-start gap-3 text-sm">
                <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
                <div>
                  <span className="font-bold">Discovery Error:</span> {jobsError}
                </div>
              </div>
            )}

            {/* Aggregation statistics widget */}
            {jobSearchStats && (
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="bg-neutral-900/30 border border-neutral-900 p-4 rounded-xl text-center">
                  <div className="text-2xl font-black text-neutral-100">{jobSearchStats.jobs_found}</div>
                  <div className="text-[10px] uppercase font-bold text-neutral-500 tracking-wider mt-1">Jobs Found</div>
                </div>
                <div className="bg-neutral-900/30 border border-neutral-900 p-4 rounded-xl text-center">
                  <div className="text-2xl font-black text-emerald-400">{jobSearchStats.new_jobs}</div>
                  <div className="text-[10px] uppercase font-bold text-neutral-500 tracking-wider mt-1">New Jobs Saved</div>
                </div>
                <div className="bg-neutral-900/30 border border-neutral-900 p-4 rounded-xl text-center">
                  <div className="text-2xl font-black text-amber-500">{jobSearchStats.duplicates_removed}</div>
                  <div className="text-[10px] uppercase font-bold text-neutral-500 tracking-wider mt-1">Duplicates Removed</div>
                </div>
                <div className="bg-neutral-900/30 border border-neutral-900 p-4 rounded-xl flex flex-col justify-center items-center">
                  {Object.keys(jobSearchStats.errors).length > 0 ? (
                    <div className="text-xs text-rose-400 font-semibold flex items-center gap-1.5">
                      <AlertCircle className="w-4 h-4 flex-shrink-0" />
                      {Object.keys(jobSearchStats.errors).length} Source Failure(s)
                    </div>
                  ) : (
                    <div className="text-xs text-emerald-400 font-semibold flex items-center gap-1.5">
                      <CheckCircle2 className="w-4 h-4" />
                      All Sources Online
                    </div>
                  )}
                  <div className="text-[10px] uppercase font-bold text-neutral-500 tracking-wider mt-1">Source Status</div>
                </div>
              </div>
            )}

            {/* Source error breakdown panel */}
            {jobSearchStats && Object.keys(jobSearchStats.errors).length > 0 && (
              <div className="p-4 bg-amber-950/15 border border-amber-500/20 text-amber-300 rounded-xl flex flex-col gap-1 text-xs">
                <div className="font-bold flex items-center gap-1.5 mb-1 text-amber-400">
                  <Info className="w-4 h-4" />
                  Failed Ingestion Sources Breakdown:
                </div>
                {Object.entries(jobSearchStats.errors).map(([src, err]) => (
                  <div key={src}>
                    * <span className="font-semibold underline uppercase">{src}</span>: {err}
                  </div>
                ))}
              </div>
            )}

            {/* List and Board filtering */}
            <div className="flex flex-col md:flex-row gap-6">
              
              {/* Left filter side rail */}
              <div className="w-full md:w-56 flex-shrink-0 flex flex-col gap-4">
                {/* Sources Filter */}
                <div className="bg-neutral-900/40 border border-neutral-900 p-4 rounded-xl">
                  <h3 className="text-xs font-bold text-neutral-400 uppercase tracking-wider mb-3">Sources Filter</h3>
                  <div className="flex flex-wrap md:flex-col gap-2">
                    {["", "remoteok", "adzuna"].map((src) => (
                      <button
                        key={src}
                        onClick={async () => {
                          setJobFilterSource(src);
                          const filtered = await getJobs({
                            page: 1,
                            limit: 30,
                            source: src || undefined,
                            remote: searchRemote === "any" ? undefined : searchRemote,
                            title: searchQuery || undefined
                          });
                          setJobs(filtered);
                          setJobsPage(1);
                          setHasMoreJobs(filtered.length === 30);
                        }}
                        className={`px-3 py-1.5 text-xs font-semibold rounded-lg text-left transition-all cursor-pointer ${
                          jobFilterSource === src
                            ? "bg-indigo-600 text-white"
                            : "bg-neutral-950 hover:bg-neutral-850 text-neutral-400 hover:text-neutral-200"
                        }`}
                      >
                        {src === "" ? "All Sources" : src === "remoteok" ? "RemoteOK" : "Adzuna"}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Score & Recommendation Filters */}
                <div className="bg-neutral-900/40 border border-neutral-900 p-4 rounded-xl flex flex-col gap-4">
                  <div className="flex items-center gap-2 border-b border-neutral-950 pb-2">
                    <SlidersHorizontal className="w-3.5 h-3.5 text-indigo-400" />
                    <h3 className="text-xs font-bold text-neutral-400 uppercase tracking-wider">Suitability Filter</h3>
                  </div>

                  <div>
                    <label className="text-[10px] font-bold text-neutral-500 uppercase block mb-1">Sorting Order</label>
                    <select
                      value={jobsSortOrder}
                      onChange={(e) => setJobsSortOrder(e.target.value as any)}
                      className="w-full bg-neutral-950 border border-neutral-850 rounded-lg px-2 py-1.5 text-xs text-neutral-200"
                    >
                      <option value="score">Highest Match Score</option>
                      <option value="newest">Newest Posted</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-[10px] font-bold text-neutral-500 uppercase block mb-1">Min Match Score</label>
                    <select
                      value={matchFilterScore}
                      onChange={(e) => setMatchFilterScore(Number(e.target.value))}
                      className="w-full bg-neutral-950 border border-neutral-850 rounded-lg px-2 py-1.5 text-xs text-neutral-200"
                    >
                      <option value={0}>Show All Scores</option>
                      <option value={80}>80%+ (Strong Match)</option>
                      <option value={60}>60%+ (Match)</option>
                      <option value={45}>45%+ (Possible)</option>
                    </select>
                  </div>

                  <div>
                    <label className="text-[10px] font-bold text-neutral-500 uppercase block mb-1">Recommendation</label>
                    <select
                      value={matchFilterRec}
                      onChange={(e) => setMatchFilterRec(e.target.value)}
                      className="w-full bg-neutral-950 border border-neutral-850 rounded-lg px-2 py-1.5 text-xs text-neutral-200"
                    >
                      <option value="">Show All Classes</option>
                      <option value="STRONG_MATCH">Strong Match</option>
                      <option value="MATCH">Match</option>
                      <option value="POSSIBLE">Possible</option>
                      <option value="WEAK_MATCH">Weak Match</option>
                      <option value="REJECT">Reject</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Jobs feed card columns */}
              <div className="flex-1 flex flex-col gap-4">
                {filteredJobs.length === 0 ? (
                  <div className="bg-neutral-900/20 border border-neutral-900 p-12 text-center rounded-2xl flex flex-col items-center justify-center text-neutral-500">
                    <Search className="w-8 h-8 mb-2 text-neutral-600" />
                    <p className="text-sm font-semibold">No active job listings match your filters.</p>
                    <p className="text-xs text-neutral-600 mt-1">Adjust filters or search keywords above.</p>
                  </div>
                ) : (
                  <>
                    <div className="grid grid-cols-1 gap-4">
                      {filteredJobs.map((job) => {
                        const match = matches[job.job_id];
                        return (
                          <div 
                            key={job.job_id} 
                            onClick={() => handleViewJobDetails(job.job_id)}
                            className={`bg-neutral-900/40 border transition-all p-5 rounded-2xl cursor-pointer flex flex-col justify-between gap-4 ${
                              match 
                                ? `border-neutral-900 hover:border-neutral-850 hover:bg-neutral-900/50`
                                : "border-neutral-900 hover:border-neutral-800"
                            }`}
                          >
                            <div className="flex justify-between items-start gap-4">
                              <div>
                                <div className="flex items-center gap-2 flex-wrap">
                                  <h3 className="text-lg font-bold text-neutral-100 hover:text-indigo-400 transition-colors line-clamp-1">
                                    {job.title}
                                  </h3>
                                  
                                  {/* Score indicator */}
                                  {match ? (
                                    <span className={`px-2 py-0.5 rounded border text-[10px] font-bold ${getScoreColorClass(match.overall_score)}`}>
                                      {match.overall_score}% Match
                                    </span>
                                  ) : (
                                    profile && (
                                      <button
                                        onClick={(e) => handleSingleMatch(job.job_id, e)}
                                        disabled={isAnalyzingId === job.job_id}
                                        className="px-2 py-0.5 bg-indigo-500/10 hover:bg-indigo-500/20 border border-indigo-500/20 text-indigo-400 rounded text-[9px] font-extrabold uppercase tracking-wide cursor-pointer flex items-center gap-1"
                                      >
                                        {isAnalyzingId === job.job_id ? (
                                          <RefreshCw className="w-2.5 h-2.5 animate-spin" />
                                        ) : (
                                          <Gauge className="w-2.5 h-2.5" />
                                        )}
                                        Analyze
                                      </button>
                                    )
                                  )}
                                </div>
                                <p className="text-sm text-neutral-400 font-semibold mt-0.5">{job.company}</p>
                              </div>
                              
                              {/* Badges */}
                              <div className="flex items-center gap-2 flex-shrink-0">
                                {match && (
                                  <span className={`px-2 py-0.5 rounded border text-[9px] font-extrabold uppercase tracking-wider ${getRecommendationBadgeColor(match.recommendation)}`}>
                                    {match.recommendation.replace("_", " ")}
                                  </span>
                                )}
                                <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                                  job.remote_status === "remote" 
                                    ? "bg-emerald-500/10 text-emerald-400 border border-emerald-500/20" 
                                    : "bg-neutral-800 text-neutral-400 border border-neutral-750"
                                }`}>
                                  {job.remote_status === "remote" ? "Remote" : "Onsite"}
                                </span>
                                <span className="px-2.5 py-0.5 bg-neutral-950 border border-neutral-850 text-neutral-500 rounded-full text-[10px] uppercase font-bold tracking-wider">
                                  {job.source}
                                </span>
                              </div>
                            </div>
                            
                            <p className="text-xs text-neutral-500 line-clamp-2 leading-relaxed">
                              {job.description.replace(/<[^>]*>/g, " ")}
                            </p>
                            
                            <div className="flex items-center justify-between border-t border-neutral-950/60 pt-3 text-[10px] text-neutral-500 font-semibold">
                              <span className="flex items-center gap-1">
                                <Calendar className="w-3.5 h-3.5" />
                                Posted: {formatJobDate(job.posted_date)}
                              </span>
                              
                              <span className="flex items-center gap-0.5 text-indigo-400 hover:text-indigo-300">
                                View details
                                <ChevronRight className="w-3 h-3" />
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    
                    {/* Load more button */}
                    {hasMoreJobs && (
                      <button
                        onClick={loadMoreJobs}
                        className="w-full py-3 bg-neutral-900/30 hover:bg-neutral-900/50 border border-neutral-900 rounded-xl text-xs font-bold text-neutral-400 hover:text-neutral-200 transition-all cursor-pointer flex items-center justify-center gap-1.5"
                      >
                        Load More Listings
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </main>

      {/* DETAIL DRAWER SIDE PANEL */}
      {isDetailDrawerOpen && selectedJob && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-xs flex justify-end z-50">
          <div className="w-full max-w-2xl bg-neutral-950 border-l border-neutral-900 h-full overflow-y-auto flex flex-col justify-between shadow-2xl relative">
            
            {/* Drawer Header */}
            <div className="p-6 border-b border-neutral-900 flex items-center justify-between sticky top-0 bg-neutral-950 z-10">
              <div>
                <h2 className="text-xl font-bold text-neutral-100 line-clamp-1">{selectedJob.title}</h2>
                <p className="text-sm text-indigo-400 font-bold mt-0.5">{selectedJob.company}</p>
              </div>
              <button 
                onClick={() => setIsDetailDrawerOpen(false)}
                className="p-1.5 bg-neutral-900 hover:bg-neutral-855 rounded-lg text-neutral-400 hover:text-white transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="p-6 flex-1 flex flex-col gap-6">
              
              {/* Suitability Score Card */}
              <div className="bg-neutral-900/30 border border-neutral-900 rounded-xl p-5 flex flex-col gap-4 relative overflow-hidden">
                <div className="absolute top-0 right-0 w-24 h-24 bg-indigo-500/5 rounded-full blur-2xl"></div>
                
                <h3 className="text-xs font-bold text-neutral-400 uppercase tracking-wider border-b border-neutral-950 pb-2 flex items-center gap-2">
                  <Gauge className="w-4 h-4 text-indigo-400" />
                  Suitability Analysis
                </h3>

                {currentMatch ? (
                  <div className="flex flex-col gap-4">
                    <div className="flex items-center gap-4">
                      {/* Circle score indicator */}
                      <div className={`w-16 h-16 rounded-full border-4 flex flex-col items-center justify-center ${
                        currentMatch.overall_score >= 80 ? "border-emerald-500/30 text-emerald-400" :
                        currentMatch.overall_score >= 60 ? "border-teal-500/30 text-teal-400" :
                        currentMatch.overall_score >= 45 ? "border-amber-500/30 text-amber-400" : "border-rose-500/30 text-rose-400"
                      }`}>
                        <span className="text-lg font-black">{currentMatch.overall_score}%</span>
                      </div>
                      <div>
                        <span className={`px-2.5 py-0.5 rounded border text-[10px] font-extrabold uppercase tracking-wide ${getRecommendationBadgeColor(currentMatch.recommendation)}`}>
                          {currentMatch.recommendation.replace("_", " ")}
                        </span>
                        <p className="text-xs text-neutral-400 leading-relaxed mt-1.5 font-sans whitespace-pre-line">
                          {currentMatch.explanation}
                        </p>
                      </div>
                    </div>

                    {/* Breakdown sliders */}
                    <div className="grid grid-cols-2 gap-3 bg-neutral-950/40 p-3 rounded-lg border border-neutral-850/50 text-[10px] font-semibold text-neutral-400">
                      <div>
                        Skills Score: <span className="text-neutral-200 font-bold">{currentMatch.skill_score}/35</span>
                        <div className="w-full bg-neutral-900 h-1.5 rounded-full mt-1 overflow-hidden">
                          <div className="bg-indigo-500 h-full rounded-full" style={{ width: `${(currentMatch.skill_score/35)*100}%` }}></div>
                        </div>
                      </div>
                      <div>
                        Experience Fit: <span className="text-neutral-200 font-bold">{currentMatch.experience_score}/20</span>
                        <div className="w-full bg-neutral-900 h-1.5 rounded-full mt-1 overflow-hidden">
                          <div className="bg-indigo-500 h-full rounded-full" style={{ width: `${(currentMatch.experience_score/20)*100}%` }}></div>
                        </div>
                      </div>
                      <div>
                        Role Title: <span className="text-neutral-200 font-bold">{currentMatch.role_score}/15</span>
                        <div className="w-full bg-neutral-900 h-1.5 rounded-full mt-1 overflow-hidden">
                          <div className="bg-indigo-500 h-full rounded-full" style={{ width: `${(currentMatch.role_score/15)*100}%` }}></div>
                        </div>
                      </div>
                      <div>
                        Location / Remote: <span className="text-neutral-200 font-bold">{currentMatch.location_score}/15</span>
                        <div className="w-full bg-neutral-900 h-1.5 rounded-full mt-1 overflow-hidden">
                          <div className="bg-indigo-500 h-full rounded-full" style={{ width: `${(currentMatch.location_score/15)*100}%` }}></div>
                        </div>
                      </div>
                    </div>

                    {/* Matching and missing qualifications lists */}
                    <div className="flex flex-col gap-3">
                      {currentMatch.matching_skills.length > 0 && (
                        <div>
                          <label className="text-[10px] font-bold text-neutral-500 uppercase block mb-1">Matching Skills</label>
                          <div className="flex flex-wrap gap-1">
                            {currentMatch.matching_skills.map((s, i) => (
                              <span key={i} className="px-2 py-0.5 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded text-[10px] font-semibold">
                                {s}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                      
                      {currentMatch.missing_required_skills.length > 0 && (
                        <div>
                          <label className="text-[10px] font-bold text-neutral-500 uppercase block mb-1">Missing Required</label>
                          <div className="flex flex-wrap gap-1">
                            {currentMatch.missing_required_skills.map((s, i) => (
                              <span key={i} className="px-2 py-0.5 bg-rose-500/10 border border-rose-500/20 text-rose-400 rounded text-[10px] font-semibold">
                                {s}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {currentMatch.missing_preferred_skills.length > 0 && (
                        <div>
                          <label className="text-[10px] font-bold text-neutral-500 uppercase block mb-1">Missing Preferred</label>
                          <div className="flex flex-wrap gap-1">
                            {currentMatch.missing_preferred_skills.map((s, i) => (
                              <span key={i} className="px-2 py-0.5 bg-amber-500/10 border border-amber-500/20 text-amber-400 rounded text-[10px] font-semibold">
                                {s}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Concerns list */}
                      {currentMatch.concerns.length > 0 && (
                        <div className="mt-1">
                          <label className="text-[10px] font-bold text-rose-400 uppercase block mb-1">Concerns & Gaps</label>
                          <ul className="list-disc pl-4 text-xs text-rose-300 space-y-1">
                            {currentMatch.concerns.map((con, i) => (
                              <li key={i}>{con}</li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-4">
                    <p className="text-xs text-neutral-500">Suitability analysis not run yet.</p>
                    {profile && (
                      <button
                        onClick={(e) => handleSingleMatch(selectedJob.job_id, e as any)}
                        disabled={isAnalyzingId === selectedJob.job_id}
                        className="mt-3 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 border border-indigo-500/30 text-white font-semibold rounded-xl text-xs flex items-center justify-center gap-1.5 mx-auto cursor-pointer"
                      >
                        {isAnalyzingId === selectedJob.job_id ? (
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Gauge className="w-3.5 h-3.5" />
                        )}
                        Analyze Suitability
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Job Metadata Panel */}
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 bg-neutral-900/20 border border-neutral-900 p-4 rounded-xl">
                <div>
                  <span className="text-[10px] uppercase font-bold text-neutral-500">Location</span>
                  <p className="text-xs text-neutral-200 font-bold mt-0.5 flex items-center gap-1">
                    <MapPin className="w-3.5 h-3.5 text-indigo-400" />
                    {selectedJob.location}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-neutral-500">Remote Status</span>
                  <p className="text-xs text-neutral-200 font-bold mt-0.5 uppercase tracking-wide">
                    {selectedJob.remote_status}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-neutral-500">Salary Range</span>
                  <p className="text-xs text-neutral-200 font-bold mt-0.5 flex items-center gap-0.5">
                    <DollarSign className="w-3.5 h-3.5 text-indigo-400" />
                    {selectedJob.salary_min ? (
                      `${selectedJob.salary_min.toLocaleString()} ${selectedJob.salary_currency || 'USD'}`
                    ) : (
                      "Unspecified"
                    )}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-neutral-500">Source board</span>
                  <p className="text-xs text-neutral-200 font-bold mt-0.5 uppercase tracking-wide">
                    {selectedJob.source}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-neutral-500">Posted Date</span>
                  <p className="text-xs text-neutral-200 font-bold mt-0.5">
                    {formatJobDate(selectedJob.posted_date)}
                  </p>
                </div>
                <div>
                  <span className="text-[10px] uppercase font-bold text-neutral-500">First seen</span>
                  <p className="text-xs text-neutral-200 font-bold mt-0.5">
                    {formatJobDate(selectedJob.first_seen_at)}
                  </p>
                </div>
              </div>

              {/* Skills Tags */}
              {selectedJob.skills.length > 0 && (
                <div>
                  <h3 className="text-xs font-bold text-neutral-400 uppercase tracking-wider mb-2">Normalized Skills</h3>
                  <div className="flex flex-wrap gap-1.5">
                    {selectedJob.skills.map((skill, idx) => (
                      <span key={idx} className="px-2 py-1 bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 rounded-lg text-xs font-semibold">
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Description Body */}
              <div>
                <h3 className="text-xs font-bold text-neutral-400 uppercase tracking-wider mb-2">Job Description</h3>
                <div 
                  className="text-xs text-neutral-300 leading-relaxed font-sans space-y-3 whitespace-pre-line"
                  dangerouslySetInnerHTML={{ __html: selectedJob.description }}
                />
              </div>
            </div>

            {/* Drawer Actions */}
            <div className="p-6 border-t border-neutral-900 bg-neutral-950 sticky bottom-0 z-10 flex items-center justify-end gap-3">
              <a
                href={selectedJob.application_url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 active:bg-indigo-700 font-semibold rounded-xl text-sm flex items-center gap-2 cursor-pointer transition-all border border-indigo-500/30 text-white"
              >
                Apply for Position
                <ExternalLink className="w-4 h-4" />
              </a>
              <button
                onClick={() => setIsDetailDrawerOpen(false)}
                className="px-6 py-3 bg-neutral-900 hover:bg-neutral-850 border border-neutral-850 rounded-xl text-sm text-neutral-400 hover:text-neutral-200 transition-colors"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer className="border-t border-neutral-900 bg-neutral-950/40 px-6 py-4 flex items-center justify-between text-xs text-neutral-500 mt-12">
        <div>&copy; 2026 JobHunter AI. Local-first privacy mode enabled.</div>
        <div className="flex gap-4">
          <a href="#" className="hover:text-neutral-400 transition-colors">Privacy Policy</a>
          <a href="#" className="hover:text-neutral-400 transition-colors">Documentation</a>
        </div>
      </footer>
    </div>
  );
}
