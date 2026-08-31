import React, { useEffect, useState, useRef } from 'react';
import {
  Search,
  Send,
  Bookmark,
  FileText,
  Copy,
  Check,
  RotateCcw,
  ExternalLink,
  MessageSquare,
  Layers,
} from 'lucide-react';
import { useApp } from '../lib/AppContext';
import { api, ApiError } from '../lib/api';
import { CitationSource, ResearchChatMessage } from '../lib/types';
import { AnalysisHeader } from '../components/AnalysisHeader';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { Badge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';
import { ErrorBanner } from '../components/ui/ErrorBanner';
import { CardSkeleton } from '../components/ui/Skeleton';
import { MarkdownRenderer } from '../components/ui/MarkdownRenderer';

const SUGGESTED_PROMPTS = [
  'What drove revenue and operating performance in this filing?',
  'Why did operating margin or net income change?',
  'What are the primary financial, liquidity, and operational risks?',
  'How did free cash flow and balance sheet debt evolve?',
  'What are the key items noted in the auditor report or footnotes?',
];

export function ResearchPage() {
  const { activeSessionId, activeCompany, activeYear, setActiveView, openEvidenceDrawer } = useApp();

  const [messages, setMessages] = useState<ResearchChatMessage[]>([]);
  const [inputQuestion, setInputQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isInitialLoading, setIsInitialLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [activeEvidencePool, setActiveEvidencePool] = useState<CitationSource[]>([]);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const chatBottomRef = useRef<HTMLDivElement>(null);

  // Load initial research synthesis on mount
  useEffect(() => {
    if (!activeSessionId) return;

    const loadInitialResearch = async () => {
      setIsInitialLoading(true);
      setErrorMessage(null);
      try {
        const data = await api.getResearch(activeSessionId);
        if (data.answer || data.summary) {
          const initialMsg: ResearchChatMessage = {
            id: 'init-1',
            sender: 'agent',
            text: data.answer || data.summary || '',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            sources: data.sources || [],
            modelUsed: data.model_used || 'Gemini / Vector Semantic Retrieval',
          };
          setMessages([initialMsg]);
          setActiveEvidencePool(data.sources || []);
        }
      } catch (err) {
        if (err instanceof ApiError) {
          setErrorMessage(err.detail || err.message);
        } else {
          setErrorMessage('Could not load initial research findings.');
        }
      } finally {
        setIsInitialLoading(false);
      }
    };

    loadInitialResearch();
  }, [activeSessionId]);

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isLoading]);

  if (!activeSessionId) {
    return (
      <div className="max-w-4xl mx-auto py-12">
        <EmptyState
          icon={Search}
          title="No Active Filing for Research"
          description="Upload a filing in the Workspace to initiate grounded financial question answering with full citation evidence."
          actionLabel="Go to Workspace"
          onAction={() => setActiveView('workspace')}
        />
      </div>
    );
  }

  const handleSendQuestion = async (questionText: string) => {
    const q = questionText.trim();
    if (!q || !activeSessionId || isLoading) return;

    setErrorMessage(null);

    // Append user message
    const userMsg: ResearchChatMessage = {
      id: `user-${Date.now()}`,
      sender: 'user',
      text: q,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuestion('');
    setIsLoading(true);

    try {
      const response = await api.queryResearch(activeSessionId, q);

      const agentMsg: ResearchChatMessage = {
        id: `agent-${Date.now()}`,
        sender: 'agent',
        text: response.answer || response.summary || 'No answer generated for this inquiry.',
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        sources: response.sources || [],
        modelUsed: response.model_used || 'ChromaDB Grounded Retrieval',
      };

      setMessages((prev) => [...prev, agentMsg]);

      // Update right-side evidence pool
      if (response.sources && response.sources.length > 0) {
        setActiveEvidencePool(response.sources);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setErrorMessage(err.detail || err.message);
      } else {
        setErrorMessage('Failed to execute research query. Verify the backend connection.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleCopyMessage = (id: string, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const handleResetThread = () => {
    setMessages([]);
    setActiveEvidencePool([]);
    // Reload initial research
    api.getResearch(activeSessionId).then((data) => {
      if (data.answer || data.summary) {
        setMessages([
          {
            id: 'init-reset',
            sender: 'agent',
            text: data.answer || data.summary || '',
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
            sources: data.sources || [],
            modelUsed: data.model_used || 'Vector Retrieval',
          },
        ]);
        setActiveEvidencePool(data.sources || []);
      }
    });
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6 pb-12">
      <AnalysisHeader
        onAskQuestion={() => {}}
        onCompare={() => setActiveView('comparison')}
      />

      {errorMessage && (
        <ErrorBanner
          title="Research Console Notice"
          message={errorMessage}
          onRetry={() => inputQuestion && handleSendQuestion(inputQuestion)}
        />
      )}

      {/* Main Grid: Chat Console + Desktop Evidence Sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left 2 Cols: Research Conversation */}
        <div className="lg:col-span-2 space-y-4 flex flex-col h-[740px]">
          <Card className="flex-1 border-slate-800 bg-slate-900/90 flex flex-col overflow-hidden">
            {/* Console Header */}
            <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/60 shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400">
                  <Search className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-100">Analyst Research Console</h3>
                  <p className="text-[11px] text-slate-400">
                    Grounded in {activeCompany || 'uploaded filing'} (FY {activeYear})
                  </p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={handleResetThread}
                  leftIcon={<RotateCcw className="w-3 h-3" />}
                  title="Reset conversation to baseline synthesis"
                >
                  Reset
                </Button>
              </div>
            </div>

            {/* Conversation Stream */}
            <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-6">
              {isInitialLoading ? (
                <div className="space-y-4">
                  <CardSkeleton lines={4} />
                  <CardSkeleton lines={3} />
                </div>
              ) : messages.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center p-8">
                  <MessageSquare className="w-10 h-10 text-slate-600 mb-3" />
                  <h4 className="text-sm font-semibold text-slate-300">Ready for Analyst Research</h4>
                  <p className="text-xs text-slate-500 max-w-sm mt-1">
                    Ask questions regarding revenue drivers, capital expenditures, risk footnotes, or margins.
                  </p>
                </div>
              ) : (
                messages.map((msg) => {
                  const isUser = msg.sender === 'user';
                  return (
                    <div
                      key={msg.id}
                      className={`flex flex-col ${isUser ? 'items-end' : 'items-start'} space-y-1.5`}
                    >
                      <div className="flex items-center gap-2 px-1 text-[11px] text-slate-500 font-mono">
                        <span>{isUser ? 'Analyst' : 'FinSight Agent'}</span>
                        <span>·</span>
                        <span>{msg.timestamp}</span>
                        {msg.modelUsed && (
                          <span className="hidden sm:inline text-slate-400">({msg.modelUsed})</span>
                        )}
                      </div>

                      <div
                        className={`rounded-2xl p-4 sm:p-5 max-w-[92%] sm:max-w-[85%] text-sm ${
                          isUser
                            ? 'bg-cyan-600 text-white rounded-tr-sm shadow-md font-medium'
                            : 'bg-slate-950 border border-slate-800 text-slate-200 rounded-tl-sm shadow-sm'
                        }`}
                      >
                        {isUser ? (
                          <p className="whitespace-pre-wrap">{msg.text}</p>
                        ) : (
                          <div className="space-y-3">
                            <MarkdownRenderer
                              content={msg.text}
                              sources={msg.sources || []}
                              onCitationClick={openEvidenceDrawer}
                            />

                            {/* Message Actions */}
                            <div className="pt-2 border-t border-slate-800/80 flex items-center justify-between text-xs">
                              <span className="text-[11px] text-slate-400 font-mono">
                                {msg.sources && msg.sources.length > 0
                                  ? `${msg.sources.length} grounding citation(s)`
                                  : 'Grounded retrieval'}
                              </span>

                              <button
                                onClick={() => handleCopyMessage(msg.id, msg.text)}
                                className="flex items-center gap-1 text-[11px] text-slate-400 hover:text-slate-200 transition-colors"
                              >
                                {copiedId === msg.id ? (
                                  <>
                                    <Check className="w-3 h-3 text-emerald-400" />
                                    <span className="text-emerald-400">Copied</span>
                                  </>
                                ) : (
                                  <>
                                    <Copy className="w-3 h-3" />
                                    <span>Copy</span>
                                  </>
                                )}
                              </button>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })
              )}

              {isLoading && (
                <div className="flex items-start space-y-1.5">
                  <div className="rounded-2xl rounded-tl-sm p-4 bg-slate-950 border border-cyan-500/30 text-xs text-cyan-300 flex items-center gap-3">
                    <Layers className="w-4 h-4 animate-spin text-cyan-400" />
                    <span>Querying ChromaDB vector space & reasoning evidence...</span>
                  </div>
                </div>
              )}

              <div ref={chatBottomRef} />
            </div>

            {/* Suggested Question Chips */}
            <div className="p-3 bg-slate-950/80 border-t border-slate-800 shrink-0 overflow-x-auto">
              <div className="flex items-center gap-2 min-w-max">
                <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 mr-1">
                  Prompts:
                </span>
                {SUGGESTED_PROMPTS.map((prompt, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSendQuestion(prompt)}
                    disabled={isLoading}
                    className="px-2.5 py-1 rounded-lg bg-slate-900 border border-slate-800 hover:border-cyan-500/50 hover:bg-slate-850 text-[11px] text-slate-300 transition-all cursor-pointer truncate max-w-xs"
                  >
                    {prompt}
                  </button>
                ))}
              </div>
            </div>

            {/* Input Bar */}
            <div className="p-3.5 bg-slate-900 border-t border-slate-800 shrink-0">
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSendQuestion(inputQuestion);
                }}
                className="flex items-center gap-2"
              >
                <input
                  type="text"
                  placeholder="Ask a question grounded in this filing (e.g. revenue, risks, margins)..."
                  value={inputQuestion}
                  onChange={(e) => setInputQuestion(e.target.value)}
                  disabled={isLoading}
                  className="flex-1 px-4 py-2.5 rounded-xl bg-slate-950 border border-slate-800 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 font-medium"
                />
                <Button
                  type="submit"
                  variant="primary"
                  size="md"
                  disabled={!inputQuestion.trim() || isLoading}
                  isLoading={isLoading}
                  leftIcon={<Send className="w-4 h-4" />}
                >
                  Query
                </Button>
              </form>
            </div>
          </Card>
        </div>

        {/* Right 1 Col: Evidence & Citations Explorer Panel */}
        <div className="space-y-4">
          <Card className="border-slate-800 bg-slate-900/90 h-[740px] flex flex-col">
            <CardHeader className="p-4 border-b border-slate-800 bg-slate-950/60 shrink-0">
              <div className="flex items-center justify-between">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Bookmark className="w-4 h-4 text-cyan-400" />
                  Citation Evidence Explorer
                </CardTitle>
                <Badge variant="primary" size="sm">
                  {activeEvidencePool.length} Sources
                </Badge>
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5">
                Retrieved chunks grounded in active response
              </p>
            </CardHeader>

            <CardContent className="p-4 flex-1 overflow-y-auto space-y-3">
              {activeEvidencePool.length > 0 ? (
                activeEvidencePool.map((src, idx) => (
                  <div
                    key={idx}
                    onClick={() => openEvidenceDrawer(src)}
                    className="p-3.5 rounded-xl bg-slate-950 border border-slate-800/80 hover:border-cyan-500/60 hover:bg-slate-950/90 transition-all cursor-pointer group space-y-2"
                  >
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold text-slate-200 flex items-center gap-1.5">
                        <FileText className="w-3.5 h-3.5 text-cyan-400" />
                        {src.source_file || 'Filing Document'}
                      </span>
                      {src.page && (
                        <Badge variant="outline" size="sm" className="font-mono">
                          Page {src.page}
                        </Badge>
                      )}
                    </div>

                    <p className="text-xs text-slate-400 line-clamp-3 font-mono leading-relaxed bg-slate-900/60 p-2 rounded-lg border border-slate-800/50">
                      {src.snippet || 'Evidence chunk indexed.'}
                    </p>

                    <div className="flex items-center justify-between text-[10px] text-slate-500 pt-1">
                      <span className="truncate max-w-[150px]">
                        {src.section || `Chunk ${src.chunk_id ? src.chunk_id.slice(0, 8) : idx + 1}`}
                      </span>
                      <span className="text-cyan-400 group-hover:text-cyan-300 font-medium flex items-center gap-1">
                        Inspect <ExternalLink className="w-2.5 h-2.5" />
                      </span>
                    </div>
                  </div>
                ))
              ) : (
                <div className="h-full flex flex-col items-center justify-center text-center p-6">
                  <Bookmark className="w-8 h-8 text-slate-700 mb-2" />
                  <p className="text-xs font-semibold text-slate-400">No active citations</p>
                  <p className="text-[11px] text-slate-500 mt-1">
                    Execute a research query to load grounded vector evidence snippets.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
