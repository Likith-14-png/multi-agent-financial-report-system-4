import { useState } from 'react';
import { useApp } from '@/lib/AppContext';
import { Icon } from '@/components/Icon';

export function LoginPage() {
  const { login } = useApp();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [showPw, setShowPw] = useState(false);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email || !password) return;
    setLoading(true);
    setTimeout(() => login(email), 800);
  };

  return (
    <div className="min-h-screen flex bg-base">
      {/* Left brand panel */}
      <div className="hidden lg:flex lg:w-1/2 relative overflow-hidden gradient-brand">
        <div className="absolute inset-0 opacity-20" style={{
          backgroundImage: 'radial-gradient(circle at 20% 30%, white 0%, transparent 40%), radial-gradient(circle at 80% 70%, #06b6d4 0%, transparent 40%)'
        }} />
        <div className="relative z-10 flex flex-col justify-between p-12 text-white">
          <div className="flex items-center gap-3">
            <div className="w-11 h-11 rounded-xl bg-white/15 backdrop-blur flex items-center justify-center border border-white/20">
              <Icon name="BrainCircuit" size={26} className="text-white" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight">FinSight AI</h1>
              <p className="text-xs text-white/70">Multi-Agent Financial Research</p>
            </div>
          </div>

          <div className="max-w-md">
            <h2 className="text-4xl font-bold leading-tight tracking-tight">
              Analyze 10-K filings with a team of AI agents.
            </h2>
            <p className="text-white/80 mt-4 text-lg leading-relaxed">
              Six specialized agents parse, extract, benchmark, and report on financial documents — grounded in source citations, ready in minutes.
            </p>
            <div className="mt-8 space-y-3">
              {[
                { icon: 'FileText', text: 'Upload 10-K, 10-Q, and earnings reports' },
                { icon: 'ShieldAlert', text: 'Automatic red-flag and risk detection' },
                { icon: 'MessageSquare', text: 'Chat with your documents, cited answers' },
                { icon: 'FileCheck2', text: 'Generate investment-grade PDF reports' },
              ].map((f, i) => (
                <div key={i} className="flex items-center gap-3 animate-slide-up" style={{ animationDelay: `${i * 80}ms` }}>
                  <div className="w-8 h-8 rounded-lg bg-white/15 flex items-center justify-center shrink-0">
                    <Icon name={f.icon} size={16} className="text-white" />
                  </div>
                  <span className="text-white/90 text-sm">{f.text}</span>
                </div>
              ))}
            </div>
          </div>

          <p className="text-xs text-white/50">Infosys Springboard Virtual Internship · 2026</p>
        </div>
      </div>

      {/* Right login form */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="w-full max-w-sm animate-slide-up">
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="w-10 h-10 rounded-xl gradient-brand flex items-center justify-center">
              <Icon name="BrainCircuit" size={22} className="text-white" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-primary">FinSight AI</h1>
              <p className="text-xs text-secondary">Multi-Agent Financial Research</p>
            </div>
          </div>

          <h2 className="text-2xl font-bold text-primary tracking-tight">Sign in to your workspace</h2>
          <p className="text-sm text-secondary mt-1.5 mb-8">Enter your credentials to access the research platform.</p>

          <form onSubmit={submit} className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-primary mb-1.5">Email address</label>
              <div className="relative">
                <Icon name="User" size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-tertiary" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="analyst@finsight.ai"
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-base bg-surface text-primary text-sm outline-none transition-all focus:border-brand-400 focus:ring-4 focus:ring-brand-500/10"
                  required
                />
              </div>
            </div>

            <div>
              <div className="flex items-center justify-between mb-1.5">
                <label className="block text-sm font-medium text-primary">Password</label>
                <button type="button" className="text-xs text-brand-600 hover:text-brand-700 font-medium">Forgot?</button>
              </div>
              <div className="relative">
                <Icon name="ShieldCheck" size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-tertiary" />
                <input
                  type={showPw ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="w-full pl-10 pr-12 py-2.5 rounded-xl border border-base bg-surface text-primary text-sm outline-none transition-all focus:border-brand-400 focus:ring-4 focus:ring-brand-500/10"
                  required
                />
                <button type="button" onClick={() => setShowPw(!showPw)} className="absolute right-3 top-1/2 -translate-y-1/2 text-tertiary hover:text-secondary">
                  <Icon name="Eye" size={18} />
                </button>
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm text-secondary cursor-pointer select-none">
              <input type="checkbox" className="rounded border-base text-brand-500 focus:ring-brand-500/20" />
              Keep me signed in
            </label>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 rounded-xl gradient-brand text-white font-medium text-sm shadow-card hover:shadow-elevated transition-all flex items-center justify-center gap-2 disabled:opacity-70"
            >
              {loading ? (
                <>
                  <Icon name="Loader2" size={18} className="animate-spin" />
                  Signing in…
                </>
              ) : (
                <>
                  Sign in
                  <Icon name="ArrowUpRight" size={18} />
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <p className="text-xs text-secondary">
              Don't have an account?{' '}
              <button className="text-brand-600 hover:text-brand-700 font-medium">Request access</button>
            </p>
          </div>

          <div className="mt-8 pt-6 border-t border-base text-center">
            <p className="text-xs text-tertiary">Secured with enterprise-grade encryption · SOC 2 Type II</p>
          </div>
        </div>
      </div>
    </div>
  );
}
