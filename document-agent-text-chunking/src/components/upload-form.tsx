'use client';

import { useState } from 'react';
import { uploadDocument } from '@/app/actions';
import { Upload, Loader2, CheckCircle2, AlertCircle } from 'lucide-react';

export function UploadDocumentForm() {
  const [isUploading, setIsUploading] = useState(false);
  const [result, setResult] = useState<{ success?: boolean; error?: string } | null>(null);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setIsUploading(true);
    setResult(null);

    const formData = new FormData(e.currentTarget);
    const res = await uploadDocument(formData);
    
    setResult(res);
    setIsUploading(false);
    if (res.success) {
      (e.target as HTMLFormElement).reset();
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="relative border-2 border-dashed border-slate-300 rounded-lg p-6 hover:border-indigo-400 transition-colors group cursor-pointer">
        <input
          type="file"
          name="file"
          accept=".pdf,.txt"
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          required
          onChange={() => setResult(null)}
        />
        <div className="text-center">
          <Upload className="mx-auto h-10 w-10 text-slate-400 group-hover:text-indigo-500 transition-colors" />
          <p className="mt-2 text-sm font-medium text-slate-700">Click or drag file to upload</p>
          <p className="mt-1 text-xs text-slate-500">PDF or Text (max 10MB)</p>
        </div>
      </div>
      
      <button
        type="submit"
        disabled={isUploading}
        className="w-full bg-indigo-600 text-white py-2 px-4 rounded-lg font-medium hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center"
      >
        {isUploading ? (
          <>
            <Loader2 className="animate-spin h-4 w-4 mr-2" />
            Processing Agent...
          </>
        ) : (
          'Run Document Agent'
        )}
      </button>

      {result?.success && (
        <div className="flex items-center p-3 bg-green-50 text-green-700 rounded-lg text-sm border border-green-100 animate-in fade-in duration-300">
          <CheckCircle2 className="h-4 w-4 mr-2" />
          Document processed and chunked successfully!
        </div>
      )}

      {result?.error && (
        <div className="flex items-center p-3 bg-red-50 text-red-700 rounded-lg text-sm border border-red-100 animate-in fade-in duration-300">
          <AlertCircle className="h-4 w-4 mr-2" />
          {result.error}
        </div>
      )}
    </form>
  );
}
