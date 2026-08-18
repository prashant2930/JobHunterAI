import React, { useState, useEffect } from 'react';
import {
  X,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  UserCheck,
  Edit3,
  ExternalLink,
  ShieldCheck,
  FileText,
  Loader2
} from 'lucide-react';
import {
  ApplicationResponse,
  ApplicationFormField,
  approveApplication
} from '../services/api';

interface ApplicationReviewModalProps {
  isOpen: boolean;
  onClose: () => void;
  application: ApplicationResponse | null;
  jobTitle: string;
  companyName: string;
  onApproveSuccess?: (updated: ApplicationResponse) => void;
}

export const ApplicationReviewModal: React.FC<ApplicationReviewModalProps> = ({
  isOpen,
  onClose,
  application,
  jobTitle,
  companyName,
  onApproveSuccess
}) => {
  const [editedFields, setEditedFields] = useState<Record<string, string>>({});
  const [currentApp, setCurrentApp] = useState<ApplicationResponse | null>(null);
  const [isApproving, setIsApproving] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    setCurrentApp(application);
    if (application) {
      const initialMap: Record<string, string> = {};
      application.fields.forEach(f => {
        initialMap[f.id] = f.current_value || f.suggested_value || '';
      });
      setEditedFields(initialMap);
    }
  }, [application]);

  if (!isOpen || !currentApp) return null;

  const handleValueChange = (fieldId: string, val: string) => {
    setEditedFields(prev => ({ ...prev, [fieldId]: val }));
  };

  const handleApprove = async () => {
    setIsApproving(true);
    setErrorMsg(null);
    try {
      const updates = Object.entries(editedFields).map(([fieldId, val]) => ({
        field_id: fieldId,
        current_value: val as string,
        requires_review: false
      }));


      const updated = await approveApplication(currentApp.id, updates);
      setCurrentApp(updated);
      if (onApproveSuccess) {
        onApproveSuccess(updated);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to approve application.');
    } finally {
      setIsApproving(false);
    }
  };

  const isApproved = currentApp.status === 'APPROVED';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fadeIn">
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden border border-slate-200">
        
        {/* Modal Header */}
        <div className="px-6 py-5 border-b border-slate-100 bg-slate-50 flex items-center justify-between">
          <div>
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-indigo-600" />
              <h2 className="text-xl font-bold text-slate-900">Application Intelligence Review</h2>
              <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-slate-200 text-slate-700 capitalize">
                {currentApp.platform}
              </span>
              {isApproved ? (
                <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-emerald-100 text-emerald-800 flex items-center gap-1">
                  <CheckCircle2 className="w-3.5 h-3.5" /> APPROVED
                </span>
              ) : (
                <span className="px-2.5 py-0.5 text-xs font-semibold rounded-full bg-amber-100 text-amber-800 flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5" /> REVIEW REQUIRED
                </span>
              )}
            </div>
            <p className="text-sm text-slate-500 mt-1">
              Target Position: <span className="font-semibold text-slate-700">{jobTitle}</span> at{' '}
              <span className="font-semibold text-slate-700">{companyName}</span>
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {errorMsg && (
            <div className="p-4 bg-red-50 text-red-700 text-sm rounded-xl border border-red-200 flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Form Fields Analysis Section */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-base font-semibold text-slate-900">
                Detected Application Form Fields ({currentApp.fields.length})
              </h3>
              {currentApp.application_url && (
                <a
                  href={currentApp.application_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-xs text-indigo-600 hover:text-indigo-800 font-medium inline-flex items-center gap-1"
                >
                  View External Job Page <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </div>

            <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl overflow-hidden bg-white">
              {currentApp.fields.map((field: ApplicationFormField) => {
                const val = editedFields[field.id] ?? '';
                const isProfile = field.source === 'candidate_profile';
                const isLLM = field.source === 'llm_generated';
                const isUser = field.source === 'user_override';

                return (
                  <div key={field.id} className="p-4 space-y-2 hover:bg-slate-50/50 transition-colors">
                    <div className="flex items-center justify-between gap-4">
                      <label className="text-sm font-medium text-slate-900 flex items-center gap-1.5">
                        <span>{field.label}</span>
                        {field.required && <span className="text-red-500 font-bold">*</span>}
                        <span className="text-[10px] uppercase tracking-wider text-slate-400 font-normal px-1.5 py-0.5 bg-slate-100 rounded">
                          {field.field_type}
                        </span>
                      </label>

                      {/* Badges */}
                      <div className="flex items-center gap-2 shrink-0">
                        {isProfile && (
                          <span className="px-2 py-0.5 text-xs font-medium bg-blue-50 text-blue-700 rounded-md border border-blue-200 flex items-center gap-1">
                            <UserCheck className="w-3 h-3" /> Candidate Profile
                          </span>
                        )}
                        {isLLM && (
                          <span className="px-2 py-0.5 text-xs font-medium bg-purple-50 text-purple-700 rounded-md border border-purple-200 flex items-center gap-1">
                            <Sparkles className="w-3 h-3" /> AI Generated
                          </span>
                        )}
                        {isUser && (
                          <span className="px-2 py-0.5 text-xs font-medium bg-emerald-50 text-emerald-700 rounded-md border border-emerald-200 flex items-center gap-1">
                            <Edit3 className="w-3 h-3" /> User Edit
                          </span>
                        )}
                        {!isProfile && !isLLM && !isUser && (
                          <span className="px-2 py-0.5 text-xs font-medium bg-slate-100 text-slate-600 rounded-md">
                            Unknown
                          </span>
                        )}

                        <span className="text-xs font-mono text-slate-500">
                          {Math.round((field.confidence || 0) * 100)}%
                        </span>

                        {field.requires_review && !isApproved && (
                          <span className="px-2 py-0.5 text-xs font-medium bg-amber-50 text-amber-700 rounded-md border border-amber-200 flex items-center gap-1">
                            <AlertTriangle className="w-3 h-3" /> Review
                          </span>
                        )}
                      </div>
                    </div>

                    {/* Field Inputs */}
                    {field.field_type === 'TEXTAREA' ? (
                      <textarea
                        value={val}
                        onChange={e => handleValueChange(field.id, e.target.value)}
                        rows={3}
                        placeholder={field.requires_review ? 'Review / enter answer...' : ''}
                        className="w-full text-sm p-2.5 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                      />
                    ) : field.field_type === 'SELECT' && field.options && field.options.length > 0 ? (
                      <select
                        value={val}
                        onChange={e => handleValueChange(field.id, e.target.value)}
                        className="w-full text-sm p-2.5 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all bg-white"
                      >
                        <option value="">-- Select option --</option>
                        {field.options.map((opt, i) => (
                          <option key={i} value={opt}>
                            {opt}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type={field.field_type === 'EMAIL' ? 'email' : 'text'}
                        value={val}
                        onChange={e => handleValueChange(field.id, e.target.value)}
                        placeholder={field.requires_review ? 'Review / enter value...' : ''}
                        className="w-full text-sm p-2.5 rounded-lg border border-slate-200 focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 outline-none transition-all"
                      />
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-slate-100 bg-slate-50 flex items-center justify-between">
          <p className="text-xs text-slate-500 flex items-center gap-1.5">
            <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0" />
            No automatic external web submission will be performed. Approval saves package status.
          </p>

          <div className="flex items-center gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-slate-700 bg-white border border-slate-200 rounded-xl hover:bg-slate-100 transition-colors"
            >
              Close
            </button>
            <button
              onClick={handleApprove}
              disabled={isApproving}
              className="px-5 py-2 text-sm font-medium text-white bg-indigo-600 rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition-colors flex items-center gap-2 shadow-sm"
            >
              {isApproving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Approving...
                </>
              ) : isApproved ? (
                <>
                  <CheckCircle2 className="w-4 h-4" /> Package Approved
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" /> Approve Application Package
                </>
              )}
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
