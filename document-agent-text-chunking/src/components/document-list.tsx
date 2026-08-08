import { FileText, Clock, File } from 'lucide-react';
import { formatDistanceToNow } from 'date-fns';

type Document = {
  id: string;
  name: string;
  type: string;
  status: string;
  createdAt: Date;
};

export function DocumentList({ initialDocuments }: { initialDocuments: Document[] }) {
  if (initialDocuments.length === 0) {
    return (
      <div className="p-12 text-center">
        <div className="bg-slate-100 rounded-full h-12 w-12 flex items-center justify-center mx-auto mb-4">
          <File className="h-6 w-6 text-slate-400" />
        </div>
        <p className="text-slate-500 text-sm">No documents processed yet.</p>
      </div>
    );
  }

  return (
    <div className="divide-y divide-slate-100">
      {initialDocuments.map((doc) => (
        <div key={doc.id} className="p-4 hover:bg-slate-50 transition-colors flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="bg-slate-100 p-2 rounded-lg">
              <FileText className="h-5 w-5 text-slate-600" />
            </div>
            <div>
              <h3 className="text-sm font-medium text-slate-900 truncate max-w-[200px] md:max-w-md">
                {doc.name}
              </h3>
              <div className="flex items-center text-xs text-slate-500 mt-0.5 space-x-2">
                <span className="flex items-center">
                  <Clock className="h-3 w-3 mr-1" />
                  {formatDistanceToNow(doc.createdAt, { addSuffix: true })}
                </span>
                <span>•</span>
                <span>{doc.type}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center space-x-3">
            <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider ${
              doc.status === 'processed' ? 'bg-green-100 text-green-700' : 
              doc.status === 'failed' ? 'bg-red-100 text-red-700' : 
              'bg-blue-100 text-blue-700 animate-pulse'
            }`}>
              {doc.status}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
