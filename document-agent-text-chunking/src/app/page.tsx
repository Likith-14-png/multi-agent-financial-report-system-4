import { db } from "@/db";
import { documents, chunks } from "@/db/schema";
import { desc, count } from "drizzle-orm";
import { UploadDocumentForm } from "@/components/upload-form";
import { DocumentList } from "@/components/document-list";
import { PythonCodeSnippet } from "@/components/python-code";
import { FileText, Cpu, Database, BarChart3 } from "lucide-react";

export default async function Home() {
  const docs = await db.query.documents.findMany({
    orderBy: [desc(documents.createdAt)],
  });

  const stats = await db.select({ value: count() }).from(chunks);
  const totalChunks = stats[0]?.value || 0;

  return (
    <main className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-slate-200 py-6">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <div className="bg-indigo-600 p-2 rounded-lg">
                <Cpu className="h-6 w-6 text-white" />
              </div>
              <div>
                <h1 className="text-2xl font-bold text-slate-900">Multi-Agent Financial Research System</h1>
                <p className="text-sm text-slate-500 text-indigo-600 font-medium">Document Extraction & Chunking Agent</p>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-right">
                <p className="text-sm font-medium text-slate-500 uppercase tracking-wider">Total Chunks</p>
                <p className="text-2xl font-bold text-slate-900">{totalChunks}</p>
              </div>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Left Column: Upload and Stats */}
          <div className="lg:col-span-1 space-y-8">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center">
                <FileText className="h-5 w-5 mr-2 text-indigo-500" />
                Ingest Document
              </h2>
              <UploadDocumentForm />
              <div className="mt-4 p-3 bg-blue-50 rounded-lg border border-blue-100">
                <p className="text-xs text-blue-700 leading-relaxed">
                  Supported formats: PDF, TXT. Documents are automatically extracted and split into chunks for analysis.
                </p>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
              <h2 className="text-lg font-semibold text-slate-900 mb-4 flex items-center">
                <BarChart3 className="h-5 w-5 mr-2 text-indigo-500" />
                Agent Status
              </h2>
              <div className="space-y-4">
                <div className="flex justify-between items-center text-sm">
                  <span className="text-slate-500">Document Agent</span>
                  <span className="px-2 py-1 rounded-full bg-green-100 text-green-700 text-xs font-medium">Active</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-slate-500">Research Agent</span>
                  <span className="px-2 py-1 rounded-full bg-slate-100 text-slate-400 text-xs font-medium">Idle</span>
                </div>
                <div className="flex justify-between items-center text-sm">
                  <span className="text-slate-500">Summary Agent</span>
                  <span className="px-2 py-1 rounded-full bg-slate-100 text-slate-400 text-xs font-medium">Idle</span>
                </div>
              </div>
            </div>
          </div>

          {/* Right Column: List and Code */}
          <div className="lg:col-span-2 space-y-8">
            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <div className="px-6 py-4 border-b border-slate-200 bg-slate-50/50">
                <h2 className="text-lg font-semibold text-slate-900 flex items-center">
                  <Database className="h-5 w-5 mr-2 text-indigo-500" />
                  Processed Documents
                </h2>
              </div>
              <DocumentList initialDocuments={docs} />
            </div>

            <div className="bg-slate-900 rounded-xl shadow-sm border border-slate-800 p-6 overflow-hidden">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-semibold text-white">Document Agent Implementation (Python)</h2>
                <div className="flex space-x-1">
                  <div className="w-3 h-3 rounded-full bg-red-500"></div>
                  <div className="w-3 h-3 rounded-full bg-yellow-500"></div>
                  <div className="w-3 h-3 rounded-full bg-green-500"></div>
                </div>
              </div>
              <PythonCodeSnippet />
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
