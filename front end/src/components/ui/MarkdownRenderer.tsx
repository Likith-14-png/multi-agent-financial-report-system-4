import React from 'react';
import { ExternalLink } from 'lucide-react';
import { CitationSource } from '../../lib/types';

export interface MarkdownRendererProps {
  content: string;
  sources?: CitationSource[];
  onCitationClick?: (citation: CitationSource) => void;
  className?: string;
}

export function MarkdownRenderer({
  content,
  sources = [],
  onCitationClick,
  className = '',
}: MarkdownRendererProps) {
  if (!content) return null;

  // Helper to render inline formatting: bold, italic, code, citations
  const renderInline = (text: string): React.ReactNode[] => {
    // Split by citation patterns like [Source 1], [1], [Chunk chunk_id], [page 3]
    const citationRegex = /\[(?:Source\s*(\d+)|Citation\s*(\d+)|(\d+)|(?:Chunk\s*([\w-]+))|(?:Page\s*(\d+)))\]/gi;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    let match: RegExpExecArray | null;

    while ((match = citationRegex.exec(text)) !== null) {
      const matchIndex = match.index;
      if (matchIndex > lastIndex) {
        parts.push(...formatBasicText(text.slice(lastIndex, matchIndex)));
      }

      const rawCitation = match[0];
      const sourceNum = match[1] || match[2] || match[3];
      const chunkId = match[4];
      const pageNum = match[5];

      // Find matching source
      let matchedSource: CitationSource | undefined;
      if (sourceNum) {
        const idx = parseInt(sourceNum, 10) - 1;
        if (idx >= 0 && idx < sources.length) {
          matchedSource = sources[idx];
        }
      } else if (chunkId) {
        matchedSource = sources.find((s) => s.chunk_id === chunkId);
      } else if (pageNum) {
        matchedSource = sources.find((s) => String(s.page) === pageNum);
      }

      parts.push(
        <button
          key={`cite-${matchIndex}`}
          type="button"
          onClick={() => {
            if (matchedSource && onCitationClick) {
              onCitationClick(matchedSource);
            } else if (sources.length > 0 && onCitationClick) {
              onCitationClick(sources[0]);
            }
          }}
          className="inline-flex items-center gap-1 mx-1 px-1.5 py-0.5 rounded text-[11px] font-mono bg-cyan-950/80 text-cyan-300 border border-cyan-700/60 hover:bg-cyan-900 hover:border-cyan-500 transition-colors cursor-pointer align-baseline"
          title={matchedSource?.snippet || 'Inspect evidence citation'}
        >
          <span>{rawCitation}</span>
          <ExternalLink className="w-2.5 h-2.5 opacity-70" />
        </button>
      );

      lastIndex = citationRegex.lastIndex;
    }

    if (lastIndex < text.length) {
      parts.push(...formatBasicText(text.slice(lastIndex)));
    }

    return parts.length > 0 ? parts : [text];
  };

  const formatBasicText = (subtext: string): React.ReactNode[] => {
    // Process code `...`, bold **...**, italic *...*
    const tokens: React.ReactNode[] = [];
    const formattingRegex = /(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*)/g;
    let prev = 0;
    let match: RegExpExecArray | null;

    while ((match = formattingRegex.exec(subtext)) !== null) {
      if (match.index > prev) {
        tokens.push(subtext.slice(prev, match.index));
      }
      const token = match[0];
      if (token.startsWith('`') && token.endsWith('`')) {
        tokens.push(
          <code
            key={match.index}
            className="px-1.5 py-0.5 bg-slate-800 text-cyan-300 rounded text-xs font-mono border border-slate-700/50"
          >
            {token.slice(1, -1)}
          </code>
        );
      } else if (token.startsWith('**') && token.endsWith('**')) {
        tokens.push(
          <strong key={match.index} className="font-semibold text-slate-100">
            {token.slice(2, -2)}
          </strong>
        );
      } else if (token.startsWith('*') && token.endsWith('*')) {
        tokens.push(
          <em key={match.index} className="italic text-slate-300">
            {token.slice(1, -1)}
          </em>
        );
      }
      prev = formattingRegex.lastIndex;
    }

    if (prev < subtext.length) {
      tokens.push(subtext.slice(prev));
    }
    return tokens;
  };

  // Parse lines into blocks: headers, lists, tables, paragraphs
  const lines = content.split('\n');
  const blocks: React.ReactNode[] = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];
    const trimmed = line.trim();

    if (!trimmed) {
      i++;
      continue;
    }

    // Headers
    if (trimmed.startsWith('#### ')) {
      blocks.push(
        <h5 key={i} className="text-sm font-semibold text-slate-200 mt-4 mb-1">
          {renderInline(trimmed.slice(5))}
        </h5>
      );
      i++;
      continue;
    }
    if (trimmed.startsWith('### ')) {
      blocks.push(
        <h4 key={i} className="text-base font-semibold text-slate-100 mt-5 mb-2">
          {renderInline(trimmed.slice(4))}
        </h4>
      );
      i++;
      continue;
    }
    if (trimmed.startsWith('## ')) {
      blocks.push(
        <h3 key={i} className="text-lg font-bold text-slate-100 mt-6 mb-2 pb-1 border-b border-slate-800">
          {renderInline(trimmed.slice(3))}
        </h3>
      );
      i++;
      continue;
    }
    if (trimmed.startsWith('# ')) {
      blocks.push(
        <h2 key={i} className="text-xl font-extrabold text-white mt-6 mb-3 pb-1 border-b border-slate-800">
          {renderInline(trimmed.slice(2))}
        </h2>
      );
      i++;
      continue;
    }

    // Markdown Table Detection
    if (trimmed.startsWith('|') && trimmed.endsWith('|') && lines[i + 1]?.trim().startsWith('|')) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
        tableLines.push(lines[i].trim());
        i++;
      }

      const headers = tableLines[0]
        .split('|')
        .slice(1, -1)
        .map((h) => h.trim());
      const hasSeparator = tableLines.length > 1 && tableLines[1].includes('---');
      const rowLines = hasSeparator ? tableLines.slice(2) : tableLines.slice(1);

      blocks.push(
        <div key={`tbl-${i}`} className="my-4 overflow-x-auto rounded-xl border border-slate-800">
          <table className="w-full text-xs text-left border-collapse">
            <thead className="bg-slate-900/90 text-slate-300 font-semibold border-b border-slate-800">
              <tr>
                {headers.map((h, hIdx) => (
                  <th key={hIdx} className="py-2.5 px-3.5 font-medium border-r border-slate-800/60 last:border-r-0">
                    {renderInline(h)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60 bg-slate-950/40">
              {rowLines.map((r, rIdx) => {
                const cells = r
                  .split('|')
                  .slice(1, -1)
                  .map((c) => c.trim());
                return (
                  <tr key={rIdx} className="hover:bg-slate-900/40 transition-colors">
                    {cells.map((c, cIdx) => (
                      <td
                        key={cIdx}
                        className="py-2 px-3.5 text-slate-300 border-r border-slate-800/40 last:border-r-0 font-mono text-[11px]"
                      >
                        {renderInline(c)}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      );
      continue;
    }

    // Lists (bullets or numbers)
    if (/^(\*|-|\d+\.)\s+/.test(trimmed)) {
      const listItems: string[] = [];
      const isOrdered = /^\d+\./.test(trimmed);
      while (i < lines.length && /^(\*|-|\d+\.)\s+/.test(lines[i].trim())) {
        listItems.push(lines[i].trim().replace(/^(\*|-|\d+\.)\s+/, ''));
        i++;
      }

      if (isOrdered) {
        blocks.push(
          <ol key={`ol-${i}`} className="list-decimal list-inside my-3 space-y-1.5 text-sm text-slate-300 pl-1">
            {listItems.map((item, idx) => (
              <li key={idx} className="leading-relaxed">
                {renderInline(item)}
              </li>
            ))}
          </ol>
        );
      } else {
        blocks.push(
          <ul key={`ul-${i}`} className="list-disc list-inside my-3 space-y-1.5 text-sm text-slate-300 pl-1">
            {listItems.map((item, idx) => (
              <li key={idx} className="leading-relaxed">
                {renderInline(item)}
              </li>
            ))}
          </ul>
        );
      }
      continue;
    }

    // Blockquote
    if (trimmed.startsWith('> ')) {
      blocks.push(
        <blockquote
          key={i}
          className="my-3 pl-3.5 border-l-2 border-cyan-500/70 bg-cyan-950/20 py-1 text-sm text-slate-300 italic rounded-r-md"
        >
          {renderInline(trimmed.slice(2))}
        </blockquote>
      );
      i++;
      continue;
    }

    // Default Paragraph
    blocks.push(
      <p key={i} className="my-2.5 text-sm text-slate-300 leading-relaxed">
        {renderInline(trimmed)}
      </p>
    );
    i++;
  }

  return <div className={`space-y-1 ${className}`}>{blocks}</div>;
}
