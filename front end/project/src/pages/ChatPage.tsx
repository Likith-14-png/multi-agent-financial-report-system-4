import { useState, useRef, useEffect } from 'react';
import { Card, Badge } from '@/components/ui';
import { Icon } from '@/components/Icon';
import { INITIAL_CHAT, SUGGESTED_PROMPTS } from '@/lib/mockData';
import type { ChatMessage } from '@/lib/types';

const SAMPLE_RESPONSES: Record<string, { content: string; citations: ChatMessage['citations'] }> = {
  compare: {
    content:
      "Based on the 10-K filings I analyzed, here's how Microsoft and Apple compare across key financial metrics:\n\n• **Revenue**: Apple leads with $383.3B vs Microsoft's $245.1B, though Microsoft is growing faster (16% vs -2.8% YoY).\n• **Profitability**: Microsoft's operating margin of 44.7% significantly outpaces Apple's 30.0%, reflecting Azure's high-margin software model.\n• **Debt Position**: Apple carries $111.1B in debt vs Microsoft's $97.4B, but Apple's larger asset base gives it a lower debt-to-asset ratio.\n• **Cash Flow**: Both generate robust cash — Microsoft $118.5B, Apple $110.5B.\n\n**Key takeaway**: Microsoft offers stronger margin expansion and cloud growth, while Apple has higher absolute revenue but faces iPhone-driven headwinds.",
    citations: [
      { label: 'Microsoft 10-K FY24', source: 'MSFT_10K_2024.pdf', page: 42 },
      { label: 'Apple 10-K FY24', source: 'AAPL_10K_2024.pdf', page: 38 },
    ],
  },
  revenue: {
    content:
      "Revenue growth analysis across the analyzed companies:\n\n• **Microsoft**: $245.1B (+16.2% YoY) — driven by Azure cloud and AI services\n• **Apple**: $383.3B (-2.8% YoY) — iPhone softness in key markets\n• **Alphabet**: $307.4B (+8.9% YoY) — Search and YouTube ad recovery\n• **Amazon**: $574.8B (+11.8% YoY) — AWS and retail strength\n\nMicrosoft shows the strongest growth trajectory, while Apple is the only company with declining revenue in the cohort.",
    citations: [{ label: 'Big Tech Q4 Comparison', source: 'Comparison_Agent_Report', page: 7 }],
  },
  risk: {
    content:
      "I've identified several financial risks from the analyzed filings:\n\n**Critical**: Amazon's debt-to-equity ratio of 2.14 has risen 18% YoY, increasing leverage exposure.\n\n**High**: Apple's revenue declined 2.8% year-over-year, primarily from iPhone softness. Alphabet showed negative free cash flow in the latest quarter due to a CapEx surge.\n\n**Medium**: Amazon's auditor flagged revenue recognition timing for AWS contracts. Alphabet faces ongoing antitrust proceedings with $3.1B in contingent liabilities.\n\nI recommend monitoring Amazon's liquidity ratio (currently 0.97) closely — it has fallen below the 1.0 safety threshold.",
    citations: [
      { label: 'Red Flag Agent Report', source: 'RedFlag_Agent', page: 3 },
      { label: 'Amazon 10-K FY24', source: 'AMZN_10K_2024.pdf', page: 55 },
    ],
  },
  investment: {
    content:
      "**Investment Summary — Big Tech Cohort**\n\n**Microsoft (Bullish)**: Strongest margin profile (44.7% operating margin) with accelerating cloud and AI revenue. Low debt-to-asset ratio. Azure growth runway remains significant.\n\n**Apple (Neutral)**: High absolute revenue and cash flow but declining growth. iPhone dependency remains a structural risk. Strong buyback program supports EPS.\n\n**Alphabet (Bullish)**: Solid revenue growth with improving ad market. Watch antitrust overhang and CapEx intensity impacting free cash flow.\n\n**Amazon (Cautious)**: Revenue growth is strong but rising leverage and liquidity concerns warrant caution. AWS remains the profit engine.\n\n**Overall**: Microsoft and Alphabet present the most favorable risk-adjusted profiles in this cohort.",
    citations: [{ label: 'Report Agent Summary', source: 'Report_Agent', page: 1 }],
  },
};

function getResponse(prompt: string): { content: string; citations: ChatMessage['citations'] } {
  const p = prompt.toLowerCase();
  if (p.includes('compare') || p.includes('microsoft') && p.includes('apple')) return SAMPLE_RESPONSES.compare;
  if (p.includes('revenue') || p.includes('growth')) return SAMPLE_RESPONSES.revenue;
  if (p.includes('risk') || p.includes('flag') || p.includes('debt')) return SAMPLE_RESPONSES.risk;
  if (p.includes('investment') || p.includes('summary') || p.includes('report')) return SAMPLE_RESPONSES.investment;
  return {
    content: "I've analyzed the uploaded filings and can help with that. Try asking me to compare companies, show revenue trends, identify financial risks, or generate an investment summary. I'll ground every answer in the source documents with citations.",
    citations: [],
  };
}

export function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_CHAT);
  const [input, setInput] = useState('');
  const [typing, setTyping] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages, typing]);

  const send = (text: string) => {
    if (!text.trim()) return;
    const userMsg: ChatMessage = {
      id: `m${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }),
    };
    setMessages((m) => [...m, userMsg]);
    setInput('');
    setTyping(true);
    setTimeout(() => {
      const res = getResponse(text);
      const aiMsg: ChatMessage = {
        id: `m${Date.now() + 1}`,
        role: 'assistant',
        content: res.content,
        timestamp: new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }),
        citations: res.citations,
      };
      setMessages((m) => [...m, aiMsg]);
      setTyping(false);
    }, 1200);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h1 className="text-2xl font-bold text-primary tracking-tight">AI Research Chat</h1>
          <p className="text-sm text-secondary mt-1 flex items-center gap-2">
            <span className="relative flex w-2 h-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
            </span>
            Research Agent · Grounded in 7 documents
          </p>
        </div>
        <Badge variant="brand"><Icon name="BrainCircuit" size={12} /> Multi-step Reasoning</Badge>
      </div>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto scrollbar-thin space-y-6 pb-4">
        <div className="max-w-3xl mx-auto w-full">
          {messages.map((m) => (
            <div key={m.id} className={`flex gap-3 mb-6 ${m.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
                m.role === 'user' ? 'bg-subtle' : 'gradient-brand'
              }`}>
                <Icon name={m.role === 'user' ? 'User' : 'Sparkles'} size={18} className={m.role === 'user' ? 'text-secondary' : 'text-white'} />
              </div>
              <div className={`max-w-[80%] ${m.role === 'user' ? 'items-end' : ''}`}>
                <div className={`rounded-2xl px-4 py-3 ${
                  m.role === 'user'
                    ? 'bg-brand-600 text-white'
                    : 'bg-surface border border-base text-primary shadow-card'
                }`}>
                  <div className="text-sm leading-relaxed whitespace-pre-wrap">{m.content}</div>
                </div>
                {m.citations && m.citations.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {m.citations.map((c, i) => (
                      <div key={i} className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-brand-50 dark:bg-brand-500/10 border border-brand-200 dark:border-brand-500/20 text-xs text-brand-700 dark:text-brand-300">
                        <Icon name="FileSearch" size={13} />
                        <span className="font-medium">{c.label}</span>
                        {c.page && <span className="text-tertiary">· p.{c.page}</span>}
                      </div>
                    ))}
                  </div>
                )}
                <p className="text-[11px] text-tertiary mt-1 px-1">{m.timestamp}</p>
              </div>
            </div>
          ))}

          {typing && (
            <div className="flex gap-3 mb-6">
              <div className="w-9 h-9 rounded-xl gradient-brand flex items-center justify-center shrink-0">
                <Icon name="Sparkles" size={18} className="text-white" />
              </div>
              <div className="rounded-2xl px-4 py-3 bg-surface border border-base shadow-card">
                <div className="flex items-center gap-1.5">
                  <span className="w-2 h-2 rounded-full bg-brand-400 animate-bounce" style={{ animationDelay: '0ms' }} />
                  <span className="w-2 h-2 rounded-full bg-brand-400 animate-bounce" style={{ animationDelay: '150ms' }} />
                  <span className="w-2 h-2 rounded-full bg-brand-400 animate-bounce" style={{ animationDelay: '300ms' }} />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Suggested prompts */}
      {messages.length <= 1 && !typing && (
        <div className="max-w-3xl mx-auto w-full mb-4">
          <p className="text-xs text-tertiary mb-2 px-1">Suggested prompts</p>
          <div className="flex flex-wrap gap-2">
            {SUGGESTED_PROMPTS.map((p) => (
              <button
                key={p}
                onClick={() => send(p)}
                className="px-3.5 py-2 rounded-xl border border-base bg-surface text-sm text-secondary hover:border-brand-300 hover:bg-brand-50 dark:hover:bg-brand-500/10 hover:text-brand-700 dark:hover:text-brand-300 transition-all"
              >
                {p}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Input */}
      <div className="max-w-3xl mx-auto w-full">
        <div className="relative flex items-end gap-2 bg-surface border border-base rounded-2xl shadow-card p-2 focus-within:border-brand-400 focus-within:ring-4 focus-within:ring-brand-500/10 transition-all">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            placeholder="Ask about financials, risks, comparisons…"
            className="flex-1 resize-none bg-transparent text-sm text-primary outline-none px-3 py-2 max-h-32 placeholder:text-tertiary scrollbar-thin"
          />
          <button
            onClick={() => send(input)}
            disabled={!input.trim()}
            className="w-10 h-10 rounded-xl gradient-brand text-white flex items-center justify-center shrink-0 disabled:opacity-40 hover:shadow-elevated transition-all"
          >
            <Icon name="Send" size={18} />
          </button>
        </div>
        <p className="text-[11px] text-tertiary text-center mt-2">
          FinSight AI grounds answers in your uploaded documents. Verify critical figures before investment decisions.
        </p>
      </div>
    </div>
  );
}
